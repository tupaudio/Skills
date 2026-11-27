"""Bateria de validação analítica e comparativa com scipy/numpy para os 5 motores prioritários.

Motores cobertos:
- motor_estatistico
- motor_dimensional
- motor_dados
- motor_incerteza
- motor_consistencia_cruzada

Operações explicitamente NÃO comparadas numericamente nesta suíte (métodos estocásticos ou triagens heurísticas):
- expression_dimension (motor_dimensional)
- sample_vs_reported (motor_dados)
- assumptions_check (motor_estatistico)
- bootstrap_ci (motor_estatistico)
- permutation_test (motor_estatistico)
- autocorrelation (motor_estatistico)
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pytest
import scipy.stats as stats

from scripts.common.schema_validator import validate_contract
from scripts.engines import (
    motor_consistencia_cruzada,
    motor_dados,
    motor_dimensional,
    motor_estatistico,
    motor_incerteza,
)


# =========================================================================
# 1. MOTOR_ESTATISTICO
# =========================================================================

def test_t_test_independent_vs_scipy() -> None:
    sample_a = [10.0, 12.0, 14.0, 16.0]
    sample_b = [20.0, 22.0, 24.0, 26.0]

    # Referência scipy Welch t-test
    sci_res = stats.ttest_ind(sample_a, sample_b, equal_var=False)
    motor_res = motor_estatistico.t_test_independent(sample_a, sample_b, equal_var=False)

    assert math.isclose(motor_res["statistic"], float(sci_res.statistic), rel_tol=1e-7)
    assert math.isclose(motor_res["p_value"], float(sci_res.pvalue), rel_tol=1e-7)


def test_t_test_paired_vs_scipy() -> None:
    sample_a = [10.0, 12.0, 15.0, 16.0]
    sample_b = [20.0, 21.0, 24.0, 28.0]

    # Referência scipy paired t-test
    sci_res = stats.ttest_rel(sample_a, sample_b)
    motor_res = motor_estatistico.t_test_paired(sample_a, sample_b)

    assert math.isclose(motor_res["statistic"], float(sci_res.statistic), rel_tol=1e-7)
    assert math.isclose(motor_res["p_value"], float(sci_res.pvalue), rel_tol=1e-7)


def test_t_test_negative_case_reported_p_discrepancy() -> None:
    # Caso negativo: reported_p muito divergente do p-value real recalculado
    sample_a = [10.0, 12.0, 14.0, 16.0]
    sample_b = [20.0, 22.0, 24.0, 26.0]
    # p-value real ~ 0.00155, reported_p falso = 0.50
    out = motor_estatistico.run_motor(
        {
            "operation": "t_test_independent",
            "sample_a": sample_a,
            "sample_b": sample_b,
            "reported_p": 0.50,
        }
    )
    validate_contract(out, "schema_motor.json")
    assert out["status"] == "COM_ACHADOS"
    assert len(out["achados"]) == 1
    assert "discrepancia_estatistica" in out["achados"][0]["categoria"]


def test_mann_whitney_vs_scipy() -> None:
    sample_a = [10.0, 12.0, 14.0, 16.0]
    sample_b = [20.0, 22.0, 24.0, 26.0]

    # Referência scipy Mann-Whitney bicaudal
    sci_res = stats.mannwhitneyu(sample_a, sample_b, alternative="two-sided")
    motor_res = motor_estatistico.mann_whitney(sample_a, sample_b)

    assert math.isclose(motor_res["statistic_U"], float(sci_res.statistic), rel_tol=1e-7)
    assert math.isclose(motor_res["p_value"], float(sci_res.pvalue), rel_tol=1e-7)


def test_anova_oneway_vs_scipy() -> None:
    g1, g2, g3 = [1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]

    # Referência scipy ANOVA one-way
    sci_res = stats.f_oneway(g1, g2, g3)
    motor_res = motor_estatistico.anova_oneway([g1, g2, g3])

    assert math.isclose(motor_res["F_statistic"], float(sci_res.statistic), rel_tol=1e-7)
    assert math.isclose(motor_res["p_value"], float(sci_res.pvalue), rel_tol=1e-7)


def test_confidence_interval_vs_scipy() -> None:
    sample = [10.0, 11.0, 12.0, 10.5, 11.5]
    arr = np.array(sample, dtype=float)

    # Referência scipy t-interval
    ci_low, ci_high = stats.t.interval(
        0.95, df=len(arr) - 1, loc=float(np.mean(arr)), scale=float(stats.sem(arr))
    )
    motor_res = motor_estatistico.confidence_interval(sample, confidence=0.95)

    assert math.isclose(motor_res["lower"], float(ci_low), rel_tol=1e-7)
    assert math.isclose(motor_res["upper"], float(ci_high), rel_tol=1e-7)


def test_tost_equivalence_analytical() -> None:
    # Dois grupos com variabilidade e médias próximas dentro dos limites [-1.0, 1.0]
    s1 = [10.0, 10.5, 9.5, 10.0]
    s2 = [10.1, 10.4, 9.6, 9.9]

    motor_res = motor_estatistico.tost_equivalence(s1, s2, low_bound=-1.0, high_bound=1.0)
    assert motor_res["equivalent"] is True
    assert motor_res["p_tost"] < 0.05


def test_multiple_comparisons_holm_analytical() -> None:
    raw_p = [0.01, 0.04, 0.03]
    # Holm-Bonferroni passo a passo:
    # Ordenado: p[0]=0.01 (k=1, mult=3 -> 0.03)
    #           p[2]=0.03 (k=2, mult=2 -> 0.06)
    #           p[1]=0.04 (k=3, mult=1 -> 0.04, ajustado para max acumulado: 0.06)
    # Resultado esperado na ordem original: [0.03, 0.06, 0.06]
    motor_res = motor_estatistico.multiple_comparisons(raw_p, method="holm")
    assert motor_res["adjusted_p_values"] == [0.03, 0.06, 0.06]


# =========================================================================
# 2. MOTOR_DIMENSIONAL
# =========================================================================

def test_convert_unit_temperature_and_metric() -> None:
    # 25 °C = 298.15 K
    deg_c = motor_dimensional.convert_unit(25.0, "°C", "K")
    assert math.isclose(deg_c["converted_value"], 298.15, rel_tol=1e-9)

    # 1000 m = 1 km
    dist = motor_dimensional.convert_unit(1000.0, "m", "km")
    assert math.isclose(dist["converted_value"], 1.0, rel_tol=1e-9)


def test_convert_unit_negative_case_incompatible_dimensions() -> None:
    # Caso negativo: tentar converter massa (kg) em comprimento (m)
    res = motor_dimensional.convert_unit(10.0, "kg", "m")
    assert res["compatible"] is False
    assert res["status"] == "discrepancy_detected"
    assert "Dimensões incompatíveis" in res["error"]


def test_equation_homogeneity_analytical() -> None:
    # Segunda Lei de Newton: F = m * a -> [M L T^-2] = [M] * [L T^-2]
    res_ok = motor_dimensional.check_equation_homogeneity(
        "F", "m * a", {"F": "N", "m": "kg", "a": "m/s^2"}
    )
    assert res_ok["homogeneous"] is True

    # Equação não homogênea: F = m + a (massa somada à aceleração)
    res_bad = motor_dimensional.check_equation_homogeneity(
        "F", "m + a", {"F": "N", "m": "kg", "a": "m/s^2"}
    )
    assert res_bad["homogeneous"] is False


def test_power_vs_energy_distinction() -> None:
    # Potência declarada com kWh (energia)
    res = motor_dimensional.check_power_vs_energy("potencia", "kWh")
    assert res["consistent"] is False
    assert res["status"] == "discrepancy_detected"


# =========================================================================
# 3. MOTOR_DADOS
# =========================================================================

def test_audit_tabular_quality_analytical() -> None:
    rows = [{"a": 1, "b": 2}, {"a": None, "b": 4}]
    res = motor_dados.audit_tabular_quality(rows)
    assert res["total_missing_cells"] == 1


def test_detect_outliers_tukey_iqr() -> None:
    # Amostra: [1, 2, 2, 3, 2, 100]
    # Método de quartil utilizado pelo motor: np.percentile (método padrão linear 'weibull'/'linear' de numpy)
    # Para [1, 2, 2, 2, 3, 100], Q1=2.0, Q3=2.75, IQR=0.75
    # Cerca superior = Q3 + 1.5 * IQR = 2.75 + 1.125 = 3.875 -> 100 > 3.875 (detectado outlier)
    sample = [1, 2, 2, 3, 2, 100]
    res = motor_dados.detect_outliers(sample)
    assert 5 in res["iqr_outlier_indices"]  # índice do valor 100


def test_ml_leakage_audit_exact_intersection() -> None:
    # Interseção de conjuntos: {1, 2, 3, 4} e {4, 5, 6} -> {4} (1 elemento de overlap)
    train_ids = [1, 2, 3, 4]
    test_ids = [4, 5, 6]
    res = motor_dados.ml_leakage_audit(train_ids, test_ids)
    assert res["overlap_train_test_count"] == 1
    assert res["leakage_detected"] is True


def test_pvalue_distribution_screen_analytical() -> None:
    # Razão em [0.04, 0.05]: 10 valores para atingir min_n padrão (todos no intervalo crítico)
    pvals = [0.041, 0.042, 0.043, 0.044, 0.045, 0.046, 0.047, 0.048, 0.049, 0.0495]
    res = motor_dados.pvalue_distribution_screen(pvals)
    assert math.isclose(res["ratio_near_threshold"], 1.0, rel_tol=1e-7)


# =========================================================================
# 4. MOTOR_INCERTEZA
# =========================================================================

def test_propagate_gum_analytical_multiplication() -> None:
    # z = x * y, com x = 2.0 +- 0.1 e y = 3.0 +- 0.2
    # Derivadas parciais: dz/dx = y = 3.0; dz/dy = x = 2.0
    # u_c = sqrt((3.0 * 0.1)^2 + (2.0 * 0.2)^2) = sqrt(0.09 + 0.16) = sqrt(0.25) = 0.5
    res = motor_incerteza.propagate_gum(
        "x * y",
        {"x": {"value": 2.0, "u": 0.1}, "y": {"value": 3.0, "u": 0.2}},
    )
    assert math.isclose(res["u_combined"], 0.5, rel_tol=1e-7)


def test_monte_carlo_propagation_sum_of_normals() -> None:
    # z = x + y, x ~ N(10, 1^2), y ~ N(20, 2^2)
    # Pela teoria de probabilidades:
    # E[z] = 10 + 20 = 30
    # Var[z] = Var[x] + Var[y] = 1 + 4 = 5 -> SD[z] = sqrt(5) ~= 2.236068
    res = motor_incerteza.monte_carlo_propagation(
        "x + y",
        {"x": {"value": 10.0, "std": 1.0}, "y": {"value": 20.0, "std": 2.0}},
        n_samples=50000,
        seed=42,
    )
    assert math.isclose(res["mean"], 30.0, rel_tol=0.01)
    assert math.isclose(res["std"], math.sqrt(5.0), rel_tol=0.02)


# =========================================================================
# 5. MOTOR_CONSISTENCIA_CRUZADA
# =========================================================================

def test_check_quantity_consistency_agreement() -> None:
    # 1000 m vs 1 km -> após normalização de unidade, resíduo é 0
    res = motor_consistencia_cruzada.check_quantity_consistency(
        "Q_dist",
        [
            {"source_type": "tabela", "value": 1000.0, "unit": "m", "location": "tab1"},
            {"source_type": "texto", "value": 1.0, "unit": "km", "location": "p.2"},
        ],
    )
    assert res["status"] == "ok"
    assert len(res["divergences"]) == 0


def test_check_quantity_consistency_negative_divergence_detected() -> None:
    # Caso negativo: 1000 m vs 1.5 km -> divergência de 50%
    out = motor_consistencia_cruzada.run_motor(
        {
            "quantities": [
                {
                    "quantity_id": "Q_div",
                    "observations": [
                        {"source_type": "tabela", "value": 1000.0, "unit": "m", "location": "tab1"},
                        {"source_type": "texto", "value": 1.5, "unit": "km", "location": "p.2"},
                    ],
                }
            ]
        }
    )
    validate_contract(out, "schema_motor.json")
    assert out["status"] == "COM_ACHADOS"
    assert len(out["achados"]) == 1
    assert "divergencia_consistencia_cruzada" in out["achados"][0]["categoria"]


def test_check_quantity_consistency_negative_incompatible_units() -> None:
    # Caso negativo: grandeza comparada entre metros e segundos (incompatível)
    res = motor_consistencia_cruzada.check_quantity_consistency(
        "Q_bad_dim",
        [
            {"source_type": "tabela", "value": 10.0, "unit": "m", "location": "tab1"},
            {"source_type": "texto", "value": 10.0, "unit": "s", "location": "p.2"},
        ],
    )
    assert res["status"] == "discrepancy_detected"
    assert len(res["divergences"]) == 1
    assert "Dimensões incompatíveis" in res["divergences"][0]["reason"]
