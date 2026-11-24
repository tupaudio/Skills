"""Suíte adversarial estrita para cabeçalho RUN_ID em artefatos (ACH-B6.5-001 — v8.0-beta.6.6).

Cobre integralmente todos os 13 cenários obrigatórios:
1. Cabeçalho correto aceito (`RUN_ID=` e `# run_id=`);
2. Identificador apenas no corpo rejeitado;
3. Cabeçalho ausente rejeitado;
4. Cabeçalho vazio rejeitado (`RUN_ID=`, `RUN_ID=   `, `# run_id=`);
5. Cabeçalho malformado rejeitado (espaços à esquerda, texto extra na linha, formato inválido);
6. Identificador divergente rejeitado;
7. Dois cabeçalhos idênticos (rejeitados por padrão; aceitos apenas com allow_duplicate_identical_headers=True);
8. Dois cabeçalhos conflitantes (sempre rejeitados, mesmo com allow_duplicate_identical_headers=True);
9. Cabeçalho correto com outro identificador mencionado no corpo (aceito sem falso positivo);
10. Arquivo vazio rejeitado;
11. Arquivo inexistente rejeitado;
12. Codificação inválida (bytes não UTF-8) rejeitada;
13. Integração completa com `validate_run_consistency()`.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

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


def test_b65_001_valid_header_accepted(tmp_path: Path) -> None:
    """[Cenário 1] Cabeçalho estritamente conforme (`RUN_ID=` e `# run_id=`) é aceito."""
    rid = "BETA6.6-20261124T000000Z-a1b2c3d4"
    f1 = tmp_path / "log1.txt"
    f1.write_text(f"RUN_ID={rid}\n160 passed in 12.0s\n", encoding="utf-8")
    res1 = validate_artifact_run_id(f1, rid)
    assert res1["valid"] is True
    assert res1["header_count"] == 1
    assert res1["found_run_ids"] == [rid]

    f2 = tmp_path / "log2.txt"
    f2.write_text(f"# run_id={rid}\nTOTAL 100 10 90%\n", encoding="utf-8")
    res2 = validate_artifact_run_id(f2, rid)
    assert res2["valid"] is True
    assert res2["header_count"] == 1


def test_b65_001_id_only_in_body_rejected(tmp_path: Path) -> None:
    """[Cenário 2] Presença do run_id apenas no corpo textual (sem cabeçalho autorizado) é rejeitada."""
    rid = "BETA6.6-20261124T000000Z-a1b2c3d4"
    f = tmp_path / "body_only.md"
    f.write_text(f"# Relatorio\nEste texto menciona {rid} apenas no corpo.\n", encoding="utf-8")
    with pytest.raises(ConsistencyValidationError, match="cabeçalho"):
        validate_artifact_run_id(f, rid)


def test_b65_001_missing_header_rejected(tmp_path: Path) -> None:
    """[Cenário 3] Ausência total de cabeçalho e identificador é rejeitada."""
    f = tmp_path / "no_header.txt"
    f.write_text("160 passed in 12.0s\n", encoding="utf-8")
    with pytest.raises(ConsistencyValidationError, match="cabeçalho"):
        validate_artifact_run_id(f, "BETA6.6-20261124T000000Z-a1b2c3d4")


@pytest.mark.parametrize("bad_line", ["RUN_ID=", "RUN_ID=   ", "# run_id=", "# run_id=   "])
def test_b65_001_empty_header_rejected(tmp_path: Path, bad_line: str) -> None:
    """[Cenário 4] Cabeçalho vazio é rejeitado explicitamente."""
    rid = "BETA6.6-20261124T000000Z-a1b2c3d4"
    f = tmp_path / "empty_hdr.txt"
    f.write_text(f"{bad_line}\n{rid}\n", encoding="utf-8")
    with pytest.raises(ConsistencyValidationError, match="vazio ou malformado"):
        validate_artifact_run_id(f, rid)


@pytest.mark.parametrize(
    "malformed",
    [
        "  RUN_ID=BETA6.6-20261124T000000Z-a1b2c3d4",
        "RUN_ID=BETA6.6-20261124T000000Z-a1b2c3d4 lixo_extra",
        "RUN_ID= BETA6.6-20261124T000000Z-a1b2c3d4",
        "run_id=BETA6.6-20261124T000000Z-a1b2c3d4",
        "RUN_ID=!!!invalido!!!",
    ],
)
def test_b65_001_malformed_header_rejected(tmp_path: Path, malformed: str) -> None:
    """[Cenário 5] Cabeçalho malformado (indentação, lixo extra, minúsculas sem #, caracteres inválidos) é rejeitado."""
    rid = "BETA6.6-20261124T000000Z-a1b2c3d4"
    f = tmp_path / "malformed.txt"
    f.write_text(f"{malformed}\n160 passed\n", encoding="utf-8")
    with pytest.raises(ConsistencyValidationError, match="vazio ou malformado"):
        validate_artifact_run_id(f, rid)


def test_b65_001_divergent_header_rejected(tmp_path: Path) -> None:
    """[Cenário 6] Cabeçalho válido porém com identificador diferente do esperado é rejeitado."""
    f = tmp_path / "divergent.txt"
    f.write_text("RUN_ID=BETA6.6-20260101T000000Z-99999999\n160 passed\n", encoding="utf-8")
    with pytest.raises(ConsistencyValidationError, match="divergente"):
        validate_artifact_run_id(f, "BETA6.6-20261124T000000Z-a1b2c3d4")


def test_b65_001_duplicate_identical_headers_policy(tmp_path: Path) -> None:
    """[Cenário 7] Dois cabeçalhos idênticos são rejeitados por padrão e aceitos apenas com opt-in explícito."""
    rid = "BETA6.6-20261124T000000Z-a1b2c3d4"
    f = tmp_path / "dup.txt"
    f.write_text(f"RUN_ID={rid}\nRUN_ID={rid}\n160 passed\n", encoding="utf-8")

    with pytest.raises(ConsistencyValidationError, match="duplicados"):
        validate_artifact_run_id(f, rid)

    ok = validate_artifact_run_id(f, rid, allow_duplicate_identical_headers=True)
    assert ok["valid"] is True
    assert ok["header_count"] == 2


def test_b65_001_conflicting_headers_always_rejected(tmp_path: Path) -> None:
    """[Cenário 8] Dois cabeçalhos conflitantes são sempre rejeitados (mesmo com allow_duplicate_identical_headers=True)."""
    rid = "BETA6.6-20261124T000000Z-a1b2c3d4"
    f = tmp_path / "conflict.txt"
    f.write_text(f"RUN_ID={rid}\nRUN_ID=BETA6.6-OUTRO-9999\n160 passed\n", encoding="utf-8")

    with pytest.raises(ConsistencyValidationError, match="conflitantes"):
        validate_artifact_run_id(f, rid)
    with pytest.raises(ConsistencyValidationError, match="conflitantes"):
        validate_artifact_run_id(f, rid, allow_duplicate_identical_headers=True)


def test_b65_001_valid_header_with_other_id_mentioned_in_body_accepted(tmp_path: Path) -> None:
    """[Cenário 9] Cabeçalho válido com menção histórica a outro run_id no corpo é aceito sem falso positivo."""
    rid = "BETA6.6-20261124T000000Z-a1b2c3d4"
    f = tmp_path / "history_ref.md"
    f.write_text(
        f"# Relatorio\nRUN_ID={rid}\nComparacao com execucao anterior BETA6.5-20261124T020228Z-49ae3874.\n",
        encoding="utf-8",
    )
    res = validate_artifact_run_id(f, rid)
    assert res["valid"] is True
    assert res["found_run_ids"] == [rid]


def test_b65_001_empty_missing_and_bad_encoding_files_rejected(tmp_path: Path) -> None:
    """[Cenários 10, 11 e 12] Arquivo vazio, inexistente e com codificação UTF-8 inválida são rejeitados."""
    rid = "BETA6.6-20261124T000000Z-a1b2c3d4"

    f_empty = tmp_path / "empty.txt"
    f_empty.write_text("   \n\n", encoding="utf-8")
    with pytest.raises(ConsistencyValidationError, match="vazio"):
        validate_artifact_run_id(f_empty, rid)

    with pytest.raises(ConsistencyValidationError, match="ausente"):
        validate_artifact_run_id(tmp_path / "nao_existe.txt", rid)

    f_bin = tmp_path / "bad_utf8.txt"
    f_bin.write_bytes(b"\xff\xfe\xfdRUN_ID=" + rid.encode("ascii"))
    with pytest.raises(ConsistencyValidationError, match="ilegível"):
        validate_artifact_run_id(f_bin, rid)


def test_b65_001_integration_with_validate_run_consistency_rejects_body_only_artifact(tmp_path: Path) -> None:
    """[Cenário 13] Integração com validate_run_consistency(): artefato com ID apenas no corpo falha mesmo com hashes válidos."""
    run_id = generate_run_id("BETA6.6")
    env = capture_runtime_environment(tmp_path)
    rep_dir = tmp_path / "relatorios_execucao"
    rep_dir.mkdir(parents=True, exist_ok=True)

    # pytest_verbose.txt contém o run_id apenas no corpo, SEM cabeçalho RUN_ID=
    p_log = rep_dir / "pytest_verbose.txt"
    p_log.write_text(f"Texto qualquer citando {run_id} no meio da linha.\n10 passed\n", encoding="utf-8")
    c_log = rep_dir / "coverage_report.txt"
    c_log.write_text(f"RUN_ID={run_id}\nTOTAL 10 0 100%\n", encoding="utf-8")
    s_log = rep_dir / "smoke_tests.txt"
    s_log.write_text(f"RUN_ID={run_id}\n[CLI OK]\n", encoding="utf-8")
    rep_text = (
        f"# Relatorio\nRUN_ID={run_id}\nPython: `{env['python_version']}`\n"
        f"Build: `{env['os_build']}`\nAprovados: `10 passed`\nWarnings: `0`\n"
    )
    h_log = rep_dir / "homologacao_v8.0-beta.6.6.md"
    h_log.write_text(rep_text, encoding="utf-8")

    artifacts = [
        build_artifact_record(p_log, tmp_path, run_id=run_id, artifact_type="pytest_log"),
        build_artifact_record(c_log, tmp_path, run_id=run_id, artifact_type="coverage_report"),
        build_artifact_record(s_log, tmp_path, run_id=run_id, artifact_type="smoke_tests"),
        build_artifact_record(h_log, tmp_path, run_id=run_id, artifact_type="homologation_report"),
    ]
    manifest = build_run_manifest(
        run_id,
        [p_log, c_log, s_log, h_log],
        skill_version="8.0.0-beta.6.6",
        runtime_environment=env,
        durations={"test_suite_seconds": 0.5, "total_seconds": 1.0},
        test_results={
            "run_id": run_id,
            "python_version": env["python_version"],
            "os_name": env["os_name"],
            "os_build": env["os_build"],
            "collected": 10,
            "passed": 10,
            "failed": 0,
            "skipped": 0,
            "collection_errors": 0,
            "warnings": 0,
            "duration_seconds": 0.5,
            "exit_code": 0,
        },
        artifacts=artifacts,
        self_excluded_files=["relatorios_execucao/run_manifest.json"],
        exit_code=0,
        overall_result="PASSED",
        repo_root=tmp_path,
    )
    manifest["audited_code_commit"] = "abcd1234"
    manifest["git_commit"] = "abcd1234"
    save_run_manifest(manifest, rep_dir / "run_manifest.json")

    inv = build_expected_checksum_inventory(manifest, tmp_path)
    sha_file = tmp_path / "SHA256SUMS"
    sha_file.write_text("\n".join(f"{_sha(tmp_path / r)}  {r}" for r in inv["expected_files"]) + "\n", encoding="utf-8")

    with pytest.raises(ConsistencyValidationError, match="cabeçalho"):
        validate_run_consistency(
            manifest,
            root_dir=tmp_path,
            sha256sums_path=sha_file,
            expected_commit="abcd1234",
            report_text=rep_text,
        )
