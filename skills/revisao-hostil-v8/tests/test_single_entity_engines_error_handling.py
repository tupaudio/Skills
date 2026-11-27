"""Testes unitários e de CLI para tratamento estruturado de entradas inválidas nos motores sem lote."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.common.schema_validator import validate_contract
from scripts.engines import (
    motor_argumentacao,
    motor_estetico,
    motor_linguagem,
    motor_temporal,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]


def test_motor_argumentacao_invalid_payload_returns_structured_error() -> None:
    # 1. Payload vazio
    out_empty = motor_argumentacao.run_motor({})
    validate_contract(out_empty, "schema_motor.json")
    assert out_empty["status"] == "ERRO_VALIDACAO"
    assert out_empty["metricas"]["erros"] == 1
    assert "arguments" in out_empty["resultados"]["error"]

    # 2. arguments não é lista
    out_bad_type = motor_argumentacao.run_motor({"arguments": "not_a_list"})
    validate_contract(out_bad_type, "schema_motor.json")
    assert out_bad_type["status"] == "ERRO_VALIDACAO"

    # 3. Payload válido preservado
    valid_payload = {
        "arguments": [
            {
                "id": "A1",
                "claim": "Hipótese razoável",
                "premises": ["P1"],
                "conclusion": "C1",
                "scheme": "expert_opinion",
                "evidence_ids": ["EV_01"],
            }
        ]
    }
    out_valid = motor_argumentacao.run_motor(valid_payload)
    validate_contract(out_valid, "schema_motor.json")
    assert out_valid["status"] in ("OK", "COM_ACHADOS")
    assert out_valid["metricas"]["argumentos"] == 1


def test_motor_linguagem_invalid_payload_returns_structured_error() -> None:
    # 1. Payload vazio
    out_empty = motor_linguagem.run_motor({})
    validate_contract(out_empty, "schema_motor.json")
    assert out_empty["status"] == "ERRO_VALIDACAO"
    assert out_empty["metricas"]["erros"] == 1
    assert "text" in out_empty["resultados"]["error"]

    # 2. text não é string
    out_bad_type = motor_linguagem.run_motor({"text": 12345})
    validate_contract(out_bad_type, "schema_motor.json")
    assert out_bad_type["status"] == "ERRO_VALIDACAO"

    # 3. Payload válido preservado
    out_valid = motor_linguagem.run_motor({"text": "O método apresenta convergência assintótica sob condições normais."})
    validate_contract(out_valid, "schema_motor.json")
    assert out_valid["status"] == "OK"
    assert out_valid["metricas"]["word_count"] > 0


def test_motor_estetico_invalid_payload_returns_structured_error(tmp_path: Path) -> None:
    # 1. Payload vazio
    out_empty = motor_estetico.run_motor({})
    validate_contract(out_empty, "schema_motor.json")
    assert out_empty["status"] == "ERRO_VALIDACAO"
    assert out_empty["metricas"]["erros"] == 1
    assert "file_path" in out_empty["resultados"]["error"]

    # 2. Arquivo inexistente
    out_not_found = motor_estetico.run_motor({"file_path": str(tmp_path / "inexistente.png")})
    validate_contract(out_not_found, "schema_motor.json")
    assert out_not_found["status"] == "ERRO_VALIDACAO"


def test_motor_temporal_invalid_payload_returns_structured_error() -> None:
    # 1. Payload com events: None
    out_none = motor_temporal.run_motor({"events": None})
    validate_contract(out_none, "schema_motor.json")
    assert out_none["status"] == "ERRO_VALIDACAO"
    assert out_none["metricas"]["erros"] == 1
    assert "events" in out_none["resultados"]["error"]

    # 2. Payload vazio
    out_empty = motor_temporal.run_motor({})
    validate_contract(out_empty, "schema_motor.json")
    assert out_empty["status"] == "ERRO_VALIDACAO"

    # 3. Payload válido preservado
    valid_payload = {
        "events": {
            "E1": "2026-01-01T10:00:00Z",
            "E2": "2026-01-01T11:00:00Z",
        },
        "precedence_rules": [{"before": "E1", "after": "E2"}],
    }
    out_valid = motor_temporal.run_motor(valid_payload)
    validate_contract(out_valid, "schema_motor.json")
    assert out_valid["status"] == "OK"
    assert out_valid["metricas"]["eventos_verificados"] == 2


@pytest.mark.parametrize(
    ("script_name", "invalid_payload"),
    [
        ("motor_argumentacao.py", {}),
        ("motor_linguagem.py", {}),
        ("motor_estetico.py", {}),
        ("motor_temporal.py", {"events": None}),
    ],
)
def test_cli_execution_path_on_invalid_payload_returns_code_1_and_structured_json(
    script_name: str,
    invalid_payload: dict,
) -> None:
    cmd = [sys.executable, f"scripts/engines/{script_name}"]
    p = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(_REPO_ROOT),
    )
    stdout, stderr = p.communicate(input=json.dumps(invalid_payload))

    # Código de saída 1 para erro de validação/execução
    assert p.returncode == 1

    # Sem traceback descontrolado em stderr
    assert "Traceback (most recent call last)" not in stderr

    # Saída estruturada válida em JSON
    cli_out = json.loads(stdout)
    validate_contract(cli_out, "schema_motor.json")
    assert cli_out["status"] == "ERRO_VALIDACAO"
    assert cli_out["deterministico"] is True
