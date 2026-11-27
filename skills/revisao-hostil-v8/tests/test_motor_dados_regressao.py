import pytest
from scripts.common.schema_validator import validate_contract
from scripts.engines.motor_dados import run_motor, pvalue_distribution_screen


def test_pvalue_distribution_screen_sample_too_small():
    # Com 6 observações e min_n padrão de 10: status sample_too_small
    payload = {
        "operation": "pvalue_distribution_screen",
        "p_values": [0.045, 0.048, 0.049, 0.042, 0.047, 0.01],
    }
    out = run_motor(payload)
    errors = validate_contract(out, "schema_motor.json", raise_on_error=False)
    assert not errors, f"Schema invalido: {errors}"
    assert out["status"] == "OK"
    res = out["resultados"]["results"][0]
    assert res["status"] == "sample_too_small"
    assert res["investigation_recommended"] is False
    assert res["total_p_values"] == 6
    assert res["min_n"] == 10
    assert len(out["achados"]) == 0


def test_pvalue_distribution_screen_custom_min_n():
    # Com 5 observações e min_n customizado de 5: status ok e investigação sinalizada
    payload = {
        "operation": "pvalue_distribution_screen",
        "p_values": [0.041, 0.042, 0.043, 0.044, 0.045],
        "min_n": 5,
    }
    out = run_motor(payload)
    errors = validate_contract(out, "schema_motor.json", raise_on_error=False)
    assert not errors, f"Schema invalido: {errors}"
    res = out["resultados"]["results"][0]
    assert res["status"] == "ok"
    assert res["investigation_recommended"] is True
    assert res["min_n"] == 5


def test_pvalue_distribution_screen_invalid_min_n():
    payload = {
        "operation": "pvalue_distribution_screen",
        "p_values": [0.01, 0.02],
        "min_n": 0,
    }
    out = run_motor(payload)
    errors = validate_contract(out, "schema_motor.json", raise_on_error=False)
    assert not errors, f"Schema invalido: {errors}"
    assert out["status"] == "ERRO_VALIDACAO"
    res = out["resultados"]["results"][0]
    assert res["success"] is False
    assert "min_n deve ser >= 1" in res["error"]
