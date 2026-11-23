"""Carregador e validador base de perfis YAML e catálogo de motores (Core v8.0)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

DEFAULT_REFERENCES_DIR = Path(__file__).resolve().parents[2] / "references"
REQUIRED_PROFILE_KEYS = ("profile_id", "profile_version", "profile_status", "domain", "engines")


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


def load_profile(profile_path: str | Path, catalog_path: str | Path | None = None) -> dict[str, Any]:
    """Carrega um perfil YAML, valida campos mínimos e verifica se os motores existem no catálogo."""
    profile = load_yaml_file(profile_path)
    missing = [k for k in REQUIRED_PROFILE_KEYS if k not in profile]
    if missing:
        raise ValueError(f"Perfil YAML inválido ({profile_path}); campos ausentes: {missing}")

    engines_cfg = profile.get("engines", {})
    if not isinstance(engines_cfg, dict):
        raise ValueError("Campo 'engines' do perfil deve ser um objeto com 'required'/'optional'.")

    catalog = load_engine_catalog(catalog_path)
    unknown: list[str] = []
    for bucket in ("required", "optional"):
        for engine_id in engines_cfg.get(bucket, []) or []:
            if engine_id not in catalog:
                unknown.append(engine_id)
    if unknown:
        raise ValueError(f"Perfil '{profile['profile_id']}' referencia motores não catalogados: {unknown}")

    return profile
