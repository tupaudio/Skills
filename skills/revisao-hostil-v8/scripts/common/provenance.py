"""Proveniência, hashes SHA-256 e gerador oficial de run_manifest.json (Core v8.0)."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

from . import CORE_VERSION, SCHEMA_VERSION
from .evidence import utc_now_iso


def sha256_file(path: str | Path) -> str:
    p = Path(path)
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _detect_git_commit(cwd: Path | None = None) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=3,
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except Exception:
        pass
    return None


def _installed_packages(names: tuple[str, ...]) -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for pkg in names:
        try:
            versions[pkg] = importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError:
            versions[pkg] = None
    return versions


def build_run_manifest(
    run_id: str,
    inspected_files: list[str | Path],
    *,
    skill_version: str = CORE_VERSION,
    engine_versions: dict[str, str] | None = None,
    profile_versions: dict[str, str] | None = None,
    config: dict[str, Any] | None = None,
    seeds: dict[str, int] | None = None,
    limitations: list[str] | None = None,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """Cria o manifesto determinístico de execução (run_manifest.json)."""
    file_records: list[dict[str, Any]] = []
    for item in inspected_files:
        p = Path(item)
        if p.exists() and p.is_file():
            file_records.append(
                {
                    "path": str(p.resolve()),
                    "name": p.name,
                    "bytes": p.stat().st_size,
                    "sha256": sha256_file(p),
                }
            )
        else:
            file_records.append(
                {
                    "path": str(p),
                    "name": p.name,
                    "bytes": None,
                    "sha256": None,
                    "missing": True,
                }
            )

    root_path = Path(repo_root) if repo_root else Path(__file__).resolve().parents[2]
    deps = _installed_packages(
        ("numpy", "scipy", "sympy", "python-docx", "pypdf", "PyYAML", "jsonschema", "pytest")
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "timestamp_utc": utc_now_iso(),
        "skill_version": skill_version,
        "engine_versions": dict(engine_versions or {}),
        "profile_versions": dict(profile_versions or {}),
        "git_commit": _detect_git_commit(root_path),
        "environment": {
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "dependencies": deps,
        },
        "config": dict(config or {}),
        "seeds": dict(seeds or {}),
        "inspected_files": file_records,
        "limitations": list(limitations or []),
    }


def save_run_manifest(manifest: dict[str, Any], out_path: str | Path) -> Path:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return p
