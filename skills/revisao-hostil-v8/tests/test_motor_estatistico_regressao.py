import pytest
from scripts.common.schema_validator import validate_contract
from scripts.engines import motor_estatistico
from scripts.engines.motor_estatistico import run_motor, t_test_independent, t_test_paired, statistical_power_two_means


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


def test_statistical_power_grid_against_scipy_nct():
    import math
    from scipy import stats
    # Grade de testes (d, n, alpha) calculando a referência dinamicamente via nct
    # Tolerância 1e-9: cálculo idêntico da formulação matemática da distribuição t não central
    for d in [0.2, 0.5, 0.8, 1.0]:
        for n in [10, 20, 30, 50, 100]:
            for alpha in [0.01, 0.05, 0.10]:
                out = motor_estatistico.statistical_power_two_means(d, n, alpha=alpha)
                df = 2 * n - 2
                nc = d * (n / 2.0) ** 0.5
                t_crit = float(stats.t.ppf(1.0 - alpha / 2.0, df=df))
                p_up = float(stats.nct.sf(t_crit, df=df, nc=nc))
                p_low_raw = stats.nct.cdf(-t_crit, df=df, nc=nc)
                p_low = float(p_low_raw) if math.isfinite(p_low_raw) else 0.0
                expected = float(min(1.0, max(0.0, p_up + p_low)))
                assert abs(out["power"] - expected) < 1e-9
                assert out["adequate_80pct"] == bool(expected >= 0.80)
