"""Testes de regressão para validação estrita de incerteza em motor_incerteza.py."""

from __future__ import annotations

import math
import pytest

from scripts.common.schema_validator import validate_contract
from scripts.engines import motor_incerteza


def test_propagate_gum_missing_or_unknown_uncertainty_key_raises_error() -> None:
    # 1. Variável com chave não suportada ('standard_uncertainty' em vez de 'u')
    bad_payload = {
        "operation": "propagate_gum",
        "expression": "x * y",
        "variables": {
            "x": {"value": 2.0, "standard_uncertainty": 0.1},
            "y": {"value": 3.0, "standard_uncertainty": 0.2},
        },
    }
    out = motor_incerteza.run_motor(bad_payload)
    validate_contract(out, "schema_motor.json")
    assert out["status"] == "ERRO_VALIDACAO"
    assert out["metricas"]["falhas"] == 1
    assert "não possui incerteza informada" in out["resultados"]["results"][0]["error"]

    # 2. Variável totalmente sem campo de incerteza
    no_u_payload = {
        "operation": "propagate_gum",
        "expression": "x + 1",
        "variables": {"x": {"value": 2.0}},
    }
    out_no_u = motor_incerteza.run_motor(no_u_payload)
    validate_contract(out_no_u, "schema_motor.json")
    assert out_no_u["status"] == "ERRO_VALIDACAO"
    assert "não possui incerteza informada" in out_no_u["resultados"]["results"][0]["error"]


def test_propagate_gum_negative_or_nan_uncertainty_raises_error() -> None:
    # 1. Incerteza negativa
    neg_payload = {
        "operation": "propagate_gum",
        "expression": "x + y",
        "variables": {
            "x": {"value": 1.0, "u": -0.1},
            "y": {"value": 2.0, "u": 0.2},
        },
    }
    out_neg = motor_incerteza.run_motor(neg_payload)
    validate_contract(out_neg, "schema_motor.json")
    assert out_neg["status"] == "ERRO_VALIDACAO"
    assert "não podem ser negativas" in out_neg["resultados"]["results"][0]["error"]

    # 2. Incerteza NaN
    nan_payload = {
        "operation": "propagate_gum",
        "expression": "x + y",
        "variables": {
            "x": {"value": 1.0, "u": float("nan")},
            "y": {"value": 2.0, "u": 0.2},
        },
    }
    out_nan = motor_incerteza.run_motor(nan_payload)
    validate_contract(out_nan, "schema_motor.json")
    assert out_nan["status"] == "ERRO_VALIDACAO"
    assert "deve ser finito" in out_nan["resultados"]["results"][0]["error"]


def test_propagate_gum_valid_payload_preserved() -> None:
    # Payload válido com 'u'
    valid_payload = {
        "operation": "propagate_gum",
        "expression": "x * y",
        "variables": {
            "x": {"value": 2.0, "u": 0.1},
            "y": {"value": 3.0, "u": 0.2},
        },
    }
    out = motor_incerteza.run_motor(valid_payload)
    validate_contract(out, "schema_motor.json")
    assert out["status"] == "OK"
    assert math.isclose(out["resultados"]["results"][0]["u_combined"], 0.5, rel_tol=1e-7)

    # Payload válido com 'u_random' e 'u_systematic'
    valid_split = {
        "operation": "propagate_gum",
        "expression": "x + y",
        "variables": {
            "x": {"value": 10.0, "u_random": 0.3, "u_systematic": 0.4},
            "y": {"value": 5.0, "u_random": 0.0, "u_systematic": 0.0},
        },
    }
    out_split = motor_incerteza.run_motor(valid_split)
    validate_contract(out_split, "schema_motor.json")
    assert out_split["status"] == "OK"
    assert math.isclose(out_split["resultados"]["results"][0]["u_combined"], 0.5, rel_tol=1e-7)


def test_monte_carlo_missing_key_returns_structured_error() -> None:
    # 1. Dist normal sem 'std'
    mc_no_std = {
        "operation": "monte_carlo",
        "expression": "x + y",
        "variables": {
            "x": {"value": 10.0, "u": 1.0},
            "y": {"value": 20.0, "std": 2.0},
        },
    }
    out_mc = motor_incerteza.run_motor(mc_no_std)
    validate_contract(out_mc, "schema_motor.json")
    assert out_mc["status"] == "ERRO_VALIDACAO"
    assert "requer o campo obrigatório de desvio padrão 'std'" in out_mc["resultados"]["results"][0]["error"]

    # 2. Dist uniforme sem 'half_width'
    mc_no_half = {
        "operation": "monte_carlo",
        "expression": "x + y",
        "variables": {
            "x": {"value": 10.0, "dist": "uniform"},
            "y": {"value": 20.0, "std": 2.0},
        },
    }
    out_half = motor_incerteza.run_motor(mc_no_half)
    validate_contract(out_half, "schema_motor.json")
    assert out_half["status"] == "ERRO_VALIDACAO"
    assert "requer o campo obrigatório 'half_width'" in out_half["resultados"]["results"][0]["error"]


def test_batch_isolation_with_invalid_uncertainty_items() -> None:
    batch_payload = {
        "operation": "batch",
        "operations": [
            # Item 1: Válido
            {
                "id": "OP_OK",
                "operation": "propagate_gum",
                "expression": "x * y",
                "variables": {
                    "x": {"value": 2.0, "u": 0.1},
                    "y": {"value": 3.0, "u": 0.2},
                },
            },
            # Item 2: Inválido (sem incerteza)
            {
                "id": "OP_BAD_U",
                "operation": "propagate_gum",
                "expression": "x + y",
                "variables": {"x": {"value": 1.0}, "y": {"value": 2.0}},
            },
            # Item 3: Inválido (MC sem 'std')
            {
                "id": "OP_BAD_MC",
                "operation": "monte_carlo",
                "expression": "x + y",
                "variables": {"x": {"value": 1.0, "dist": "normal"}},
            },
        ],
    }
    out_batch = motor_incerteza.run_motor(batch_payload)
    validate_contract(out_batch, "schema_motor.json")
    assert out_batch["status"] == "PARCIAL"
    assert out_batch["metricas"]["sucesso"] == 1
    assert out_batch["metricas"]["falhas"] == 2
    res = out_batch["resultados"]["results"]
    assert res[0]["success"] is True
    assert math.isclose(res[0]["u_combined"], 0.5, rel_tol=1e-7)
    assert res[1]["success"] is False
    assert res[2]["success"] is False


@pytest.mark.parametrize(
    "name,payload,expected_status,expected_success,error_substr",
    [
        (
            "u=0 explicito propagate_gum",
            {"operation": "propagate_gum", "expression": "x + 1", "variables": {"x": {"value": 10.0, "u": 0.0}}},
            "OK",
            True,
            None,
        ),
        (
            "u=0 explicito monte_carlo",
            {"operation": "monte_carlo", "expression": "x + 1", "variables": {"x": {"value": 10.0, "dist": "normal", "std": 0.0}}},
            "OK",
            True,
            None,
        ),
        (
            "uniform sem half_width",
            {"operation": "monte_carlo", "expression": "x + 1", "variables": {"x": {"value": 10.0, "dist": "uniform"}}},
            "ERRO_VALIDACAO",
            False,
            "distribuição uniforme requer o campo obrigatório 'half_width'",
        ),
        (
            "triangular sem half_width",
            {"operation": "monte_carlo", "expression": "x + 1", "variables": {"x": {"value": 10.0, "dist": "triangular"}}},
            "ERRO_VALIDACAO",
            False,
            "distribuição triangular requer o campo obrigatório 'half_width'",
        ),
        (
            "std negativo normal",
            {"operation": "monte_carlo", "expression": "x + 1", "variables": {"x": {"value": 10.0, "dist": "normal", "std": -1.0}}},
            "ERRO_VALIDACAO",
            False,
            "std negativo em 'x'",
        ),
        (
            "half_width negativo uniform",
            {"operation": "monte_carlo", "expression": "x + 1", "variables": {"x": {"value": 10.0, "dist": "uniform", "half_width": -1.0}}},
            "ERRO_VALIDACAO",
            False,
            "half_width negativo em 'x'",
        ),
        (
            "half_width negativo triangular",
            {"operation": "monte_carlo", "expression": "x + 1", "variables": {"x": {"value": 10.0, "dist": "triangular", "half_width": -1.0}}},
            "ERRO_VALIDACAO",
            False,
            "half_width negativo em 'x'",
        ),
        (
            "std NaN normal",
            {"operation": "monte_carlo", "expression": "x + 1", "variables": {"x": {"value": 10.0, "dist": "normal", "std": float("nan")}}},
            "ERRO_VALIDACAO",
            False,
            "deve ser finito (não NaN/Inf)",
        ),
        (
            "std Inf normal",
            {"operation": "monte_carlo", "expression": "x + 1", "variables": {"x": {"value": 10.0, "dist": "normal", "std": float("inf")}}},
            "ERRO_VALIDACAO",
            False,
            "deve ser finito (não NaN/Inf)",
        ),
        (
            "half_width NaN uniform",
            {"operation": "monte_carlo", "expression": "x + 1", "variables": {"x": {"value": 10.0, "dist": "uniform", "half_width": float("nan")}}},
            "ERRO_VALIDACAO",
            False,
            "deve ser finito (não NaN/Inf)",
        ),
        (
            "half_width Inf uniform",
            {"operation": "monte_carlo", "expression": "x + 1", "variables": {"x": {"value": 10.0, "dist": "uniform", "half_width": float("inf")}}},
            "ERRO_VALIDACAO",
            False,
            "deve ser finito (não NaN/Inf)",
        ),
    ],
)
def test_motor_incerteza_eleven_edge_cases(name, payload, expected_status, expected_success, error_substr):
    out = motor_incerteza.run_motor(payload)
    errors = validate_contract(out, "schema_motor.json", raise_on_error=False)
    assert not errors, f"Schema invalido no caso '{name}': {errors}"
    assert out["status"] == expected_status
    res = out["resultados"]["results"][0]
    assert res["success"] is expected_success
    if expected_success:
        assert res["status"] == "ok"
    else:
        assert error_substr in res["error"]
