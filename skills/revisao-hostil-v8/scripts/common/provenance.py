"""Proveniência, hashes SHA-256 e gerador oficial de run_manifest.json (Core v8.0 / ACH-013, ACH-014, ACH-B6.1-005)."""

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
from .dependencies import ALLOWED_DEPENDENCY_STATUSES
from .evidence import utc_now_iso

MANIFEST_GENERATOR_VERSION = "8.0.0-beta.6.2"


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
    """Inspeciona o estado real do Git sem falsificar git_dirty (ACH-014)."""
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


def validate_run_manifest(manifest: dict[str, Any]) -> None:
    """Valida explicitamente o contrato estrutural do run_manifest.json (ACH-B6.1-005).

    Levanta ValueError se faltar qualquer campo obrigatório de proveniência ou rastreabilidade.
    """
    required_top = (
        "schema_version",
        "run_id",
        "timestamp_utc",
        "skill_version",
        "manifest_generator_version",
        "schema_validator_version",
        "audited_code_commit",
        "git_state",
        "environment",
        "test_tools",
        "profiles",
        "global_eligibility",
        "authorized_exceptions",
        "inspected_files",
        "report_references",
        "integrity",
    )
    missing_top = [k for k in required_top if k not in manifest]
    if missing_top:
        raise ValueError(f"run_manifest.json inválido: campos obrigatórios ausentes: {missing_top}")

    env = manifest["environment"]
    if not isinstance(env, dict) or not env.get("python_version") or not env.get("platform"):
        raise ValueError("run_manifest.json inválido: environment deve conter python_version e platform.")

    profiles = manifest["profiles"]
    if not isinstance(profiles, list):
        raise ValueError("run_manifest.json inválido: profiles deve ser uma lista.")

    for prof in profiles:
        for req_p in (
            "profile_id",
            "profile_version",
            "profile_status",
            "execution_eligible",
            "schema_validation",
            "semver_validation",
            "engines",
        ):
            if req_p not in prof:
                raise ValueError(
                    f"run_manifest.json inválido: perfil '{prof.get('profile_id')}' sem campo obrigatório '{req_p}'."
                )
        for eng in prof["engines"]:
            for req_e in ("engine_id", "implementation_status", "requested", "dependencies"):
                if req_e not in eng:
                    raise ValueError(
                        f"run_manifest.json inválido: motor '{eng.get('engine_id')}' no perfil "
                        f"'{prof['profile_id']}' sem campo obrigatório '{req_e}'."
                    )
            for dep in eng["dependencies"]:
                for req_d in (
                    "distribution_name",
                    "required",
                    "version_specifier",
                    "installed_version",
                    "status",
                    "reason",
                ):
                    if req_d not in dep:
                        raise ValueError(
                            f"run_manifest.json inválido: dependência em '{prof['profile_id']}/{eng['engine_id']}' "
                            f"sem campo obrigatório '{req_d}'."
                        )
                if dep["status"] not in ALLOWED_DEPENDENCY_STATUSES:
                    raise ValueError(
                        f"run_manifest.json inválido: status de dependência inválido '{dep['status']}' "
                        f"em '{prof['profile_id']}/{eng['engine_id']}'."
                    )


def build_run_manifest(
    run_id: str,
    inspected_files: list[str | Path],
    *,
    skill_version: str = CORE_VERSION,
    engine_versions: dict[str, str] | None = None,
    profile_versions: dict[str, str] | None = None,
    profile_audit_records: list[dict[str, Any]] | None = None,
    authorized_exceptions: list[dict[str, Any]] | None = None,
    report_references: dict[str, str] | None = None,
    integrity_info: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    seeds: dict[str, int] | None = None,
    limitations: list[str] | None = None,
    self_excluded_files: list[str] | None = None,
    excluded_dirty_paths: list[str] | None = None,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """Cria o manifesto determinístico de execução (run_manifest.json) com proveniência completa."""
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
            "packaging",
            "pytest",
            "pytest-cov",
            "coverage",
        )
    )
    test_tools = {
        "pytest": deps["pytest"],
        "pytest-cov": deps["pytest-cov"],
        "coverage": deps["coverage"],
        "packaging": deps["packaging"],
    }

    git_commit = _detect_git_commit(root_path)
    git_state = _inspect_git_dirty_state(root_path, excluded_dirty_paths=excluded_dirty_paths)

    profiles_list = list(profile_audit_records or [])
    eligible_ids = [p["profile_id"] for p in profiles_list if p.get("execution_eligible") is True]
    ineligible_ids = [p["profile_id"] for p in profiles_list if p.get("execution_eligible") is not True]
    global_eligibility = {
        "evaluated_profiles": len(profiles_list),
        "eligible_count": len(eligible_ids),
        "ineligible_count": len(ineligible_ids),
        "all_profiles_eligible": len(profiles_list) > 0 and len(ineligible_ids) == 0,
        "eligible_profiles": eligible_ids,
        "ineligible_profiles": ineligible_ids,
    }

    integrity = dict(
        integrity_info
        or {
            "hash_algorithm": "SHA-256",
            "self_excluded_files": list(self_excluded_files or []),
            "inspected_file_count": len(file_records),
        }
    )

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "timestamp_utc": utc_now_iso(),
        "skill_version": skill_version,
        "manifest_generator_version": MANIFEST_GENERATOR_VERSION,
        "schema_validator_version": deps["jsonschema"],
        "engine_versions": dict(engine_versions or {}),
        "profile_versions": dict(profile_versions or {}),
        "profiles": profiles_list,
        "global_eligibility": global_eligibility,
        "authorized_exceptions": list(authorized_exceptions or []),
        "git_commit": git_commit,
        "audited_code_commit": git_commit,
        "artifact_commit_note": (
            "O commit que publica os artefatos de relatório (pytest_verbose.txt, coverage_report.txt, "
            "smoke_tests.txt, run_manifest.json, homologacao_v8.0-beta.6.2.md e SHA256SUMS) é criado "
            "após esta geração tendo audited_code_commit como pai direto."
        ),
        "git_dirty": git_state["git_dirty_raw"],
        "git_state": git_state,
        "environment": {
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "dependencies": deps,
        },
        "test_tools": test_tools,
        "config": dict(config) if config is not None else {"status": "no_custom_config_used"},
        "seeds": dict(seeds) if seeds is not None else {"status": "no_stochastic_seed_used"},
        "self_excluded_files": list(self_excluded_files or []),
        "report_references": dict(report_references or {}),
        "integrity": integrity,
        "inspected_files": file_records,
        "limitations": list(limitations or []),
    }
    validate_run_manifest(manifest)
    return manifest


def save_run_manifest(manifest: dict[str, Any], out_path: str | Path) -> Path:
    validate_run_manifest(manifest)
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    return p
