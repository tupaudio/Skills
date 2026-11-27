"""Testes de robustez de processamento em lotes e isolamento de falhas para os 11 motores afetados."""

from __future__ import annotations

import pytest

from scripts.common.schema_validator import validate_contract
from scripts.engines import (
    motor_consistencia_cruzada,
    motor_dados,
    motor_dimensional,
    motor_estatistico,
    motor_etica,
    motor_figuras,
    motor_geometrico,
    motor_imagem_forense,
    motor_incerteza,
    motor_qualitativo,
    motor_risco,
)


@pytest.mark.parametrize(
    ("engine_mod", "valid_op", "prefix"),
    [
        (
            motor_dados,
            {"id": "op_valid", "operation": "tabular_quality", "rows": [{"col": 1}, {"col": 2}]},
            "DAT",
        ),
        (
            motor_dimensional,
            {"id": "op_valid", "operation": "convert_unit", "value": 1000.0, "from_unit": "m", "to_unit": "km", "reported_value": 1.0},
            "DIM",
        ),
        (
            motor_estatistico,
            {"id": "op_valid", "operation": "confidence_interval", "sample": [10, 11, 12, 10.5, 11.5]},
            "EST",
        ),
        (
            motor_etica,
            {"id": "op_valid", "operation": "screen_ethics_declarations", "text": "This study was approved by the Institutional Ethics Committee."},
            "ETI",
        ),
        (
            motor_figuras,
            {"id": "op_valid", "operation": "build_visual_inventory", "items": []},
            "FIG",
        ),
        (
            motor_geometrico,
            {"id": "op_valid", "operation": "solid_3d", "shape": "sphere", "dimensions": {"radius": 1.0}},
            "GEO",
        ),
        (
            motor_imagem_forense,
            {"id": "op_valid", "operation": "check_image_duplicates", "file_paths": []},
            "IMF",
        ),
        (
            motor_incerteza,
            {
                "id": "op_valid",
                "operation": "propagate_gum",
                "expression": "x + y",
                "variables": {
                    "x": {"value": 10.0, "standard_uncertainty": 0.1},
                    "y": {"value": 5.0, "standard_uncertainty": 0.2},
                },
            },
            "INC",
        ),
        (
            motor_qualitativo,
            {"id": "op_valid", "operation": "cohens_kappa", "coder_a": ["sim", "nao"], "coder_b": ["sim", "nao"]},
            "QUA",
        ),
        (
            motor_risco,
            {"id": "op_valid", "operation": "evaluate_risk_matrix", "hazard": "Ruido", "probability": 2, "severity": 3},
            "RSK",
        ),
    ],
)
def test_batch_mixed_malformed_items_preserves_valid_and_isolates_failure(engine_mod, valid_op, prefix: str) -> None:
    # 1. Lote misto: item válido + None + string + int
    payload = {
        "operation": "batch",
        "operations": [
            valid_op,
            None,
            "string_invalida",
            999,
        ],
    }

    report = engine_mod.run_motor(payload)
    validate_contract(report, "schema_motor.json")

    assert report["status"] == "PARCIAL"
    metrics = report["metricas"]
    assert metrics["sucesso"] == 1
    assert metrics["falhas"] == 3
    assert metrics["total_operacoes"] == 4

    results = report["resultados"]["results"]
    assert len(results) == 4

    # Item válido preservado
    assert results[0]["id"] == "op_valid"
    assert results[0]["success"] is True

    # Itens inválidos isolados com mensagem clara sem traceback
    for idx, r in enumerate(results[1:], start=2):
        assert r["id"] == f"{prefix}_{idx:03d}"
        assert r["success"] is False
        assert r["status"] == "error"
        assert "Item de lote inválido" in r["error"]


@pytest.mark.parametrize(
    ("engine_mod", "prefix"),
    [
        (motor_dados, "DAT"),
        (motor_dimensional, "DIM"),
        (motor_estatistico, "EST"),
        (motor_etica, "ETI"),
        (motor_figuras, "FIG"),
        (motor_geometrico, "GEO"),
        (motor_imagem_forense, "IMF"),
        (motor_incerteza, "UNC"),
        (motor_qualitativo, "QUA"),
        (motor_risco, "RSK"),
    ],
)
def test_batch_completely_invalid_returns_validation_error(engine_mod, prefix: str) -> None:
    # Lote totalmente inválido não pode ser OK nem PARCIAL; deve ser ERRO_VALIDACAO
    payload = {
        "operation": "batch",
        "operations": [None, 42],
    }

    report = engine_mod.run_motor(payload)
    validate_contract(report, "schema_motor.json")

    assert report["status"] == "ERRO_VALIDACAO"
    assert report["metricas"]["sucesso"] == 0
    assert report["metricas"]["falhas"] == 2
    assert len(report["resultados"]["results"]) == 2


def test_motor_consistencia_cruzada_quantities_isolation() -> None:
    # 1. Lote misto de grandezas: quantidade válida + None + string
    valid_q = {
        "quantity_id": "P_NOM",
        "observations": [
            {"source_type": "texto", "location": "p.1", "value": 100.0, "unit": "W"},
            {"source_type": "tabela", "location": "tab.1", "value": 100.0, "unit": "W"},
        ],
    }
    payload = {
        "quantities": [
            valid_q,
            None,
            "grandeza_invalida",
        ]
    }

    report = motor_consistencia_cruzada.run_motor(payload)
    validate_contract(report, "schema_motor.json")

    assert report["status"] == "PARCIAL"
    metrics = report["metricas"]
    assert metrics["sucesso"] == 1
    assert metrics["falhas"] == 2
    assert metrics["total_grandezas"] == 3

    quantities = report["resultados"]["quantities"]
    assert len(quantities) == 3
    assert quantities[0]["quantity_id"] == "P_NOM"
    assert quantities[0]["success"] is True

    assert quantities[1]["quantity_id"] == "Q_002"
    assert quantities[1]["success"] is False
    assert "Item de quantidade inválido" in quantities[1]["error"]

    assert quantities[2]["quantity_id"] == "Q_003"
    assert quantities[2]["success"] is False

    # 2. Todas inválidas
    all_invalid = motor_consistencia_cruzada.run_motor({"quantities": [None, 123]})
    validate_contract(all_invalid, "schema_motor.json")
    assert all_invalid["status"] == "ERRO_VALIDACAO"
    assert all_invalid["metricas"]["sucesso"] == 0
    assert all_invalid["metricas"]["falhas"] == 2
