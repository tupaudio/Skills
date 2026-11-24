"""Validação centralizada de dependências e compatibilidade de versões (Revisão Hostil v8.0-beta.6.3).

Implementa integralmente:
- ACH-B6.1-001 (P1): bloqueio efetivo de execução quando dependências obrigatórias estão
  ausentes, incompatíveis ou desconhecidas; separação por motor (obrigatório vs opcional
  solicitado vs opcional não solicitado).
- ACH-B6.1-003 (P2): comparação real entre restrições declaradas (`requirements.txt` / catálogo / perfil)
  e versões efetivamente instaladas via `packaging.specifiers.SpecifierSet` e `packaging.version.Version`,
  distinguindo nome de distribuição PyPI e nome de módulo de importação.
- ACH-B6.2-002 (P2): parser fail-closed de `requirements.txt` (arquivo ausente, erro de leitura/UTF-8,
  linhas malformadas, consolidação e detecção de conflitos em declarações duplicadas, extras,
  marcadores de ambiente e recusa de classificar dependência sem restrição como `available`).
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


class RequirementsParseError(ValueError):
    """Erro fail-closed de leitura ou parsing do contrato `requirements.txt` (ACH-B6.2-002)."""

    def __init__(
        self,
        *,
        path: str,
        line_number: int,
        line_content: str,
        reason: str,
    ) -> None:
        self.path = path
        self.line_number = line_number
        self.line_content = line_content
        self.reason = reason
        location = f"{path}:{line_number}" if line_number > 0 else path
        msg = f"Erro no contrato de requisitos ({location}): {reason}"
        if line_content:
            msg += f" | linha={line_content!r}"
        super().__init__(msg)


class RequirementsConflictError(RequirementsParseError):
    """Erro levantado quando declarações duplicadas possuem restrições de versão mutuamente incompatíveis."""


def _normalize_dist_key(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def _detect_specifier_conflict(dist_name: str, spec_set: SpecifierSet) -> str | None:
    """Detecta conflitos lógicos entre restrições de versão (ex.: >=3.0 e <2.0, ==2.0 e ==3.0)."""
    exact_pins: set[Version] = set()
    excluded: set[Version] = set()
    lower_bound: tuple[Version, bool] | None = None  # (version, inclusive)
    upper_bound: tuple[Version, bool] | None = None  # (version, inclusive)

    for sp in spec_set:
        op = sp.operator
        raw_v = sp.version
        if "*" in raw_v:
            continue
        try:
            ver = Version(raw_v)
        except InvalidVersion:
            continue

        if op in ("==", "==="):
            exact_pins.add(ver)
        elif op == "!=":
            excluded.add(ver)
        elif op == ">=":
            if lower_bound is None or ver > lower_bound[0]:
                lower_bound = (ver, True)
        elif op == ">":
            if lower_bound is None or ver > lower_bound[0] or (ver == lower_bound[0] and lower_bound[1]):
                lower_bound = (ver, False)
        elif op == "<=":
            if upper_bound is None or ver < upper_bound[0]:
                upper_bound = (ver, True)
        elif op == "<":
            if upper_bound is None or ver < upper_bound[0] or (ver == upper_bound[0] and upper_bound[1]):
                upper_bound = (ver, False)

    if len(exact_pins) > 1:
        pins_txt = ", ".join(str(v) for v in sorted(exact_pins))
        return f"Conflito de restrições exatas para '{dist_name}': {pins_txt} ({spec_set})."

    if len(exact_pins) == 1:
        pin = next(iter(exact_pins))
        if not spec_set.contains(pin, prereleases=True):
            return f"Restrição exata '{pin}' conflita com o conjunto '{spec_set}' para '{dist_name}'."

    if lower_bound is not None and upper_bound is not None:
        low_v, low_inc = lower_bound
        high_v, high_inc = upper_bound
        if low_v > high_v:
            return f"Intervalo vazio/conflitante para '{dist_name}': limite inferior {low_v} > limite superior {high_v} ({spec_set})."
        if low_v == high_v and not (low_inc and high_inc):
            return f"Intervalo vazio/conflitante para '{dist_name}': limites exclusivos coincidentes em {low_v} ({spec_set})."
        if low_v == high_v and low_inc and high_inc and low_v in excluded:
            return f"Intervalo vazio/conflitante para '{dist_name}': único ponto {low_v} está excluído por != ({spec_set})."

    return None


def parse_requirements_file(
    requirements_path: str | Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Lê `requirements.txt` em modo fail-closed como contrato obrigatório de ambiente (ACH-B6.2-002).

    - Levanta `RequirementsParseError` se o arquivo não existir, não puder ser lido,
      tiver codificação UTF-8 inválida ou contiver qualquer linha malformada.
    - Consolida declarações duplicadas compatíveis e levanta `RequirementsConflictError`
      quando há conflito de restrições de versão.
    - Preserva nome de distribuição, nome de importação, especificadores, extras,
      marcadores de ambiente e origem da declaração.
    """
    path = Path(requirements_path) if requirements_path else DEFAULT_REQUIREMENTS_PATH
    if not path.exists() or not path.is_file():
        raise RequirementsParseError(
            path=str(path),
            line_number=0,
            line_content="",
            reason="Arquivo obrigatório de requisitos não encontrado.",
        )

    try:
        raw_bytes = path.read_bytes()
    except OSError as exc:
        raise RequirementsParseError(
            path=str(path),
            line_number=0,
            line_content="",
            reason=f"Falha de leitura do arquivo de requisitos: {exc}",
        ) from exc

    try:
        content = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RequirementsParseError(
            path=str(path),
            line_number=0,
            line_content="",
            reason=f"Codificação UTF-8 inválida no arquivo de requisitos: {exc}",
        ) from exc

    parsed: dict[str, dict[str, Any]] = {}
    for lineno, raw_line in enumerate(content.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        code_part = raw_line.split("#", 1)[0].strip()
        if not code_part:
            continue

        try:
            req = Requirement(code_part)
        except InvalidRequirement as exc:
            raise RequirementsParseError(
                path=str(path),
                line_number=lineno,
                line_content=raw_line,
                reason=f"Linha malformada em requirements.txt: {exc}",
            ) from exc

        key = _normalize_dist_key(req.name)
        canonical_dist, import_name = DISTRIBUTION_REGISTRY.get(key, (req.name, req.name.replace("-", "_")))
        marker_str = str(req.marker) if req.marker is not None else None
        marker_active = bool(req.marker.evaluate()) if req.marker is not None else True
        source_rec = {
            "file": str(path),
            "line_number": lineno,
            "raw_line": raw_line,
            "marker": marker_str,
            "marker_active": marker_active,
        }

        conflict_single = _detect_specifier_conflict(canonical_dist, req.specifier)
        if conflict_single:
            raise RequirementsConflictError(
                path=str(path),
                line_number=lineno,
                line_content=raw_line,
                reason=conflict_single,
            )

        if key in parsed:
            existing = parsed[key]
            existing["sources"].append(source_rec)
            existing["extras"] = sorted(set(existing["extras"]) | set(req.extras))
            if marker_str is not None and marker_str not in existing["markers"]:
                existing["markers"].append(marker_str)

            # Consolida restrições quando ambas são ativas neste ambiente
            if existing["marker_active"] and marker_active:
                combined = existing["specifier_set"] & req.specifier
                conflict = _detect_specifier_conflict(canonical_dist, combined)
                if conflict:
                    raise RequirementsConflictError(
                        path=str(path),
                        line_number=lineno,
                        line_content=raw_line,
                        reason=conflict,
                    )
                existing["specifier_set"] = combined
                existing["version_specifier"] = str(combined)
                existing["has_version_specifier"] = len(combined) > 0
            elif marker_active and not existing["marker_active"]:
                existing["specifier_set"] = req.specifier
                existing["version_specifier"] = str(req.specifier)
                existing["has_version_specifier"] = len(req.specifier) > 0
                existing["marker_active"] = True
        else:
            parsed[key] = {
                "distribution_name": canonical_dist,
                "import_name": import_name,
                "version_specifier": str(req.specifier),
                "specifier_set": req.specifier,
                "has_version_specifier": len(req.specifier) > 0,
                "extras": sorted(req.extras),
                "markers": [marker_str] if marker_str is not None else [],
                "marker_active": marker_active,
                "sources": [source_rec],
                "origin": str(path),
            }

    return parsed


def _default_metadata_resolver(distribution_name: str) -> str | None:
    """Consulta real à metadata instalada no ambiente Python via importlib.metadata."""
    return importlib.metadata.version(distribution_name)


def parse_dependency_declaration(
    dep_spec: str | dict[str, Any],
    *,
    required: bool,
    requirements_map: dict[str, dict[str, Any]],
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
                "has_version_specifier": False,
                "extras": [],
                "markers": [],
                "marker_active": True,
                "origin": "structured_declaration",
                "parse_error": "Declaração estruturada de dependência sem distribution_name.",
            }
        try:
            parsed_name_req = Requirement(raw_dist)
        except InvalidRequirement as exc:
            return {
                "distribution_name": raw_dist,
                "import_name": dep_spec.get("import_name"),
                "required": bool(dep_spec.get("required", required)),
                "version_specifier": dep_spec.get("version_specifier"),
                "has_version_specifier": False,
                "extras": [],
                "markers": [],
                "marker_active": True,
                "origin": "structured_declaration",
                "parse_error": f"Nome de distribuição inválido ({raw_dist!r}): {exc}",
            }

        key = _normalize_dist_key(parsed_name_req.name)
        reg_dist, reg_imp = DISTRIBUTION_REGISTRY.get(key, (parsed_name_req.name, dep_spec.get("import_name")))
        req_entry = requirements_map.get(key)
        explicit_spec = dep_spec.get("version_specifier")
        if explicit_spec is not None and str(explicit_spec).strip():
            spec_str = str(explicit_spec).strip()
            origin = "structured_declaration"
        elif req_entry is not None and req_entry.get("version_specifier"):
            spec_str = str(req_entry["version_specifier"])
            origin = str(req_entry.get("origin", "requirements.txt"))
        else:
            spec_str = ""
            origin = "unconstrained"

        return {
            "distribution_name": reg_dist,
            "import_name": dep_spec.get("import_name") or (req_entry["import_name"] if req_entry else reg_imp),
            "required": bool(dep_spec.get("required", required)),
            "version_specifier": spec_str,
            "has_version_specifier": bool(spec_str),
            "extras": list(req_entry["extras"]) if req_entry else sorted(parsed_name_req.extras),
            "markers": list(req_entry["markers"]) if req_entry else [],
            "marker_active": bool(req_entry["marker_active"]) if req_entry else True,
            "origin": origin,
            "parse_error": None,
        }

    if not isinstance(dep_spec, str) or not dep_spec.strip():
        return {
            "distribution_name": str(dep_spec),
            "import_name": None,
            "required": required,
            "version_specifier": None,
            "has_version_specifier": False,
            "extras": [],
            "markers": [],
            "marker_active": True,
            "origin": "invalid",
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
            "has_version_specifier": False,
            "extras": [],
            "markers": [],
            "marker_active": True,
            "origin": "invalid",
            "parse_error": f"Especificação de dependência inválida ({raw_str!r}): {exc}",
        }

    key = _normalize_dist_key(req.name)
    reg_dist, reg_imp = DISTRIBUTION_REGISTRY.get(key, (req.name, None))
    req_entry = requirements_map.get(key)

    marker_str = str(req.marker) if req.marker is not None else None
    marker_active = bool(req.marker.evaluate()) if req.marker is not None else (
        bool(req_entry["marker_active"]) if req_entry else True
    )
    markers = [marker_str] if marker_str is not None else (list(req_entry["markers"]) if req_entry else [])
    extras = sorted(set(req.extras) | (set(req_entry["extras"]) if req_entry else set()))

    if str(req.specifier):
        spec_str = str(req.specifier)
        origin = "inline_declaration"
    elif req_entry is not None and req_entry.get("version_specifier"):
        spec_str = str(req_entry["version_specifier"])
        origin = str(req_entry.get("origin", "requirements.txt"))
    else:
        spec_str = ""
        origin = "unconstrained"

    import_name = reg_imp or (req_entry["import_name"] if req_entry else None)
    return {
        "distribution_name": reg_dist,
        "import_name": import_name,
        "required": required,
        "version_specifier": spec_str,
        "has_version_specifier": bool(spec_str),
        "extras": extras,
        "markers": markers,
        "marker_active": marker_active,
        "origin": origin,
        "parse_error": None,
    }


def validate_single_dependency(
    dep_spec: str | dict[str, Any],
    *,
    required: bool = True,
    requirements_map: dict[str, dict[str, Any]] | None = None,
    requirements_path: str | Path | None = None,
    metadata_resolver: Callable[[str], str | None] | None = None,
    require_version_specifier: bool = True,
) -> dict[str, Any]:
    """Valida existência e compatibilidade real de versão de uma única dependência."""
    ts = utc_now_iso()
    req_map = requirements_map if requirements_map is not None else parse_requirements_file(requirements_path)
    resolver = metadata_resolver or _default_metadata_resolver

    decl = parse_dependency_declaration(dep_spec, required=required, requirements_map=req_map)
    dist_name = decl["distribution_name"]
    import_name = decl["import_name"]
    is_required = decl["required"]
    spec_str = decl["version_specifier"]
    has_spec = bool(decl["has_version_specifier"])
    base_meta = {
        "distribution_name": dist_name,
        "import_name": import_name,
        "required": is_required,
        "version_specifier": spec_str or None,
        "has_version_specifier": has_spec,
        "extras": decl["extras"],
        "markers": decl["markers"],
        "origin": decl["origin"],
        "validation_timestamp": ts,
    }

    if decl["parse_error"]:
        return {
            **base_meta,
            "installed_version": None,
            "status": "unknown",
            "reason": decl["parse_error"],
        }

    # Marcador de ambiente inativo -> not_applicable
    if not decl["marker_active"]:
        return {
            **base_meta,
            "installed_version": None,
            "status": "not_applicable",
            "reason": f"Dependência '{dist_name}' possui marcador de ambiente inativo ({decl['markers']}).",
        }

    # Valida sintaxe e coerência da restrição de versão antes de aceitar qualquer resultado
    spec_set: SpecifierSet | None = None
    if spec_str:
        try:
            spec_set = SpecifierSet(spec_str)
        except InvalidSpecifier as exc:
            return {
                **base_meta,
                "installed_version": None,
                "status": "unknown",
                "reason": f"Restrição de versão inválida '{spec_str}' para '{dist_name}': {exc}",
            }
        conflict = _detect_specifier_conflict(dist_name, spec_set)
        if conflict:
            return {
                **base_meta,
                "installed_version": None,
                "status": "unknown",
                "reason": conflict,
            }

    # Consulta metadados reais do ambiente
    try:
        installed_raw = resolver(dist_name)
    except importlib.metadata.PackageNotFoundError:
        return {
            **base_meta,
            "installed_version": None,
            "status": "missing",
            "reason": f"Distribuição '{dist_name}' não encontrada no ambiente Python.",
        }
    except Exception as exc:
        return {
            **base_meta,
            "installed_version": None,
            "status": "unknown",
            "reason": f"Falha ao consultar metadados de '{dist_name}': {exc}",
        }

    if installed_raw is None or not isinstance(installed_raw, str) or not installed_raw.strip():
        return {
            **base_meta,
            "installed_version": None,
            "status": "unknown",
            "reason": f"Distribuição '{dist_name}' instalada sem metadados de versão utilizáveis.",
        }

    try:
        installed_ver = Version(installed_raw.strip())
    except InvalidVersion as exc:
        return {
            **base_meta,
            "installed_version": installed_raw,
            "status": "unknown",
            "reason": f"Versão instalada '{installed_raw}' de '{dist_name}' não pôde ser interpretada (PEP 440): {exc}",
        }

    # Regra ACH-B6.2-002: ausência de restrição não pode ser confundida com compatibilidade validada
    if spec_set is None:
        if require_version_specifier:
            return {
                **base_meta,
                "installed_version": str(installed_ver),
                "status": "unknown",
                "reason": (
                    f"Distribuição '{dist_name}' (versão {installed_ver}) declarada sem restrição explícita "
                    "de versão; compatibilidade não comprovada (fail-closed)."
                ),
            }
        return {
            **base_meta,
            "installed_version": str(installed_ver),
            "status": "available",
            "reason": f"Versão instalada '{installed_ver}' verificada (restrição de faixa explicitamente dispensada).",
        }

    if not spec_set.contains(installed_ver, prereleases=True):
        return {
            **base_meta,
            "installed_version": str(installed_ver),
            "status": "incompatible",
            "reason": (
                f"Versão instalada '{installed_ver}' de '{dist_name}' é incompatível "
                f"com a restrição declarada '{spec_str}'."
            ),
        }

    return {
        **base_meta,
        "installed_version": str(installed_ver),
        "status": "available",
        "reason": f"Versão instalada '{installed_ver}' satisfaz restrição '{spec_str}'.",
    }


def validate_engine_dependencies(
    engine_id: str,
    declared_dependencies: list[str | dict[str, Any]],
    *,
    implementation_status: str,
    required_by_profile: bool,
    requested: bool,
    requirements_map: dict[str, dict[str, Any]] | None = None,
    requirements_path: str | Path | None = None,
    metadata_resolver: Callable[[str], str | None] | None = None,
) -> dict[str, Any]:
    """Valida todas as dependências declaradas de um único motor."""
    ts = utc_now_iso()
    req_map = requirements_map if requirements_map is not None else parse_requirements_file(requirements_path)

    if not declared_dependencies:
        dep_records = [
            {
                "distribution_name": None,
                "import_name": None,
                "required": required_by_profile or requested,
                "version_specifier": None,
                "has_version_specifier": False,
                "extras": [],
                "markers": [],
                "origin": "none",
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
    """Validação centralizada fail-closed do ambiente para todos os motores de um perfil."""
    ts = utc_now_iso()
    try:
        req_map = parse_requirements_file(requirements_path)
    except RequirementsParseError as exc:
        # Fail-closed: registra todas as dependências como unknown e bloqueia execução
        failed_engines: list[dict[str, Any]] = []
        for eng in engines_spec:
            eid = eng["engine_id"]
            impl_status = str(eng["implementation_status"])
            req_by_prof = bool(eng["required_by_profile"])
            requested = bool(eng["requested"])
            deps = list(eng.get("dependencies", []) or [])
            if not deps:
                dep_recs = [
                    {
                        "distribution_name": None,
                        "import_name": None,
                        "required": req_by_prof or requested,
                        "version_specifier": None,
                        "has_version_specifier": False,
                        "extras": [],
                        "markers": [],
                        "origin": "none",
                        "installed_version": None,
                        "status": "not_applicable",
                        "validation_timestamp": ts,
                        "reason": f"Motor '{eid}' não declara dependências externas.",
                    }
                ]
                satisfied = True
                eng_blocks: list[str] = []
            else:
                dep_recs = [
                    {
                        "distribution_name": str(d.get("distribution_name") if isinstance(d, dict) else d),
                        "import_name": None,
                        "required": req_by_prof or requested,
                        "version_specifier": None,
                        "has_version_specifier": False,
                        "extras": [],
                        "markers": [],
                        "origin": "requirements_error",
                        "installed_version": None,
                        "status": "unknown",
                        "validation_timestamp": ts,
                        "reason": str(exc),
                    }
                    for d in deps
                ]
                satisfied = False
                eng_blocks = [f"Motor '{eid}': validação impossibilitada por erro em requirements.txt ({exc})"]
            failed_engines.append(
                {
                    "engine_id": eid,
                    "implementation_status": impl_status,
                    "required_by_profile": req_by_prof,
                    "requested": requested,
                    "dependencies": dep_recs,
                    "all_dependencies_satisfied": satisfied,
                    "blocking_reasons": eng_blocks,
                }
            )
        return {
            "engines": failed_engines,
            "profile_dependencies": [],
            "environment_eligible": False,
            "requirements_error": str(exc),
            "blocking_reasons": [str(exc)],
            "optional_unmet_warnings": [],
        }

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
        "requirements_error": None,
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
