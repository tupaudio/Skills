#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Motor matemático determinístico para verificações simbólicas, matriciais e numéricas.
(Revisão Hostil v8.0-beta.2 — Core estabilizado)

Correções aplicadas sobre a v6.0-legacy:
- DEF-M01: validação de finitude antes de rank/det/cond em matrix e linear_system.
- DEF-M02: sinalização explícita de resultado complexo ou não finito frente a reported_value real.
- DEF-M03: suporte a limites infinitos ('oo', '-oo', 'inf') em integrate.
- DEF-M04: validação de interval/mesh e suporte a parameters em ode_bvp.
- DEF-M05: validação estrita de parameters numéricos finitos em ode_ivp.
- DEF-M06: remoção do sequestro silencioso da variável minúscula 'e' (constante de Euler = 'E').
- DEF-M07: envelope padronizado conforme references/schemas/schema_motor.json.
- DEF-S03: limites de tamanho de expressão, profundidade da AST e expoente máximo (anti-DoS).
"""

from __future__ import annotations

import argparse
import ast
import json
import math
import sys
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8")

# Permite execução direta via CLI ou importação como pacote
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import numpy as np
import sympy as sp
from scipy.integrate import solve_bvp, solve_ivp

from scripts.common import SCHEMA_VERSION
from scripts.common.evidence import create_evidence, create_finding, utc_now_iso
from scripts.common.validation import (
    MAX_AST_DEPTH,
    MAX_EXPONENT_ABS,
    MAX_EXPRESSION_LENGTH,
    require_finite_array,
    require_finite_number,
    sanitize_for_json,
)

MOTOR_ID = "motor_matematico"
MOTOR_VERSION = "8.0.0-beta.2"

_trapz = getattr(np, "trapezoid", getattr(np, "trapz", None))


class SafeExpressionParser:
    """Converte expressões matemáticas em texto para expressões SymPy via AST seguro (sem eval)."""

    FUNCTIONS = {
        "sin": sp.sin,
        "cos": sp.cos,
        "tan": sp.tan,
        "asin": sp.asin,
        "acos": sp.acos,
        "atan": sp.atan,
        "atan2": sp.atan2,
        "sinh": sp.sinh,
        "cosh": sp.cosh,
        "tanh": sp.tanh,
        "exp": sp.exp,
        "log": sp.log,
        "log10": lambda x: sp.log(x, 10),
        "log2": lambda x: sp.log(x, 2),
        "ln": sp.log,
        "sqrt": sp.sqrt,
        "Abs": sp.Abs,
        "abs": sp.Abs,
        "sign": sp.sign,
        "floor": sp.floor,
        "ceil": sp.ceiling,
        "max": sp.Max,
        "min": sp.Min,
        "rad": lambda x: x * sp.pi / 180,
        "deg": lambda x: x * 180 / sp.pi,
        "factorial": sp.factorial,
    }

    BINOPS = {
        ast.Add: lambda a, b: a + b,
        ast.Sub: lambda a, b: a - b,
        ast.Mult: lambda a, b: a * b,
        ast.Div: lambda a, b: a / b,
        ast.Pow: lambda a, b: a**b,
    }

    UNARYOPS = {
        ast.UAdd: lambda a: a,
        ast.USub: lambda a: -a,
    }

    @classmethod
    def parse(
        cls,
        expression: str,
        symbols: dict[str, Any] | None = None,
        auto_declare: bool = False,
        allow_infinity: bool = False,
    ) -> sp.Expr:
        if not isinstance(expression, str) or not expression.strip():
            raise ValueError("A expressão deve ser uma string não vazia.")
        if len(expression) > MAX_EXPRESSION_LENGTH:
            raise ValueError(
                f"Expressão excede o limite de segurança ({MAX_EXPRESSION_LENGTH} caracteres)."
            )

        cleaned_expr = expression.strip().replace("^", "**")

        sym_table = dict(symbols or {})
        sym_table.setdefault("pi", sp.pi)
        sym_table.setdefault("E", sp.E)
        if allow_infinity:
            sym_table.setdefault("oo", sp.oo)
            sym_table.setdefault("inf", sp.oo)

        tree = ast.parse(cleaned_expr, mode="eval")
        return cls._convert(tree.body, sym_table, auto_declare=auto_declare, depth=0)

    @classmethod
    def _convert(
        cls,
        node: ast.AST,
        symbols: dict[str, Any],
        auto_declare: bool = False,
        depth: int = 0,
    ) -> sp.Expr:
        if depth > MAX_AST_DEPTH:
            raise ValueError(f"Profundidade máxima da AST excedida ({MAX_AST_DEPTH}).")

        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            val = float(node.value)
            if not math.isfinite(val):
                raise ValueError(f"Constante não finita não permitida: {node.value}")
            return sp.Integer(node.value) if isinstance(node.value, int) else sp.Float(node.value)

        if isinstance(node, ast.Name):
            if node.id in symbols:
                return symbols[node.id]
            if auto_declare and node.id not in cls.FUNCTIONS:
                sym = sp.Symbol(node.id)
                symbols[node.id] = sym
                return sym
            raise ValueError(f"Símbolo não declarado: {node.id}")

        if isinstance(node, ast.BinOp) and type(node.op) in cls.BINOPS:
            if isinstance(node.op, ast.Pow) and isinstance(node.right, ast.BinOp) and isinstance(node.right.op, ast.Pow):
                raise ValueError("Torre de potências aninhadas (a**b**c) bloqueada por segurança.")
            left = cls._convert(node.left, symbols, auto_declare=auto_declare, depth=depth + 1)
            right = cls._convert(node.right, symbols, auto_declare=auto_declare, depth=depth + 1)
            if isinstance(node.op, ast.Pow):
                if right.is_number and right.is_real:
                    try:
                        exp_val = abs(float(right.evalf()))
                        if exp_val > MAX_EXPONENT_ABS:
                            raise ValueError(
                                f"Expoente excede o limite de segurança (|exp| > {MAX_EXPONENT_ABS})."
                            )
                    except (TypeError, ValueError) as exc:
                        if "limite de segurança" in str(exc):
                            raise
            return cls.BINOPS[type(node.op)](left, right)

        if isinstance(node, ast.UnaryOp) and type(node.op) in cls.UNARYOPS:
            value = cls._convert(node.operand, symbols, auto_declare=auto_declare, depth=depth + 1)
            return cls.UNARYOPS[type(node.op)](value)

        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            function = cls.FUNCTIONS.get(node.func.id)
            if function is None or node.keywords:
                raise ValueError(f"Função não permitida: {node.func.id}")
            arguments = [
                cls._convert(arg, symbols, auto_declare=auto_declare, depth=depth + 1)
                for arg in node.args
            ]
            return function(*arguments)

        raise ValueError(
            "Expressão contém construção não permitida. "
            "Use números, símbolos declarados, +, -, *, /, ** e funções matemáticas suportadas."
        )


class MathematicalFirewall:
    """Operações matemáticas auditáveis e resoluções determinísticas."""

    @staticmethod
    def plug_in_check(
        expression: str,
        substitutions: dict[str, Any] | None,
        reported_value: float | None = None,
        rel_tolerance: float = 0.02,
        abs_tolerance: float = 1e-6,
    ) -> dict[str, Any]:
        subs_clean: dict[str, float] = {}
        for k, v in (substitutions or {}).items():
            subs_clean[k] = require_finite_number(v, name=f"substitutions.{k}")

        if reported_value is not None:
            reported_value = require_finite_number(reported_value, name="reported_value")

        sym_map = {name: sp.Symbol(name) for name in subs_clean}
        expr = SafeExpressionParser.parse(expression, sym_map, auto_declare=True)

        subs_sympy = {sp.Symbol(k): sp.Float(v) for k, v in subs_clean.items()}
        evaluated = expr.evalf(subs=subs_sympy)

        free_syms = sorted(str(s) for s in evaluated.free_symbols)
        if free_syms:
            return {
                "operation": "plug_in",
                "expression": expression,
                "substitutions": subs_clean,
                "status": "incomplete_parameters",
                "missing_symbols": free_syms,
                "symbolic_partial": str(evaluated),
                "note": f"Faltam valores numéricos para os símbolos: {', '.join(free_syms)}",
            }

        try:
            c_val = complex(evaluated)
        except (TypeError, ValueError):
            return {
                "operation": "plug_in",
                "expression": expression,
                "substitutions": subs_clean,
                "reported_value": reported_value,
                "calculated_value": str(evaluated),
                "matches_within_tolerance": False if reported_value is not None else None,
                "status": "non_finite_result",
                "note": "Expressão avaliou para valor não finito ou indeterminado.",
            }

        if not (math.isfinite(c_val.real) and math.isfinite(c_val.imag)):
            return {
                "operation": "plug_in",
                "expression": expression,
                "substitutions": subs_clean,
                "reported_value": reported_value,
                "calculated_value": [c_val.real, c_val.imag],
                "matches_within_tolerance": False if reported_value is not None else None,
                "status": "non_finite_result",
                "note": "Resultado numérico não finito (NaN ou Inf).",
            }

        is_real = abs(c_val.imag) < 1e-12
        calculated_value: float | list[float] = (
            float(c_val.real) if is_real else [float(c_val.real), float(c_val.imag)]
        )

        result: dict[str, Any] = {
            "operation": "plug_in",
            "expression": expression,
            "substitutions": subs_clean,
            "calculated_value": calculated_value,
            "reported_value": reported_value,
        }

        if reported_value is not None:
            if not is_real:
                result.update(
                    {
                        "matches_within_tolerance": False,
                        "status": "complex_result_vs_real_reported",
                        "note": (
                            f"A fórmula produziu valor complexo ({c_val.real:.6g} + {c_val.imag:.6g}i) "
                            f"enquanto o manuscrito reportou valor real ({reported_value})."
                        ),
                    }
                )
            else:
                abs_err = abs(float(calculated_value) - reported_value)
                rel_err = (
                    abs_err / abs(reported_value)
                    if abs(reported_value) > 1e-15
                    else (0.0 if abs_err <= abs_tolerance else float("inf"))
                )
                matches = bool((abs_err <= abs_tolerance) or (rel_err <= rel_tolerance))
                result.update(
                    {
                        "absolute_error": abs_err,
                        "relative_error_pct": rel_err * 100.0,
                        "matches_within_tolerance": matches,
                        "rel_tolerance_pct": rel_tolerance * 100.0,
                        "status": "ok" if matches else "discrepancy_detected",
                    }
                )
        else:
            result["status"] = "calculated"

        return result

    @staticmethod
    def check_formula(
        lhs: Any,
        rhs: Any,
        substitutions: dict[str, Any] | None = None,
        tolerance: float = 1e-9,
    ) -> dict[str, Any]:
        subs_clean = {
            k: require_finite_number(v, name=f"substitutions.{k}")
            for k, v in (substitutions or {}).items()
        }
        sym_map = {name: sp.Symbol(name) for name in subs_clean}

        lhs_expr = (
            SafeExpressionParser.parse(lhs, sym_map, auto_declare=True)
            if isinstance(lhs, str)
            else sp.sympify(lhs)
        )
        rhs_expr = (
            SafeExpressionParser.parse(rhs, sym_map, auto_declare=True)
            if isinstance(rhs, str)
            else sp.sympify(rhs)
        )

        difference = sp.simplify(lhs_expr - rhs_expr)

        # Classificação simbólica conservadora
        if difference == 0 or difference.is_zero is True:
            symbolic_equivalence = "proven_equal"
            symbolically_equal: bool | None = True
            initial_status = "ok"
            note = None
        elif difference.is_zero is False:
            # Comprovadamente não nula (ex.: constante não zero, -1, etc.)
            symbolic_equivalence = "proven_different"
            symbolically_equal = False
            initial_status = "discrepancy_detected"
            note = f"Diferença simbólica comprovadamente não nula ({difference})."
        elif difference.free_symbols:
            try:
                poly = difference.as_poly(*difference.free_symbols)
                if poly is not None and poly.is_zero is False:
                    symbolic_equivalence = "proven_different"
                    symbolically_equal = False
                    initial_status = "discrepancy_detected"
                    note = f"Diferença simbólica polinomial não nula ({difference})."
                else:
                    symbolic_equivalence = "inconclusive"
                    symbolically_equal = None
                    initial_status = "not_symbolically_equal"
                    note = f"Equivalência simbólica inconclusiva ({difference})."
            except Exception:
                symbolic_equivalence = "inconclusive"
                symbolically_equal = None
                initial_status = "not_symbolically_equal"
                note = f"Equivalência simbólica inconclusiva ({difference})."
        else:
            symbolic_equivalence = "inconclusive"
            symbolically_equal = None
            initial_status = "not_symbolically_equal"
            note = f"Equivalência simbólica inconclusiva ({difference})."

        result: dict[str, Any] = {
            "operation": "formula",
            "symbolic_equivalence": symbolic_equivalence,
            "symbolically_equal": symbolically_equal,
            "simplified_difference": str(difference),
            "numeric_check": None,
            "tolerance": tolerance,
            "status": initial_status,
        }
        if note:
            result["note"] = note

        if subs_clean:
            substitution_map = {sp.Symbol(name): sp.Float(value) for name, value in subs_clean.items()}
            evaluated_diff = difference.evalf(subs=substitution_map)
            free_syms = sorted(str(s) for s in evaluated_diff.free_symbols)
            if free_syms:
                result["numeric_check"] = {
                    "status": "incomplete_substitutions",
                    "missing_symbols": free_syms,
                    "partial_expression": str(evaluated_diff),
                    "within_tolerance": None,
                }
            else:
                residual = float(abs(complex(evaluated_diff)))
                within = bool(math.isfinite(residual) and residual <= tolerance)
                result["numeric_check"] = {
                    "residual": residual,
                    "within_tolerance": within,
                    "scope": "Aplica-se somente às substituições numéricas fornecidas; não prova identidade simbólica.",
                }
                if not within:
                    result["status"] = "discrepancy_detected"
                    result["note"] = f"Discrepância numérica fora da tolerância (residual={residual:.2e} > tol={tolerance:.2e})."
                elif initial_status == "discrepancy_detected":
                    # Preserva a discrepância simbólica comprovada mesmo com coincidência pontual nos pontos fornecidos
                    result["status"] = "discrepancy_detected"
                elif symbolic_equivalence == "proven_equal":
                    result["status"] = "ok"
                else:
                    result["status"] = "numerically_equal_at_samples"

        return result

    @staticmethod
    def simplify_expression(expression: str, variables: list[str] | None = None) -> dict[str, Any]:
        symbols = {name: sp.Symbol(name) for name in (variables or [])}
        parsed = SafeExpressionParser.parse(expression, symbols, auto_declare=True)
        return {
            "operation": "simplify",
            "input": expression,
            "simplified": str(sp.simplify(parsed)),
            "factored": str(sp.factor(parsed)),
            "expanded": str(sp.expand(parsed)),
            "status": "ok",
        }

    @staticmethod
    def differentiate(expression: str, variable: str, order: int = 1) -> dict[str, Any]:
        if not isinstance(order, int) or isinstance(order, bool) or order < 1:
            raise ValueError("A ordem da derivada deve ser um inteiro >= 1.")
        x = sp.Symbol(variable)
        parsed = SafeExpressionParser.parse(expression, {variable: x}, auto_declare=True)
        return {
            "operation": "differentiate",
            "expression": expression,
            "variable": variable,
            "order": order,
            "derivative": str(sp.diff(parsed, x, order)),
            "status": "ok",
        }

    @staticmethod
    def integrate(
        expression: str,
        variable: str,
        lower: Any = None,
        upper: Any = None,
    ) -> dict[str, Any]:
        x = sp.Symbol(variable)
        parsed = SafeExpressionParser.parse(expression, {variable: x}, auto_declare=True)

        if lower is None and upper is None:
            value = sp.integrate(parsed, x)
            kind = "indefinite"
        elif lower is not None and upper is not None:
            low_expr = (
                SafeExpressionParser.parse(
                    str(lower), {variable: x}, auto_declare=True, allow_infinity=True
                )
                if isinstance(lower, str)
                else sp.sympify(require_finite_number(lower, name="lower"))
            )
            up_expr = (
                SafeExpressionParser.parse(
                    str(upper), {variable: x}, auto_declare=True, allow_infinity=True
                )
                if isinstance(upper, str)
                else sp.sympify(require_finite_number(upper, name="upper"))
            )
            value = sp.integrate(parsed, (x, low_expr, up_expr))
            kind = "definite"
        else:
            raise ValueError("Para integral definida, informe ambos 'lower' e 'upper'.")

        eval_val = sp.N(value)
        num_res: float | list[float] | None = None
        if not eval_val.free_symbols:
            try:
                c_val = complex(eval_val)
                if math.isfinite(c_val.real) and math.isfinite(c_val.imag):
                    num_res = (
                        float(c_val.real)
                        if abs(c_val.imag) < 1e-12
                        else [float(c_val.real), float(c_val.imag)]
                    )
            except Exception:
                num_res = None

        return {
            "operation": "integrate",
            "kind": kind,
            "expression": expression,
            "variable": variable,
            "lower": lower,
            "upper": upper,
            "result": str(value),
            "numeric_result": num_res,
            "status": "ok",
        }

    @staticmethod
    def solve_linear_system(matrix: Any, vector: Any, singular_tolerance: float = 1e-12) -> dict[str, Any]:
        A = require_finite_array(matrix, name="matrix", ndim=2)
        b = require_finite_array(vector, name="vector", ndim=1)

        if A.shape[0] != b.shape[0]:
            raise ValueError("Dimensões incompatíveis para Ax=b.")

        rank = int(np.linalg.matrix_rank(A, tol=singular_tolerance))
        condition = float(np.linalg.cond(A))

        if A.shape[0] == A.shape[1] and rank == A.shape[0]:
            solution = np.linalg.solve(A, b)
            method = "solve"
        else:
            solution, _, _, _ = np.linalg.lstsq(A, b, rcond=None)
            method = "least_squares"

        residual = A @ solution - b
        return {
            "operation": "linear_system",
            "method": method,
            "rank": rank,
            "shape": list(A.shape),
            "condition_number": condition,
            "solution": solution.tolist(),
            "residual_norm_2": float(np.linalg.norm(residual)),
            "status": "ok",
        }

    @staticmethod
    def audit_matrix(matrix: Any, tolerance: float = 1e-10) -> dict[str, Any]:
        A = require_finite_array(matrix, name="matrix", ndim=2)

        result: dict[str, Any] = {
            "operation": "matrix",
            "shape": list(A.shape),
            "rank": int(np.linalg.matrix_rank(A, tol=tolerance)),
            "finite": True,
            "status": "ok",
        }

        if A.shape[0] == A.shape[1]:
            result["determinant"] = float(np.linalg.det(A))
            result["condition_number_2"] = float(np.linalg.cond(A))
            result["invertible_at_tolerance"] = bool(result["rank"] == A.shape[0])
            result["eigenvalues"] = [
                [float(value.real), float(value.imag)] for value in np.linalg.eigvals(A)
            ]

        return result

    @staticmethod
    def solve_ode_ivp(
        rhs: list[str],
        t_span: list[float],
        y0: list[float],
        t_eval: list[float] | None = None,
        parameters: dict[str, Any] | None = None,
        method: str = "RK45",
        rtol: float = 1e-8,
        atol: float = 1e-10,
        max_step: float = np.inf,
    ) -> dict[str, Any]:
        y0_arr = require_finite_array(y0, name="y0", ndim=1)
        t_span_arr = require_finite_array(t_span, name="t_span", ndim=1)
        if t_span_arr.size != 2 or t_span_arr[0] == t_span_arr[1]:
            raise ValueError("t_span deve conter dois tempos distintos [t0, tf].")
        if len(rhs) != len(y0_arr):
            raise ValueError("Deve haver uma expressão RHS para cada componente de y.")

        t = sp.Symbol("t")
        states = [sp.Symbol(f"y{i}") for i in range(len(y0_arr))]
        symbols: dict[str, Any] = {"t": t}
        symbols.update({str(state): state for state in states})
        if parameters:
            for k, v in parameters.items():
                symbols[k] = sp.Float(require_finite_number(v, name=f"parameters.{k}"))

        expressions = [SafeExpressionParser.parse(item, symbols) for item in rhs]
        functions = [sp.lambdify([t] + states, expression, modules="numpy") for expression in expressions]

        def system(time: float, state: np.ndarray) -> np.ndarray:
            values = [function(time, *state) for function in functions]
            return np.asarray(values, dtype=float)

        t_eval_arr = None if t_eval is None else require_finite_array(t_eval, name="t_eval", ndim=1)
        solution = solve_ivp(
            system,
            (float(t_span_arr[0]), float(t_span_arr[1])),
            y0_arr,
            method=method,
            t_eval=t_eval_arr,
            rtol=rtol,
            atol=atol,
            max_step=max_step,
        )

        return {
            "operation": "ode_ivp",
            "problem_type": "IVP",
            "method": method,
            "solver_success": bool(solution.success),
            "message": solution.message,
            "nfev": int(solution.nfev),
            "t": solution.t.tolist(),
            "y": solution.y.tolist(),
            "final_state": solution.y[:, -1].tolist() if solution.y.size > 0 else [],
            "tolerances": {"rtol": rtol, "atol": atol},
            "status": "ok" if solution.success else "solver_failed",
        }

    @staticmethod
    def solve_ode_bvp(
        rhs: list[str],
        boundary_conditions: list[str],
        interval: list[float],
        mesh: list[float] | None = None,
        initial_guess: list[list[float]] | None = None,
        parameters: dict[str, Any] | None = None,
        tol: float = 1e-5,
    ) -> dict[str, Any]:
        n = len(rhs)
        if len(boundary_conditions) != n:
            raise ValueError("BVP de primeira ordem requer n condições para n estados.")

        interval_arr = require_finite_array(interval, name="interval", ndim=1)
        if interval_arr.size != 2 or interval_arr[0] >= interval_arr[1]:
            raise ValueError("interval deve conter [a, b] com a < b.")

        if mesh is None:
            mesh_arr = np.linspace(interval_arr[0], interval_arr[1], 11)
        else:
            mesh_arr = require_finite_array(mesh, name="mesh", ndim=1)
            if mesh_arr.size < 2 or np.any(np.diff(mesh_arr) <= 0):
                raise ValueError("mesh deve ter >= 2 pontos estritamente crescentes.")
            if not (
                math.isclose(mesh_arr[0], interval_arr[0], rel_tol=1e-6, abs_tol=1e-9)
                and math.isclose(mesh_arr[-1], interval_arr[1], rel_tol=1e-6, abs_tol=1e-9)
            ):
                raise ValueError(
                    f"Extremos de mesh [{mesh_arr[0]}, {mesh_arr[-1]}] não coincidem com interval {interval_arr.tolist()}."
                )

        if initial_guess is None:
            guess_arr = np.zeros((n, mesh_arr.size), dtype=float)
        else:
            guess_arr = require_finite_array(initial_guess, name="initial_guess", ndim=2)
            if guess_arr.shape != (n, mesh_arr.size):
                raise ValueError(
                    f"initial_guess deve ter forma ({n}, {mesh_arr.size}), recebido {guess_arr.shape}."
                )

        x = sp.Symbol("x")
        states = [sp.Symbol(f"y{i}") for i in range(n)]
        symbols: dict[str, Any] = {"x": x}
        symbols.update({str(state): state for state in states})
        if parameters:
            for k, v in parameters.items():
                symbols[k] = sp.Float(require_finite_number(v, name=f"parameters.{k}"))

        rhs_exprs = [SafeExpressionParser.parse(expr, symbols) for expr in rhs]
        rhs_funcs = [sp.lambdify([x] + states, expr, modules="numpy") for expr in rhs_exprs]

        bc_symbols = {f"ya{i}": sp.Symbol(f"ya{i}") for i in range(n)}
        bc_symbols.update({f"yb{i}": sp.Symbol(f"yb{i}") for i in range(n)})
        if parameters:
            for k, v in parameters.items():
                bc_symbols[k] = sp.Float(require_finite_number(v, name=f"parameters.{k}"))

        bc_exprs = [SafeExpressionParser.parse(expr, bc_symbols) for expr in boundary_conditions]
        bc_funcs = [
            sp.lambdify(
                [bc_symbols[f"ya{i}"] for i in range(n)] + [bc_symbols[f"yb{i}"] for i in range(n)],
                expr,
                modules="numpy",
            )
            for expr in bc_exprs
        ]

        def fun(x_values: np.ndarray, y_values: np.ndarray) -> np.ndarray:
            rows = []
            for function in rhs_funcs:
                val = np.asarray(function(x_values, *y_values), dtype=float)
                if val.ndim == 0:
                    val = np.full_like(x_values, float(val), dtype=float)
                rows.append(val)
            return np.vstack(rows)

        def bc(ya: np.ndarray, yb: np.ndarray) -> np.ndarray:
            arguments = list(ya) + list(yb)
            return np.asarray([function(*arguments) for function in bc_funcs], dtype=float)

        solution = solve_bvp(fun, bc, mesh_arr, guess_arr, tol=tol)
        return {
            "operation": "ode_bvp",
            "problem_type": "BVP",
            "interval": interval_arr.tolist(),
            "solver_success": bool(solution.success),
            "message": solution.message,
            "nodes": solution.x.tolist(),
            "solution": solution.y.tolist(),
            "max_rms_residual": float(np.max(solution.rms_residuals)) if solution.rms_residuals.size > 0 else 0.0,
            "tolerance": tol,
            "status": "ok" if solution.success else "solver_failed",
        }

    @staticmethod
    def solve_symbolic_first_order_ode(
        rhs: str,
        independent: str = "x",
        dependent: str = "y",
        initial: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        x = sp.Symbol(independent)
        y_function = sp.Function(dependent)
        y = y_function(x)

        symbols = {independent: x, dependent: y}
        rhs_expr = SafeExpressionParser.parse(rhs, symbols, auto_declare=True)
        equation = sp.Eq(sp.diff(y, x), rhs_expr)

        ics = None
        if initial is not None:
            if "x0" not in initial or "y0" not in initial:
                raise ValueError("Condição inicial requer x0 e y0.")
            x0 = require_finite_number(initial["x0"], name="initial.x0")
            y0 = require_finite_number(initial["y0"], name="initial.y0")
            ics = {y.subs(x, x0): y0}

        answer = sp.dsolve(equation, y, ics=ics)
        return {
            "operation": "ode_symbolic",
            "problem_type": "symbolic_first_order_ODE",
            "equation": str(equation),
            "solution": str(answer),
            "initial_condition": initial,
            "status": "ok",
            "note": "Solução simbólica obtida pelo SymPy; confira domínio e hipóteses.",
        }

    @staticmethod
    def audit_mpc_feasibility(
        x0: dict[str, Any],
        constraints: dict[str, dict[str, Any]],
        tolerance: float = 0.0,
    ) -> dict[str, Any]:
        tol = require_finite_number(tolerance, name="tolerance")
        violations = []

        for state, raw_value in x0.items():
            value = require_finite_number(raw_value, name=f"x0.{state}")
            if state not in constraints:
                continue

            limit = constraints[state]
            if "min" in limit:
                min_v = require_finite_number(limit["min"], name=f"constraints.{state}.min")
                if value < min_v - tol:
                    violations.append({"state": state, "value": value, "constraint": "min", "limit": min_v})
            if "max" in limit:
                max_v = require_finite_number(limit["max"], name=f"constraints.{state}.max")
                if value > max_v + tol:
                    violations.append({"state": state, "value": value, "constraint": "max", "limit": max_v})

        return {
            "operation": "mpc_feasibility",
            "initial_state_feasible": not violations,
            "violations": violations,
            "status": "ok" if not violations else "discrepancy_detected",
            "scope": "Checagem do estado inicial; não prova viabilidade recursiva em horizonte N.",
        }

    @staticmethod
    def audit_energy_profile(
        time_seconds: Any,
        generation_w: Any,
        load_w: Any,
        losses_w: Any = None,
    ) -> dict[str, Any]:
        t = require_finite_array(time_seconds, name="time_seconds", ndim=1)
        generation = require_finite_array(generation_w, name="generation_w", ndim=1)
        load = require_finite_array(load_w, name="load_w", ndim=1)
        losses = np.zeros_like(t) if losses_w is None else require_finite_array(losses_w, name="losses_w", ndim=1)

        if not (len(t) == len(generation) == len(load) == len(losses)):
            raise ValueError("Todos os perfis devem ter o mesmo número de amostras.")
        if len(t) < 2 or np.any(np.diff(t) <= 0):
            raise ValueError("O tempo deve ter pelo menos dois pontos e ser estritamente crescente.")

        e_gen_wh = float(_trapz(generation, t) / 3600.0)
        e_load_wh = float(_trapz(load, t) / 3600.0)
        e_losses_wh = float(_trapz(losses, t) / 3600.0)
        net_wh = e_gen_wh - e_load_wh - e_losses_wh

        return {
            "operation": "energy_profile",
            "generation_Wh": e_gen_wh,
            "load_Wh": e_load_wh,
            "losses_Wh": e_losses_wh,
            "net_energy_Wh": net_wh,
            "net_nonnegative": bool(net_wh >= 0),
            "status": "ok" if net_wh >= 0 else "discrepancy_detected",
            "note": "Para validar SoC da bateria, inclua capacidade nominal, DoD máximo e eficiências de carga/descarga.",
        }

    @staticmethod
    def audit_ahp_matrix(
        matrix: Any,
        ri_table: dict[Any, float] | None = None,
        threshold: float = 0.10,
        tolerance: float = 1e-4,
    ) -> dict[str, Any]:
        A = require_finite_array(matrix, name="matrix", ndim=2)
        if A.shape[0] != A.shape[1]:
            return {"operation": "ahp_matrix", "valid": False, "status": "invalid_input", "error": "A matriz deve ser quadrada."}
        if np.any(A <= 0):
            return {"operation": "ahp_matrix", "valid": False, "status": "invalid_input", "error": "Entradas AHP devem ser estritamente positivas."}

        n = int(A.shape[0])
        reciprocal = bool(np.allclose(A * A.T, np.ones_like(A), atol=tolerance))
        unit_diagonal = bool(np.allclose(np.diag(A), np.ones(n), atol=tolerance))

        if not reciprocal or not unit_diagonal:
            return {
                "operation": "ahp_matrix",
                "valid": False,
                "status": "discrepancy_detected",
                "reciprocal": reciprocal,
                "unit_diagonal": unit_diagonal,
                "max_reciprocity_deviation": float(np.max(np.abs(A * A.T - 1.0))),
                "error": "A matriz deve ser recíproca (a_ij * a_ji = 1) e ter diagonal principal igual a 1.",
            }

        eigenvalues, eigenvectors = np.linalg.eig(A)
        index = int(np.argmax(eigenvalues.real))
        lambda_max = float(eigenvalues[index].real)
        weights = np.abs(eigenvectors[:, index].real)
        w_sum = float(weights.sum())
        if w_sum <= 0:
            return {"operation": "ahp_matrix", "valid": False, "status": "invalid_input", "error": "Autovetor principal degenerado."}
        weights = weights / w_sum

        ci = 0.0 if n <= 1 else max(0.0, (lambda_max - n) / (n - 1))
        default_ri = {
            1: 0.00, 2: 0.00, 3: 0.58, 4: 0.90, 5: 1.12,
            6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45, 10: 1.49,
            11: 1.51, 12: 1.48, 13: 1.56, 14: 1.57, 15: 1.59,
        }
        ri = default_ri.get(n) if ri_table is None else ri_table.get(n, ri_table.get(str(n), default_ri.get(n)))
        cr = 0.0 if (ri is not None and ri == 0.0 and n <= 2) else (None if ri is None or ri == 0 else float(ci / ri))
        consistent = None if cr is None else bool(cr < threshold)

        return {
            "operation": "ahp_matrix",
            "valid": True,
            "n": n,
            "reciprocal": reciprocal,
            "unit_diagonal": unit_diagonal,
            "lambda_max": lambda_max,
            "weights": weights.tolist(),
            "weights_sum": float(weights.sum()),
            "CI": float(ci),
            "RI": ri,
            "CR": cr,
            "consistent_at_threshold": consistent,
            "threshold": threshold,
            "status": "ok" if (consistent is None or consistent) else "discrepancy_detected",
            "note": "CR < 0.10 valida a consistência lógica dos julgamentos, não a validade física dos critérios.",
        }


def execute_single_operation(request: dict[str, Any]) -> dict[str, Any]:
    operation = request.get("operation")

    if operation in ("plug_in", "evaluate"):
        return MathematicalFirewall.plug_in_check(
            expression=request["expression"],
            substitutions=request.get("substitutions", {}),
            reported_value=request.get("reported_value"),
            rel_tolerance=request.get("rel_tolerance", 0.02),
            abs_tolerance=request.get("abs_tolerance", 1e-6),
        )
    if operation == "ode_ivp":
        return MathematicalFirewall.solve_ode_ivp(
            rhs=request["rhs"],
            t_span=request["t_span"],
            y0=request["y0"],
            t_eval=request.get("t_eval"),
            parameters=request.get("parameters"),
            method=request.get("method", "RK45"),
            rtol=request.get("rtol", 1e-8),
            atol=request.get("atol", 1e-10),
            max_step=request.get("max_step", np.inf),
        )
    if operation == "ode_bvp":
        return MathematicalFirewall.solve_ode_bvp(
            rhs=request["rhs"],
            boundary_conditions=request["boundary_conditions"],
            interval=request["interval"],
            mesh=request.get("mesh"),
            initial_guess=request.get("initial_guess"),
            parameters=request.get("parameters"),
            tol=request.get("tol", 1e-5),
        )
    if operation == "ode_symbolic":
        return MathematicalFirewall.solve_symbolic_first_order_ode(
            rhs=request["rhs"],
            independent=request.get("independent", "x"),
            dependent=request.get("dependent", "y"),
            initial=request.get("initial"),
        )
    if operation == "matrix":
        return MathematicalFirewall.audit_matrix(request["matrix"], request.get("tolerance", 1e-10))
    if operation == "linear_system":
        return MathematicalFirewall.solve_linear_system(request["matrix"], request["vector"])
    if operation == "formula":
        return MathematicalFirewall.check_formula(
            request["lhs"], request["rhs"], request.get("substitutions"), request.get("tolerance", 1e-9)
        )
    if operation == "differentiate":
        return MathematicalFirewall.differentiate(
            request["expression"], request["variable"], request.get("order", 1)
        )
    if operation == "integrate":
        return MathematicalFirewall.integrate(
            request["expression"], request["variable"], request.get("lower"), request.get("upper")
        )
    if operation == "simplify":
        return MathematicalFirewall.simplify_expression(request["expression"], request.get("variables"))
    if operation == "mpc_feasibility":
        return MathematicalFirewall.audit_mpc_feasibility(
            request["x0"], request["constraints"], request.get("tolerance", 0.0)
        )
    if operation == "energy_profile":
        return MathematicalFirewall.audit_energy_profile(
            request["time_seconds"], request["generation_w"], request["load_w"], request.get("losses_w")
        )
    if operation == "ahp_matrix":
        return MathematicalFirewall.audit_ahp_matrix(
            request["matrix"],
            request.get("ri_table"),
            request.get("threshold", 0.10),
            request.get("tolerance", 1e-4),
        )
    raise ValueError(f"Operação desconhecida: {operation}")


def _extract_findings_from_results(results: list[dict[str, Any]], source_label: str) -> list[dict[str, Any]]:
    achados: list[dict[str, Any]] = []
    for idx, res in enumerate(results, start=1):
        op_id = str(res.get("id") or f"OP_{idx}")
        status = res.get("status")
        if not res.get("success", True):
            ev = create_evidence(
                f"EV-MAT-{idx:03d}",
                "numerica",
                source_label,
                op_id,
                f"Erro na operação {res.get('operation')}: {res.get('error')}",
                motor_origem=MOTOR_ID,
            )
            achados.append(
                create_finding(
                    f"ACH-MAT-{idx:03d}",
                    f"Falha de validação/execução em {op_id}",
                    "erro_operacao_matematica",
                    "MAIOR",
                    "ALTA",
                    op_id,
                    str(res.get("error")),
                    [ev],
                    estado="ABERTO",
                    portao="G03",
                    origem_componente=MOTOR_ID,
                )
            )
        elif status in ("discrepancy_detected", "complex_result_vs_real_reported", "non_finite_result"):
            ev = create_evidence(
                f"EV-MAT-{idx:03d}",
                "numerica",
                source_label,
                op_id,
                f"Status={status} | calculado={res.get('calculated_value')} | reportado={res.get('reported_value')}",
                valor_observado=res.get("reported_value"),
                valor_calculado=res.get("calculated_value"),
                motor_origem=MOTOR_ID,
            )
            achados.append(
                create_finding(
                    f"ACH-MAT-{idx:03d}",
                    f"Discrepância matemática detectada em {op_id}",
                    "discrepancia_matematica",
                    "CRITICO" if status == "discrepancy_detected" else "MAIOR",
                    "ALTA",
                    op_id,
                    res.get("note") or res.get("error") or f"Divergência detectada ({status}).",
                    [ev],
                    estado="CONFIRMADO",
                    portao="G03",
                    origem_componente=MOTOR_ID,
                )
            )
        elif status == "incomplete_parameters":
            ev = create_evidence(
                f"EV-MAT-{idx:03d}",
                "simbolica",
                source_label,
                op_id,
                f"Parâmetros ausentes: {res.get('missing_symbols')}",
                motor_origem=MOTOR_ID,
            )
            achados.append(
                create_finding(
                    f"ACH-MAT-{idx:03d}",
                    f"Parâmetros incompletos em {op_id}",
                    "parametros_incompletos",
                    "MODERADO",
                    "ALTA",
                    op_id,
                    res.get("note") or "Faltam parâmetros numéricos para fechamento.",
                    [ev],
                    estado="NAO_VERIFICADO",
                    portao="G08",
                    origem_componente=MOTOR_ID,
                )
            )
    return achados


def run_motor(payload: Any, *, run_id: str | None = None, artefato_alvo: str | None = None) -> dict[str, Any]:
    """Executa operação única ou lote retornando envelope aderente a schema_motor.json."""
    # Suporta envelope schema_input.json ou payload direto v6.0
    if isinstance(payload, dict) and "payload" in payload and "motor_id" in payload:
        run_id = run_id or payload.get("run_id")
        artefato_alvo = artefato_alvo or payload.get("artefato_alvo")
        inner = payload["payload"]
    else:
        inner = payload

    is_batch = isinstance(inner, list) or (isinstance(inner, dict) and inner.get("operation") == "batch")
    if is_batch:
        items = inner if isinstance(inner, list) else inner.get("operations", [])
        results: list[dict[str, Any]] = []
        for idx, item in enumerate(items, start=1):
            label = item.get("id") or item.get("label") or f"op_{idx}"
            try:
                res = execute_single_operation(item)
                res["id"] = label
                res["success"] = True
                results.append(res)
            except Exception as err:
                results.append(
                    {
                        "id": label,
                        "operation": item.get("operation"),
                        "success": False,
                        "status": "error",
                        "error_type": type(err).__name__,
                        "error": str(err),
                    }
                )
        succeeded = sum(1 for r in results if r.get("success"))
        failed = len(results) - succeeded
        raw_results: dict[str, Any] = {
            "batch": True,
            "total_operations": len(results),
            "succeeded": succeeded,
            "failed": failed,
            "results": results,
        }
        achados = _extract_findings_from_results(results, artefato_alvo or "payload_inline")
    else:
        res = execute_single_operation(inner)
        res["id"] = inner.get("id") or inner.get("label") or "op_1"
        res["success"] = True
        raw_results = res
        achados = _extract_findings_from_results([res], artefato_alvo or "payload_inline")
        failed = 0

    operation_results = results if is_batch else [res]
    solver_failures = sum(
        1 for item in operation_results
        if item.get("operation") in ("ode_ivp", "ode_bvp") and item.get("status") == "solver_failed"
    )
    formula_nonconclusive = sum(
        1 for item in operation_results
        if item.get("operation") == "formula"
        and item.get("status") in ("not_symbolically_equal", "numerically_equal_at_samples")
    )

    if failed > 0 and raw_results.get("succeeded", 0) == 0:
        motor_status = "ERRO_VALIDACAO"
    elif failed > 0 or solver_failures > 0 or formula_nonconclusive > 0:
        motor_status = "PARCIAL"
    elif achados:
        motor_status = "COM_ACHADOS"
    else:
        motor_status = "OK"

    return sanitize_for_json(
        {
            "schema_version": SCHEMA_VERSION,
            "motor_id": MOTOR_ID,
            "motor_version": MOTOR_VERSION,
            "run_id": run_id,
            "deterministico": True,
            "status": motor_status,
            "timestamp": utc_now_iso(),
            "artefato_alvo": artefato_alvo,
            "hash_artefato": None,
            "metricas": {
                "total_operacoes": raw_results.get("total_operations", 1),
                "sucesso": raw_results.get("succeeded", 1),
                "falhas": failed,
                "solvers_nao_convergidos": solver_failures,
                "verificacoes_formula_nao_conclusivas": formula_nonconclusive,
                "total_achados": len(achados),
            },
            "resultados": raw_results,
            "achados": achados,
            "limitacoes": [
                "O motor verifica expressões e sistemas fornecidos; não infere premissas físicas ausentes do modelo.",
                "Constante de Euler deve ser escrita como 'E' maiúsculo; 'e' minúsculo é tratado como variável simbólica.",
            ],
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Motor matemático determinístico (Revisão Hostil v8.0-beta.2)."
    )
    parser.add_argument("--input", "-i", help="Arquivo JSON de entrada (se omitido, lê de stdin).")
    parser.add_argument("--out", "-o", help="Arquivo JSON de saída (se omitido, imprime em stdout).")
    parser.add_argument("--run-id", help="Identificador opcional da campanha.")
    args = parser.parse_args()

    try:
        if args.input:
            raw_json = Path(args.input).read_text(encoding="utf-8")
            request = json.loads(raw_json)
            artefato = str(Path(args.input).resolve())
        else:
            request = json.load(sys.stdin)
            artefato = "stdin"

        output = run_motor(request, run_id=args.run_id, artefato_alvo=artefato)
        serialized = json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False)

        if args.out:
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(serialized, encoding="utf-8")
            print(f"Resultado matemático salvo em: {args.out}")
        else:
            print(serialized)

    except Exception as error:
        err_out = json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "motor_id": MOTOR_ID,
                "motor_version": MOTOR_VERSION,
                "deterministico": True,
                "status": "ERRO_EXECUCAO",
                "timestamp": utc_now_iso(),
                "resultados": {"error_type": type(error).__name__, "error": str(error)},
                "achados": [],
                "limitacoes": [],
            },
            ensure_ascii=False,
            indent=2,
        )
        if args.out:
            Path(args.out).write_text(err_out, encoding="utf-8")
        print(err_out)
        sys.exit(1)


if __name__ == "__main__":
    main()
