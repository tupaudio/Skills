import pytest
from scripts.common.schema_validator import validate_contract
from scripts.engines.motor_estatistico import run_motor, t_test_independent, t_test_paired


def test_t_test_independent_zero_variance_with_reported_p():
    # Médias iguais (5 == 5) e variâncias nulas: 0/0
    payload = {
        "operation": "t_test_independent",
        "sample_a": [5.0, 5.0, 5.0],
        "sample_b": [5.0, 5.0, 5.0],
        "reported_p": 0.05,
    }
    out = run_motor(payload)
    errors = validate_contract(out, "schema_motor.json", raise_on_error=False)
    assert not errors, f"Schema invalido: {errors}"
    assert out["status"] == "PARCIAL"
    assert len(out["achados"]) == 1
    achado = out["achados"][0]
    assert achado["estado"] == "NAO_VERIFICADO"
    assert "0/0" in achado["descricao"]


def test_t_test_independent_zero_variance_different_means_with_reported_p():
    # Médias distintas (5 != 6) e variâncias nulas: |t| -> inf
    payload = {
        "operation": "t_test_independent",
        "sample_a": [5.0, 5.0, 5.0],
        "sample_b": [6.0, 6.0, 6.0],
        "reported_p": 0.05,
    }
    out = run_motor(payload)
    errors = validate_contract(out, "schema_motor.json", raise_on_error=False)
    assert not errors, f"Schema invalido: {errors}"
    assert out["status"] == "PARCIAL"
    assert len(out["achados"]) == 1
    achado = out["achados"][0]
    assert achado["estado"] == "NAO_VERIFICADO"
    assert "|t| -> inf" in achado["descricao"] or "não finita" in achado["descricao"]


def test_t_test_paired_zero_variance_with_reported_p():
    # Diferenças nulas (1-1, 2-2, 3-3): 0/0
    payload = {
        "operation": "t_test_paired",
        "sample_a": [1.0, 2.0, 3.0],
        "sample_b": [1.0, 2.0, 3.0],
        "reported_p": 0.04,
    }
    out = run_motor(payload)
    errors = validate_contract(out, "schema_motor.json", raise_on_error=False)
    assert not errors, f"Schema invalido: {errors}"
    assert out["status"] == "PARCIAL"
    assert len(out["achados"]) == 1
    achado = out["achados"][0]
    assert achado["estado"] == "NAO_VERIFICADO"
    assert "0/0" in achado["descricao"]


def test_t_test_paired_zero_variance_different_means_with_reported_p():
    # Diferenças constantes não nulas (5-6 = -1, sd=0): |t| -> inf
    payload = {
        "operation": "t_test_paired",
        "sample_a": [5.0, 5.0, 5.0],
        "sample_b": [6.0, 6.0, 6.0],
        "reported_p": 0.05,
    }
    out = run_motor(payload)
    errors = validate_contract(out, "schema_motor.json", raise_on_error=False)
    assert not errors, f"Schema invalido: {errors}"
    assert out["status"] == "PARCIAL"
    assert len(out["achados"]) == 1
    achado = out["achados"][0]
    assert achado["estado"] == "NAO_VERIFICADO"
    assert "|t| -> inf" in achado["descricao"] or "não finita" in achado["descricao"]


def test_t_test_zero_variance_without_reported_p():
    payload = {
        "operation": "t_test_independent",
        "sample_a": [5.0, 5.0, 5.0],
        "sample_b": [5.0, 5.0, 5.0],
    }
    out = run_motor(payload)
    errors = validate_contract(out, "schema_motor.json", raise_on_error=False)
    assert not errors, f"Schema invalido: {errors}"
    assert out["status"] == "OK"
    assert len(out["achados"]) == 0
