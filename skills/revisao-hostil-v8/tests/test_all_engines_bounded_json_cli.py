"""Testes programáticos para verificar que todos os 21 motores utilizam read_bounded_json no CLI e rejeitam payloads excedentes."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.common.schema_validator import validate_contract
from scripts.common.validation import MAX_JSON_PAYLOAD_BYTES

_REPO_ROOT = Path(__file__).resolve().parents[1]
_ENGINES_DIR = _REPO_ROOT / "scripts" / "engines"


def test_programmatic_verification_all_21_engines_use_read_bounded_json() -> None:
    engine_files = sorted(_ENGINES_DIR.glob("motor_*.py"))
    assert len(engine_files) == 21, f"Esperado exatamente 21 motores, encontrados: {len(engine_files)}"

    unprotected = []
    for f in engine_files:
        content = f.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(f))

        has_bounded_call = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id == "read_bounded_json":
                    has_bounded_call = True
                    break
        if not has_bounded_call:
            unprotected.append(f.name)

    assert not unprotected, f"Motores sem chamada a read_bounded_json detectados: {unprotected}"


@pytest.mark.parametrize(
    "script_name",
    [
        "motor_dados.py",
        "motor_dimensional.py",
        "motor_estatistico.py",
        "motor_consistencia_cruzada.py",
        "motor_argumentacao.py",
        "motor_linguagem.py",
        "motor_temporal.py",
    ],
)
def test_representative_engine_clis_reject_oversized_stdin_with_code_1_and_structured_json(
    script_name: str,
) -> None:
    # 1. Payload que excede MAX_JSON_PAYLOAD_BYTES em 1 byte
    oversized = '{"op": "' + ("x" * MAX_JSON_PAYLOAD_BYTES) + '"}'
    cmd = [sys.executable, str(_ENGINES_DIR / script_name)]

    p = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(_REPO_ROOT),
    )
    stdout, stderr = p.communicate(input=oversized)

    assert p.returncode == 1, f"{script_name} deveria ter saído com código 1 em payload excedente"
    assert "Traceback (most recent call last)" not in stderr, f"Traceback vazou em stderr para {script_name}"

    # Saída estruturada válida em JSON
    cli_out = json.loads(stdout)
    validate_contract(cli_out, "schema_motor.json")
    assert cli_out["status"] == "ERRO_EXECUCAO"
    assert cli_out["deterministico"] is True
    assert cli_out["resultados"]["error_type"] == "ValueError"
    assert "excede o limite máximo permitido" in cli_out["resultados"]["error"]


@pytest.mark.parametrize(
    "script_name",
    [
        "motor_dados.py",
        "motor_dimensional.py",
        "motor_argumentacao.py",
    ],
)
def test_representative_engine_clis_reject_oversized_file(tmp_path: Path, script_name: str) -> None:
    target_file = tmp_path / "oversized.json"
    content = '{"op": "' + ("y" * MAX_JSON_PAYLOAD_BYTES) + '"}'
    target_file.write_text(content, encoding="utf-8")

    cmd = [sys.executable, str(_ENGINES_DIR / script_name), "--input", str(target_file)]
    p = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(_REPO_ROOT),
    )
    stdout, stderr = p.communicate()

    assert p.returncode == 1
    assert "Traceback (most recent call last)" not in stderr
    cli_out = json.loads(stdout)
    validate_contract(cli_out, "schema_motor.json")
    assert cli_out["status"] == "ERRO_EXECUCAO"
    assert "excede o limite" in cli_out["resultados"]["error"]
