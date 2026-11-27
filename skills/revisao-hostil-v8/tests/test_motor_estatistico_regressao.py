import math
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


def test_statistical_power_independent_benchmark_cohen_80pct():
    # Âncora de referência: software G*Power (Faul et al., 2007), valor ~0.8015,
    # não tabela impressa de Cohen (que apresentava 2 casas decimais, 0.80).
    # O valor 0.80145963... vem da avaliação analítica exata da distribuição t não central do próprio SciPy (scipy.stats.nct),
    # não constituindo fonte analítica externa independente da formulação nct.
    # Validamos contra a âncora 0.8015 com tolerância metodológica de 5e-4.
    res = statistical_power_two_means(0.5, 64, alpha=0.05)
    assert abs(res["power"] - 0.8015) < 5e-4
    assert res["adequate_80pct"] is True
    assert res["nan_fallback_applied"] is False


def test_statistical_power_negative_d_invariance():
    # O poder de um teste bicaudal para duas médias depende apenas da magnitude |d| (invariância sob inversão de sinal).
    for d, n, alpha in [(0.5, 64, 0.05), (1.0, 100, 0.01)]:
        res_pos = statistical_power_two_means(d, n, alpha=alpha)
        res_neg = statistical_power_two_means(-d, n, alpha=alpha)
        assert res_pos["power"] == res_neg["power"]
        assert res_neg["effect_size_d"] == abs(-d)
        assert res_neg["nan_fallback_applied"] is False


def test_statistical_power_extreme_tail_symmetry_evaluation():
    # Em regimes extremos (ex.: d=1.0, n=100, alpha=0.01; df=198, nc=7.071, t_crit=2.6009),
    # a chamada direta stats.nct.cdf(-t_crit) do SciPy produz NaN numérico.
    # Avaliando pela forma simétrica stats.nct.sf(t_crit, df, -nc), obtém-se o valor finito 0.0,
    # mantendo nan_fallback_applied=False sem necessidade de fallback arbitrário.
    # A cota teórica da cauda inferior para nc >= 0 é estritamente <= alpha / 2 = 0.005.
    res = statistical_power_two_means(1.0, 100, alpha=0.01)
    assert math.isfinite(res["power"])
    assert 0.99999 <= res["power"] <= 1.0
    assert res["adequate_80pct"] is True
    assert res["nan_fallback_applied"] is False


def test_statistical_power_nan_fallback_branch_coverage(monkeypatch):
    # Cobre explicitamente o ramo de salvaguarda quando scipy.stats.nct.sf retorna NaN numérico na cauda inferior.
    from scipy import stats

    original_sf = stats.nct.sf

    def mock_sf(t, df, nc):
        # Se for a cauda inferior (nc < 0), simula retorno de NaN numérico
        if nc < 0:
            return float("nan")
        return original_sf(t, df=df, nc=nc)

    monkeypatch.setattr(stats.nct, "sf", mock_sf)
    res = statistical_power_two_means(1.0, 100, alpha=0.01)
    assert res["nan_fallback_applied"] is True
    assert math.isfinite(res["power"])
    assert 0.0 <= res["power"] <= 1.0
    assert res["adequate_80pct"] is True


@pytest.mark.parametrize(
    "d,n,alpha",
    [
        (d, n, alpha)
        for d in [0.2, 0.5, 0.8, 1.0]
        for n in [10, 20, 30, 50, 100]
        for alpha in [0.01, 0.05, 0.10]
    ],
)
def test_statistical_power_grid_against_scipy_nct(d, n, alpha):
    import math
    from scipy import stats

    out = statistical_power_two_means(d, n, alpha=alpha)
    df = 2 * n - 2
    nc = d * (n / 2.0) ** 0.5
    t_crit = float(stats.t.ppf(1.0 - alpha / 2.0, df=df))
    p_up = float(stats.nct.sf(t_crit, df=df, nc=nc))
    p_low_raw = stats.nct.sf(t_crit, df=df, nc=-nc)
    p_low = float(p_low_raw) if math.isfinite(p_low_raw) else 0.0
    expected = float(min(1.0, max(0.0, p_up + p_low)))
    assert abs(out["power"] - expected) < 1e-9
    assert out["adequate_80pct"] == bool(expected >= 0.80)
