"""Suíte dedicada de proveniência interna de artefatos e completude de SHA256SUMS.

Cobre integralmente os 11 cenários obrigatórios de ACH-B6.3-001 (Seção 3.5)
e os 15 cenários obrigatórios de ACH-B6.3-002 (Seção 4.5), usando fixtures isoladas
e adulterações controladas.
"""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from typing import Any

import pytest

from scripts.common.provenance import (
    ConsistencyValidationError,
    build_artifact_record,
    build_expected_checksum_inventory,
    build_run_manifest,
    capture_runtime_environment,
    generate_run_id,
    save_run_manifest,
    validate_artifact_run_id,
    validate_run_consistency,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _create_full_run_sandbox(tmp_path: Path) -> tuple[dict[str, Any], Path, str, str]:
    """Cria um mini-repositório completo com código, logs, manifesto e SHA256SUMS 100% válidos."""
    run_id = generate_run_id("BETA6.5")
    env = capture_runtime_environment(tmp_path)

    # Arquivo de código versionado simulado
    src_dir = tmp_path / "scripts"
    src_dir.mkdir(parents=True, exist_ok=True)
    code_file = src_dir / "modulo_exemplo.py"
    code_file.write_text("def soma(a: int, b: int) -> int:\n    return a + b\n", encoding="utf-8")

    # Artefatos obrigatórios de execução com cabeçalho RUN_ID=
    rep_dir = tmp_path / "relatorios_execucao"
    rep_dir.mkdir(parents=True, exist_ok=True)

    pytest_log = rep_dir / "pytest_verbose.txt"
    pytest_log.write_text(f"RUN_ID={run_id}\n10 passed in 0.42s\n", encoding="utf-8")

    cov_log = rep_dir / "coverage_report.txt"
    cov_log.write_text(f"RUN_ID={run_id}\nTOTAL 100 10 90%\n", encoding="utf-8")

    smoke_log = rep_dir / "smoke_tests.txt"
    smoke_log.write_text(f"RUN_ID={run_id}\n[CLI OK] motor_dimensional\n", encoding="utf-8")

    report_text = (
        f"# Relatorio\n"
        f"RUN_ID={run_id}\n"
        f"Python: `{env['python_version']}`\n"
        f"Build: `{env['os_build']}`\n"
        f"Aprovados: `10 passed`\n"
        f"Warnings: `0`\n"
    )
    homolog_file = rep_dir / "homologacao_v8.0-beta.6.5.md"
    homolog_file.write_text(report_text, encoding="utf-8")

    artifacts = [
        build_artifact_record(pytest_log, tmp_path, run_id=run_id, artifact_type="pytest_log"),
        build_artifact_record(cov_log, tmp_path, run_id=run_id, artifact_type="coverage_report"),
        build_artifact_record(smoke_log, tmp_path, run_id=run_id, artifact_type="smoke_tests"),
        build_artifact_record(homolog_file, tmp_path, run_id=run_id, artifact_type="homologation_report"),
    ]

    test_results = {
        "run_id": run_id,
        "pytest_version": env["test_tools"].get("pytest"),
        "python_version": env["python_version"],
        "os_name": env["os_name"],
        "os_build": env["os_build"],
        "collected": 10,
        "passed": 10,
        "failed": 0,
        "skipped": 0,
        "collection_errors": 0,
        "warnings": 0,
        "duration_seconds": 0.42,
        "exit_code": 0,
    }

    manifest = build_run_manifest(
        run_id,
        [code_file, pytest_log, cov_log, smoke_log, homolog_file],
        skill_version="8.0.0-beta.6.5",
        runtime_environment=env,
        durations={"test_suite_seconds": 0.42, "total_seconds": 1.00},
        test_results=test_results,
        artifacts=artifacts,
        self_excluded_files=["relatorios_execucao/run_manifest.json"],
        exit_code=0,
        overall_result="PASSED",
        repo_root=tmp_path,
    )
    manifest["audited_code_commit"] = "1111222233334444"
    manifest["git_commit"] = "1111222233334444"
    manifest_file = save_run_manifest(manifest, rep_dir / "run_manifest.json")

    inv = build_expected_checksum_inventory(manifest, tmp_path)
    sha_file = tmp_path / "SHA256SUMS"
    sha_lines = [f"{_sha(tmp_path / rel)}  {rel}" for rel in inv["expected_files"]]
    sha_file.write_text("\n".join(sha_lines) + "\n", encoding="utf-8")
    assert manifest_file.exists()
    return manifest, sha_file, report_text, run_id


def _rewrite_sha_from_manifest(manifest: dict[str, Any], root: Path, sha_file: Path) -> None:
    inv = build_expected_checksum_inventory(manifest, root)
    lines = [f"{_sha(root / rel)}  {rel}" for rel in inv["expected_files"]]
    sha_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


# =============================================================================
# ACH-B6.3-001 — 11 CENÁRIOS OBRIGATÓRIOS (RUN_ID NO CONTEÚDO DOS ARTEFATOS)
# =============================================================================


def test_b64_001_1_and_4_pytest_and_coverage_with_valid_run_id(tmp_path: Path) -> None:
    """[Cenários 1 e 4] Log pytest e relatório de cobertura com RUN_ID correto são aceitos."""
    _, _, _, run_id = _create_full_run_sandbox(tmp_path)
    r1 = validate_artifact_run_id(tmp_path / "relatorios_execucao" / "pytest_verbose.txt", run_id)
    r2 = validate_artifact_run_id(tmp_path / "relatorios_execucao" / "coverage_report.txt", run_id)
    assert r1["valid"] is True and r1["expected_run_id"] == run_id
    assert r2["valid"] is True and r2["expected_run_id"] == run_id


@pytest.mark.parametrize(
    "artifact_name,content_template",
    [
        ("pytest_verbose.txt", "10 passed in 0.42s\n"),                                  # Cenário 2: sem run_id
        ("pytest_verbose.txt", "RUN_ID=BETA6.5-OUTRA-EXEC\n10 passed in 0.42s\n"),        # Cenário 3: run_id diferente
        ("coverage_report.txt", "TOTAL 100 10 90%\n"),                                    # Cenário 5: sem run_id
        ("coverage_report.txt", "RUN_ID=BETA6.5-OUTRA-EXEC\nTOTAL 100 10 90%\n"),         # Cenário 6: run_id divergente
        ("pytest_verbose.txt", "RUN_ID={run_id}\nRUN_ID=BETA6.5-CONFLITO\n10 passed\n"),  # Cenário 9: dois run_id conflitantes
    ],
)
def test_b64_001_rejects_missing_divergent_or_conflicting_run_id(
    tmp_path: Path, artifact_name: str, content_template: str
) -> None:
    """[Cenários 2, 3, 5, 6, 9] Rejeita ausência, divergência ou múltiplos RUN_ID conflitantes no artefato."""
    _, _, _, run_id = _create_full_run_sandbox(tmp_path)
    target = tmp_path / "relatorios_execucao" / artifact_name
    target.write_text(content_template.format(run_id=run_id), encoding="utf-8")
    with pytest.raises(ConsistencyValidationError):
        validate_artifact_run_id(target, run_id)


def test_b64_001_7_manifest_ok_but_content_tampered(tmp_path: Path) -> None:
    """[Cenário 7] Manifesto com run_id correto, mas conteúdo adulterado em disco -> rejeitado."""
    manifest, sha_file, report_text, _ = _create_full_run_sandbox(tmp_path)
    (tmp_path / "relatorios_execucao" / "pytest_verbose.txt").write_text("ADULTERADO\n", encoding="utf-8")
    with pytest.raises(ConsistencyValidationError):
        validate_run_consistency(manifest, root_dir=tmp_path, sha256sums_path=sha_file, report_text=report_text)


def test_b64_001_8_and_11_replaced_artifact_with_recomputed_hash_still_rejected(tmp_path: Path) -> None:
    """[Cenários 8 e 11] Trocar artefato por outra execução E atualizar SHA-256 no manifesto e SHA256SUMS falha."""
    manifest, sha_file, report_text, _ = _create_full_run_sandbox(tmp_path)
    m = copy.deepcopy(manifest)

    target = tmp_path / "relatorios_execucao" / "coverage_report.txt"
    target.write_text("RUN_ID=BETA6.5-20260101T000000Z-deadbeef\nTOTAL 100 10 90%\n", encoding="utf-8")

    # Ataque completo: atualiza bytes e sha256 no manifesto E regenera SHA256SUMS
    for art in m["artifacts"]:
        if art["name"] == "coverage_report.txt":
            art["bytes"] = target.stat().st_size
            art["sha256"] = _sha(target)
    save_run_manifest(m, tmp_path / "relatorios_execucao" / "run_manifest.json")
    _rewrite_sha_from_manifest(m, tmp_path, sha_file)

    with pytest.raises(ConsistencyValidationError, match="run_id"):
        validate_run_consistency(m, root_dir=tmp_path, sha256sums_path=sha_file, report_text=report_text)


def test_b64_001_10_missing_required_artifact_rejected(tmp_path: Path) -> None:
    """[Cenário 10] Artefato obrigatório ausente em disco é rejeitado."""
    manifest, sha_file, report_text, _ = _create_full_run_sandbox(tmp_path)
    (tmp_path / "relatorios_execucao" / "smoke_tests.txt").unlink()
    with pytest.raises(ConsistencyValidationError, match="ausente"):
        validate_run_consistency(manifest, root_dir=tmp_path, sha256sums_path=sha_file, report_text=report_text)


# =============================================================================
# ACH-B6.3-002 — 15 CENÁRIOS OBRIGATÓRIOS (COMPLETUDE E SEGURANÇA DE SHA256SUMS)
# =============================================================================


def test_b64_002_1_and_13_complete_inventory_and_legitimate_temp_exclusion(tmp_path: Path) -> None:
    """[Cenários 1 e 13] Inventário completo passa; arquivos temporários/cache são excluídos legitimamente."""
    manifest, sha_file, report_text, _ = _create_full_run_sandbox(tmp_path)
    # Adiciona arquivos temporários/cache legítimos (devem ser ignorados pela política explícita)
    cache_dir = tmp_path / "scripts" / "__pycache__"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "modulo_exemplo.cpython-314.pyc").write_bytes(b"\x00\x01")
    (tmp_path / "scratch.tmp").write_text("temporario", encoding="utf-8")

    inv = build_expected_checksum_inventory(manifest, tmp_path)
    assert "SHA256SUMS" not in inv["expected_files"]
    assert "relatorios_execucao/run_manifest.json" in inv["expected_files"]
    assert "scripts/modulo_exemplo.py" in inv["expected_files"]
    assert any(e["relative_path"].endswith(".pyc") for e in inv["excluded_files"])
    assert any(e["relative_path"] == "scratch.tmp" for e in inv["excluded_files"])

    res = validate_run_consistency(
        manifest,
        root_dir=tmp_path,
        sha256sums_path=sha_file,
        expected_commit="1111222233334444",
        report_text=report_text,
    )
    assert res["valid"] is True
    assert res["expected_files_count"] == res["sha256_verified"]
    assert res["sha256_failed"] == 0


@pytest.mark.parametrize(
    "omitted_rel",
    [
        "scripts/modulo_exemplo.py",                        # Cenário 2: omissão de arquivo de código
        "relatorios_execucao/run_manifest.json",            # Cenário 3: omissão do manifesto
        "relatorios_execucao/homologacao_v8.0-beta.6.5.md", # Cenário 4: omissão do relatório de homologação
        "relatorios_execucao/pytest_verbose.txt",           # Cenário 5: omissão de um log
    ],
)
def test_b64_002_omission_of_any_expected_file_rejected(tmp_path: Path, omitted_rel: str) -> None:
    """[Cenários 2, 3, 4, 5] Omissão de código, manifesto, relatório ou log do SHA256SUMS falha."""
    manifest, sha_file, report_text, _ = _create_full_run_sandbox(tmp_path)
    filtered = [ln for ln in sha_file.read_text(encoding="utf-8").splitlines() if not ln.endswith(f"  {omitted_rel}")]
    sha_file.write_text("\n".join(filtered) + "\n", encoding="utf-8")
    with pytest.raises(ConsistencyValidationError, match="omitido"):
        validate_run_consistency(manifest, root_dir=tmp_path, sha256sums_path=sha_file, report_text=report_text)


@pytest.mark.parametrize(
    "tamper_kind",
    [
        "nonexistent_file",       # Cenário 6
        "absolute_outside_root",  # Cenário 7
        "duplicate_entry",        # Cenário 8
        "duplicate_diff_sep",     # Cenário 8b (separadores diferentes)
        "malformed_hash",         # Cenário 9
        "wrong_hash",             # Cenário 10
        "modified_after_sha",     # Cenário 11
        "self_inclusion",         # Cenário 12
        "directory_traversal",    # Cenário 14
    ],
)
def test_b64_002_rejects_all_checksum_integrity_and_path_attacks(tmp_path: Path, tamper_kind: str) -> None:
    """[Cenários 6-12 e 14] Rejeita arquivos inexistentes, fora da raiz, duplicatas, hashes ruins, travessia e auto-inclusão."""
    manifest, sha_file, report_text, _ = _create_full_run_sandbox(tmp_path)
    lines = sha_file.read_text(encoding="utf-8").splitlines()

    if tamper_kind == "nonexistent_file":
        sha_file.write_text("\n".join(lines + [("a" * 64) + "  scripts/fantasma.py"]) + "\n", encoding="utf-8")
    elif tamper_kind == "absolute_outside_root":
        sha_file.write_text("\n".join(lines + [("a" * 64) + "  /etc/passwd"]) + "\n", encoding="utf-8")
    elif tamper_kind == "duplicate_entry":
        sha_file.write_text("\n".join(lines + [lines[0]]) + "\n", encoding="utf-8")
    elif tamper_kind == "duplicate_diff_sep":
        h0, p0 = lines[0].split("  ", 1)
        sha_file.write_text("\n".join(lines + [f"{h0}  {p0.replace('/', chr(92))}"]) + "\n", encoding="utf-8")
    elif tamper_kind == "malformed_hash":
        _, p0 = lines[0].split("  ", 1)
        sha_file.write_text("\n".join([f"NAO_HEX_64  {p0}"] + lines[1:]) + "\n", encoding="utf-8")
    elif tamper_kind == "wrong_hash":
        _, p0 = lines[0].split("  ", 1)
        sha_file.write_text("\n".join([f"{'0' * 64}  {p0}"] + lines[1:]) + "\n", encoding="utf-8")
    elif tamper_kind == "modified_after_sha":
        (tmp_path / "scripts" / "modulo_exemplo.py").write_text("def soma(a, b): return a - b\n", encoding="utf-8")
    elif tamper_kind == "self_inclusion":
        sha_file.write_text("\n".join(lines + [("b" * 64) + "  SHA256SUMS"]) + "\n", encoding="utf-8")
    elif tamper_kind == "directory_traversal":
        sha_file.write_text("\n".join(lines + [("a" * 64) + "  ../fora_da_raiz.txt"]) + "\n", encoding="utf-8")

    with pytest.raises(ConsistencyValidationError):
        validate_run_consistency(manifest, root_dir=tmp_path, sha256sums_path=sha_file, report_text=report_text)


def test_b64_002_15_symlink_outside_root_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """[Cenário 15] Link simbólico apontando para fora da raiz autorizada é rejeitado (real ou simulado se SO restringir)."""
    outside = tmp_path / "segredo_externo.txt"
    outside.write_text("segredo\n", encoding="utf-8")
    repo = tmp_path / "repo"
    repo.mkdir()
    manifest, sha_file, report_text, _ = _create_full_run_sandbox(repo)
    lines = sha_file.read_text(encoding="utf-8").splitlines()

    link_path = repo / "link_externo.txt"
    try:
        link_path.symlink_to(outside)
        sha_file.write_text("\n".join(lines + [f"{_sha(outside)}  link_externo.txt"]) + "\n", encoding="utf-8")
    except OSError:
        # Windows sem Developer Mode: simula symlink apontando para fora da raiz
        link_path.write_text("placeholder\n", encoding="utf-8")
        sha_file.write_text("\n".join(lines + [f"{_sha(outside)}  link_externo.txt"]) + "\n", encoding="utf-8")
        orig_is_symlink = Path.is_symlink
        orig_resolve = Path.resolve

        def _fake_is_symlink(self: Path) -> bool:
            if self.name == "link_externo.txt":
                return True
            return orig_is_symlink(self)

        def _fake_resolve(self: Path, strict: bool = False) -> Path:
            if self.name == "link_externo.txt":
                return outside.resolve()
            return orig_resolve(self, strict=strict)

        monkeypatch.setattr(Path, "is_symlink", _fake_is_symlink)
        monkeypatch.setattr(Path, "resolve", _fake_resolve)

    with pytest.raises(ConsistencyValidationError, match="fora da raiz"):
        validate_run_consistency(manifest, root_dir=repo, sha256sums_path=sha_file, report_text=report_text)
