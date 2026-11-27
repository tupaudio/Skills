"""Testes unitários, negativos, segurança e regressão do motor_matematico.py (Beta 2)."""

from __future__ import annotations

import io
import json
import math
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import sympy as sp

import scripts.engines.motor_matematico as motor_module

from scripts.common.schema_validator import validate_contract
from scripts.common.validation import (
    MAX_JSON_PAYLOAD_BYTES,
    read_bounded_json,
    validate_safe_file_path,
)
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


def test_ode_ivp_rejects_parameter_collision_with_t_or_states() -> None:
    # 1. IVP rejeitar parameters contendo t
    with pytest.raises(ValueError, match="Colisão de parâmetro: 't' é um símbolo reservado"):
        MathematicalFirewall.solve_ode_ivp(
            rhs=["-y0"], t_span=[0, 1], y0=[1.0], parameters={"t": 2.0}
        )

    # 2. IVP rejeitar parameters contendo um estado, por exemplo y0
    with pytest.raises(ValueError, match="Colisão de parâmetro: 'y0' é um símbolo reservado"):
        MathematicalFirewall.solve_ode_ivp(
            rhs=["-y0"], t_span=[0, 1], y0=[1.0], parameters={"y0": 2.0}
        )


def test_ode_bvp_rejects_parameter_collision_with_x_states_or_bc_vars() -> None:
    bvp_kwargs = {
        "rhs": ["y0"],
        "boundary_conditions": ["ya0"],
        "interval": [0, 1],
    }

    # 3. BVP rejeitar parameters contendo x
    with pytest.raises(ValueError, match="Colisão de parâmetro: 'x' é um símbolo reservado"):
        MathematicalFirewall.solve_ode_bvp(**bvp_kwargs, parameters={"x": 2.0})

    # 4. BVP rejeitar parameters contendo um estado
    with pytest.raises(ValueError, match="Colisão de parâmetro: 'y0' é um símbolo reservado"):
        MathematicalFirewall.solve_ode_bvp(**bvp_kwargs, parameters={"y0": 2.0})

    # 5. BVP rejeitar parameters contendo ya0 ou yb0
    with pytest.raises(ValueError, match="Colisão de parâmetro: 'ya0' é um símbolo reservado"):
        MathematicalFirewall.solve_ode_bvp(**bvp_kwargs, parameters={"ya0": 2.0})

    with pytest.raises(ValueError, match="Colisão de parâmetro: 'yb0' é um símbolo reservado"):
        MathematicalFirewall.solve_ode_bvp(**bvp_kwargs, parameters={"yb0": 2.0})


def test_ode_rejects_invalid_parameter_keys_and_non_finite_values() -> None:
    # 7. chave de parâmetro inválida e valor não finito serem rejeitados
    with pytest.raises(ValueError, match="Chave de parâmetro inválida"):
        MathematicalFirewall.solve_ode_ivp(
            rhs=["-y0"], t_span=[0, 1], y0=[1.0], parameters={"k-1": 1.0}
        )

    with pytest.raises(ValueError, match="deve ser finito"):
        MathematicalFirewall.solve_ode_ivp(
            rhs=["-k*y0"], t_span=[0, 1], y0=[1.0], parameters={"k": float("inf")}
        )

    with pytest.raises(ValueError, match="deve ser finito"):
        MathematicalFirewall.solve_ode_ivp(
            rhs=["-k*y0"], t_span=[0, 1], y0=[1.0], parameters={"k": float("nan")}
        )

    with pytest.raises(ValueError, match="Chave de parâmetro inválida"):
        MathematicalFirewall.solve_ode_bvp(
            rhs=["y0"], boundary_conditions=["ya0"], interval=[0, 1], parameters={"1k": 1.0}
        )

    with pytest.raises(ValueError, match="deve ser finito"):
        MathematicalFirewall.solve_ode_bvp(
            rhs=["y0"], boundary_conditions=["ya0"], interval=[0, 1], parameters={"k": float("inf")}
        )



def test_ode_valid_parameters_work_and_validate_in_batch_envelope() -> None:
    # 6. parâmetros válidos continuarem funcionando em IVP e BVP
    out = run_motor(
        {
            "operation": "batch",
            "operations": [
                {
                    "id": "ivp_valid_param",
                    "operation": "ode_ivp",
                    "rhs": ["-alpha*y0"],
                    "t_span": [0, 1],
                    "y0": [1.0],
                    "parameters": {"alpha": 2.0},
                },
                {
                    "id": "bvp_valid_param",
                    "operation": "ode_bvp",
                    "rhs": ["y1", "-omega_sq*y0"],
                    "boundary_conditions": ["ya0", "yb0 - 1"],
                    "interval": [0, math.pi / 2],
                    "parameters": {"omega_sq": 1.0},
                },
                {
                    "id": "ivp_collision_caught",
                    "operation": "ode_ivp",
                    "rhs": ["-y0"],
                    "t_span": [0, 1],
                    "y0": [1.0],
                    "parameters": {"t": 1.0},
                },
            ],
        }
    )
    validate_contract(out, "schema_motor.json")

    results = out["resultados"]["results"]
    assert results[0]["success"] is True
    assert results[0]["status"] == "ok"
    assert results[1]["success"] is True
    assert results[1]["status"] == "ok"
    assert results[2]["success"] is False
    assert results[2]["status"] == "error"
    assert "Colisão de parâmetro" in results[2]["error"]
    assert out["status"] == "PARCIAL"
    assert out["metricas"]["falhas"] == 1
    assert out["metricas"]["sucesso"] == 2


def test_batch_mixed_malformed_items_isolates_failures_and_completes_valid_op() -> None:
    # Lote misto com uma operação válida e itens None, string, número e lista
    out = run_motor(
        {
            "operation": "batch",
            "operations": [
                None,
                "string_invalida",
                12345,
                ["lista_invalida"],
                {"id": "valid_simplify", "operation": "simplify", "expression": "x + x"},
            ],
        }
    )
    validate_contract(out, "schema_motor.json")

    res = out["resultados"]
    assert res["batch"] is True
    assert res["total_operations"] == 5
    assert res["succeeded"] == 1
    assert res["failed"] == 4

    results = res["results"]
    assert results[0]["id"] == "op_1"
    assert results[0]["success"] is False
    assert results[0]["error_type"] == "TypeError"

    assert results[1]["id"] == "op_2"
    assert results[1]["success"] is False

    assert results[2]["id"] == "op_3"
    assert results[2]["success"] is False

    assert results[3]["id"] == "op_4"
    assert results[3]["success"] is False

    assert results[4]["id"] == "valid_simplify"
    assert results[4]["success"] is True
    assert results[4]["simplified"] == "2*x"

    assert out["status"] == "PARCIAL"
    assert out["metricas"]["sucesso"] == 1
    assert out["metricas"]["falhas"] == 4


def test_batch_dict_item_missing_operation_field_fails_gracefully() -> None:
    # Dicionário de operação sem o campo operation
    out = run_motor(
        {
            "operation": "batch",
            "operations": [
                {"id": "missing_op", "foo": "bar"},
                {"id": "valid_op", "operation": "simplify", "expression": "y + 0"},
            ],
        }
    )
    validate_contract(out, "schema_motor.json")

    results = out["resultados"]["results"]
    assert results[0]["id"] == "missing_op"
    assert results[0]["success"] is False
    assert results[0]["error_type"] == "ValueError"
    assert "Operação desconhecida: None" in results[0]["error"]

    assert results[1]["id"] == "valid_op"
    assert results[1]["success"] is True
    assert out["status"] == "PARCIAL"


def test_batch_operations_field_not_a_list_returns_validation_error() -> None:
    # Campo operations que não seja lista
    for bad_ops in ["string_ops", 999, {"k": "v"}, True]:
        out = run_motor(
            {
                "id": "bad_batch_root",
                "operation": "batch",
                "operations": bad_ops,
            }
        )
        validate_contract(out, "schema_motor.json")
        assert out["status"] == "ERRO_VALIDACAO"
        assert out["metricas"]["falhas"] == 1
        assert out["metricas"]["sucesso"] == 0
        assert out["resultados"]["total_operations"] == 0
        assert out["resultados"]["failed"] == 1
        assert "deve ser uma lista" in out["resultados"]["results"][0]["error"]


def test_batch_empty_is_rejected_as_validation_error() -> None:
    # Lote vazio tanto em payload dict com operations=[] quanto lista vazia []
    out_dict = run_motor({"operation": "batch", "operations": []})
    validate_contract(out_dict, "schema_motor.json")
    assert out_dict["status"] == "ERRO_VALIDACAO"
    assert out_dict["metricas"]["falhas"] == 1
    assert out_dict["metricas"]["sucesso"] == 0
    assert "Lote vazio" in out_dict["resultados"]["results"][0]["error"]

    out_list = run_motor([])
    validate_contract(out_list, "schema_motor.json")
    assert out_list["status"] == "ERRO_VALIDACAO"
    assert out_list["metricas"]["falhas"] == 1
    assert out_list["metricas"]["sucesso"] == 0
    assert "Lote vazio" in out_list["resultados"]["results"][0]["error"]


def test_batch_completely_invalid_items_returns_validation_error() -> None:
    # Lote totalmente inválido
    out = run_motor([None, 123, "inválido"])
    validate_contract(out, "schema_motor.json")
    assert out["status"] == "ERRO_VALIDACAO"
    assert out["metricas"]["total_operacoes"] == 3
    assert out["metricas"]["falhas"] == 3
    assert out["metricas"]["sucesso"] == 0
    assert out["resultados"]["failed"] == 3
    assert out["resultados"]["succeeded"] == 0




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


def test_resource_limits_ast_node_count() -> None:
    # AST node limit: MAX_AST_NODES = 1500
    # Gera árvore balanceada para testar nós sem atingir a profundidade máxima (40)
    def build_balanced(n: int) -> str:
        if n == 1:
            return "x"
        left = build_balanced(n // 2)
        right = build_balanced(n - n // 2)
        return f"({left} + {right})"

    # Limiar aceito (64 termos ~ 255 nós)
    expr_ok = build_balanced(64)
    parsed = SafeExpressionParser.parse(expr_ok, {"x": sp.Symbol("x")})
    assert parsed is not None

    # Limiar rejeitado (512 termos ~ 2047 nós > 1500 nós)
    expr_excess = build_balanced(512)
    with pytest.raises(ValueError, match="Complexidade da expressão excede o limite de nós da AST"):
        SafeExpressionParser.parse(expr_excess, {"x": sp.Symbol("x")})



def test_resource_limits_matrix_and_vector_dimensions() -> None:
    # Matriz quadrada 5x5 aceita
    mat_ok = [[1.0 if i == j else 0.0 for j in range(5)] for i in range(5)]
    res = MathematicalFirewall.audit_matrix(mat_ok)
    assert res["status"] == "ok"

    # Matriz com eixo excedendo MAX_MATRIX_DIMENSION (500)
    mat_excess = [[0.0] * 501]
    with pytest.raises(ValueError, match="dimensão máxima permitida no eixo 1"):
        MathematicalFirewall.audit_matrix(mat_excess)

    with pytest.raises(ValueError, match="dimensão máxima permitida no eixo 1"):
        MathematicalFirewall.solve_linear_system(mat_excess, [0.0])


def test_resource_limits_batch_operations_count() -> None:
    # Lote de tamanho aceito (ex.: 5 ops)
    batch_ok = run_motor(
        {
            "operation": "batch",
            "operations": [{"operation": "simplify", "expression": f"x + {i}"} for i in range(5)],
        }
    )
    validate_contract(batch_ok, "schema_motor.json")
    assert batch_ok["status"] == "OK"
    assert batch_ok["metricas"]["sucesso"] == 5

    # Lote excedendo MAX_BATCH_OPERATIONS (500)
    batch_excess = run_motor(
        {
            "operation": "batch",
            "operations": [{"operation": "simplify", "expression": "x"} for _ in range(501)],
        }
    )
    validate_contract(batch_excess, "schema_motor.json")
    assert batch_excess["status"] == "ERRO_VALIDACAO"
    assert batch_excess["metricas"]["sucesso"] == 0
    assert batch_excess["metricas"]["falhas"] == 1
    assert "excede o limite máximo permitido" in batch_excess["resultados"]["results"][0]["error"]


def test_resource_limits_ode_mesh_and_order() -> None:
    # ODE IVP com dimensão de estados excedendo MAX_ODE_SYSTEM_ORDER (50)
    with pytest.raises(ValueError, match="excede o número máximo permitido de elementos"):
        MathematicalFirewall.solve_ode_ivp(
            rhs=[f"-y{i}" for i in range(51)],
            t_span=[0, 1],
            y0=[1.0] * 51,
        )

    # ODE IVP com t_eval excedendo MAX_ODE_MESH_POINTS (5000)
    with pytest.raises(ValueError, match="excede o número máximo permitido de elementos"):
        MathematicalFirewall.solve_ode_ivp(
            rhs=["-y0"],
            t_span=[0, 1],
            y0=[1.0],
            t_eval=list(np.linspace(0, 1, 5001)),
        )

    # ODE BVP com ordem excedendo MAX_ODE_SYSTEM_ORDER (50)
    with pytest.raises(ValueError, match="Ordem do sistema BVP excede o limite máximo"):
        MathematicalFirewall.solve_ode_bvp(
            rhs=[f"y{i}" for i in range(51)],
            boundary_conditions=[f"ya{i}" for i in range(51)],
            interval=[0, 1],
        )

    # ODE BVP com mesh excedendo MAX_ODE_MESH_POINTS (5000)
    with pytest.raises(ValueError, match="excede o número máximo permitido de elementos"):
        MathematicalFirewall.solve_ode_bvp(
            rhs=["y0"],
            boundary_conditions=["ya0"],
            interval=[0, 1],
            mesh=list(np.linspace(0, 1, 5001)),
        )


def test_resource_limits_payload_file_size(tmp_path: pytest.TempPathFactory) -> None:
    # Arquivo JSON excedendo MAX_JSON_PAYLOAD_BYTES (10 MB)
    large_file = tmp_path / "huge_payload.json"
    # Criamos um arquivo com tamanho ligeiramente superior a 10 MB usando truncate
    with open(large_file, "wb") as f:
        f.seek(10 * 1024 * 1024 + 10)
        f.write(b" ")

    with pytest.raises(ValueError, match="Arquivo excede o limite"):
        validate_safe_file_path(large_file, max_bytes=10 * 1024 * 1024)



@pytest.mark.parametrize(
    ("solver_name", "payload", "failed_solution"),
    [
        (
            "solve_ivp",
            {"operation": "ode_ivp", "rhs": ["-y0"], "t_span": [0, 1], "y0": [1.0]},
            SimpleNamespace(
                success=False,
                message="failed to converge",
                nfev=1,
                t=np.array([]),
                y=np.empty((1, 0)),
            ),
        ),
        (
            "solve_bvp",
            {
                "operation": "ode_bvp",
                "rhs": ["y0"],
                "boundary_conditions": ["ya0"],
                "interval": [0, 1],
            },
            SimpleNamespace(
                success=False,
                message="failed to converge",
                x=np.array([0.0, 1.0]),
                y=np.zeros((1, 2)),
                rms_residuals=np.array([1.0]),
            ),
        ),
    ],
)
def test_failed_ode_solver_is_not_reported_as_top_level_ok(
    monkeypatch: pytest.MonkeyPatch,
    solver_name: str,
    payload: dict,
    failed_solution: SimpleNamespace,
) -> None:
    monkeypatch.setattr(motor_module, solver_name, lambda *args, **kwargs: failed_solution)
    out = run_motor(payload)
    validate_contract(out, "schema_motor.json")

    assert out["resultados"]["status"] == "solver_failed"
    assert out["resultados"]["success"] is True  # operação executada, solver não convergiu
    assert out["status"] == "PARCIAL"
    assert out["metricas"]["solvers_nao_convergidos"] == 1
    assert out["metricas"]["sucesso"] == 1


def test_formula_proven_symbolic_difference_with_numeric_match_remains_discrepancy() -> None:
    # 1. x versus x**2 com x=0: diferença polinomial simbolicamente comprovada como não nula;
    # numeric_check dentro da tolerância, mas discrepancy_detected e achado mantidos.
    out = run_motor(
        {
            "operation": "formula",
            "lhs": "x",
            "rhs": "x^2",
            "substitutions": {"x": 0},
        }
    )
    validate_contract(out, "schema_motor.json")

    formula = out["resultados"]
    assert formula["symbolic_equivalence"] == "proven_different"
    assert formula["symbolically_equal"] is False
    assert formula["numeric_check"]["within_tolerance"] is True
    assert formula["status"] == "discrepancy_detected"
    assert out["status"] == "COM_ACHADOS"
    assert out["metricas"]["verificacoes_formula_nao_conclusivas"] == 0
    assert len(out["achados"]) == 1
    achado = out["achados"][0]
    validate_contract(achado, "schema_achado.json")
    assert achado["categoria"] == "discrepancia_matematica"
    assert "Diferença simbólica polinomial não nula" in achado["descricao"]


def test_formula_inconclusive_symbolic_equivalence_with_numeric_match_is_numerically_equal_at_samples() -> None:
    # 2. sqrt(x**2) versus x em x=0: equivalência simbólica inconclusiva;
    # coincidência pontual informada sem declarar identidade nem erro confirmado.
    out = run_motor(
        {
            "operation": "formula",
            "lhs": "sqrt(x**2)",
            "rhs": "x",
            "substitutions": {"x": 0},
        }
    )
    validate_contract(out, "schema_motor.json")

    formula = out["resultados"]
    assert formula["symbolic_equivalence"] == "inconclusive"
    assert formula["symbolically_equal"] is None
    assert formula["numeric_check"]["within_tolerance"] is True
    assert "somente às substituições" in formula["numeric_check"]["scope"]
    assert formula["status"] == "numerically_equal_at_samples"
    assert out["status"] == "PARCIAL"
    assert out["metricas"]["verificacoes_formula_nao_conclusivas"] == 1
    assert len(out["achados"]) == 0


def test_formula_numeric_disagreement_remains_a_finding() -> None:
    out = run_motor(
        {
            "operation": "formula",
            "lhs": "x",
            "rhs": "x + 1",
            "substitutions": {"x": 0},
        }
    )
    validate_contract(out, "schema_motor.json")

    assert out["resultados"]["symbolic_equivalence"] == "proven_different"
    assert out["resultados"]["symbolically_equal"] is False
    assert out["resultados"]["status"] == "discrepancy_detected"
    assert out["status"] == "COM_ACHADOS"
    assert len(out["achados"]) == 1


def test_symbolic_identity_remains_ok_with_numeric_substitution() -> None:
    result = MathematicalFirewall.check_formula(
        "(x+1)^2", "x^2 + 2*x + 1", {"x": 0}
    )
    assert result["symbolic_equivalence"] == "proven_equal"
    assert result["symbolically_equal"] is True
    assert result["numeric_check"]["within_tolerance"] is True
    assert result["status"] == "ok"


def test_formula_proven_symbolic_difference_without_substitutions_is_discrepancy() -> None:
    out = run_motor(
        {
            "operation": "formula",
            "lhs": "x + 1",
            "rhs": "x + 2",
        }
    )
    validate_contract(out, "schema_motor.json")

    assert out["resultados"]["symbolic_equivalence"] == "proven_different"
    assert out["resultados"]["symbolically_equal"] is False
    assert out["resultados"]["numeric_check"] is None
    assert out["resultados"]["status"] == "discrepancy_detected"
    assert out["status"] == "COM_ACHADOS"
    assert out["metricas"]["verificacoes_formula_nao_conclusivas"] == 0
    assert len(out["achados"]) == 1
    achado = out["achados"][0]
    validate_contract(achado, "schema_achado.json")
    assert achado["categoria"] == "discrepancia_matematica"
    assert "comprovadamente não nula" in achado["descricao"]


def test_formula_inconclusive_symbolic_equivalence_remains_parcial() -> None:
    out = run_motor(
        {
            "operation": "formula",
            "lhs": "sqrt(x**2)",
            "rhs": "x",
        }
    )
    validate_contract(out, "schema_motor.json")

    assert out["resultados"]["symbolic_equivalence"] == "inconclusive"
    assert out["resultados"]["symbolically_equal"] is None
    assert out["resultados"]["numeric_check"] is None
    assert out["resultados"]["status"] == "not_symbolically_equal"
    assert out["status"] == "PARCIAL"
    assert out["metricas"]["verificacoes_formula_nao_conclusivas"] == 1
    assert len(out["achados"]) == 0


def test_bounded_json_file_exact_boundaries(tmp_path: Path) -> None:
    # 1. Arquivo exatamente no limite máximo (MAX_JSON_PAYLOAD_BYTES)
    target_len = MAX_JSON_PAYLOAD_BYTES
    prefix = '{"operation": "simplify", "expression": "'
    suffix = '"}'
    pad_len = target_len - len(prefix.encode("utf-8")) - len(suffix.encode("utf-8"))
    assert pad_len > 0
    valid_exact = prefix + ("a" * pad_len) + suffix
    exact_file = tmp_path / "exact.json"
    exact_file.write_bytes(valid_exact.encode("utf-8"))
    assert exact_file.stat().st_size == MAX_JSON_PAYLOAD_BYTES

    decoded, artefato = read_bounded_json(exact_file, max_bytes=MAX_JSON_PAYLOAD_BYTES)
    assert decoded["operation"] == "simplify"
    assert artefato == str(exact_file.resolve())

    # 2. Arquivo com MAX_JSON_PAYLOAD_BYTES + 1 deve ser rejeitado antes de json.load
    excess_file = tmp_path / "excess.json"
    excess_file.write_bytes((valid_exact + " ").encode("utf-8"))
    assert excess_file.stat().st_size == MAX_JSON_PAYLOAD_BYTES + 1

    with pytest.raises(ValueError, match="excede o limite"):
        read_bounded_json(excess_file, max_bytes=MAX_JSON_PAYLOAD_BYTES)


def test_bounded_json_stream_exact_boundaries() -> None:
    # 1. Stream exatamente no limite máximo
    target_len = MAX_JSON_PAYLOAD_BYTES
    prefix = '{"operation": "simplify", "expression": "'
    suffix = '"}'
    pad_len = target_len - len(prefix.encode("utf-8")) - len(suffix.encode("utf-8"))
    valid_exact = prefix + ("b" * pad_len) + suffix
    assert len(valid_exact.encode("utf-8")) == MAX_JSON_PAYLOAD_BYTES

    stream = io.StringIO(valid_exact)
    decoded, artefato = read_bounded_json(stream, max_bytes=MAX_JSON_PAYLOAD_BYTES)
    assert decoded["operation"] == "simplify"
    assert artefato == "stdin"

    # 2. Stream com MAX_JSON_PAYLOAD_BYTES + 1 deve ser rejeitado imediatamente
    excess_stream = io.StringIO(valid_exact + "x")
    with pytest.raises(ValueError, match="Entrada excede o limite máximo permitido"):
        read_bounded_json(excess_stream, max_bytes=MAX_JSON_PAYLOAD_BYTES)


def test_motor_cli_stdin_boundary_and_excess(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # 1. Validação via CLI: stream dentro do limite máximo
    target_len = 1000
    prefix = '{"operation": "simplify", "expression": "'
    suffix = '"}'
    pad_len = target_len - len(prefix.encode("utf-8")) - len(suffix.encode("utf-8"))
    valid_json = prefix + ("c" * pad_len) + suffix

    monkeypatch.setattr(sys, "stdin", io.StringIO(valid_json))
    monkeypatch.setattr(sys, "argv", ["motor_matematico.py"])

    # Execução não deve levantar exceção não tratada
    motor_module.main()
    captured = capsys.readouterr()
    cli_out = json.loads(captured.out)
    assert cli_out["status"] in ("OK", "ERRO_VALIDACAO")
    assert cli_out["motor_id"] == "motor_matematico"

    # 2. Validação via CLI: stream com MAX_JSON_PAYLOAD_BYTES + 1 deve sair com código 1 e erro estruturado
    oversized = '{"op": "' + ("d" * MAX_JSON_PAYLOAD_BYTES) + '"}'
    monkeypatch.setattr(sys, "stdin", io.StringIO(oversized))
    monkeypatch.setattr(sys, "argv", ["motor_matematico.py"])

    with pytest.raises(SystemExit) as exc_info:
        motor_module.main()

    assert exc_info.value.code == 1
    err_captured = capsys.readouterr()
    err_json = json.loads(err_captured.out)
    assert err_json["status"] == "ERRO_EXECUCAO"
    assert err_json["deterministico"] is True
    assert err_json["resultados"]["error_type"] == "ValueError"
    assert "excede o limite máximo permitido" in err_json["resultados"]["error"]
