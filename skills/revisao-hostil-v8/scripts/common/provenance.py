"""Proveniência, hashes SHA-256 e gerador oficial de run_manifest.json (Core v8.0 / ACH-013 + ACH-014)."""

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


def _inspect_git_dirty_state(
    cwd: Path | None = None,
    excluded_dirty_paths: list[str] | None = None,
) -> dict[str, Any]:
    """Inspeciona o estado real do Git sem falsificar git_dirty (ACH-014).

    Distingue:
    - git_dirty_raw: estado real completo da árvore Git (nunca forçado para False);
    - git_dirty_code: se há alterações fora dos artefatos de relatório explicitamente excluídos;
    - dirty_files_all / dirty_files_code / dirty_files_excluded: listas rastreáveis.
    """
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=3,
        )
        if proc.returncode != 0:
            return {
                "in_git_repo": False,
                "git_dirty_raw": None,
                "git_dirty_code": None,
                "dirty_files_all": [],
                "dirty_files_code": [],
                "dirty_files_excluded": [],
                "dirty_exclusion_policy": None,
            }
    except Exception:
        return {
            "in_git_repo": False,
            "git_dirty_raw": None,
            "git_dirty_code": None,
            "dirty_files_all": [],
            "dirty_files_code": [],
            "dirty_files_excluded": [],
            "dirty_exclusion_policy": None,
        }

    dirty_all: list[str] = []
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        # Formato porcelain: XY <path> (ou XY <old> -> <new>)
        path_part = line[3:].strip()
        if " -> " in path_part:
            path_part = path_part.split(" -> ", 1)[1].strip()
        path_part = path_part.strip('"').replace("\\", "/")
        dirty_all.append(path_part)

    excl_norm = [p.replace("\\", "/").strip("/") for p in (excluded_dirty_paths or [])]

    def _is_excluded(rel: str) -> bool:
        return any(rel == e or rel.endswith("/" + e) for e in excl_norm)

    dirty_excluded = [p for p in dirty_all if _is_excluded(p)]
    dirty_code = [p for p in dirty_all if not _is_excluded(p)]

    return {
        "in_git_repo": True,
        "git_dirty_raw": len(dirty_all) > 0,
        "git_dirty_code": len(dirty_code) > 0,
        "dirty_files_all": dirty_all,
        "dirty_files_code": dirty_code,
        "dirty_files_excluded": dirty_excluded,
        "dirty_exclusion_policy": (
            "Arquivos de relatório gerados na própria execução de auditoria são listados em "
            "dirty_files_excluded e excluídos apenas de git_dirty_code; git_dirty_raw reflete "
            "sempre o estado real não filtrado da árvore Git."
            if excl_norm
            else "Nenhuma exclusão aplicada; git_dirty_code == git_dirty_raw."
        ),
    }


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
    self_excluded_files: list[str] | None = None,
    excluded_dirty_paths: list[str] | None = None,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """Cria o manifesto determinístico de execução (run_manifest.json) com caminhos relativos e proveniência Git rigorosa."""
    root_path = (Path(repo_root) if repo_root else Path(__file__).resolve().parents[2]).resolve()
    file_records: list[dict[str, Any]] = []
    for item in inspected_files:
        p = Path(item)
        if p.exists() and p.is_file():
            resolved = p.resolve()
            try:
                rel_path = resolved.relative_to(root_path).as_posix()
            except ValueError:
                rel_path = p.name
            file_records.append(
                {
                    "relative_path": rel_path,
                    "name": p.name,
                    "bytes": p.stat().st_size,
                    "sha256": sha256_file(p),
                }
            )
        else:
            file_records.append(
                {
                    "relative_path": p.as_posix(),
                    "name": p.name,
                    "bytes": None,
                    "sha256": None,
                    "missing": True,
                }
            )

    deps = _installed_packages(
        (
            "numpy",
            "scipy",
            "sympy",
            "python-docx",
            "pypdf",
            "Pillow",
            "PyYAML",
            "jsonschema",
            "referencing",
            "pytest",
            "pytest-cov",
            "coverage",
        )
    )

    git_commit = _detect_git_commit(root_path)
    git_state = _inspect_git_dirty_state(root_path, excluded_dirty_paths=excluded_dirty_paths)

    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "timestamp_utc": utc_now_iso(),
        "skill_version": skill_version,
        "engine_versions": dict(engine_versions or {}),
        "profile_versions": dict(profile_versions or {}),
        "git_commit": git_commit,
        "audited_code_commit": git_commit,
        "artifact_commit_note": (
            "O commit que publica os artefatos de relatório (pytest_verbose.txt, smoke_tests.txt, "
            "run_manifest.json e SHA256SUMS) é criado após esta geração tendo audited_code_commit como pai direto."
        ),
        "git_dirty": git_state["git_dirty_raw"],
        "git_state": git_state,
        "environment": {
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "dependencies": deps,
        },
        "config": dict(config) if config is not None else {"status": "no_custom_config_used"},
        "seeds": dict(seeds) if seeds is not None else {"status": "no_stochastic_seed_used"},
        "self_excluded_files": list(self_excluded_files or []),
        "inspected_files": file_records,
        "limitations": list(limitations or []),
    }


def save_run_manifest(manifest: dict[str, Any], out_path: str | Path) -> Path:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    return p
