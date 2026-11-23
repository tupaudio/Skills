"""Carregador e validador formal de perfis YAML multidisciplinares (Revisão Hostil v8.0-beta.6.1).

Correções incorporadas:
- ACH-B6-005: validação obrigatória contra JSON Schema executável (`references/schemas/schema_profile.json`)
  e validação real de calendário para `effective_date`;
- ACH-B6-006: validação estrita conforme especificação SemVer 2.0.0 (rejeita zeros à esquerda);
- ACH-B6-007: perfis `draft` e `deprecated` são bloqueados para execução normal por padrão
  (exigem `allow_non_active=True` explícito, registrado no manifesto);
- ACH-B6-008: verificação real de disponibilidade das dependências no ambiente Python via `importlib.metadata`.
"""

from __future__ import annotations

import importlib.metadata
import re
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from .schema_validator import validate_contract

DEFAULT_REFERENCES_DIR = Path(__file__).resolve().parents[2] / "references"
ALLOWED_PROFILE_STATUS = {"active", "draft", "deprecated"}

# Expressão regular oficial da especificação SemVer 2.0.0 (https://semver.org/)
SEMVER_2_0_0_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)

# Mapa de nomes de catálogo -> nomes de distribuição PyPI para importlib.metadata
_DIST_NAME_ALIASES: dict[str, str] = {
    "pyyaml": "PyYAML",
    "yaml": "PyYAML",
    "pillow": "Pillow",
    "pil": "Pillow",
    "docx": "python-docx",
}


def is_valid_semver(version: str) -> bool:
    """Valida estritamente conformidade com SemVer 2.0.0."""
    return isinstance(version, str) and bool(SEMVER_2_0_0_RE.match(version))


def verify_environment_dependencies(engine_deps: dict[str, list[str]]) -> dict[str, dict[str, Any]]:
    """Verifica disponibilidade real no ambiente Python das dependências declaradas (ACH-B6-008)."""
    all_deps = sorted({dep for deps in engine_deps.values() for dep in deps})
    if not all_deps:
        return {"_summary": {"status": "nao_aplicavel", "all_available": True}}

    report: dict[str, dict[str, Any]] = {}
    all_ok = True
    for raw_dep in all_deps:
        dist_name = _DIST_NAME_ALIASES.get(raw_dep.lower(), raw_dep)
        try:
            ver = importlib.metadata.version(dist_name)
            report[raw_dep] = {"distribution": dist_name, "status": "disponivel", "installed_version": ver}
        except importlib.metadata.PackageNotFoundError:
            all_ok = False
            report[raw_dep] = {"distribution": dist_name, "status": "ausente", "installed_version": None}
    report["_summary"] = {"status": "disponivel" if all_ok else "ausente", "all_available": all_ok}
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
    require_implemented: bool = True,
    allow_non_active: bool = False,
) -> dict[str, Any]:
    """Carrega e valida formalmente um perfil YAML contra `schema_profile.json`.

    - Valida estrutura, enums, tipos e SemVer 2.0.0 via `schema_profile.json` (ACH-B6-005 / ACH-B6-006);
    - Valida data real de calendário em `effective_date`;
    - Bloqueia perfis `draft`/`deprecated` para execução normal salvo `allow_non_active=True` (ACH-B6-007);
    - Rejeita motores obrigatórios com `status='planejado'` quando `require_implemented=True` (ACH-B6-002);
    - Verifica disponibilidade real das dependências no ambiente Python (ACH-B6-008).
    """
    ref_dir = Path(references_dir) if references_dir else DEFAULT_REFERENCES_DIR
    candidate = Path(profile_ref)
    if not candidate.exists():
        by_id = ref_dir / "profiles" / f"{profile_ref}.yaml"
        if by_id.exists():
            candidate = by_id
        else:
            raise FileNotFoundError(f"Perfil YAML não encontrado: {profile_ref}")

    profile = load_yaml_file(candidate)

    # 1. Validação executável contra schema_profile.json (ACH-B6-005)
    validate_contract(profile, "schema_profile.json")

    # 2. Validação explícita SemVer 2.0.0 (ACH-B6-006) e data real de calendário
    version = str(profile["profile_version"])
    if not is_valid_semver(version):
        raise ValueError(f"profile_version não conforme com SemVer 2.0.0 em '{profile['profile_id']}': {version}")
    try:
        date.fromisoformat(str(profile["effective_date"]))
    except ValueError as exc:
        raise ValueError(f"effective_date inválida em '{profile['profile_id']}': {profile['effective_date']}") from exc

    # 3. Elegibilidade de execução por status (ACH-B6-007)
    status = str(profile["profile_status"])
    if status != "active" and not allow_non_active:
        raise ValueError(
            f"Perfil '{profile['profile_id']}' possui status '{status}' e não é elegível para execução normal "
            "(use allow_non_active=True explicitamente para desenvolvimento ou consulta histórica)."
        )

    # 4. Validação de motores contra catálogo (ACH-B6-002)
    engines_cfg = profile["engines"]
    catalog = load_engine_catalog(catalog_path)
    unknown: list[str] = []
    planned_required: list[str] = []
    optional_implemented: list[str] = []
    optional_planned: list[str] = []
    engine_deps: dict[str, list[str]] = {}
    engine_versions: dict[str, str] = {}

    for engine_id in engines_cfg.get("required", []) or []:
        if engine_id not in catalog:
            unknown.append(engine_id)
            continue
        meta = catalog[engine_id]
        if require_implemented and str(meta.get("status", "")).lower() == "planejado":
            planned_required.append(engine_id)
        engine_deps[engine_id] = list(meta.get("dependencias", []) or [])
        engine_versions[engine_id] = str(meta.get("versao", "unknown"))

    for engine_id in engines_cfg.get("optional", []) or []:
        if engine_id not in catalog:
            unknown.append(engine_id)
            continue
        meta = catalog[engine_id]
        if str(meta.get("status", "")).lower() == "planejado":
            optional_planned.append(engine_id)
        else:
            optional_implemented.append(engine_id)
        engine_deps[engine_id] = list(meta.get("dependencias", []) or [])
        engine_versions[engine_id] = str(meta.get("versao", "unknown"))

    if unknown:
        raise ValueError(f"Perfil '{profile['profile_id']}' referencia motores não catalogados: {unknown}")
    if planned_required:
        raise ValueError(
            f"Perfil '{profile['profile_id']}' exige motores ainda não implementados (status='planejado'): {planned_required}"
        )

    # 5. Verificação real das dependências no ambiente (ACH-B6-008)
    verified_deps = verify_environment_dependencies(engine_deps)

    # 6. Carrega vocabulário canônico e checklists opcionais
    loaded_vocabulary: dict[str, Any] | None = None
    vocab_cfg = profile.get("vocabulary") or {}
    if isinstance(vocab_cfg, dict) and vocab_cfg.get("canonical_file"):
        loaded_vocabulary = load_yaml_file(ref_dir / vocab_cfg["canonical_file"])

    loaded_checklists: list[dict[str, Any]] = []
    for chk_rel in profile.get("checklists", []) or []:
        loaded_checklists.append(load_yaml_file(ref_dir / chk_rel))

    profile["_resolved"] = {
        "source_file": candidate.name,
        "execution_eligible": status == "active",
        "non_active_override": status != "active" and allow_non_active,
        "engine_dependencies": engine_deps,
        "verified_dependencies": verified_deps,
        "engine_versions": engine_versions,
        "optional_implemented": optional_implemented,
        "optional_planned": optional_planned,
        "loaded_vocabulary": loaded_vocabulary,
        "loaded_checklists": loaded_checklists,
        "manifest_entry": {
            profile["profile_id"]: {
                "version": version,
                "status": status,
                "non_active_override": status != "active" and allow_non_active,
                "dependencies_available": verified_deps["_summary"]["all_available"],
            }
        },
    }
    return profile
