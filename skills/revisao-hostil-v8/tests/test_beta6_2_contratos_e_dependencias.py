"""Suíte de testes unitários, de integração, negativos e adversariais — Revisão Hostil v8.0-beta.6.2.

Cobre integralmente os cinco achados da reauditoria externa:
- ACH-B6.1-001 (P1): bloqueio efetivo de dependências obrigatórias e separação execução vs diagnóstico;
- ACH-B6.1-002 (P2): validação estrita SemVer 2.0.0 via fullmatch() sem normalização silenciosa;
- ACH-B6.1-003 (P2): compatibilidade real de versões com packaging (SpecifierSet / Version);
- ACH-B6.1-004 (P2): fechamento dos 8 contratos JSON (additionalProperties: false);
- ACH-B6.1-005 (P2): rastreabilidade completa perfil -> motor -> dependência -> versão -> estado no manifesto.
"""

from __future__ import annotations

import importlib.metadata
from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts.common.dependencies import (
    ExecutionBlockedError,
    assert_engine_execution_allowed,
    execute_engine_with_profile,
    validate_single_dependency,
)
from scripts.common.profile_loader import (
    is_valid_semver,
    list_available_profiles,
    load_profile,
    validate_semver_strict,
)
from scripts.common.provenance import build_run_manifest, save_run_manifest, validate_run_manifest
from scripts.common.schema_validator import SchemaValidationError, SchemaValidator, validate_contract


def _write_profile(tmp_path: Path, name: str, data: dict[str, Any]) -> Path:
    p = tmp_path / f"{name}.yaml"
    p.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return p


def _base_profile(**overrides: Any) -> dict[str, Any]:
    prof: dict[str, Any] = {
        "profile_id": "perfil_teste_b62",
        "profile_version": "1.0.0",
        "profile_status": "active",
        "effective_date": "2026-11-23",
        "domain": {
            "name": "Engenharia de Teste",
            "parent": None,
            "epistemological_family": "exatas_engenharia",
        },
        "reasoning_modes": ["engineering", "quantitative"],
        "evidence_framework": "ENGENHARIA_EMPIRICA",
        "engines": {
            "required": ["motor_matematico", "motor_dimensional"],
            "optional": ["motor_estetico"],
        },
        "gates": ["G01", "G02"],
    }
    prof.update(overrides)
    return prof


def _make_resolver(mapping: dict[str, Any]):
    """Cria resolvedor determinístico de metadados para testes unitários/adversariais."""
    def _resolve(dist_name: str) -> str | None:
        if dist_name not in mapping:
            raise importlib.metadata.PackageNotFoundError(dist_name)
        val = mapping[dist_name]
        if isinstance(val, Exception):
            raise val
        return val
    return _resolve


# =============================================================================
# ETAPA 1 — ACH-B6.1-001 (P1): Bloqueio efetivo de dependências obrigatórias
# =============================================================================


def test_ach_b61_001_required_dep_installed_and_compatible_allows_execution(tmp_path: Path) -> None:
    """[Integração] Dependência obrigatória instalada e compatível -> execution_eligible=True e motor executa."""
    p = _write_profile(tmp_path, "ok", _base_profile())
    prof = load_profile(p, mode="execution")
    assert prof["_resolved"]["execution_eligible"] is True

    out = execute_engine_with_profile(
        prof,
        "motor_matematico",
        {"operation": "plug_in", "expression": "3*x", "substitutions": {"x": 4}, "reported_value": 12},
    )
    assert out["status"] == "OK"


def test_ach_b61_001_required_dep_missing_blocks_execution_and_no_engine_runs(tmp_path: Path) -> None:
    """[Negativo/Adversarial] Dependência obrigatória ausente bloqueia perfil e impede execução de qualquer motor."""
    p = _write_profile(tmp_path, "missing_req", _base_profile())
    resolver = _make_resolver({"scipy": "1.18.1", "sympy": "1.14.0", "Pillow": "12.3.0"})  # numpy ausente

    with pytest.raises(ExecutionBlockedError, match="numpy"):
        load_profile(p, mode="execution", metadata_resolver=resolver)

    # Modo diagnóstico inspeciona sem levantar exceção, mas NUNCA marca como execution_eligible=True
    diag = load_profile(p, mode="diagnostic", metadata_resolver=resolver)
    assert diag["_resolved"]["execution_eligible"] is False
    assert diag["_resolved"]["mode"] == "diagnostic"

    calls = 0

    def _spy_runner(payload: dict[str, Any]) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return {"status": "OK"}

    with pytest.raises(ExecutionBlockedError):
        execute_engine_with_profile(diag, "motor_matematico", {}, engine_runner=_spy_runner)
    with pytest.raises(ExecutionBlockedError):
        execute_engine_with_profile(diag, "motor_dimensional", {}, engine_runner=_spy_runner)
    assert calls == 0


def test_ach_b61_001_required_dep_incompatible_blocks_execution(tmp_path: Path) -> None:
    """[Negativo] Perfil ativo com dependência obrigatória incompatível é bloqueado."""
    p = _write_profile(tmp_path, "incompat_req", _base_profile())
    resolver = _make_resolver({"numpy": "1.26.4", "scipy": "1.18.1", "sympy": "1.14.0", "Pillow": "12.3.0"})

    with pytest.raises(ExecutionBlockedError, match="incompatible"):
        load_profile(p, mode="execution", metadata_resolver=resolver)

    diag = load_profile(p, mode="diagnostic", metadata_resolver=resolver)
    assert diag["_resolved"]["execution_eligible"] is False
    math_eng = next(e for e in diag["_resolved"]["engines_audit"] if e["engine_id"] == "motor_matematico")
    numpy_dep = next(d for d in math_eng["dependencies"] if d["distribution_name"] == "numpy")
    assert numpy_dep["status"] == "incompatible"
    assert numpy_dep["installed_version"] == "1.26.4"


def test_ach_b61_001_optional_dep_missing_tolerated_when_not_requested_and_blocked_when_requested(
    tmp_path: Path,
) -> None:
    """[Integração] Dependência opcional ausente é tolerada se motor não solicitado, e bloqueada se solicitado."""
    p = _write_profile(tmp_path, "opt_dep", _base_profile())
    # Pillow (exigido apenas por motor_estetico, que é opcional) está ausente
    resolver = _make_resolver({"numpy": "2.5.4", "scipy": "1.18.1", "sympy": "1.14.0"})

    # 1. Motor opcional NÃO solicitado -> perfil elegível para os motores obrigatórios
    prof = load_profile(p, mode="execution", metadata_resolver=resolver)
    assert prof["_resolved"]["execution_eligible"] is True
    assert any("Pillow" in w for w in prof["_resolved"]["optional_unmet_warnings"])

    # Mas tentar executar o motor opcional sem sua dependência continua bloqueado no portão pré-execução!
    calls = 0

    def _spy(payload: dict[str, Any]) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return {"status": "OK"}

    with pytest.raises(ExecutionBlockedError, match="Pillow"):
        execute_engine_with_profile(prof, "motor_estetico", {}, engine_runner=_spy)
    assert calls == 0

    # 2. Motor opcional explicitamente SOLICITADO -> bloqueia o próprio carregamento em modo execução
    with pytest.raises(ExecutionBlockedError, match="Pillow"):
        load_profile(
            p,
            mode="execution",
            requested_optional_engines=["motor_estetico"],
            metadata_resolver=resolver,
        )


def test_ach_b61_001_unknown_dep_never_treated_as_available_and_bypass_attempts_fail(tmp_path: Path) -> None:
    """[Adversarial] Dependência desconhecida vira 'unknown' e parâmetros de exceção não contornam dependências."""
    p = _write_profile(
        tmp_path,
        "unknown_dep",
        _base_profile(
            dependencies=[
                {"distribution_name": "numpy", "version_specifier": ">=2.0.0", "required": True}
            ]
        ),
    )
    # Metadados corrompidos (None) para numpy
    resolver = _make_resolver({"numpy": None, "scipy": "1.18.1", "sympy": "1.14.0", "Pillow": "12.3.0"})

    # Mesmo passando allow_non_active=True e require_implemented=False, NUNCA contorna dependência obrigatória!
    with pytest.raises(ExecutionBlockedError, match="unknown"):
        load_profile(
            p,
            mode="execution",
            allow_non_active=True,
            require_implemented=False,
            metadata_resolver=resolver,
        )

    diag = load_profile(p, mode="diagnostic", metadata_resolver=resolver)
    assert diag["_resolved"]["execution_eligible"] is False
    assert diag["_resolved"]["profile_dependencies_audit"][0]["status"] == "unknown"

    # Tentativa adversarial de executar sem passar por load_profile()
    with pytest.raises(ExecutionBlockedError):
        assert_engine_execution_allowed(_base_profile(), "motor_matematico")


# =============================================================================
# ETAPA 2 — ACH-B6.1-002 (P2): Validação estrita SemVer 2.0.0
# =============================================================================


@pytest.mark.parametrize(
    "valid_ver",
    [
        "1.0.0",
        "2.3.4",
        "0.0.0",
        "1.0.0-alpha",
        "1.0.0-alpha.1",
        "1.0.0-0",
        "1.0.0-0a",
        "1.0.0+build.5",
        "1.0.0-alpha+build.5",
        "1.0.0-alpha.1+exp.sha.5114f85",
    ],
)
def test_ach_b61_002_semver_valid_cases(valid_ver: str) -> None:
    """[Unitário] Todas as entradas SemVer 2.0.0 válidas são aceitas."""
    ok, reason = validate_semver_strict(valid_ver)
    assert ok is True
    assert is_valid_semver(valid_ver) is True
    assert "válido" in reason.lower()


@pytest.mark.parametrize(
    "invalid_ver",
    [
        "01.02.03",
        "1.0",
        "1.0.0.",
        "v1.0.0",
        "1.0.0\n",
        "1.0.0 ",
        " 1.0.0",
        "1.0.0-alpha..1",
        "1.0.0-01",
        "1.0.0+",
        "1.0.0-",
        "",
        None,
        100,
    ],
)
def test_ach_b61_002_semver_invalid_cases_rejected_without_normalization(invalid_ver: Any) -> None:
    """[Negativo/Adversarial] Entradas inválidas (incl. '\\n' final e espaços) são rejeitadas com motivo explícito."""
    ok, reason = validate_semver_strict(invalid_ver)
    assert ok is False
    assert is_valid_semver(invalid_ver) is False
    assert isinstance(reason, str) and len(reason) > 5
    # Também rejeitado diretamente pelo JSON Schema executável (inclusive '1.0.0\n')
    if isinstance(invalid_ver, str):
        with pytest.raises(SchemaValidationError):
            validate_contract(_base_profile(profile_version=invalid_ver), "schema_profile.json")


# =============================================================================
# ETAPA 3 — ACH-B6.1-003 (P2): Compatibilidade real de versões instaladas
# =============================================================================


def test_ach_b61_003_version_compatibility_matrix() -> None:
    """[Unitário] Valida versão exata, superior, inferior, intervalo, inválida, ausente, sem metadados e opcional."""
    # Versão mínima exata
    r_exact = validate_single_dependency("numpy>=2.0.0", required=True, metadata_resolver=_make_resolver({"numpy": "2.0.0"}))
    assert r_exact["status"] == "available"
    assert r_exact["installed_version"] == "2.0.0"

    # Versão superior
    r_high = validate_single_dependency("numpy>=2.0.0", required=True, metadata_resolver=_make_resolver({"numpy": "2.1.0"}))
    assert r_high["status"] == "available"

    # Versão inferior -> incompatible
    r_low = validate_single_dependency("numpy>=2.0.0", required=True, metadata_resolver=_make_resolver({"numpy": "1.26.4"}))
    assert r_low["status"] == "incompatible"
    assert r_low["installed_version"] == "1.26.4"

    # Intervalo de versões
    r_in = validate_single_dependency("numpy>=2.0.0,<3.0.0", required=True, metadata_resolver=_make_resolver({"numpy": "2.5.4"}))
    assert r_in["status"] == "available"
    r_out = validate_single_dependency("numpy>=2.0.0,<3.0.0", required=True, metadata_resolver=_make_resolver({"numpy": "3.0.0"}))
    assert r_out["status"] == "incompatible"

    # Versão instalada inválida (não PEP 440) -> unknown
    r_bad_ver = validate_single_dependency("numpy>=2.0.0", required=True, metadata_resolver=_make_resolver({"numpy": "versao_quebrada!!!"}))
    assert r_bad_ver["status"] == "unknown"

    # Restrição inválida -> unknown
    r_bad_spec = validate_single_dependency({"distribution_name": "numpy", "version_specifier": ">>2.0.0"}, required=True, metadata_resolver=_make_resolver({"numpy": "2.1.0"}))
    assert r_bad_spec["status"] == "unknown"

    # Pacote ausente -> missing
    r_miss = validate_single_dependency("pacote-inexistente>=1.0.0", required=True, metadata_resolver=_make_resolver({}))
    assert r_miss["status"] == "missing"

    # Distribuição instalada sem metadados utilizáveis -> unknown
    r_empty = validate_single_dependency("numpy>=2.0.0", required=True, metadata_resolver=_make_resolver({"numpy": ""}))
    assert r_empty["status"] == "unknown"

    # Distinção distribution_name vs import_name + dependência opcional
    r_pil = validate_single_dependency("pillow>=10.0.0", required=False, metadata_resolver=_make_resolver({"Pillow": "12.3.0"}))
    assert r_pil["distribution_name"] == "Pillow"
    assert r_pil["import_name"] == "PIL"
    assert r_pil["required"] is False
    assert r_pil["status"] == "available"


# =============================================================================
# ETAPA 4 — ACH-B6.1-004 (P2): Fechamento dos 8 contratos JSON
# =============================================================================


def test_ach_b61_004_all_eight_schemas_and_seven_profiles_valid_and_closed(tmp_path: Path) -> None:
    """[Integração/Negativo] Todos os 8 schemas fecham propriedades desconhecidas preservando os 7 perfis-piloto."""
    validator = SchemaValidator()
    expected_schemas = [
        "schema_achado.json",
        "schema_agente.json",
        "schema_evidencia.json",
        "schema_input.json",
        "schema_iteracao.json",
        "schema_motor.json",
        "schema_profile.json",
        "schema_relatorio_final.json",
    ]
    for sname in expected_schemas:
        schema = validator.get_schema(sname)
        assert schema.get("additionalProperties") is False, f"{sname} raiz deve ter additionalProperties=false"

    # Todos os 7 perfis-piloto continuam válidos sem alteração artificial
    pids = list_available_profiles()
    assert len(pids) == 7
    for pid in pids:
        prof = load_profile(pid, mode="execution")
        assert prof["_resolved"]["execution_eligible"] is True

    # Propriedade desconhecida na raiz do perfil
    bad_root = _base_profile(extra_campo_nao_autorizado=True)
    with pytest.raises(SchemaValidationError):
        validate_contract(bad_root, "schema_profile.json")

    # Propriedade desconhecida em objeto de motor (`engines`)
    bad_eng = _base_profile(engines={"required": ["motor_matematico"], "bypass_check": True})
    with pytest.raises(SchemaValidationError):
        validate_contract(bad_eng, "schema_profile.json")

    # Propriedade desconhecida em objeto de dependência (`dependencies[]`)
    bad_dep = _base_profile(
        dependencies=[{"distribution_name": "numpy", "required": True, "chave_invalida": 123}]
    )
    with pytest.raises(SchemaValidationError):
        validate_contract(bad_dep, "schema_profile.json")

    # Estrutura de domínio inválida / propriedade desconhecida em domain
    bad_dom = _base_profile(
        domain={"name": "Teste", "parent": None, "epistemological_family": "exatas_engenharia", "extra": "x"}
    )
    with pytest.raises(SchemaValidationError):
        validate_contract(bad_dom, "schema_profile.json")

    # Tipo incorreto, enum inválido e data impossível
    with pytest.raises(SchemaValidationError):
        validate_contract(_base_profile(gates="G01"), "schema_profile.json")
    with pytest.raises(SchemaValidationError):
        validate_contract(_base_profile(profile_status="production"), "schema_profile.json")
    p_bad_date = _write_profile(tmp_path, "bad_date", _base_profile(effective_date="2026-02-30"))
    with pytest.raises(ValueError, match="effective_date"):
        load_profile(p_bad_date, mode="execution")

    # Campos opcionais ausentes vs preenchidos corretamente
    minimal = {
        "profile_id": "perfil_minimo",
        "profile_version": "1.0.0",
        "profile_status": "active",
        "effective_date": "2026-11-23",
        "domain": {"name": "Minimo", "epistemological_family": "exatas_engenharia"},
        "reasoning_modes": ["engineering"],
        "engines": {"required": ["motor_dimensional"]},
        "gates": ["G01"],
    }
    validate_contract(minimal, "schema_profile.json")

    full_opt = _base_profile(
        dependencies=[{"distribution_name": "numpy", "import_name": "numpy", "version_specifier": ">=2.0.0", "required": True}],
        normative_sources=[{"id": "ISO-IEC-17025", "jurisdiction": "INTERNATIONAL", "official_source_required": True, "verification_date_required": True}],
        vocabulary={"canonical_file": "vocabularies/engenharia_geral.yaml"},
        checklists=["checklists/engenharia_geral.yaml"],
        domain_rules=[{"category": "T", "portao": "G01", "pattern": "x", "prompt": "p"}],
    )
    validate_contract(full_opt, "schema_profile.json")

    # Propriedade desconhecida rejeitada em schema_motor.json (mantendo metricas/resultados extensíveis)
    with pytest.raises(SchemaValidationError):
        validate_contract(
            {
                "schema_version": "1.0.0",
                "motor_id": "motor_dimensional",
                "motor_version": "0.1.0",
                "deterministico": True,
                "status": "OK",
                "timestamp": "2026-11-23T00:00:00Z",
                "resultados": {"custom_key": 1},
                "metricas": {"custom_metric": 2},
                "achados": [],
                "limitacoes": [],
                "campo_ilegal": "nao_permitido",
            },
            "schema_motor.json",
        )


# =============================================================================
# ETAPA 5 — ACH-B6.1-005 (P2): Rastreabilidade completa no run_manifest.json
# =============================================================================


def test_ach_b61_005_manifest_full_profile_engine_dependency_provenance(tmp_path: Path) -> None:
    """[Integração/Contrato] run_manifest.json registra perfil -> motor -> dependência -> versão -> estado."""
    profile_records = []
    profile_versions = {}
    for pid in list_available_profiles():
        prof = load_profile(pid, mode="execution")
        profile_versions[pid] = prof["profile_version"]
        profile_records.append(prof["_resolved"]["manifest_profile_record"])

    manifest = build_run_manifest(
        "TEST-B6.2-MANIFEST",
        [Path(__file__)],
        skill_version="8.0.0-beta.6.2",
        profile_versions=profile_versions,
        profile_audit_records=profile_records,
        authorized_exceptions=[],
        report_references={"pytest_verbose": "relatorios_execucao/pytest_verbose.txt"},
    )

    assert manifest["manifest_generator_version"] == "8.0.0-beta.6.2"
    assert manifest["schema_validator_version"] is not None
    assert manifest["test_tools"]["pytest"] is not None
    assert manifest["test_tools"]["packaging"] is not None
    assert manifest["global_eligibility"]["evaluated_profiles"] == 7
    assert manifest["global_eligibility"]["all_profiles_eligible"] is True
    assert manifest["integrity"]["hash_algorithm"] == "SHA-256"

    # Confere associação completa perfil -> motor -> dependência -> versão -> estado
    eng_prof = next(p for p in manifest["profiles"] if p["profile_id"] == "engenharia_geral")
    assert eng_prof["execution_eligible"] is True
    assert eng_prof["schema_validation"]["valid"] is True
    assert eng_prof["semver_validation"]["valid"] is True
    math_eng = next(e for e in eng_prof["engines"] if e["engine_id"] == "motor_matematico")
    assert math_eng["requested"] is True
    numpy_dep = next(d for d in math_eng["dependencies"] if d["distribution_name"] == "numpy")
    assert numpy_dep["status"] == "available"
    assert numpy_dep["version_specifier"] == ">=2.0.0"
    assert numpy_dep["installed_version"] is not None
    assert numpy_dep["validation_timestamp"] is not None

    # Motor sem dependências externas deve aparecer explicitamente como not_applicable
    dim_eng = next(e for e in eng_prof["engines"] if e["engine_id"] == "motor_dimensional")
    assert dim_eng["dependencies"][0]["status"] == "not_applicable"

    out_path = save_run_manifest(manifest, tmp_path / "run_manifest.json")
    assert out_path.exists()

    # Falha explícita se o contrato do manifesto for violado
    broken = dict(manifest)
    broken.pop("global_eligibility")
    with pytest.raises(ValueError, match="global_eligibility"):
        validate_run_manifest(broken)
