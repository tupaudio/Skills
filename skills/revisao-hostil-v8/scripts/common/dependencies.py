"""Validação centralizada de dependências e compatibilidade de versões (Revisão Hostil v8.0-beta.6.2).

Implementa integralmente:
- ACH-B6.1-001 (P1): bloqueio efetivo de execução quando dependências obrigatórias estão
  ausentes, incompatíveis ou desconhecidas; separação por motor (obrigatório vs opcional
  solicitado vs opcional não solicitado).
- ACH-B6.1-003 (P2): comparação real entre restrições declaradas (`requirements.txt` / catálogo / perfil)
  e versões efetivamente instaladas via `packaging.specifiers.SpecifierSet` e `packaging.version.Version`,
  distinguindo nome de distribuição PyPI e nome de módulo de importação.
"""

from __future__ import annotations

import importlib
import importlib.metadata
from pathlib import Path
from typing import Any, Callable

from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from .evidence import utc_now_iso

DEFAULT_REQUIREMENTS_PATH = Path(__file__).resolve().parents[2] / "requirements.txt"

ALLOWED_DEPENDENCY_STATUSES = (
    "available",
    "missing",
    "incompatible",
    "unknown",
    "not_applicable",
)

BLOCKING_DEPENDENCY_STATUSES = frozenset({"missing", "incompatible", "unknown"})

# Mapa explícito de nomes de catálogo/distribuição -> (distribution_name canônico, import_name)
# Nunca inferir dependências a partir de nomes de motores.
DISTRIBUTION_REGISTRY: dict[str, tuple[str, str]] = {
    "numpy": ("numpy", "numpy"),
    "scipy": ("scipy", "scipy"),
    "sympy": ("sympy", "sympy"),
    "pillow": ("Pillow", "PIL"),
    "pil": ("Pillow", "PIL"),
    "pyyaml": ("PyYAML", "yaml"),
    "yaml": ("PyYAML", "yaml"),
    "python-docx": ("python-docx", "docx"),
    "docx": ("python-docx", "docx"),
    "pypdf": ("pypdf", "pypdf"),
    "jsonschema": ("jsonschema", "jsonschema"),
    "referencing": ("referencing", "referencing"),
    "packaging": ("packaging", "packaging"),
    "pytest": ("pytest", "pytest"),
    "pytest-cov": ("pytest-cov", "pytest_cov"),
    "coverage": ("coverage", "coverage"),
}


class ExecutionBlockedError(RuntimeError):
    """Erro bloqueante levantado antes de qualquer execução quando o ambiente ou perfil é inelegível."""

    def __init__(self, message: str, *, reasons: list[str] | None = None) -> None:
        self.reasons = list(reasons or [message])
        super().__init__(message)


def _normalize_dist_key(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def parse_requirements_file(
    requirements_path: str | Path | None = None,
) -> dict[str, dict[str, str]]:
    """Lê `requirements.txt` como fonte de verdade de restrições de versão."""
    path = Path(requirements_path) if requirements_path else DEFAULT_REQUIREMENTS_PATH
    if not path.exists():
        return {}

    parsed: dict[str, dict[str, str]] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        try:
            req = Requirement(line)
        except InvalidRequirement:
            continue
        key = _normalize_dist_key(req.name)
        canonical_dist, import_name = DISTRIBUTION_REGISTRY.get(key, (req.name, req.name.replace("-", "_")))
        parsed[key] = {
            "distribution_name": canonical_dist,
            "import_name": import_name,
            "version_specifier": str(req.specifier),
            "raw_requirement": line,
        }
    return parsed


def _default_metadata_resolver(distribution_name: str) -> str | None:
    """Consulta real à metadata instalada no ambiente Python via importlib.metadata."""
    return importlib.metadata.version(distribution_name)


def parse_dependency_declaration(
    dep_spec: str | dict[str, Any],
    *,
    required: bool,
    requirements_map: dict[str, dict[str, str]],
) -> dict[str, Any]:
    """Normaliza uma declaração de dependência (string ou objeto estruturado) sem inventar versões."""
    if isinstance(dep_spec, dict):
        raw_dist = str(dep_spec.get("distribution_name", "")).strip()
        if not raw_dist:
            return {
                "distribution_name": "",
                "import_name": None,
                "required": bool(dep_spec.get("required", required)),
                "version_specifier": dep_spec.get("version_specifier"),
                "parse_error": "Declaração estruturada de dependência sem distribution_name.",
            }
        key = _normalize_dist_key(raw_dist)
        reg_dist, reg_imp = DISTRIBUTION_REGISTRY.get(key, (raw_dist, dep_spec.get("import_name")))
        req_entry = requirements_map.get(key)
        spec_str = dep_spec.get("version_specifier")
        if spec_str is None and req_entry is not None:
            spec_str = req_entry["version_specifier"]
        return {
            "distribution_name": reg_dist,
            "import_name": dep_spec.get("import_name") or (req_entry["import_name"] if req_entry else reg_imp),
            "required": bool(dep_spec.get("required", required)),
            "version_specifier": spec_str if spec_str is not None else "",
            "parse_error": None,
        }

    if not isinstance(dep_spec, str) or not dep_spec.strip():
        return {
            "distribution_name": str(dep_spec),
            "import_name": None,
            "required": required,
            "version_specifier": None,
            "parse_error": f"Declaração de dependência inválida: {dep_spec!r}.",
        }

    raw_str = dep_spec.strip()
    try:
        req = Requirement(raw_str)
    except InvalidRequirement as exc:
        return {
            "distribution_name": raw_str,
            "import_name": None,
            "required": required,
            "version_specifier": raw_str,
            "parse_error": f"Especificação de dependência inválida ({raw_str!r}): {exc}",
        }

    key = _normalize_dist_key(req.name)
    reg_dist, reg_imp = DISTRIBUTION_REGISTRY.get(key, (req.name, None))
    req_entry = requirements_map.get(key)
    spec_str = str(req.specifier)
    if not spec_str and req_entry is not None:
        spec_str = req_entry["version_specifier"]
    import_name = reg_imp or (req_entry["import_name"] if req_entry else None)
    return {
        "distribution_name": reg_dist,
        "import_name": import_name,
        "required": required,
        "version_specifier": spec_str,
        "parse_error": None,
    }


def validate_single_dependency(
    dep_spec: str | dict[str, Any],
    *,
    required: bool = True,
    requirements_map: dict[str, dict[str, str]] | None = None,
    metadata_resolver: Callable[[str], str | None] | None = None,
) -> dict[str, Any]:
    """Valida existência e compatibilidade de versão de uma única dependência."""
    ts = utc_now_iso()
    req_map = requirements_map if requirements_map is not None else parse_requirements_file()
    resolver = metadata_resolver or _default_metadata_resolver

    decl = parse_dependency_declaration(dep_spec, required=required, requirements_map=req_map)
    dist_name = decl["distribution_name"]
    import_name = decl["import_name"]
    is_required = decl["required"]
    spec_str = decl["version_specifier"]

    if decl["parse_error"]:
        return {
            "distribution_name": dist_name,
            "import_name": import_name,
            "required": is_required,
            "version_specifier": spec_str,
            "installed_version": None,
            "status": "unknown",
            "validation_timestamp": ts,
            "reason": decl["parse_error"],
        }

    # Valida sintaxe da restrição de versão antes de aceitar qualquer resultado
    spec_set: SpecifierSet | None = None
    if spec_str:
        try:
            spec_set = SpecifierSet(spec_str)
        except InvalidSpecifier as exc:
            return {
                "distribution_name": dist_name,
                "import_name": import_name,
                "required": is_required,
                "version_specifier": spec_str,
                "installed_version": None,
                "status": "unknown",
                "validation_timestamp": ts,
                "reason": f"Restrição de versão inválida '{spec_str}' para '{dist_name}': {exc}",
            }

    # Consulta metadados reais do ambiente
    try:
        installed_raw = resolver(dist_name)
    except importlib.metadata.PackageNotFoundError:
        return {
            "distribution_name": dist_name,
            "import_name": import_name,
            "required": is_required,
            "version_specifier": spec_str or None,
            "installed_version": None,
            "status": "missing",
            "validation_timestamp": ts,
            "reason": f"Distribuição '{dist_name}' não encontrada no ambiente Python.",
        }
    except Exception as exc:
        return {
            "distribution_name": dist_name,
            "import_name": import_name,
            "required": is_required,
            "version_specifier": spec_str or None,
            "installed_version": None,
            "status": "unknown",
            "validation_timestamp": ts,
            "reason": f"Falha ao consultar metadados de '{dist_name}': {exc}",
        }

    if installed_raw is None or not isinstance(installed_raw, str) or not installed_raw.strip():
        return {
            "distribution_name": dist_name,
            "import_name": import_name,
            "required": is_required,
            "version_specifier": spec_str or None,
            "installed_version": None,
            "status": "unknown",
            "validation_timestamp": ts,
            "reason": f"Distribuição '{dist_name}' instalada sem metadados de versão utilizáveis.",
        }

    try:
        installed_ver = Version(installed_raw.strip())
    except InvalidVersion as exc:
        return {
            "distribution_name": dist_name,
            "import_name": import_name,
            "required": is_required,
            "version_specifier": spec_str or None,
            "installed_version": installed_raw,
            "status": "unknown",
            "validation_timestamp": ts,
            "reason": f"Versão instalada '{installed_raw}' de '{dist_name}' não pôde ser interpretada (PEP 440): {exc}",
        }

    if spec_set is not None and not spec_set.contains(installed_ver, prereleases=True):
        return {
            "distribution_name": dist_name,
            "import_name": import_name,
            "required": is_required,
            "version_specifier": spec_str,
            "installed_version": str(installed_ver),
            "status": "incompatible",
            "validation_timestamp": ts,
            "reason": (
                f"Versão instalada '{installed_ver}' de '{dist_name}' é incompatível "
                f"com a restrição declarada '{spec_str}'."
            ),
        }

    reason_ok = (
        f"Versão instalada '{installed_ver}' satisfaz restrição '{spec_str}'."
        if spec_set is not None
        else f"Versão instalada '{installed_ver}' verificada (sem restrição de faixa declarada)."
    )
    return {
        "distribution_name": dist_name,
        "import_name": import_name,
        "required": is_required,
        "version_specifier": spec_str or None,
        "installed_version": str(installed_ver),
        "status": "available",
        "validation_timestamp": ts,
        "reason": reason_ok,
    }


def validate_engine_dependencies(
    engine_id: str,
    declared_dependencies: list[str | dict[str, Any]],
    *,
    implementation_status: str,
    required_by_profile: bool,
    requested: bool,
    requirements_map: dict[str, dict[str, str]] | None = None,
    metadata_resolver: Callable[[str], str | None] | None = None,
) -> dict[str, Any]:
    """Valida todas as dependências declaradas de um único motor."""
    ts = utc_now_iso()
    req_map = requirements_map if requirements_map is not None else parse_requirements_file()

    if not declared_dependencies:
        dep_records = [
            {
                "distribution_name": None,
                "import_name": None,
                "required": required_by_profile or requested,
                "version_specifier": None,
                "installed_version": None,
                "status": "not_applicable",
                "validation_timestamp": ts,
                "reason": f"Motor '{engine_id}' não declara dependências externas (apenas biblioteca padrão).",
            }
        ]
        return {
            "engine_id": engine_id,
            "implementation_status": implementation_status,
            "required_by_profile": required_by_profile,
            "requested": requested,
            "dependencies": dep_records,
            "all_dependencies_satisfied": True,
            "blocking_reasons": [],
        }

    dep_records = []
    blocking_reasons: list[str] = []
    dep_required_flag = required_by_profile or requested

    for dep in declared_dependencies:
        rec = validate_single_dependency(
            dep,
            required=dep_required_flag,
            requirements_map=req_map,
            metadata_resolver=metadata_resolver,
        )
        dep_records.append(rec)
        if rec["status"] in BLOCKING_DEPENDENCY_STATUSES:
            blocking_reasons.append(
                f"Motor '{engine_id}': dependência '{rec['distribution_name']}' em estado "
                f"'{rec['status']}' ({rec['reason']})"
            )

    return {
        "engine_id": engine_id,
        "implementation_status": implementation_status,
        "required_by_profile": required_by_profile,
        "requested": requested,
        "dependencies": dep_records,
        "all_dependencies_satisfied": len(blocking_reasons) == 0,
        "blocking_reasons": blocking_reasons,
    }


def validate_environment_for_profile(
    engines_spec: list[dict[str, Any]],
    *,
    profile_extra_dependencies: list[dict[str, Any]] | None = None,
    requirements_path: str | Path | None = None,
    metadata_resolver: Callable[[str], str | None] | None = None,
) -> dict[str, Any]:
    """Validação centralizada do ambiente para todos os motores de um perfil."""
    req_map = parse_requirements_file(requirements_path)
    engine_reports: list[dict[str, Any]] = []
    blocking_reasons: list[str] = []
    warnings_optional: list[str] = []

    for eng in engines_spec:
        eid = eng["engine_id"]
        impl_status = str(eng["implementation_status"])
        req_by_prof = bool(eng["required_by_profile"])
        requested = bool(eng["requested"])
        deps = list(eng.get("dependencies", []) or [])

        report = validate_engine_dependencies(
            eid,
            deps,
            implementation_status=impl_status,
            required_by_profile=req_by_prof,
            requested=requested,
            requirements_map=req_map,
            metadata_resolver=metadata_resolver,
        )
        engine_reports.append(report)

        if req_by_prof or requested:
            if impl_status.lower() == "planejado":
                blocking_reasons.append(
                    f"Motor '{eid}' exigido/solicitado possui status '{impl_status}' (não implementado)."
                )
            blocking_reasons.extend(report["blocking_reasons"])
        else:
            # Motor opcional NÃO solicitado: ausências são registradas sem bloquear o perfil
            if report["blocking_reasons"]:
                warnings_optional.extend(report["blocking_reasons"])

    profile_dep_reports: list[dict[str, Any]] = []
    for extra in profile_extra_dependencies or []:
        rec = validate_single_dependency(
            extra,
            required=bool(extra.get("required", True)),
            requirements_map=req_map,
            metadata_resolver=metadata_resolver,
        )
        profile_dep_reports.append(rec)
        if rec["required"] and rec["status"] in BLOCKING_DEPENDENCY_STATUSES:
            blocking_reasons.append(
                f"Dependência de perfil '{rec['distribution_name']}' em estado '{rec['status']}' ({rec['reason']})"
            )

    return {
        "engines": engine_reports,
        "profile_dependencies": profile_dep_reports,
        "environment_eligible": len(blocking_reasons) == 0,
        "blocking_reasons": blocking_reasons,
        "optional_unmet_warnings": warnings_optional,
    }


def assert_engine_execution_allowed(
    profile: dict[str, Any],
    engine_id: str,
) -> dict[str, Any]:
    """Portão obrigatório pré-execução: impede execução de qualquer motor em ambiente/perfil inelegível."""
    resolved = profile.get("_resolved")
    if not isinstance(resolved, dict):
        raise ExecutionBlockedError(
            "Perfil não passou por validação formal via load_profile(); execução bloqueada."
        )

    if resolved.get("mode") != "execution":
        raise ExecutionBlockedError(
            f"Perfil '{profile.get('profile_id')}' foi carregado em modo '{resolved.get('mode')}' "
            "(diagnóstico) e não pode executar motores."
        )

    if not resolved.get("execution_eligible", False):
        reasons = list(resolved.get("blocking_reasons") or ["Perfil inelegível para execução."])
        raise ExecutionBlockedError(
            f"Execução do motor '{engine_id}' bloqueada: perfil '{profile.get('profile_id')}' "
            f"não é elegível para execução ({'; '.join(reasons)}).",
            reasons=reasons,
        )

    engines_audit = resolved.get("engines_audit", [])
    engine_entry = next((e for e in engines_audit if e["engine_id"] == engine_id), None)
    if engine_entry is None:
        raise ExecutionBlockedError(
            f"Motor '{engine_id}' não pertence aos motores declarados do perfil '{profile.get('profile_id')}'."
        )

    if str(engine_entry.get("implementation_status", "")).lower() == "planejado":
        raise ExecutionBlockedError(
            f"Execução bloqueada: motor '{engine_id}' possui status 'planejado' (não implementado)."
        )

    if not engine_entry.get("all_dependencies_satisfied", False):
        reasons = list(engine_entry.get("blocking_reasons") or [f"Dependências do motor '{engine_id}' não atendidas."])
        raise ExecutionBlockedError(
            f"Execução bloqueada para o motor '{engine_id}': {'; '.join(reasons)}",
            reasons=reasons,
        )

    return engine_entry


def execute_engine_with_profile(
    profile: dict[str, Any],
    engine_id: str,
    payload: dict[str, Any],
    *,
    engine_runner: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Executa um motor somente após aprovação integral do portão de elegibilidade e dependências."""
    assert_engine_execution_allowed(profile, engine_id)

    if engine_runner is not None:
        return engine_runner(payload)

    mod = importlib.import_module(f"scripts.engines.{engine_id}")
    return mod.run_motor(payload)
