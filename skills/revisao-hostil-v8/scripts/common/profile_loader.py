"""Carregador e validador formal de perfis YAML multidisciplinares (Revisão Hostil v8.0-beta.6.2).

Correções incorporadas:
- ACH-B6-005 / ACH-B6.1-004: validação obrigatória contra JSON Schema executável fechado
  (`references/schemas/schema_profile.json`) e validação real de calendário para `effective_date`;
- ACH-B6-006 / ACH-B6.1-002: validação estrita conforme especificação SemVer 2.0.0 usando
  `fullmatch()` com âncoras `\\A...\\Z`, rejeitando espaços, quebras de linha e zeros à esquerda,
  sem normalização silenciosa;
- ACH-B6-007 / ACH-B6.1-001: bloqueio efetivo de perfis não-ativos e de dependências obrigatórias
  ausentes, incompatíveis ou desconhecidas; separação explícita entre `mode="execution"` e
  `mode="diagnostic"` (um perfil em diagnóstico nunca é marcado como `execution_eligible=True`);
- ACH-B6-008 / ACH-B6.1-003 / ACH-B6.1-005: validação real de compatibilidade de versões via
  `packaging.specifiers.SpecifierSet` + `packaging.version.Version` e geração do registro
  completo de proveniência `perfil -> motor -> dependência -> versão -> estado`.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any, Callable

import yaml

from .dependencies import (
    ExecutionBlockedError,
    RequirementsParseError,
    parse_requirements_file,
    validate_environment_for_profile,
    validate_single_dependency,
)
from .schema_validator import SchemaValidationError, validate_contract

DEFAULT_REFERENCES_DIR = Path(__file__).resolve().parents[2] / "references"
ALLOWED_PROFILE_STATUS = {"active", "draft", "deprecated"}
ALLOWED_LOAD_MODES = {"execution", "diagnostic"}

# Expressão regular oficial da especificação SemVer 2.0.0 (https://semver.org/)
# Usa \A e \Z + fullmatch() para impedir quebras de linha finais (\n) que $ aceitaria em Python.
SEMVER_2_0_0_RE = re.compile(
    r"\A(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?\Z"
)


def validate_semver_strict(version: Any) -> tuple[bool, str]:
    """Valida estritamente SemVer 2.0.0 sem normalização silenciosa, retornando (valido, motivo)."""
    if not isinstance(version, str):
        return False, f"Valor de versão não é string: {type(version).__name__}."
    if version == "":
        return False, "Versão vazia não é um SemVer 2.0.0 válido."
    if any(ch in version for ch in (" ", "\t", "\n", "\r")):
        return False, f"Versão contém espaços ou quebras de linha proibidos: {version!r}."
    if version.startswith(("v", "V")):
        return False, f"Prefixo '{version[0]}' não pertence à especificação SemVer 2.0.0: {version!r}."
    if SEMVER_2_0_0_RE.fullmatch(version) is None:
        return False, f"String {version!r} viola a gramática estrita SemVer 2.0.0."
    return True, "SemVer 2.0.0 válido."


def is_valid_semver(version: Any) -> bool:
    """Valida estritamente conformidade com SemVer 2.0.0 (ACH-B6.1-002)."""
    ok, _ = validate_semver_strict(version)
    return ok


def verify_environment_dependencies(
    engine_deps: dict[str, list[str]],
    *,
    requirements_path: str | Path | None = None,
    metadata_resolver: Callable[[str], str | None] | None = None,
) -> dict[str, dict[str, Any]]:
    """Verifica disponibilidade e compatibilidade real no ambiente Python das dependências declaradas."""
    all_deps = sorted({dep for deps in engine_deps.values() for dep in deps})
    if not all_deps:
        return {"_summary": {"status": "not_applicable", "all_available": True}}

    try:
        req_map = parse_requirements_file(requirements_path)
    except RequirementsParseError as exc:
        report: dict[str, dict[str, Any]] = {}
        for raw_dep in all_deps:
            report[raw_dep] = {
                "distribution": raw_dep,
                "import_name": None,
                "version_specifier": None,
                "status": "unknown",
                "installed_version": None,
                "reason": str(exc),
                "validation_timestamp": None,
            }
        report["_summary"] = {
            "status": "unknown",
            "all_available": False,
            "requirements_error": str(exc),
        }
        return report
    report: dict[str, dict[str, Any]] = {}
    all_ok = True
    worst_status = "available"
    severity_order = {"available": 0, "incompatible": 1, "missing": 2, "unknown": 3}

    for raw_dep in all_deps:
        res = validate_single_dependency(
            raw_dep,
            required=True,
            requirements_map=req_map,
            metadata_resolver=metadata_resolver,
        )
        report[raw_dep] = {
            "distribution": res["distribution_name"],
            "import_name": res["import_name"],
            "version_specifier": res["version_specifier"],
            "status": res["status"],
            "installed_version": res["installed_version"],
            "reason": res["reason"],
            "validation_timestamp": res["validation_timestamp"],
        }
        if res["status"] != "available":
            all_ok = False
            if severity_order.get(res["status"], 3) >= severity_order.get(worst_status, 0):
                worst_status = res["status"]

    report["_summary"] = {
        "status": "available" if all_ok else worst_status,
        "all_available": all_ok,
    }
    return report


def load_yaml_file(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Arquivo YAML não encontrado: {p}")
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Conteúdo YAML raiz deve ser um mapeamento (dict): {p}")
    return data


def load_engine_catalog(catalog_path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    path = Path(catalog_path) if catalog_path else DEFAULT_REFERENCES_DIR / "catalogo_motores.yaml"
    data = load_yaml_file(path)
    motores = data.get("motores", [])
    return {m["id"]: m for m in motores if isinstance(m, dict) and "id" in m}


def list_available_profiles(profiles_dir: str | Path | None = None) -> list[str]:
    pdir = Path(profiles_dir) if profiles_dir else DEFAULT_REFERENCES_DIR / "profiles"
    if not pdir.exists():
        return []
    return sorted(
        p.stem for p in pdir.glob("*.yaml") if p.name != "schema_profile.yaml"
    )


def load_profile(
    profile_ref: str | Path,
    *,
    catalog_path: str | Path | None = None,
    references_dir: str | Path | None = None,
    requirements_path: str | Path | None = None,
    require_implemented: bool = True,
    allow_non_active: bool = False,
    mode: str = "execution",
    requested_optional_engines: list[str] | None = None,
    metadata_resolver: Callable[[str], str | None] | None = None,
) -> dict[str, Any]:
    """Carrega e valida formalmente um perfil YAML contra `schema_profile.json` e o ambiente real.

    Modos suportados:
    - `mode="execution"` (padrão): bloqueia com exceção qualquer violação de schema, SemVer,
      data, status não-ativo (sem `allow_non_active`), motor planejado obrigatório ou dependência
      obrigatória ausente/incompatível/desconhecida. Nenhum parâmetro contorna dependências obrigatórias.
    - `mode="diagnostic"`: coleta todos os resultados de validação sem levantar erro de bloqueio
      e marca obrigatoriamente `execution_eligible = False` (nunca apresentável como executável).
    """
    if mode not in ALLOWED_LOAD_MODES:
        raise ValueError(f"Modo inválido '{mode}'. Use um de: {sorted(ALLOWED_LOAD_MODES)}.")

    ref_dir = Path(references_dir) if references_dir else DEFAULT_REFERENCES_DIR
    candidate = Path(profile_ref)
    if not candidate.exists():
        by_id = ref_dir / "profiles" / f"{profile_ref}.yaml"
        if by_id.exists():
            candidate = by_id
        else:
            raise FileNotFoundError(f"Perfil YAML não encontrado: {profile_ref}")

    profile = load_yaml_file(candidate)
    profile_id = str(profile.get("profile_id", candidate.stem))
    blocking_reasons: list[str] = []

    # 1. Validação executável contra schema_profile.json fechado (ACH-B6-005 / ACH-B6.1-004)
    schema_errors = validate_contract(profile, "schema_profile.json", raise_on_error=False)
    schema_valid = len(schema_errors) == 0
    if not schema_valid:
        if mode == "execution":
            raise SchemaValidationError("schema_profile.json", schema_errors)
        blocking_reasons.extend(f"Schema inválido: {err}" for err in schema_errors)

    # 2. Validação estrita SemVer 2.0.0 (ACH-B6.1-002) e data real de calendário
    raw_version = profile.get("profile_version")
    semver_valid, semver_reason = validate_semver_strict(raw_version)
    version = raw_version if isinstance(raw_version, str) else str(raw_version)
    if not semver_valid:
        msg = f"profile_version não conforme com SemVer 2.0.0 em '{profile_id}': {semver_reason}"
        if mode == "execution":
            raise ValueError(msg)
        blocking_reasons.append(msg)

    raw_date = profile.get("effective_date")
    date_valid = True
    try:
        if not isinstance(raw_date, str):
            raise ValueError("effective_date deve ser string YYYY-MM-DD")
        date.fromisoformat(raw_date)
    except ValueError as exc:
        date_valid = False
        msg = f"effective_date inválida em '{profile_id}': {raw_date!r}"
        if mode == "execution":
            raise ValueError(msg) from exc
        blocking_reasons.append(msg)

    # 3. Elegibilidade de execução por status (ACH-B6-007 / ACH-B6.1-001)
    status = str(profile.get("profile_status", ""))
    if status != "active":
        msg = (
            f"Perfil '{profile_id}' possui status '{status}' e não é elegível para execução normal "
            "(use allow_non_active=True explicitamente para inspeção/desenvolvimento ou mode='diagnostic')."
        )
        if mode == "execution" and not allow_non_active:
            raise ValueError(msg)
        blocking_reasons.append(f"Status do perfil é '{status}' (exige 'active' para execução).")

    # 4. Validação de motores contra catálogo (ACH-B6-002)
    engines_cfg = profile.get("engines") if isinstance(profile.get("engines"), dict) else {}
    catalog = load_engine_catalog(catalog_path)
    req_opt_set = set(requested_optional_engines or [])

    unknown: list[str] = []
    planned_required: list[str] = []
    optional_implemented: list[str] = []
    optional_planned: list[str] = []
    engine_deps_map: dict[str, list[str]] = {}
    engine_versions: dict[str, str] = {}
    engines_spec_for_env: list[dict[str, Any]] = []

    for engine_id in engines_cfg.get("required", []) or []:
        if engine_id not in catalog:
            unknown.append(engine_id)
            continue
        meta = catalog[engine_id]
        impl_status = str(meta.get("status", "unknown"))
        if require_implemented and impl_status.lower() == "planejado":
            planned_required.append(engine_id)
        deps = list(meta.get("dependencias", []) or [])
        engine_deps_map[engine_id] = deps
        engine_versions[engine_id] = str(meta.get("versao", "unknown"))
        engines_spec_for_env.append(
            {
                "engine_id": engine_id,
                "implementation_status": impl_status,
                "required_by_profile": True,
                "requested": True,
                "dependencies": deps,
            }
        )

    for engine_id in engines_cfg.get("optional", []) or []:
        if engine_id not in catalog:
            unknown.append(engine_id)
            continue
        meta = catalog[engine_id]
        impl_status = str(meta.get("status", "unknown"))
        if impl_status.lower() == "planejado":
            optional_planned.append(engine_id)
        else:
            optional_implemented.append(engine_id)
        deps = list(meta.get("dependencias", []) or [])
        engine_deps_map[engine_id] = deps
        engine_versions[engine_id] = str(meta.get("versao", "unknown"))
        engines_spec_for_env.append(
            {
                "engine_id": engine_id,
                "implementation_status": impl_status,
                "required_by_profile": False,
                "requested": engine_id in req_opt_set,
                "dependencies": deps,
            }
        )

    if unknown:
        msg = f"Perfil '{profile_id}' referencia motores não catalogados: {unknown}"
        if mode == "execution":
            raise ValueError(msg)
        blocking_reasons.append(msg)
    if planned_required:
        msg = f"Perfil '{profile_id}' exige motores ainda não implementados (status='planejado'): {planned_required}"
        if mode == "execution":
            raise ValueError(msg)
        blocking_reasons.append(msg)

    # 5. Validação centralizada de ambiente e compatibilidade de versões (ACH-B6.1-001 + ACH-B6.1-003)
    env_audit = validate_environment_for_profile(
        engines_spec_for_env,
        profile_extra_dependencies=profile.get("dependencies") if isinstance(profile.get("dependencies"), list) else None,
        requirements_path=requirements_path,
        metadata_resolver=metadata_resolver,
    )
    blocking_reasons.extend(env_audit["blocking_reasons"])

    # Regra mandatória ACH-B6.1-001: em modo execution, NENHUM parâmetro contorna dependências obrigatórias!
    if mode == "execution" and not env_audit["environment_eligible"]:
        raise ExecutionBlockedError(
            f"Perfil '{profile_id}' bloqueado para execução por falha de dependências/ambiente: "
            + "; ".join(env_audit["blocking_reasons"]),
            reasons=env_audit["blocking_reasons"],
        )

    verified_deps = verify_environment_dependencies(
        engine_deps_map,
        requirements_path=requirements_path,
        metadata_resolver=metadata_resolver,
    )

    # 6. Carrega vocabulário canônico e checklists opcionais
    loaded_vocabulary: dict[str, Any] | None = None
    vocab_cfg = profile.get("vocabulary") or {}
    if isinstance(vocab_cfg, dict) and vocab_cfg.get("canonical_file"):
        loaded_vocabulary = load_yaml_file(ref_dir / vocab_cfg["canonical_file"])

    loaded_checklists: list[dict[str, Any]] = []
    for chk_rel in profile.get("checklists", []) or []:
        loaded_checklists.append(load_yaml_file(ref_dir / chk_rel))

    # Regra estrita de elegibilidade (ACH-B6.1-001): todas as 6 condições + modo execution
    execution_eligible = (
        mode == "execution"
        and schema_valid
        and semver_valid
        and date_valid
        and status == "active"
        and len(unknown) == 0
        and len(planned_required) == 0
        and env_audit["environment_eligible"]
    )

    # Registro completo de proveniência para run_manifest.json (ACH-B6.1-005)
    manifest_profile_record = {
        "profile_id": profile_id,
        "profile_version": version,
        "profile_status": status,
        "execution_eligible": execution_eligible,
        "mode": mode,
        "schema_validation": {
            "valid": schema_valid,
            "schema": "schema_profile.json",
            "errors": schema_errors,
        },
        "semver_validation": {
            "valid": semver_valid,
            "version": version,
            "reason": semver_reason,
        },
        "engines": [
            {
                "engine_id": eng["engine_id"],
                "implementation_status": eng["implementation_status"],
                "requested": eng["requested"],
                "required_by_profile": eng["required_by_profile"],
                "dependencies": eng["dependencies"],
            }
            for eng in env_audit["engines"]
        ],
        "profile_dependencies": env_audit["profile_dependencies"],
        "requirements_error": env_audit.get("requirements_error"),
        "blocking_reasons": blocking_reasons,
        "optional_unmet_warnings": env_audit["optional_unmet_warnings"],
    }

    profile["_resolved"] = {
        "source_file": candidate.name,
        "mode": mode,
        "execution_eligible": execution_eligible,
        "non_active_override": status != "active" and allow_non_active,
        "blocking_reasons": blocking_reasons,
        "optional_unmet_warnings": env_audit["optional_unmet_warnings"],
        "engine_dependencies": engine_deps_map,
        "verified_dependencies": verified_deps,
        "engines_audit": env_audit["engines"],
        "profile_dependencies_audit": env_audit["profile_dependencies"],
        "engine_versions": engine_versions,
        "optional_implemented": optional_implemented,
        "optional_planned": optional_planned,
        "loaded_vocabulary": loaded_vocabulary,
        "loaded_checklists": loaded_checklists,
        "manifest_profile_record": manifest_profile_record,
        "manifest_entry": {
            profile_id: {
                "version": version,
                "status": status,
                "execution_eligible": execution_eligible,
                "non_active_override": status != "active" and allow_non_active,
                "dependencies_available": env_audit["environment_eligible"],
            }
        },
    }
    return profile
