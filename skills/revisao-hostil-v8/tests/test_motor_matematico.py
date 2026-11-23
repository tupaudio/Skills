"""Testes unitários, negativos, segurança e regressão do motor_matematico.py (Beta 2)."""

from __future__ import annotations

import math

import pytest

from scripts.common.schema_validator import validate_contract
from scripts.engines.motor_matematico import MathematicalFirewall, SafeExpressionParser, run_motor


def test_all_13_operations_batch_and_schema_contract() -> None:
    payload = {
        "operation": "batch",
        "operations": [
            {"id": "op_plug_in", "operation": "plug_in", "expression": "2*x + 3", "substitutions": {"x": 4}, "reported_value": 11.0},
            {"id": "op_formula", "operation": "formula", "lhs": "(x+1)^2", "rhs": "x^2 + 2*x + 1"},
            {"id": "op_simplify", "operation": "simplify", "expression": "(x^2 - 1)/(x - 1)"},
            {"id": "op_diff", "operation": "differentiate", "expression": "x^3 + sin(x)", "variable": "x", "order": 2},
            {"id": "op_int_def", "operation": "integrate", "expression": "x^2", "variable": "x", "lower": 0, "upper": 3},
            {"id": "op_linsys", "operation": "linear_system", "matrix": [[2, 1], [1, 3]], "vector": [5, 7]},
            {"id": "op_matrix", "operation": "matrix", "matrix": [[2, 0], [0, 3]]},
            {"id": "op_ode_ivp", "operation": "ode_ivp", "rhs": ["-k*y0"], "t_span": [0, 1], "y0": [1.0], "parameters": {"k": 2.0}},
            {
                "id": "op_ode_bvp",
                "operation": "ode_bvp",
                "rhs": ["y1", "-y0"],
                "boundary_conditions": ["ya0", "yb0 - 1"],
                "interval": [0, math.pi / 2],
            },
            {"id": "op_ode_sym", "operation": "ode_symbolic", "rhs": "-2*y", "independent": "x", "dependent": "y", "initial": {"x0": 0, "y0": 1}},
            {"id": "op_mpc", "operation": "mpc_feasibility", "x0": {"T": 280}, "constraints": {"T": {"min": 250, "max": 300}}},
            {"id": "op_energy", "operation": "energy_profile", "time_seconds": [0, 3600], "generation_w": [100, 100], "load_w": [80, 80]},
            {"id": "op_ahp", "operation": "ahp_matrix", "matrix": [[1, 3, 5], [1 / 3, 1, 2], [1 / 5, 0.5, 1]]},
        ],
    }

    out = run_motor(payload, run_id="TEST-BATCH-01")
    validate_contract(out, "schema_motor.json")
    assert out["status"] == "OK"
    assert out["resultados"]["succeeded"] == 13
    assert out["resultados"]["failed"] == 0


def test_def_m01_non_finite_matrix_and_linear_system_rejected() -> None:
    with pytest.raises(ValueError, match="não finitos"):
        MathematicalFirewall.audit_matrix([[1.0, float("nan")], [0.0, 1.0]])

    with pytest.raises(ValueError, match="não finitos"):
        MathematicalFirewall.solve_linear_system([[1.0, float("inf")], [0.0, 1.0]], [1.0, 2.0])


def test_def_m02_complex_result_flagged_against_real_reported() -> None:
    out = run_motor(
        {"id": "eq_complex", "operation": "plug_in", "expression": "log(-1)", "substitutions": {}, "reported_value": 0.0}
    )
    validate_contract(out, "schema_motor.json")
    assert out["resultados"]["status"] == "complex_result_vs_real_reported"
    assert out["resultados"]["matches_within_tolerance"] is False
    assert out["status"] == "COM_ACHADOS"
    assert len(out["achados"]) == 1


def test_def_m03_integrate_infinite_limit() -> None:
    res = MathematicalFirewall.integrate("exp(-x)", "x", lower=0, upper="oo")
    assert res["result"] == "1"
    assert math.isclose(res["numeric_result"], 1.0, rel_tol=1e-9)


def test_def_m04_ode_bvp_validates_interval_and_supports_parameters() -> None:
    with pytest.raises(ValueError, match="não coincidem com interval"):
        MathematicalFirewall.solve_ode_bvp(
            rhs=["y1", "-y0"],
            boundary_conditions=["ya0", "yb0 - 1"],
            interval=[0.0, 1.0],
            mesh=[0.0, 0.5, 2.0],
        )

    res = MathematicalFirewall.solve_ode_bvp(
        rhs=["y1", "-k*y0"],
        boundary_conditions=["ya0", "yb0 - 1"],
        interval=[0.0, math.pi / 2],
        parameters={"k": 1.0},
    )
    assert res["solver_success"] is True


def test_def_m05_ode_ivp_rejects_non_numeric_parameter() -> None:
    with pytest.raises(ValueError, match="número real finito"):
        MathematicalFirewall.solve_ode_ivp(
            rhs=["-k*y0"], t_span=[0, 1], y0=[1.0], parameters={"k": "invalido"}
        )


def test_def_m06_lowercase_e_not_hijacked_as_euler() -> None:
    res_missing = MathematicalFirewall.plug_in_check("a * (1 - e^2)", {"a": 7000.0}, reported_value=6900.0)
    assert res_missing["status"] == "incomplete_parameters"
    assert res_missing["missing_symbols"] == ["e"]

    res_euler = MathematicalFirewall.plug_in_check("E^1", {}, reported_value=math.e, rel_tolerance=1e-6)
    assert res_euler["status"] == "ok"


def test_def_m07_ahp_invalid_reciprocity_produces_finding_and_valid_schema() -> None:
    out = run_motor(
        {"id": "ahp_bad", "operation": "ahp_matrix", "matrix": [[1, 3, 5], [0.2, 1, 2], [0.2, 0.5, 1]]}
    )
    validate_contract(out, "schema_motor.json")
    assert out["resultados"]["valid"] is False
    assert out["status"] == "COM_ACHADOS"
    assert len(out["achados"]) == 1


def test_def_s03_ast_security_limits() -> None:
    with pytest.raises(ValueError, match="Torre de potências"):
        SafeExpressionParser.parse("9**9**9")

    with pytest.raises(ValueError, match="Expoente excede"):
        SafeExpressionParser.parse("2**5000")

    with pytest.raises(ValueError, match="Profundidade máxima"):
        SafeExpressionParser.parse("sin(" * 50 + "1" + ")" * 50)
