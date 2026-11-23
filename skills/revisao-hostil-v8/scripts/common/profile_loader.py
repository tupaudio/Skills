"""Carregador e validador completo de perfis YAML multidisciplinares (Revisão Hostil v8.0-beta.6)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

DEFAULT_REFERENCES_DIR = Path(__file__).resolve().parents[2] / "references"
REQUIRED_PROFILE_KEYS = (
    "profile_id",
    "profile_version",
    "profile_status",
    "domain",
    "engines",
)
ALLOWED_PROFILE_STATUS = {"active", "draft", "deprecated"}
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[a-zA-Z0-9.]+)?$")


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
) -> dict[str, Any]:
    """Carrega um perfil YAML por caminho ou profile_id, valida estrutura, versão, status,
    motores (rejeitando motores obrigatórios ainda com status='planejado' — ACH-B6-002),
    vocabulário e checklists, retornando pacote pronto para execução e manifesto.
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
    missing = [k for k in REQUIRED_PROFILE_KEYS if k not in profile]
    if missing:
        raise ValueError(f"Perfil YAML inválido ({candidate}); campos ausentes: {missing}")

    version = str(profile["profile_version"])
    if not SEMVER_RE.match(version):
        raise ValueError(f"profile_version inválida em '{profile['profile_id']}': {version}")

    status = str(profile["profile_status"])
    if status not in ALLOWED_PROFILE_STATUS:
        raise ValueError(f"profile_status inválido em '{profile['profile_id']}': {status}")

    engines_cfg = profile.get("engines", {})
    if not isinstance(engines_cfg, dict):
        raise ValueError("Campo 'engines' do perfil deve ser um objeto com 'required'/'optional'.")

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

    # Carrega vocabulário canônico opcional
    loaded_vocabulary: dict[str, Any] | None = None
    vocab_cfg = profile.get("vocabulary") or {}
    if isinstance(vocab_cfg, dict) and vocab_cfg.get("canonical_file"):
        vpath = ref_dir / vocab_cfg["canonical_file"]
        loaded_vocabulary = load_yaml_file(vpath)

    # Carrega checklists opcionais
    loaded_checklists: list[dict[str, Any]] = []
    for chk_rel in profile.get("checklists", []) or []:
        cpath = ref_dir / chk_rel
        loaded_checklists.append(load_yaml_file(cpath))

    profile["_resolved"] = {
        "source_file": candidate.name,
        "engine_dependencies": engine_deps,
        "engine_versions": engine_versions,
        "optional_implemented": optional_implemented,
        "optional_planned": optional_planned,
        "loaded_vocabulary": loaded_vocabulary,
        "loaded_checklists": loaded_checklists,
        "manifest_entry": {profile["profile_id"]: version},
    }
    return profile
