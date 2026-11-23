"""Testes de aceitação dos 5 motores científicos universais (Fase 3 / v8.0-beta.3)."""

from __future__ import annotations

import math

import pytest

from scripts.common.schema_validator import validate_contract
from scripts.engines import (
    motor_dados,
    motor_dimensional,
    motor_estatistico,
    motor_geometrico,
    motor_incerteza,
)


# =========================================================================
# 1. MOTOR DIMENSIONAL
# =========================================================================
def test_dimensional_homogeneity_and_incompatibility() -> None:
    # F = m * a (homogênea)
    ok = motor_dimensional.run_motor(
        {
            "id": "eq_newton",
            "operation": "equation_homogeneity",
            "lhs": "F",
            "rhs": "m * a",
            "variable_units": {"F": "N", "m": "kg", "a": "m/s^2"},
        }
    )
    validate_contract(ok, "schema_motor.json")
    assert ok["status"] == "OK"

    # Equação dimensionalmente incompatível: soma de distância com tempo (critério Passo 3.6)
    bad = motor_dimensional.run_motor(
        {
            "id": "eq_bad",
            "operation": "equation_homogeneity",
            "lhs": "d",
            "rhs": "v * t + t",
            "variable_units": {"d": "m", "v": "m/s", "t": "s"},
        }
    )
    validate_contract(bad, "schema_motor.json")
    assert bad["status"] == "COM_ACHADOS"
    assert bad["resultados"]["results"][0]["homogeneous"] is False


def test_dimensional_temperature_and_power_vs_energy() -> None:
    c2k = motor_dimensional.convert_unit(25.0, "°C", "K")
    assert math.isclose(c2k["converted_value"], 298.15, rel_tol=1e-9)

    # Temperatura absoluta vs diferença de temperatura deve ser bloqueada
    bad_temp = motor_dimensional.convert_unit(25.0, "degC", "delta_degC")
    assert bad_temp["compatible"] is False

    # Potência declarada com unidade de energia (kWh) -> discrepância
    pe = motor_dimensional.run_motor({"id": "pe_1", "operation": "power_vs_energy", "quantity_kind": "power", "unit": "kWh"})
    validate_contract(pe, "schema_motor.json")
    assert pe["status"] == "COM_ACHADOS"


# =========================================================================
# 2. MOTOR ESTATÍSTICO
# =========================================================================
def test_statistical_operations_and_invalid_input_rejection() -> None:
    payload = {
        "operation": "batch",
        "operations": [
            {"id": "t_ind", "operation": "t_test_independent", "sample_a": [10, 11, 12, 10.5, 11.5], "sample_b": [20, 21, 19, 20.5, 22]},
            {"id": "t_pair", "operation": "t_test_paired", "sample_a": [1, 2, 3, 4], "sample_b": [2, 3, 4, 6]},
            {"id": "mw", "operation": "mann_whitney", "sample_a": [1, 2, 3], "sample_b": [8, 9, 10]},
            {"id": "anova", "operation": "anova_oneway", "groups": [[1, 2, 3], [5, 6, 7], [10, 11, 12]]},
            {"id": "ci", "operation": "confidence_interval", "sample": [10, 12, 11, 13, 12]},
            {"id": "tost", "operation": "tost_equivalence", "sample_a": [10.0, 10.1, 9.9, 10.0], "sample_b": [10.05, 9.95, 10.0, 10.02], "low_bound": -0.5, "high_bound": 0.5},
            {"id": "mc", "operation": "multiple_comparisons", "p_values": [0.01, 0.04, 0.20], "method": "holm"},
            {"id": "boot", "operation": "bootstrap_ci", "sample": [1, 2, 3, 4, 5], "n_resamples": 500, "seed": 7},
            {"id": "perm", "operation": "permutation_test", "sample_a": [1, 2, 3], "sample_b": [10, 11, 12], "n_permutations": 500, "seed": 7},
            {"id": "pwr", "operation": "statistical_power", "effect_size_d": 0.8, "n_per_group": 30},
            {"id": "assump", "operation": "assumptions_check", "groups": [[1, 2, 3, 4, 5], [2, 3, 4, 5, 6]]},
            {"id": "acf", "operation": "autocorrelation", "series": [1, 2, 3, 4, 5, 6, 7, 8]},
        ],
    }
    out = motor_estatistico.run_motor(payload, run_id="TEST-EST-01")
    validate_contract(out, "schema_motor.json")
    assert out["status"] == "OK"
    assert out["metricas"]["sucesso"] == 12

    # Critério Passo 3.6: teste estatístico com amostras inválidas (NaN) deve ser rejeitado
    bad = motor_estatistico.run_motor(
        {"id": "bad_nan", "operation": "t_test_independent", "sample_a": [1.0, float("nan")], "sample_b": [2.0, 3.0]}
    )
    validate_contract(bad, "schema_motor.json")
    assert bad["status"] == "ERRO_VALIDACAO"


# =========================================================================
# 3. MOTOR GEOMÉTRICO
# =========================================================================
def test_geometric_polygon_solid_view_factor_and_invalid_matrix() -> None:
    # Área de polígono conhecido (retângulo 4x3 = 12)
    poly = motor_geometrico.polygon_2d([[0, 0], [4, 0], [4, 3], [0, 3]], reported_area=12.0)
    assert math.isclose(poly["area"], 12.0, rel_tol=1e-9)
    assert poly["status"] == "ok"

    # Matriz geométrica inválida (não ortogonal) -> detectada
    bad_rot = motor_geometrico.run_motor({"id": "rot_bad", "operation": "validate_rotation_matrix", "matrix": [[2, 0], [0, 1]]})
    validate_contract(bad_rot, "schema_motor.json")
    assert bad_rot["status"] == "COM_ACHADOS"

    # Fator de forma radiativo (reciprocidade A1*F12 == A2*F21)
    vf = motor_geometrico.view_factor_coaxial_disks(r1=1.0, r2=2.0, distance=1.5)
    assert 0.0 < vf["F12"] < 1.0
    assert vf["reciprocity_residual"] < 1e-12

    # Casca fina: 2 m^2 * 0.01 m * 2700 kg/m^3 = 54 kg
    shell = motor_geometrico.shell_mass_consistency(2.0, 0.01, 2700.0, reported_mass_kg=54.0)
    assert shell["status"] == "ok"


# =========================================================================
# 4. MOTOR DE INCERTEZA
# =========================================================================
def test_uncertainty_gum_and_monte_carlo_reference() -> None:
    # V = I * R -> I=2 +- 0.1, R=10 +- 0.5 -> V=20, u_c = sqrt((10*0.1)^2 + (2*0.5)^2) = sqrt(2)
    gum = motor_incerteza.propagate_gum(
        "I * R",
        {"I": {"value": 2.0, "u_random": 0.1}, "R": {"value": 10.0, "u_systematic": 0.5}},
        reported_uncertainty=math.sqrt(2.0),
    )
    assert gum["status"] == "ok"
    assert math.isclose(gum["u_combined"], math.sqrt(2.0), rel_tol=1e-9)
    assert math.isclose(gum["worst_case_delta"], 2.0, rel_tol=1e-9)

    mc = motor_incerteza.monte_carlo_propagation(
        "I * R",
        {"I": {"value": 2.0, "dist": "normal", "std": 0.1}, "R": {"value": 10.0, "dist": "normal", "std": 0.5}},
        n_samples=20000,
        seed=42,
    )
    assert math.isclose(mc["mean"], 20.0, rel_tol=0.02)
    assert math.isclose(mc["std"], math.sqrt(2.0), rel_tol=0.05)

    out = motor_incerteza.run_motor(
        {"id": "inc_1", "operation": "propagate_gum", "expression": "I * R", "variables": {"I": {"value": 2.0, "u": 0.1}, "R": {"value": 10.0, "u": 0.5}}, "reported_uncertainty": 0.1}
    )
    validate_contract(out, "schema_motor.json")
    assert out["status"] == "COM_ACHADOS"


# =========================================================================
# 5. MOTOR DE DADOS (COM RESTRIÇÕES METODOLÓGICAS)
# =========================================================================
def test_data_integrity_missing_leakage_and_ethical_guardrails() -> None:
    rows = [
        {"id": 1, "temp": 25.0},
        {"id": 2, "temp": None},
        {"id": 1, "temp": 25.0},
        {"id": 3, "temp": 999.0},
    ]
    tab = motor_dados.audit_tabular_quality(rows, key_column="id", numeric_bounds={"temp": {"min": -50, "max": 200}})
    assert tab["total_missing_cells"] == 1
    assert tab["duplicate_row_count"] == 1
    assert len(tab["invalid_values"]) == 1
    # Restrição metodológica obrigatória: nunca classifica MAR/MNAR sozinho
    assert tab["missingness_mechanism_classified"] is False

    # Triagem de valores-p: nunca declara p-hacking/fraude
    p_screen = motor_dados.pvalue_distribution_screen([0.045, 0.048, 0.049, 0.042, 0.047, 0.01])
    assert p_screen["investigation_recommended"] is True
    assert p_screen["declares_phacking_or_fraud"] is False

    # Vazamento de dados em ML (sobreposição treino/teste) -> CRÍTICO
    leak_out = motor_dados.run_motor(
        {
            "id": "ml_split",
            "operation": "ml_leakage_audit",
            "train_ids": [1, 2, 3, 4],
            "test_ids": [4, 5, 6],
            "train_timestamps": [10, 20, 30, 40],
            "test_timestamps": [35, 50, 60],
        }
    )
    validate_contract(leak_out, "schema_motor.json")
    assert leak_out["status"] == "COM_ACHADOS"
    assert leak_out["achados"][0]["gravidade"] == "CRITICO"
