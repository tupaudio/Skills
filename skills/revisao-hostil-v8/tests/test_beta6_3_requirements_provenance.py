"""Suíte de testes unitários, integração, negativos e adversariais — Revisão Hostil v8.0-beta.6.3.

Domínios cobertos:
- ACH-B6.2-002: parser fail-closed de requirements.txt, consolidação/conflitos, marcadores e prova de bloqueio;
- ACH-B6.2-001: fonte única de verdade (run_id), captura ambiental, consistência de artefatos e SHA-256;
- Regressão integrada dos achados ACH-B6.1-001 a ACH-B6.1-005.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.metadata
from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts.common.dependencies import (
    ExecutionBlockedError,
    RequirementsConflictError,
    RequirementsParseError,
    execute_engine_with_profile,
    parse_requirements_file,
    validate_single_dependency,
)
from scripts.common.profile_loader import load_profile
from scripts.common.provenance import (
    ConsistencyValidationError,
    build_artifact_record,
    build_run_manifest,
    capture_runtime_environment,
    generate_run_id,
    validate_run_consistency,
)


def _make_resolver(mapping: dict[str, Any]):
    def _resolve(dist_name: str) -> str | None:
        if dist_name not in mapping:
            raise importlib.metadata.PackageNotFoundError(dist_name)
        val = mapping[dist_name]
        if isinstance(val, Exception):
            raise val
        return val
    return _resolve


def _write_profile(tmp_path: Path, name: str, required_engines: list[str], optional_engines: list[str] | None = None) -> Path:
    data = {
        "profile_id": f"perfil_{name}",
        "profile_version": "1.0.0",
        "profile_status": "active",
        "effective_date": "2026-11-23",
        "domain": {
            "name": "Engenharia Teste 6.3",
            "parent": None,
            "epistemological_family": "exatas_engenharia",
        },
        "reasoning_modes": ["engineering"],
        "evidence_framework": "ENGENHARIA_EMPIRICA",
        "engines": {
            "required": required_engines,
            "optional": optional_engines or [],
        },
        "gates": ["G01"],
    }
    p = tmp_path / f"{name}.yaml"
    p.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return p


# =============================================================================
# DOMÍNIO 1 — PARSER FAIL-CLOSED DE REQUIREMENTS.TXT (ACH-B6.2-002)
# =============================================================================


def test_b63_requirements_missing_file_raises(tmp_path: Path) -> None:
    """[Negativo] Arquivo requirements.txt inexistente levanta RequirementsParseError (nunca retorna {})."""
    missing = tmp_path / "nao_existe.txt"
    with pytest.raises(RequirementsParseError) as exc_info:
        parse_requirements_file(missing)
    assert exc_info.value.line_number == 0
    assert "não encontrado" in exc_info.value.reason.lower()


def test_b63_requirements_empty_and_comments_only(tmp_path: Path) -> None:
    """[Unitário] Arquivo vazio ou contendo apenas comentários é válido e retorna dicionário vazio."""
    f_empty = tmp_path / "empty.txt"
    f_empty.write_text("", encoding="utf-8")
    assert parse_requirements_file(f_empty) == {}

    f_comments = tmp_path / "comments.txt"
    f_comments.write_text("# Apenas comentários\n   # Outro comentário\n\n", encoding="utf-8")
    assert parse_requirements_file(f_comments) == {}


@pytest.mark.parametrize(
    "bad_line",
    [
        "numpy>>>=2.0.0",
        "!!!pacote_invalido!!!>=1.0",
        "numpy==[invalido",
        "==1.0.0",
    ],
)
def test_b63_requirements_malformed_line_raises_with_location(tmp_path: Path, bad_line: str) -> None:
    """[Negativo] Linha malformada, nome inválido ou restrição inválida falha com arquivo, linha e motivo."""
    req = tmp_path / "bad.txt"
    req.write_text(f"numpy>=2.0.0\n{bad_line}\nscipy>=1.14.0\n", encoding="utf-8")
    with pytest.raises(RequirementsParseError) as exc_info:
        parse_requirements_file(req)
    assert exc_info.value.line_number == 2
    assert bad_line in exc_info.value.line_content
    assert str(req) in exc_info.value.path


def test_b63_requirements_invalid_encoding_and_read_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """[Negativo] Codificação UTF-8 inválida e falha de leitura (OSError) falham explicitamente."""
    bad_enc = tmp_path / "bad_utf8.txt"
    bad_enc.write_bytes(b"\xff\xfe\xfdnumpy>=2.0.0")
    with pytest.raises(RequirementsParseError, match="UTF-8"):
        parse_requirements_file(bad_enc)

    unreadable = tmp_path / "unreadable.txt"
    unreadable.write_text("numpy>=2.0.0\n", encoding="utf-8")
    orig_read_bytes = Path.read_bytes

    def _boom(self: Path) -> bytes:
        if self == unreadable:
            raise OSError("Permissão negada simulada")
        return orig_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", _boom)
    with pytest.raises(RequirementsParseError, match="Falha de leitura"):
        parse_requirements_file(unreadable)


def test_b63_requirements_duplicate_compatible_and_conflicting_constraints(tmp_path: Path) -> None:
    """[Unitário/Adversarial] Duplicatas compatíveis consolidam; conflitantes levantam RequirementsConflictError."""
    compat = tmp_path / "compat.txt"
    compat.write_text("numpy>=2.0.0\nnumpy<3.0.0\n", encoding="utf-8")
    parsed = parse_requirements_file(compat)
    assert "numpy" in parsed
    assert parsed["numpy"]["has_version_specifier"] is True
    assert len(parsed["numpy"]["sources"]) == 2
    assert parsed["numpy"]["specifier_set"].contains("2.5.0")
    assert not parsed["numpy"]["specifier_set"].contains("3.0.0")

    conflict = tmp_path / "conflict.txt"
    conflict.write_text("numpy>=3.0.0\nnumpy<2.0.0\n", encoding="utf-8")
    with pytest.raises(RequirementsConflictError, match="conflit"):
        parse_requirements_file(conflict)

    conflict_exact = tmp_path / "conflict_exact.txt"
    conflict_exact.write_text("numpy==2.0.0\nnumpy==2.1.0\n", encoding="utf-8")
    with pytest.raises(RequirementsConflictError):
        parse_requirements_file(conflict_exact)

    conflict_bound = tmp_path / "conflict_bound.txt"
    conflict_bound.write_text("numpy>2.0.0\nnumpy<=2.0.0\n", encoding="utf-8")
    with pytest.raises(RequirementsConflictError):
        parse_requirements_file(conflict_bound)

    conflict_excl = tmp_path / "conflict_excl.txt"
    conflict_excl.write_text("numpy>=2.0.0\nnumpy<=2.0.0\nnumpy!=2.0.0\n", encoding="utf-8")
    with pytest.raises(RequirementsConflictError):
        parse_requirements_file(conflict_excl)

    # Conflito inline em validate_single_dependency -> unknown (nunca available)
    r_conf = validate_single_dependency(
        "numpy>=3.0.0,<2.0.0",
        required=True,
        requirements_map={},
        metadata_resolver=_make_resolver({"numpy": "2.5.5"}),
    )
    assert r_conf["status"] == "unknown"


def test_b63_requirements_unconstrained_markers_and_dist_vs_import(tmp_path: Path) -> None:
    """[Unitário] Distingue dependência sem restrição (-> unknown), marcadores de ambiente e dist vs import."""
    req = tmp_path / "mixed.txt"
    req.write_text(
        "numpy\n"
        "Pillow>=10.0.0\n"
        "PyYAML>=6.0.0\n"
        'pacote-darwin>=1.0.0; sys_platform == "os_inexistente_xyz"\n',
        encoding="utf-8",
    )
    req_map = parse_requirements_file(req)
    resolver = _make_resolver({"numpy": "2.5.5", "Pillow": "13.0.0", "PyYAML": "6.0.4"})

    # Sem restrição explícita -> NUNCA available; deve ser unknown (fail-closed)
    r_unconstrained = validate_single_dependency("numpy", required=True, requirements_map=req_map, metadata_resolver=resolver)
    assert r_unconstrained["status"] == "unknown"
    assert r_unconstrained["has_version_specifier"] is False
    assert r_unconstrained["installed_version"] == "2.5.5"

    # Pillow vs PIL e PyYAML vs yaml
    r_pil = validate_single_dependency("pillow", required=True, requirements_map=req_map, metadata_resolver=resolver)
    assert r_pil["status"] == "available"
    assert r_pil["distribution_name"] == "Pillow"
    assert r_pil["import_name"] == "PIL"

    r_yaml = validate_single_dependency("pyyaml", required=True, requirements_map=req_map, metadata_resolver=resolver)
    assert r_yaml["status"] == "available"
    assert r_yaml["distribution_name"] == "PyYAML"
    assert r_yaml["import_name"] == "yaml"

    # Marcador de ambiente inativo -> not_applicable
    r_marker = validate_single_dependency("pacote-darwin", required=True, requirements_map=req_map, metadata_resolver=resolver)
    assert r_marker["status"] == "not_applicable"


# =============================================================================
# DOMÍNIO 2 — PROVA REAL DE BLOQUEIO COM SPY (Seção 3.6)
# =============================================================================


@pytest.mark.parametrize(
    "scenario",
    [
        "missing_requirements_file",
        "malformed_requirements_line",
        "conflicting_constraints",
        "unconstrained_dependency",
        "incompatible_version",
        "missing_required_package",
    ],
)
def test_b63_blocking_proof_zero_engines_executed_on_any_critical_failure(
    tmp_path: Path, scenario: str
) -> None:
    """[Integração/Adversarial] Comprova ExecutionBlockedError e 0 motores executados via spy."""
    prof_path = _write_profile(tmp_path, f"blk_{scenario}", required_engines=["motor_matematico"])
    req_path = tmp_path / "req.txt"
    resolver = _make_resolver({"numpy": "2.5.5", "scipy": "1.18.1", "sympy": "1.14.0"})

    if scenario == "missing_requirements_file":
        req_path = tmp_path / "inexistente.txt"
    elif scenario == "malformed_requirements_line":
        req_path.write_text("numpy>>>=2.0\nscipy>=1.14.0\nsympy>=1.13.0\n", encoding="utf-8")
    elif scenario == "conflicting_constraints":
        req_path.write_text("numpy>=3.0.0\nnumpy<2.0.0\nscipy>=1.14.0\nsympy>=1.13.0\n", encoding="utf-8")
    elif scenario == "unconstrained_dependency":
        req_path.write_text("numpy\nscipy>=1.14.0\nsympy>=1.13.0\n", encoding="utf-8")
    elif scenario == "incompatible_version":
        req_path.write_text("numpy>=2.0.0\nscipy>=1.14.0\nsympy>=1.13.0\n", encoding="utf-8")
        resolver = _make_resolver({"numpy": "1.26.4", "scipy": "1.18.1", "sympy": "1.14.0"})
    elif scenario == "missing_required_package":
        req_path.write_text("numpy>=2.0.0\nscipy>=1.14.0\nsympy>=1.13.0\n", encoding="utf-8")
        resolver = _make_resolver({"scipy": "1.18.1", "sympy": "1.14.0"})

    # 1. Modo execution bloqueia mesmo tentando contornar com allow_non_active=True
    with pytest.raises(ExecutionBlockedError):
        load_profile(
            prof_path,
            mode="execution",
            allow_non_active=True,
            require_implemented=False,
            requirements_path=req_path,
            metadata_resolver=resolver,
        )

    # 2. Modo diagnostic registra justificativa, mantém execution_eligible=False e 0 motores executam
    diag = load_profile(
        prof_path,
        mode="diagnostic",
        requirements_path=req_path,
        metadata_resolver=resolver,
    )
    assert diag["_resolved"]["execution_eligible"] is False
    assert len(diag["_resolved"]["blocking_reasons"]) >= 1

    calls = 0

    def _spy(payload: dict[str, Any]) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return {"status": "OK"}

    with pytest.raises(ExecutionBlockedError):
        execute_engine_with_profile(diag, "motor_matematico", {}, engine_runner=_spy)
    assert calls == 0


# =============================================================================
# DOMÍNIO 3 — PROVENIÊNCIA ÚNICA E VALIDAÇÃO DE CONSISTÊNCIA (ACH-B6.2-001)
# =============================================================================


def _build_consistent_fixture(tmp_path: Path) -> tuple[dict[str, Any], Path, str]:
    """Cria um conjunto mínimo de artefatos, manifesto e SHA256SUMS 100% consistentes."""
    run_id = generate_run_id("TEST63")
    env = capture_runtime_environment(tmp_path)
    rep_dir = tmp_path / "relatorios_execucao"
    rep_dir.mkdir(parents=True, exist_ok=True)

    (rep_dir / "pytest_verbose.txt").write_text(f"# run_id={run_id}\n93 passed in 1.25s\n", encoding="utf-8")
    (rep_dir / "coverage_report.txt").write_text(f"# run_id={run_id}\nTOTAL 100 10 90%\n", encoding="utf-8")
    (rep_dir / "smoke_tests.txt").write_text(f"# run_id={run_id}\n[CLI OK]\n", encoding="utf-8")

    report_text = (
        f"# Homologacao\n"
        f"RUN_ID={run_id}\n"
        f"Python: `{env['python_version']}`\n"
        f"Build: `{env['os_build']}`\n"
        f"Aprovados: `93 passed`\n"
        f"Warnings: `0`\n"
    )
    homolog = rep_dir / "homologacao_v8.0-beta.6.3.md"
    homolog.write_text(report_text, encoding="utf-8")

    artifacts = [
        build_artifact_record(rep_dir / "pytest_verbose.txt", tmp_path, run_id=run_id, artifact_type="pytest_log"),
        build_artifact_record(rep_dir / "coverage_report.txt", tmp_path, run_id=run_id, artifact_type="coverage_report"),
        build_artifact_record(rep_dir / "smoke_tests.txt", tmp_path, run_id=run_id, artifact_type="smoke_tests"),
        build_artifact_record(homolog, tmp_path, run_id=run_id, artifact_type="homologation_report"),
    ]

    test_results = {
        "run_id": run_id,
        "pytest_version": env["test_tools"].get("pytest"),
        "python_version": env["python_version"],
        "os_name": env["os_name"],
        "os_build": env["os_build"],
        "collected": 93,
        "passed": 93,
        "failed": 0,
        "skipped": 0,
        "collection_errors": 0,
        "warnings": 0,
        "duration_seconds": 1.25,
        "exit_code": 0,
    }
    manifest = build_run_manifest(
        run_id,
        [rep_dir / "pytest_verbose.txt", homolog],
        skill_version="8.0.0-beta.6.3",
        runtime_environment=env,
        durations={"test_suite_seconds": 1.25, "total_seconds": 2.10},
        test_results=test_results,
        artifacts=artifacts,
        exit_code=0,
        overall_result="PASSED",
        repo_root=tmp_path,
    )
    manifest["audited_code_commit"] = "abc1234"
    manifest["git_commit"] = "abc1234"

    sha_file = tmp_path / "SHA256SUMS"
    lines = []
    for art in artifacts:
        p = tmp_path / art["relative_path"]
        lines.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {art['relative_path']}")
    sha_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return manifest, sha_file, report_text


def test_b63_consistency_happy_path_passes(tmp_path: Path) -> None:
    """[Integração] Conjunto consistente com mesmo run_id e hashes reais passa em validate_run_consistency()."""
    manifest, sha_file, report_text = _build_consistent_fixture(tmp_path)
    res = validate_run_consistency(
        manifest,
        root_dir=tmp_path,
        sha256sums_path=sha_file,
        expected_commit="abc1234",
        report_text=report_text,
        required_artifact_names=(
            "pytest_verbose.txt",
            "coverage_report.txt",
            "smoke_tests.txt",
            "homologacao_v8.0-beta.6.3.md",
        ),
    )
    assert res["valid"] is True
    assert res["sha256_verified"] == 4
    assert res["sha256_failed"] == 0


@pytest.mark.parametrize(
    "tamper_case",
    [
        "run_id_artifact_mismatch",
        "run_id_pytest_mismatch",
        "python_version_mismatch",
        "os_name_mismatch",
        "os_build_mismatch",
        "test_count_report_mismatch",
        "warnings_report_mismatch",
        "duration_drift",
        "total_duration_less_than_suite",
        "exit_code_vs_passed_mismatch",
        "missing_required_artifact",
        "wrong_artifact_hash",
        "file_modified_after_generation",
        "commit_mismatch",
        "incomplete_manifest",
        "sha256sums_self_inclusion",
    ],
)
def test_b63_consistency_detects_all_divergences(tmp_path: Path, tamper_case: str) -> None:
    """[Negativo/Adversarial] Todas as 16 formas de divergência entre artefatos, ambiente e hashes falham."""
    manifest, sha_file, report_text = _build_consistent_fixture(tmp_path)
    m = copy.deepcopy(manifest)
    rep_txt = report_text
    exp_commit = "abc1234"
    req_names = (
        "pytest_verbose.txt",
        "coverage_report.txt",
        "smoke_tests.txt",
        "homologacao_v8.0-beta.6.3.md",
    )

    if tamper_case == "run_id_artifact_mismatch":
        m["artifacts"][0]["run_id"] = "OUTRA-EXECUCAO-999"
    elif tamper_case == "run_id_pytest_mismatch":
        m["test_results"]["run_id"] = "OUTRA-EXECUCAO-999"
    elif tamper_case == "python_version_mismatch":
        m["test_results"]["python_version"] = "3.11.0"
    elif tamper_case == "os_name_mismatch":
        m["test_results"]["os_name"] = "Windows" if m["test_results"]["os_name"] == "Linux" else "Linux"
    elif tamper_case == "os_build_mismatch":
        m["test_results"]["os_build"] = "10.0.19045"
    elif tamper_case == "test_count_report_mismatch":
        rep_txt = rep_txt.replace("93 passed", "99 passed")
    elif tamper_case == "warnings_report_mismatch":
        rep_txt = rep_txt.replace("Warnings: `0`", "Warnings: `3`")
    elif tamper_case == "duration_drift":
        m["durations"]["test_suite_seconds"] = 9.99
    elif tamper_case == "total_duration_less_than_suite":
        m["durations"]["total_seconds"] = 0.50
    elif tamper_case == "exit_code_vs_passed_mismatch":
        m["test_results"]["exit_code"] = 1
    elif tamper_case == "missing_required_artifact":
        m["artifacts"] = [a for a in m["artifacts"] if a["name"] != "smoke_tests.txt"]
    elif tamper_case == "wrong_artifact_hash":
        m["artifacts"][0]["sha256"] = "0" * 64
    elif tamper_case == "file_modified_after_generation":
        (tmp_path / "relatorios_execucao" / "pytest_verbose.txt").write_text("ADULTERADO\n", encoding="utf-8")
    elif tamper_case == "commit_mismatch":
        exp_commit = "deadbeef"
    elif tamper_case == "incomplete_manifest":
        m.pop("artifacts")
    elif tamper_case == "sha256sums_self_inclusion":
        sha_file.write_text(sha_file.read_text(encoding="utf-8") + ("a" * 64) + "  SHA256SUMS\n", encoding="utf-8")

    with pytest.raises(ConsistencyValidationError):
        validate_run_consistency(
            m,
            root_dir=tmp_path,
            sha256sums_path=sha_file,
            expected_commit=exp_commit,
            report_text=rep_txt,
            required_artifact_names=req_names,
        )


# =============================================================================
# DOMÍNIO 4 — ACH-B6.3-001 (run_id NO CONTEÚDO) E ACH-B6.3-002 (COMPLETUDE SHA256SUMS)
# =============================================================================


@pytest.mark.parametrize(
    "content_tamper",
    [
        "pytest_log_missing_run_id_even_with_updated_hash",
        "coverage_report_missing_run_id_even_with_updated_hash",
        "pytest_log_foreign_run_id_even_with_updated_hash",
        "coverage_report_foreign_run_id_even_with_updated_hash",
    ],
)
def test_ach_b63_001_artifact_content_must_contain_matching_run_id(tmp_path: Path, content_tamper: str) -> None:
    """[Adversarial] Substituir pytest_verbose.txt ou coverage_report.txt por outra execução falha mesmo atualizando hashes."""
    manifest, sha_file, report_text = _build_consistent_fixture(tmp_path)
    m = copy.deepcopy(manifest)

    if content_tamper == "pytest_log_missing_run_id_even_with_updated_hash":
        target_name = "pytest_verbose.txt"
        new_body = "93 passed in 1.25s (sem cabecalho run_id)\n"
    elif content_tamper == "coverage_report_missing_run_id_even_with_updated_hash":
        target_name = "coverage_report.txt"
        new_body = "TOTAL 100 10 90%\n"
    elif content_tamper == "pytest_log_foreign_run_id_even_with_updated_hash":
        target_name = "pytest_verbose.txt"
        new_body = "# run_id=OUTRA-EXECUCAO-9999\n93 passed in 1.25s\n"
    else:
        target_name = "coverage_report.txt"
        new_body = "# run_id=OUTRA-EXECUCAO-9999\nTOTAL 100 10 90%\n"

    target_path = tmp_path / "relatorios_execucao" / target_name
    target_path.write_text(new_body, encoding="utf-8")
    new_hash = hashlib.sha256(target_path.read_bytes()).hexdigest()
    new_size = target_path.stat().st_size

    # Atualiza hash no manifesto e no SHA256SUMS simulando ataque de substituição
    for art in m["artifacts"]:
        if art["name"] == target_name:
            art["sha256"] = new_hash
            art["bytes"] = new_size
    sha_lines = []
    for art in m["artifacts"]:
        p = tmp_path / art["relative_path"]
        sha_lines.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {art['relative_path']}")
    sha_file.write_text("\n".join(sha_lines) + "\n", encoding="utf-8")

    with pytest.raises(ConsistencyValidationError, match="run_id"):
        validate_run_consistency(
            m,
            root_dir=tmp_path,
            sha256sums_path=sha_file,
            expected_commit="abc1234",
            report_text=report_text,
        )


@pytest.mark.parametrize(
    "sha_tamper",
    [
        "omitted_file",
        "duplicate_entry",
        "unexpected_extra_file",
        "malformed_hash",
        "malformed_line_no_separator",
        "invalid_traversal_path",
    ],
)
def test_ach_b63_002_sha256sums_completeness_and_strict_parsing(tmp_path: Path, sha_tamper: str) -> None:
    """[Negativo/Adversarial] SHA256SUMS rejeita omissão, duplicata, arquivo extra, hash malformado e caminho inválido."""
    manifest, sha_file, report_text = _build_consistent_fixture(tmp_path)
    lines = sha_file.read_text(encoding="utf-8").splitlines()

    if sha_tamper == "omitted_file":
        sha_file.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    elif sha_tamper == "duplicate_entry":
        sha_file.write_text("\n".join(lines + [lines[0]]) + "\n", encoding="utf-8")
    elif sha_tamper == "unexpected_extra_file":
        extra = tmp_path / "extra_nao_inventariado.txt"
        extra.write_text("intruso\n", encoding="utf-8")
        eh = hashlib.sha256(extra.read_bytes()).hexdigest()
        sha_file.write_text("\n".join(lines + [f"{eh}  extra_nao_inventariado.txt"]) + "\n", encoding="utf-8")
    elif sha_tamper == "malformed_hash":
        sha_file.write_text("\n".join(["ZZZZ_HASH_INVALIDO  relatorios_execucao/pytest_verbose.txt"] + lines[1:]) + "\n", encoding="utf-8")
    elif sha_tamper == "malformed_line_no_separator":
        sha_file.write_text("\n".join(lines + ["linha_sem_separador_duplo"]) + "\n", encoding="utf-8")
    elif sha_tamper == "invalid_traversal_path":
        sha_file.write_text("\n".join(lines + [("a" * 64) + "  ../escape.txt"]) + "\n", encoding="utf-8")

    with pytest.raises(ConsistencyValidationError):
        validate_run_consistency(
            manifest,
            root_dir=tmp_path,
            sha256sums_path=sha_file,
            expected_commit="abc1234",
            report_text=report_text,
        )


def test_b64_parser_compatible_release_wildcard_and_arbitrary_equality(tmp_path: Path) -> None:
    """[Unitário] Cobre ~= (conflitante e compatível), === e curingas ==2.* no parser de requisitos."""
    # ~=2.1.0 equivale a >=2.1.0, <2.2.0 -> conflita com >=2.2.0
    c_tilde = tmp_path / "tilde_conflict.txt"
    c_tilde.write_text("numpy~=2.1.0\nnumpy>=2.2.0\n", encoding="utf-8")
    with pytest.raises(RequirementsConflictError):
        parse_requirements_file(c_tilde)

    # ~=2.1.0 compatível com 2.1.5 e incompatível com 2.2.0
    ok_tilde = tmp_path / "tilde_ok.txt"
    ok_tilde.write_text("numpy~=2.1.0\nscipy==1.*\nsympy===1.14.0\n", encoding="utf-8")
    req_map = parse_requirements_file(ok_tilde)
    assert validate_single_dependency("numpy", requirements_map=req_map, metadata_resolver=_make_resolver({"numpy": "2.1.5"}))["status"] == "available"
    assert validate_single_dependency("numpy", requirements_map=req_map, metadata_resolver=_make_resolver({"numpy": "2.2.0"}))["status"] == "incompatible"
    assert validate_single_dependency("scipy", requirements_map=req_map, metadata_resolver=_make_resolver({"scipy": "1.18.1"}))["status"] == "available"
    assert validate_single_dependency("sympy", requirements_map=req_map, metadata_resolver=_make_resolver({"sympy": "1.14.0"}))["status"] == "available"
    assert validate_single_dependency("sympy", requirements_map=req_map, metadata_resolver=_make_resolver({"sympy": "1.13.0"}))["status"] == "incompatible"
