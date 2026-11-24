"""Proveniência, hashes SHA-256, gerador oficial de run_manifest.json e validação de consistência.

Cobertura de requisitos:
- ACH-013 / ACH-014: caminhos relativos, autoexclusão e separação git_dirty_raw vs git_dirty_code;
- ACH-B6.1-005: rastreabilidade perfil -> motor -> dependência -> versão -> estado;
- ACH-B6.2-001: fonte única de verdade por execução (`run_id`), captura ambiental direta do processo,
  inventário `artifacts` com SHA-256 real e validação obrigatória `validate_run_consistency()`.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import CORE_VERSION, SCHEMA_VERSION
from .dependencies import ALLOWED_DEPENDENCY_STATUSES
from .evidence import utc_now_iso

MANIFEST_GENERATOR_VERSION = "8.0.0-beta.6.5"
_SHA256_HEX_RE = re.compile(r"\A[a-f0-9]{64}\Z")
_RUN_ID_HEADER_RE = re.compile(r"^(?:#\s*run_id=|RUN_ID=)([^\s`]+)\s*$", re.MULTILINE)

CHECKSUM_EXCLUDED_DIRS = frozenset(
    {"__pycache__", ".pytest_cache", ".git", ".venv", "venv", ".mypy_cache", ".ruff_cache", "tmp", ".tmp"}
)
CHECKSUM_EXCLUDED_FILES = frozenset({"SHA256SUMS", ".coverage", ".DS_Store"})
CHECKSUM_EXCLUDED_SUFFIXES = frozenset({".pyc", ".pyo", ".tmp"})


class ConsistencyValidationError(ValueError):
    """Erro levantado quando há divergência entre manifesto, ambiente, relatórios ou checksums."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = list(errors)
        super().__init__("Falha na validação de consistência da execução: " + "; ".join(self.errors))


def generate_run_id(prefix: str = "BETA6.3") -> str:
    """Gera identificador único por execução (fonte única de verdade para todos os artefatos)."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}-{stamp}-{uuid.uuid4().hex[:8]}"


def sha256_file(path: str | Path) -> str:
    p = Path(path)
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _run_git(args: list[str], cwd: Path | None = None) -> str | None:
    try:
        proc = subprocess.run(
            ["git", *args],
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


def _detect_git_commit(cwd: Path | None = None) -> str | None:
    return _run_git(["rev-parse", "HEAD"], cwd=cwd)


def _detect_git_branch(cwd: Path | None = None) -> str | None:
    return _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)


def _detect_base_tag(cwd: Path | None = None) -> str | None:
    return _run_git(["describe", "--tags", "--abbrev=0"], cwd=cwd)


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


def capture_runtime_environment(repo_root: str | Path | None = None) -> dict[str, Any]:
    """Captura o ambiente real UMA ÚNICA VEZ diretamente do processo em execução (ACH-B6.2-001)."""
    root_path = (Path(repo_root) if repo_root else Path(__file__).resolve().parents[2]).resolve()
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
    return {
        "python_version": sys.version.split()[0],
        "python_implementation": platform.python_implementation(),
        "os_name": platform.system(),
        "os_release": platform.release(),
        "os_build": platform.version(),
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "virtual_env": os.environ.get("VIRTUAL_ENV") or sys.prefix,
        "executable": sys.executable,
        "git_branch": _detect_git_branch(root_path),
        "base_tag": _detect_base_tag(root_path),
        "dependencies": deps,
        "test_tools": {
            "pytest": deps["pytest"],
            "pytest-cov": deps["pytest-cov"],
            "coverage": deps["coverage"],
            "packaging": deps["packaging"],
        },
    }


def build_artifact_record(
    path: str | Path,
    repo_root: str | Path,
    *,
    run_id: str,
    artifact_type: str,
    generation_status: str = "generated",
    verification_status: str = "verified",
) -> dict[str, Any]:
    """Constrói registro de proveniência de um artefato finalizado (SHA-256 real dos bytes)."""
    p = Path(path).resolve()
    root = Path(repo_root).resolve()
    try:
        rel = p.relative_to(root).as_posix()
    except ValueError:
        rel = p.name
    if not p.exists() or not p.is_file():
        return {
            "relative_path": rel,
            "name": p.name,
            "bytes": None,
            "sha256": None,
            "run_id": run_id,
            "type": artifact_type,
            "generation_status": "missing",
            "verification_status": "failed",
        }
    return {
        "relative_path": rel,
        "name": p.name,
        "bytes": p.stat().st_size,
        "sha256": sha256_file(p),
        "run_id": run_id,
        "type": artifact_type,
        "generation_status": generation_status,
        "verification_status": verification_status,
    }


def validate_run_manifest(manifest: dict[str, Any]) -> None:
    """Valida explicitamente o contrato estrutural do run_manifest.json (ACH-B6.1-005 / ACH-B6.2-001)."""
    required_top = (
        "schema_version",
        "run_id",
        "timestamp_utc",
        "timestamp_start_utc",
        "timestamp_end_utc",
        "durations",
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
        "artifacts",
        "inspected_files",
        "report_references",
        "integrity",
    )
    missing_top = [k for k in required_top if k not in manifest]
    if missing_top:
        raise ValueError(f"run_manifest.json inválido: campos obrigatórios ausentes: {missing_top}")

    env = manifest["environment"]
    for req_env in ("python_version", "platform", "os_name", "os_build", "architecture"):
        if not isinstance(env, dict) or not env.get(req_env):
            raise ValueError(f"run_manifest.json inválido: environment sem campo obrigatório '{req_env}'.")

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


def validate_artifact_run_id(
    artifact_path: str | Path,
    expected_run_id: str,
    *,
    encoding: str = "utf-8",
) -> dict[str, Any]:
    """Valida a presença inequívoca e não-conflitante de `expected_run_id` no conteúdo de um artefato (ACH-B6.3-001)."""
    p = Path(artifact_path)
    if not p.exists() or not p.is_file():
        raise ConsistencyValidationError([f"Artefato obrigatório ausente ou não é arquivo regular: {p}."])
    try:
        content = p.read_text(encoding=encoding)
    except UnicodeDecodeError as exc:
        raise ConsistencyValidationError([f"Artefato '{p}' ilegível em {encoding}: {exc}"]) from exc

    found_headers = _RUN_ID_HEADER_RE.findall(content)
    distinct_headers = sorted(set(found_headers))
    errors: list[str] = []

    if expected_run_id not in content:
        errors.append(
            f"Conteúdo do artefato '{p.name}' não contém o run_id da execução ({expected_run_id!r})."
        )
    if len(distinct_headers) > 1:
        errors.append(
            f"Artefato '{p.name}' contém múltiplos run_id conflitantes: {distinct_headers}."
        )
    for hid in distinct_headers:
        if hid != expected_run_id:
            errors.append(
                f"Cabeçalho run_id divergente em '{p.name}': encontrado={hid!r} != esperado={expected_run_id!r}."
            )

    if errors:
        raise ConsistencyValidationError(errors)

    return {
        "valid": True,
        "artifact_path": str(p),
        "expected_run_id": expected_run_id,
        "found_run_ids": distinct_headers or [expected_run_id],
        "bytes": p.stat().st_size,
        "sha256": sha256_file(p),
    }


def _is_path_excluded_from_checksum(rel_path: Path) -> tuple[bool, str | None]:
    """Avalia a política explícita de exclusão para o inventário de checksums."""
    for part in rel_path.parts[:-1]:
        if part in CHECKSUM_EXCLUDED_DIRS:
            return True, f"diretório excluído ({part})"
    if rel_path.name in CHECKSUM_EXCLUDED_FILES:
        return True, f"arquivo excluído pela política ({rel_path.name})"
    if rel_path.suffix.lower() in CHECKSUM_EXCLUDED_SUFFIXES:
        return True, f"extensão temporária/cache excluída ({rel_path.suffix})"
    return False, None


def build_expected_checksum_inventory(
    manifest: dict[str, Any],
    root_dir: str | Path,
) -> dict[str, Any]:
    """Constrói o inventário esperado de arquivos para SHA256SUMS de forma independente (ACH-B6.3-002).

    Combina a varredura controlada de `root_dir` (respeitando exclusões explícitas e bloqueando
    symlinks fora da raiz) com os artefatos e arquivos autoexcluídos do manifesto (`run_manifest.json`).
    """
    root = Path(root_dir).resolve()
    expected: set[str] = set()
    excluded: list[dict[str, str]] = []

    if root.exists():
        for item in sorted(root.rglob("*")):
            rel = item.relative_to(root)
            is_excl, reason = _is_path_excluded_from_checksum(rel)
            if is_excl:
                if item.is_file() or item.is_symlink():
                    excluded.append({"relative_path": rel.as_posix(), "reason": str(reason)})
                continue
            if item.is_symlink():
                try:
                    item.resolve().relative_to(root)
                except ValueError:
                    excluded.append({"relative_path": rel.as_posix(), "reason": "symlink fora da raiz bloqueado"})
                    continue
            if item.is_file():
                expected.add(rel.as_posix())

    for excl in manifest.get("self_excluded_files") or []:
        excl_norm = str(excl).replace("\\", "/")
        if excl_norm and excl_norm != "SHA256SUMS":
            expected.add(excl_norm)

    for art in manifest.get("artifacts") or []:
        rel_art = str(art.get("relative_path", "")).replace("\\", "/")
        if rel_art and rel_art != "SHA256SUMS":
            expected.add(rel_art)

    expected.discard("SHA256SUMS")
    return {
        "expected_files": sorted(expected),
        "excluded_files": excluded,
        "exclusion_policy": {
            "excluded_dirs": sorted(CHECKSUM_EXCLUDED_DIRS),
            "excluded_files": sorted(CHECKSUM_EXCLUDED_FILES),
            "excluded_suffixes": sorted(CHECKSUM_EXCLUDED_SUFFIXES),
        },
    }


def validate_run_consistency(
    manifest: dict[str, Any],
    *,
    root_dir: str | Path | None = None,
    sha256sums_path: str | Path | None = None,
    expected_commit: str | None = None,
    report_text: str | None = None,
    required_artifact_names: tuple[str, ...] = (),
    expected_sha256_paths: set[str] | list[str] | None = None,
    max_duration_drift_s: float = 0.05,
) -> dict[str, Any]:
    """Verifica coerência integral entre manifesto, ambiente, testes, relatórios e SHA-256 (ACH-B6.2-001).

    Levanta `ConsistencyValidationError` diante de qualquer divergência.
    """
    errors: list[str] = []
    try:
        validate_run_manifest(manifest)
    except ValueError as exc:
        raise ConsistencyValidationError([str(exc)]) from exc

    run_id = manifest["run_id"]
    env = manifest["environment"]
    durations = manifest.get("durations") or {}
    test_res = manifest.get("test_results")

    # 1. Commit auditado
    if expected_commit is not None and manifest.get("audited_code_commit") != expected_commit:
        errors.append(
            f"Commit auditado divergente: manifesto={manifest.get('audited_code_commit')!r} "
            f"!= esperado={expected_commit!r}."
        )
    if manifest.get("git_commit") != manifest.get("audited_code_commit"):
        errors.append("Divergência interna entre git_commit e audited_code_commit.")

    # 2. Consistência entre ambiente do manifesto e resultados programáticos do pytest
    if isinstance(test_res, dict) and test_res:
        if test_res.get("run_id") and test_res["run_id"] != run_id:
            errors.append(
                f"Divergência de run_id entre manifesto ({run_id!r}) e pytest ({test_res.get('run_id')!r})."
            )
        if test_res.get("python_version") != env.get("python_version"):
            errors.append(
                f"Divergência de Python: manifesto={env.get('python_version')!r} "
                f"!= pytest={test_res.get('python_version')!r}."
            )
        if test_res.get("os_name") != env.get("os_name"):
            errors.append(
                f"Divergência de SO: manifesto={env.get('os_name')!r} != pytest={test_res.get('os_name')!r}."
            )
        if test_res.get("os_build") != env.get("os_build"):
            errors.append(
                f"Divergência de build do SO: manifesto={env.get('os_build')!r} "
                f"!= pytest={test_res.get('os_build')!r}."
            )

        # Código de saída vs resultado geral
        exit_code = test_res.get("exit_code")
        overall = manifest.get("overall_result")
        failed = int(test_res.get("failed", 0))
        coll_err = int(test_res.get("collection_errors", 0))
        if overall == "PASSED" and (exit_code != 0 or failed > 0 or coll_err > 0):
            errors.append(
                f"Status 'PASSED' incompatível com exit_code={exit_code}, failed={failed}, collection_errors={coll_err}."
            )
        if exit_code == 0 and (failed > 0 or coll_err > 0):
            errors.append(f"exit_code=0 incompatível com failed={failed} ou collection_errors={coll_err}.")

        # Consistência de duração
        t_pytest = test_res.get("duration_seconds")
        t_suite = durations.get("test_suite_seconds")
        t_total = durations.get("total_seconds")
        if t_pytest is not None and t_suite is not None:
            if abs(float(t_pytest) - float(t_suite)) > max_duration_drift_s:
                errors.append(
                    f"Divergência de duração da suíte: pytest={t_pytest}s vs durations={t_suite}s."
                )
        if t_total is not None and t_suite is not None and float(t_total) + 1e-6 < float(t_suite):
            errors.append(
                f"Duração total ({t_total}s) menor que duração da suíte de testes ({t_suite}s)."
            )

    # 3. Coerência com texto do relatório de homologação (quando fornecido)
    if report_text is not None:
        if run_id not in report_text:
            errors.append(f"Relatório de homologação não contém o run_id da execução ({run_id!r}).")
        if str(env["python_version"]) not in report_text:
            errors.append(f"Relatório de homologação não contém a versão Python ({env['python_version']!r}).")
        if str(env["os_build"]) not in report_text:
            errors.append(f"Relatório de homologação não contém o build do SO ({env['os_build']!r}).")
        if isinstance(test_res, dict) and test_res:
            passed_str = f"{test_res['passed']} passed"
            if passed_str not in report_text:
                errors.append(f"Relatório de homologação diverge na contagem de testes (esperado {passed_str!r}).")
            warn_str = f"Warnings: `{test_res['warnings']}`"
            if warn_str not in report_text:
                errors.append(f"Relatório de homologação diverge na contagem de warnings (esperado {warn_str!r}).")

    # 4. Artefatos: run_id idêntico no registro E dentro do conteúdo real (ACH-B6.3-001) + SHA-256 em disco
    artifacts = manifest.get("artifacts") or []
    present_names: set[str] = set()
    root = Path(root_dir).resolve() if root_dir else None
    for art in artifacts:
        present_names.add(str(art.get("name", "")))
        if art.get("run_id") != run_id:
            errors.append(
                f"Artefato '{art.get('relative_path')}' possui run_id={art.get('run_id')!r} != {run_id!r}."
            )
        if root is not None:
            art_path = root / str(art["relative_path"])
            if not art_path.exists() or not art_path.is_file():
                errors.append(f"Artefato ausente em disco: {art['relative_path']}.")
            else:
                actual_bytes = art_path.stat().st_size
                actual_hash = sha256_file(art_path)
                if art.get("bytes") != actual_bytes:
                    errors.append(
                        f"Tamanho divergente em '{art['relative_path']}': "
                        f"manifesto={art.get('bytes')} != disco={actual_bytes}."
                    )
                if art.get("sha256") != actual_hash:
                    errors.append(
                        f"Hash SHA-256 divergente em '{art['relative_path']}': "
                        f"manifesto={art.get('sha256')} != disco={actual_hash}."
                    )
                # ACH-B6.3-001: verifica presença efetiva e não-conflitante do run_id no conteúdo do artefato
                try:
                    validate_artifact_run_id(art_path, run_id)
                except ConsistencyValidationError as exc:
                    errors.extend(exc.errors)

    for req_name in required_artifact_names:
        if req_name not in present_names:
            errors.append(f"Artefato obrigatório ausente no manifesto: {req_name}.")

    # 5. Verificação integral, segurança de caminhos e completude de SHA256SUMS (ACH-B6.3-002)
    sha_checked = 0
    sha_failed = 0
    expected_count = 0
    if sha256sums_path is not None and root is not None:
        sf = Path(sha256sums_path)
        if not sf.exists():
            errors.append(f"Arquivo SHA256SUMS ausente: {sf}.")
        else:
            if expected_sha256_paths is not None:
                expected_set = {p.replace("\\", "/") for p in expected_sha256_paths if p != "SHA256SUMS"}
                manifest_set = expected_set
            else:
                inv = build_expected_checksum_inventory(manifest, root)
                expected_set = set(inv["expected_files"])
                manifest_set = {
                    str(f["relative_path"]).replace("\\", "/")
                    for f in (manifest.get("inspected_files") or [])
                    if f.get("relative_path") and not f.get("missing")
                }
                for excl in manifest.get("self_excluded_files") or []:
                    excl_norm = str(excl).replace("\\", "/")
                    if excl_norm and excl_norm != "SHA256SUMS":
                        manifest_set.add(excl_norm)
                for art in artifacts:
                    rel_art = str(art.get("relative_path", "")).replace("\\", "/")
                    if rel_art and rel_art != "SHA256SUMS":
                        manifest_set.add(rel_art)
                manifest_set.discard("SHA256SUMS")
            expected_count = len(expected_set)

            seen_paths: set[str] = set()
            seen_norm_paths: set[str] = set()
            for lineno, raw_line in enumerate(sf.read_text(encoding="utf-8").splitlines(), start=1):
                if not raw_line.strip():
                    continue
                if "  " not in raw_line:
                    errors.append(f"SHA256SUMS:{lineno} malformada (separador '  ' ausente): {raw_line!r}.")
                    sha_failed += 1
                    continue
                expected_h, rel = raw_line.split("  ", 1)
                if not _SHA256_HEX_RE.fullmatch(expected_h):
                    errors.append(f"SHA256SUMS:{lineno} hash SHA-256 malformado para '{rel}': {expected_h!r}.")
                    sha_failed += 1
                    continue
                norm_check = rel.replace("\\", "/").lstrip("./")
                if norm_check in seen_norm_paths:
                    errors.append(f"SHA256SUMS:{lineno} entrada duplicada (mesmo caminho normalizado) para '{rel}'.")
                    sha_failed += 1
                    continue
                seen_norm_paths.add(norm_check)

                rel_obj = Path(rel)
                if (
                    not rel
                    or rel.startswith("/")
                    or rel_obj.is_absolute()
                    or "\\" in rel
                    or ".." in rel_obj.parts
                    or (len(rel) >= 2 and rel[1] == ":")
                ):
                    errors.append(f"SHA256SUMS:{lineno} caminho relativo inválido ou inseguro: {rel!r}.")
                    sha_failed += 1
                    continue
                if rel == "SHA256SUMS":
                    errors.append("SHA256SUMS não pode conter a si próprio.")
                    sha_failed += 1
                    continue
                if rel in seen_paths:
                    errors.append(f"SHA256SUMS:{lineno} entrada duplicada para '{rel}'.")
                    sha_failed += 1
                    continue
                seen_paths.add(rel)

                target = root / rel
                if target.is_symlink():
                    try:
                        target.resolve().relative_to(root)
                    except ValueError:
                        errors.append(f"SHA256SUMS:{lineno} link simbólico aponta para fora da raiz autorizada: {rel!r}.")
                        sha_failed += 1
                        continue
                else:
                    try:
                        target.resolve().relative_to(root)
                    except ValueError:
                        errors.append(f"SHA256SUMS:{lineno} caminho escapa da raiz autorizada: {rel!r}.")
                        sha_failed += 1
                        continue

                if not target.exists() or not target.is_file():
                    errors.append(f"Arquivo listado em SHA256SUMS ausente em disco: {rel}.")
                    sha_failed += 1
                    continue
                actual_h = sha256_file(target)
                if actual_h == expected_h:
                    sha_checked += 1
                else:
                    errors.append(f"Divergência SHA-256 em {rel}: esperado={expected_h} != atual={actual_h}.")
                    sha_failed += 1

            missing_in_sha = sorted((expected_set | manifest_set) - seen_paths)
            unexpected_in_sha = sorted(seen_paths - manifest_set) if manifest_set else sorted(seen_paths - expected_set)
            if missing_in_sha:
                errors.append(
                    f"SHA256SUMS incompleto — arquivo(s) esperado(s) omitido(s): {missing_in_sha}."
                )
            if unexpected_in_sha:
                errors.append(
                    f"SHA256SUMS contém arquivo(s) inesperado(s) fora do inventário: {unexpected_in_sha}."
                )

    if errors:
        raise ConsistencyValidationError(errors)

    return {
        "valid": True,
        "run_id": run_id,
        "checked_artifacts": len(artifacts),
        "expected_files_count": expected_count,
        "sha256_verified": sha_checked,
        "sha256_failed": sha_failed,
        "errors": [],
    }


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
    runtime_environment: dict[str, Any] | None = None,
    timestamp_start_utc: str | None = None,
    timestamp_end_utc: str | None = None,
    durations: dict[str, float] | None = None,
    test_results: dict[str, Any] | None = None,
    coverage_summary: dict[str, Any] | None = None,
    smoke_tests_summary: dict[str, Any] | None = None,
    artifacts: list[dict[str, Any]] | None = None,
    execution_command: str | None = None,
    execution_args: list[str] | None = None,
    exit_code: int | None = None,
    overall_result: str | None = None,
    config: dict[str, Any] | None = None,
    seeds: dict[str, int] | None = None,
    limitations: list[str] | None = None,
    self_excluded_files: list[str] | None = None,
    excluded_dirty_paths: list[str] | None = None,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """Cria o manifesto determinístico de execução (run_manifest.json) com proveniência completa."""
    root_path = (Path(repo_root) if repo_root else Path(__file__).resolve().parents[2]).resolve()
    now_iso = utc_now_iso()
    env_data = dict(runtime_environment) if runtime_environment is not None else capture_runtime_environment(root_path)

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

    deps = dict(env_data.get("dependencies") or {})
    test_tools = dict(env_data.get("test_tools") or {})
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
        "timestamp_utc": timestamp_end_utc or now_iso,
        "timestamp_start_utc": timestamp_start_utc or now_iso,
        "timestamp_end_utc": timestamp_end_utc or now_iso,
        "durations": dict(durations or {}),
        "skill_version": skill_version,
        "manifest_generator_version": MANIFEST_GENERATOR_VERSION,
        "schema_validator_version": deps.get("jsonschema"),
        "engine_versions": dict(engine_versions or {}),
        "profile_versions": dict(profile_versions or {}),
        "profiles": profiles_list,
        "global_eligibility": global_eligibility,
        "authorized_exceptions": list(authorized_exceptions or []),
        "git_commit": git_commit,
        "audited_code_commit": git_commit,
        "git_branch": env_data.get("git_branch"),
        "base_tag": env_data.get("base_tag"),
        "artifact_commit_note": (
            "O commit que publica os artefatos de relatório (pytest_verbose.txt, coverage_report.txt, "
            "smoke_tests.txt, run_manifest.json, homologacao_v8.0-beta.6.3.md e SHA256SUMS) é criado "
            "após esta geração tendo audited_code_commit como pai direto."
        ),
        "git_dirty": git_state["git_dirty_raw"],
        "git_state": git_state,
        "environment": {
            "python_version": env_data["python_version"],
            "python_implementation": env_data["python_implementation"],
            "os_name": env_data["os_name"],
            "os_release": env_data["os_release"],
            "os_build": env_data["os_build"],
            "platform": env_data["platform"],
            "architecture": env_data["architecture"],
            "virtual_env": env_data["virtual_env"],
            "dependencies": deps,
        },
        "test_tools": test_tools,
        "execution": {
            "command": execution_command or sys.executable,
            "args": list(execution_args or []),
            "exit_code": exit_code,
            "overall_result": overall_result,
        },
        "overall_result": overall_result,
        "test_results": dict(test_results) if test_results is not None else None,
        "coverage": dict(coverage_summary) if coverage_summary is not None else None,
        "smoke_tests": dict(smoke_tests_summary) if smoke_tests_summary is not None else None,
        "artifacts": list(artifacts or []),
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
