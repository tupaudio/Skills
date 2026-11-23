#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Motor matemático determinístico para verificações simbólicas, matriciais e numéricas.
(Skill: revisao-hostil v6.0)

Inclui:
- plug_in / evaluate: substituição numérica direta (Zero-Trust Numerical Plug-In)
  confrontando o valor calculado pela fórmula com o valor impresso no manuscrito;
- formula: simplificação e comparação simbólica e numérica de fórmulas (lhs = rhs);
- simplify: simplificação, fatoração e expansão algébrica;
- differentiate / integrate: derivadas e integrais simbólicas (definidas e indefinidas);
- linear_system / matrix: sistemas lineares (Ax = b) e auditoria espectral de matrizes;
- ode_ivp / ode_bvp / ode_symbolic: resolução numérica (IVP/BVP) e simbólica de EDOs;
- mpc_feasibility: verificação de factibilidade de estado inicial frente a restrições;
- energy_profile: integração temporal trapezoidal de geração, carga e perdas;
- ahp_matrix: auditoria canônica de matrizes AHP de Saaty (reciprocidade, autovetor, CI, CR);
- batch: execução em lote de múltiplas verificações em uma única chamada.

Dependências:
    numpy, scipy, sympy
"""

import argparse
import ast
import json
import math
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8")

import numpy as np
import sympy as sp
from scipy.integrate import solve_bvp, solve_ivp

# Compatibilidade NumPy 1.x e 2.0+ (np.trapz foi substituído por np.trapezoid no NumPy 2.0)
_trapz = getattr(np, "trapezoid", getattr(np, "trapz", None))


def _sanitize_for_json(obj):
    """Sanitiza recursivamente tipos NumPy e valores NaN/Inf para serialização JSON segura."""
    if isinstance(obj, dict):
        return {str(k): _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(v) for v in obj]
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        val = float(obj)
        if math.isnan(val):
            return "NaN"
        if math.isinf(val):
            return "Infinity" if val > 0 else "-Infinity"
        return val
    return obj


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
    def parse(cls, expression, symbols=None, auto_declare=False):
        if not isinstance(expression, str) or not expression.strip():
            raise ValueError("A expressão deve ser uma string não vazia.")

        # Suporte amigável para potência com ^ caso o usuário escreva estilo LaTeX/MATLAB
        cleaned_expr = expression.strip().replace("^", "**")

        symbols = dict(symbols or {})
        symbols.setdefault("pi", sp.pi)
        symbols.setdefault("E", sp.E)
        symbols.setdefault("e", sp.E)

        tree = ast.parse(cleaned_expr, mode="eval")
        return cls._convert(tree.body, symbols, auto_declare=auto_declare)

    @classmethod
    def _convert(cls, node, symbols, auto_declare=False):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
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
            left = cls._convert(node.left, symbols, auto_declare=auto_declare)
            right = cls._convert(node.right, symbols, auto_declare=auto_declare)
            return cls.BINOPS[type(node.op)](left, right)

        if isinstance(node, ast.UnaryOp) and type(node.op) in cls.UNARYOPS:
            value = cls._convert(node.operand, symbols, auto_declare=auto_declare)
            return cls.UNARYOPS[type(node.op)](value)

        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            function = cls.FUNCTIONS.get(node.func.id)
            if function is None or node.keywords:
                raise ValueError(f"Função não permitida: {node.func.id}")
            arguments = [cls._convert(arg, symbols, auto_declare=auto_declare) for arg in node.args]
            return function(*arguments)

        raise ValueError(
            "Expressão contém construção não permitida. "
            "Use números, símbolos declarados, +, -, *, /, ** e funções matemáticas suportadas."
        )


class MathematicalFirewall:
    """Operações matemáticas auditáveis e resoluções determinísticas."""

    @staticmethod
    def plug_in_check(expression, substitutions, reported_value=None, rel_tolerance=0.02, abs_tolerance=1e-6):
        """
        Regra Zero-Trust Numerical Plug-In:
        Substitui os parâmetros declarados no texto dentro da expressão e confronta
        com o valor impresso no artigo/tabela.
        """
        sym_map = {name: sp.Symbol(name) for name in (substitutions or {})}
        expr = SafeExpressionParser.parse(expression, sym_map, auto_declare=True)

        subs_sympy = {sp.Symbol(k): v for k, v in (substitutions or {}).items()}
        evaluated = expr.evalf(subs=subs_sympy)

        free_syms = [str(s) for s in evaluated.free_symbols]
        if free_syms:
            return {
                "operation": "plug_in",
                "expression": expression,
                "substitutions": substitutions,
                "status": "incomplete_parameters",
                "missing_symbols": free_syms,
                "symbolic_partial": str(evaluated),
                "note": f"Faltam valores numéricos para os símbolos: {', '.join(free_syms)}",
            }

        c_val = complex(evaluated)
        calculated_value = float(c_val.real) if abs(c_val.imag) < 1e-12 else [float(c_val.real), float(c_val.imag)]

        result = {
            "operation": "plug_in",
            "expression": expression,
            "substitutions": substitutions,
            "calculated_value": calculated_value,
            "reported_value": reported_value,
        }

        if reported_value is not None and isinstance(calculated_value, float):
            rep = float(reported_value)
            abs_err = abs(calculated_value - rep)
            rel_err = abs_err / abs(rep) if abs(rep) > 1e-15 else (0.0 if abs_err <= abs_tolerance else float("inf"))
            matches = bool((abs_err <= abs_tolerance) or (rel_err <= rel_tolerance))
            result.update({
                "absolute_error": abs_err,
                "relative_error_pct": rel_err * 100.0,
                "matches_within_tolerance": matches,
                "rel_tolerance_pct": rel_tolerance * 100.0,
                "status": "ok" if matches else "discrepancy_detected",
            })
        else:
            result["status"] = "calculated"

        return result

    @staticmethod
    def check_formula(lhs, rhs, substitutions=None, tolerance=1e-9):
        """Compara dois lados de uma fórmula simbolicamente e, opcionalmente, numericamente."""
        sym_map = {name: sp.Symbol(name) for name in (substitutions or {})}

        if isinstance(lhs, str):
            lhs_expr = SafeExpressionParser.parse(lhs, sym_map, auto_declare=True)
        else:
            lhs_expr = sp.sympify(lhs)

        if isinstance(rhs, str):
            rhs_expr = SafeExpressionParser.parse(rhs, sym_map, auto_declare=True)
        else:
            rhs_expr = sp.sympify(rhs)

        difference = sp.simplify(lhs_expr - rhs_expr)

        result = {
            "symbolically_equal": bool(difference == 0),
            "simplified_difference": str(difference),
            "numeric_check": None,
            "tolerance": tolerance,
        }

        if substitutions:
            substitution_map = {
                sp.Symbol(name): value
                for name, value in substitutions.items()
            }
            evaluated_diff = difference.evalf(subs=substitution_map)
            free_syms = [str(s) for s in evaluated_diff.free_symbols]
            if free_syms:
                result["numeric_check"] = {
                    "status": "incomplete_substitutions",
                    "missing_symbols": free_syms,
                    "partial_expression": str(evaluated_diff),
                    "within_tolerance": None,
                }
            else:
                numeric_difference = complex(evaluated_diff)
                residual = abs(numeric_difference)
                result["numeric_check"] = {
                    "residual": float(residual),
                    "within_tolerance": bool(residual <= tolerance),
                }

        return result

    @staticmethod
    def simplify_expression(expression, variables=None):
        symbols = {name: sp.Symbol(name) for name in (variables or [])}
        parsed = SafeExpressionParser.parse(expression, symbols, auto_declare=True)
        return {
            "input": expression,
            "simplified": str(sp.simplify(parsed)),
            "factored": str(sp.factor(parsed)),
            "expanded": str(sp.expand(parsed)),
        }

    @staticmethod
    def differentiate(expression, variable, order=1):
        if order < 1:
            raise ValueError("A ordem da derivada deve ser pelo menos 1.")
        x = sp.Symbol(variable)
        parsed = SafeExpressionParser.parse(expression, {variable: x}, auto_declare=True)
        return {
            "expression": expression,
            "variable": variable,
            "order": order,
            "derivative": str(sp.diff(parsed, x, order)),
        }

    @staticmethod
    def integrate(expression, variable, lower=None, upper=None):
        x = sp.Symbol(variable)
        parsed = SafeExpressionParser.parse(expression, {variable: x}, auto_declare=True)

        if lower is None or upper is None:
            value = sp.integrate(parsed, x)
            kind = "indefinite"
        else:
            low_expr = SafeExpressionParser.parse(str(lower), {variable: x}, auto_declare=True) if isinstance(lower, str) else lower
            up_expr = SafeExpressionParser.parse(str(upper), {variable: x}, auto_declare=True) if isinstance(upper, str) else upper
            value = sp.integrate(parsed, (x, low_expr, up_expr))
            kind = "definite"

        eval_val = sp.N(value)
        num_res = None
        if not eval_val.free_symbols:
            try:
                c_val = complex(eval_val)
                num_res = float(c_val.real) if abs(c_val.imag) < 1e-12 else [float(c_val.real), float(c_val.imag)]
            except Exception:
                num_res = None

        return {
            "kind": kind,
            "expression": expression,
            "variable": variable,
            "result": str(value),
            "numeric_result": num_res,
        }

    @staticmethod
    def solve_linear_system(matrix, vector, singular_tolerance=1e-12):
        A = np.asarray(matrix, dtype=float)
        b = np.asarray(vector, dtype=float)

        if A.ndim != 2 or b.ndim != 1 or A.shape[0] != b.shape[0]:
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
            "method": method,
            "rank": rank,
            "shape": list(A.shape),
            "condition_number": condition,
            "solution": solution.tolist(),
            "residual_norm_2": float(np.linalg.norm(residual)),
        }

    @staticmethod
    def audit_matrix(matrix, tolerance=1e-10):
        A = np.asarray(matrix, dtype=float)
        if A.ndim != 2:
            raise ValueError("A entrada deve ser uma matriz bidimensional.")

        result = {
            "shape": list(A.shape),
            "rank": int(np.linalg.matrix_rank(A)),
            "finite": bool(np.isfinite(A).all()),
        }

        if A.shape[0] == A.shape[1]:
            result["determinant"] = float(np.linalg.det(A))
            result["condition_number_2"] = float(np.linalg.cond(A))
            result["invertible_at_tolerance"] = bool(
                np.linalg.matrix_rank(A, tol=tolerance) == A.shape[0]
            )
            result["eigenvalues"] = [
                [float(value.real), float(value.imag)]
                for value in np.linalg.eigvals(A)
            ]

        return result

    @staticmethod
    def solve_ode_ivp(
        rhs,
        t_span,
        y0,
        t_eval=None,
        parameters=None,
        method="RK45",
        rtol=1e-8,
        atol=1e-10,
        max_step=np.inf,
    ):
        if len(rhs) != len(y0):
            raise ValueError("Deve haver uma expressão RHS para cada componente de y.")

        t = sp.Symbol("t")
        states = [sp.Symbol(f"y{i}") for i in range(len(y0))]
        symbols = {"t": t}
        symbols.update({str(state): state for state in states})
        if parameters:
            for k, v in parameters.items():
                symbols[k] = sp.Float(v) if isinstance(v, (int, float)) else sp.Symbol(k)

        expressions = [SafeExpressionParser.parse(item, symbols) for item in rhs]
        functions = [
            sp.lambdify([t] + states, expression, modules="numpy")
            for expression in expressions
        ]

        def system(time, state):
            values = [function(time, *state) for function in functions]
            return np.asarray(values, dtype=float)

        solution = solve_ivp(
            system,
            tuple(t_span),
            np.asarray(y0, dtype=float),
            method=method,
            t_eval=None if t_eval is None else np.asarray(t_eval, dtype=float),
            rtol=rtol,
            atol=atol,
            max_step=max_step,
        )

        return {
            "problem_type": "IVP",
            "method": method,
            "success": bool(solution.success),
            "message": solution.message,
            "nfev": int(solution.nfev),
            "t": solution.t.tolist(),
            "y": solution.y.tolist(),
            "final_state": solution.y[:, -1].tolist() if solution.y.size > 0 else [],
            "tolerances": {"rtol": rtol, "atol": atol},
        }

    @staticmethod
    def solve_ode_bvp(rhs, boundary_conditions, interval, mesh, initial_guess, tol=1e-5):
        n = len(rhs)
        if len(boundary_conditions) != n:
            raise ValueError("BVP de primeira ordem requer n condições para n estados.")

        x = sp.Symbol("x")
        states = [sp.Symbol(f"y{i}") for i in range(n)]
        symbols = {"x": x}
        symbols.update({str(state): state for state in states})

        rhs_exprs = [SafeExpressionParser.parse(expr, symbols) for expr in rhs]
        rhs_funcs = [
            sp.lambdify([x] + states, expr, modules="numpy")
            for expr in rhs_exprs
        ]

        bc_symbols = {"ya" + str(i): sp.Symbol("ya" + str(i)) for i in range(n)}
        bc_symbols.update({"yb" + str(i): sp.Symbol("yb" + str(i)) for i in range(n)})
        bc_exprs = [
            SafeExpressionParser.parse(expr, bc_symbols)
            for expr in boundary_conditions
        ]
        bc_funcs = [
            sp.lambdify(
                [bc_symbols[f"ya{i}"] for i in range(n)]
                + [bc_symbols[f"yb{i}"] for i in range(n)],
                expr,
                modules="numpy",
            )
            for expr in bc_exprs
        ]

        def fun(x_values, y_values):
            return np.vstack([
                function(x_values, *y_values)
                for function in rhs_funcs
            ])

        def bc(ya, yb):
            arguments = list(ya) + list(yb)
            return np.asarray([function(*arguments) for function in bc_funcs], dtype=float)

        solution = solve_bvp(
            fun,
            bc,
            np.asarray(mesh, dtype=float),
            np.asarray(initial_guess, dtype=float),
            tol=tol,
        )

        return {
            "problem_type": "BVP",
            "success": bool(solution.success),
            "message": solution.message,
            "nodes": solution.x.tolist(),
            "solution": solution.y.tolist(),
            "max_rms_residual": float(np.max(solution.rms_residuals)) if solution.rms_residuals.size > 0 else 0.0,
            "tolerance": tol,
        }

    @staticmethod
    def solve_symbolic_first_order_ode(rhs, independent="x", dependent="y", initial=None):
        x = sp.Symbol(independent)
        y_function = sp.Function(dependent)
        y = y_function(x)

        symbols = {
            independent: x,
            dependent: y,
        }
        rhs_expr = SafeExpressionParser.parse(rhs, symbols, auto_declare=True)
        equation = sp.Eq(sp.diff(y, x), rhs_expr)

        ics = None
        if initial is not None:
            if "x0" not in initial or "y0" not in initial:
                raise ValueError("Condição inicial requer x0 e y0.")
            ics = {y.subs(x, initial["x0"]): initial["y0"]}

        answer = sp.dsolve(equation, y, ics=ics)
        return {
            "problem_type": "symbolic_first_order_ODE",
            "equation": str(equation),
            "solution": str(answer),
            "initial_condition": initial,
            "note": "Solução simbólica obtida pelo SymPy; confira domínio e hipóteses.",
        }

    @staticmethod
    def audit_mpc_feasibility(x0, constraints, tolerance=0.0):
        violations = []

        for state, value in x0.items():
            if state not in constraints:
                continue

            limit = constraints[state]
            if "min" in limit and value < limit["min"] - tolerance:
                violations.append({
                    "state": state,
                    "value": value,
                    "constraint": "min",
                    "limit": limit["min"],
                })
            if "max" in limit and value > limit["max"] + tolerance:
                violations.append({
                    "state": state,
                    "value": value,
                    "constraint": "max",
                    "limit": limit["max"],
                })

        return {
            "initial_state_feasible": not violations,
            "violations": violations,
            "scope": "Checagem do estado inicial; não prova viabilidade recursiva em horizonte N.",
        }

    @staticmethod
    def audit_energy_profile(time_seconds, generation_w, load_w, losses_w=None):
        t = np.asarray(time_seconds, dtype=float)
        generation = np.asarray(generation_w, dtype=float)
        load = np.asarray(load_w, dtype=float)
        losses = (
            np.zeros_like(t)
            if losses_w is None
            else np.asarray(losses_w, dtype=float)
        )

        if not (len(t) == len(generation) == len(load) == len(losses)):
            raise ValueError("Todos os perfis devem ter o mesmo número de amostras.")
        if len(t) < 2 or np.any(np.diff(t) <= 0):
            raise ValueError("O tempo deve ter pelo menos dois pontos e ser estritamente crescente.")

        e_gen_wh = float(_trapz(generation, t) / 3600.0)
        e_load_wh = float(_trapz(load, t) / 3600.0)
        e_losses_wh = float(_trapz(losses, t) / 3600.0)
        net_wh = e_gen_wh - e_load_wh - e_losses_wh

        return {
            "generation_Wh": e_gen_wh,
            "load_Wh": e_load_wh,
            "losses_Wh": e_losses_wh,
            "net_energy_Wh": net_wh,
            "net_nonnegative": bool(net_wh >= 0),
            "note": "Para validar SoC da bateria, inclua capacidade nominal, DoD máximo e eficiências de carga/descarga.",
        }

    @staticmethod
    def audit_ahp_matrix(matrix, ri_table=None, threshold=0.10, tolerance=1e-6):
        A = np.asarray(matrix, dtype=float)

        if A.ndim != 2 or A.shape[0] != A.shape[1] or A.shape[0] == 0:
            return {"valid": False, "error": "A matriz deve ser quadrada e não vazia."}
        if not np.isfinite(A).all() or np.any(A <= 0):
            return {"valid": False, "error": "Entradas AHP devem ser finitas e estritamente positivas."}

        n = int(A.shape[0])
        reciprocal = bool(np.allclose(A * A.T, np.ones_like(A), atol=tolerance))
        unit_diagonal = bool(np.allclose(np.diag(A), np.ones(n), atol=tolerance))

        if not reciprocal or not unit_diagonal:
            return {
                "valid": False,
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
            return {"valid": False, "error": "Autovetor principal degenerado (soma zero)."}
        weights = weights / w_sum

        ci = 0.0 if n <= 1 else max(0.0, (lambda_max - n) / (n - 1))

        default_ri = {
            1: 0.00, 2: 0.00, 3: 0.58, 4: 0.90, 5: 1.12,
            6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45, 10: 1.49,
            11: 1.51, 12: 1.48, 13: 1.56, 14: 1.57, 15: 1.59,
        }
        if ri_table is None:
            ri = default_ri.get(n)
        else:
            ri = ri_table.get(n, ri_table.get(str(n), default_ri.get(n)))

        cr = 0.0 if (ri is not None and ri == 0.0 and n <= 2) else (None if ri is None or ri == 0 else float(ci / ri))

        return {
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
            "consistent_at_threshold": None if cr is None else bool(cr < threshold),
            "threshold": threshold,
            "note": "CR < 0.10 valida a consistência lógica dos julgamentos, não a validade física dos critérios.",
        }


def execute_single_operation(request):
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
            **{
                key: request[key]
                for key in ["rhs", "t_span", "y0"]
                if key in request
            },
            **{
                key: request[key]
                for key in ["t_eval", "parameters", "method", "rtol", "atol", "max_step"]
                if key in request
            },
        )
    if operation == "ode_bvp":
        return MathematicalFirewall.solve_ode_bvp(
            **{
                key: request[key]
                for key in ["rhs", "boundary_conditions", "interval", "mesh", "initial_guess"]
                if key in request
            },
            **({"tol": request["tol"]} if "tol" in request else {}),
        )
    if operation == "ode_symbolic":
        return MathematicalFirewall.solve_symbolic_first_order_ode(
            rhs=request["rhs"],
            independent=request.get("independent", "x"),
            dependent=request.get("dependent", "y"),
            initial=request.get("initial"),
        )
    if operation == "matrix":
        return MathematicalFirewall.audit_matrix(
            request["matrix"],
            request.get("tolerance", 1e-10),
        )
    if operation == "linear_system":
        return MathematicalFirewall.solve_linear_system(
            request["matrix"], request["vector"]
        )
    if operation == "formula":
        return MathematicalFirewall.check_formula(
            request["lhs"],
            request["rhs"],
            request.get("substitutions"),
            request.get("tolerance", 1e-9),
        )
    if operation == "differentiate":
        return MathematicalFirewall.differentiate(
            request["expression"],
            request["variable"],
            request.get("order", 1),
        )
    if operation == "integrate":
        return MathematicalFirewall.integrate(
            request["expression"],
            request["variable"],
            request.get("lower"),
            request.get("upper"),
        )
    if operation == "simplify":
        return MathematicalFirewall.simplify_expression(
            request["expression"],
            request.get("variables"),
        )
    if operation == "mpc_feasibility":
        return MathematicalFirewall.audit_mpc_feasibility(
            request["x0"],
            request["constraints"],
            request.get("tolerance", 0.0),
        )
    if operation == "energy_profile":
        return MathematicalFirewall.audit_energy_profile(
            request["time_seconds"],
            request["generation_w"],
            request["load_w"],
            request.get("losses_w"),
        )
    if operation == "ahp_matrix":
        return MathematicalFirewall.audit_ahp_matrix(
            request["matrix"],
            request.get("ri_table"),
            request.get("threshold", 0.10),
            request.get("tolerance", 1e-6),
        )
    raise ValueError(f"Operação desconhecida: {operation}")


def process_payload(payload):
    """Aceita uma única operação (dict) ou um lote de operações (dict com 'operations' ou list)."""
    if isinstance(payload, list) or (isinstance(payload, dict) and payload.get("operation") == "batch"):
        items = payload if isinstance(payload, list) else payload.get("operations", [])
        results = []
        for idx, item in enumerate(items, start=1):
            label = item.get("id") or item.get("label") or f"op_{idx}"
            try:
                res = execute_single_operation(item)
                res["id"] = label
                res["success"] = True
                results.append(res)
            except Exception as err:
                results.append({
                    "id": label,
                    "operation": item.get("operation"),
                    "success": False,
                    "error_type": type(err).__name__,
                    "error": str(err),
                })
        return {
            "batch": True,
            "total_operations": len(results),
            "succeeded": sum(1 for r in results if r.get("success")),
            "failed": sum(1 for r in results if not r.get("success")),
            "results": results,
        }

    res = execute_single_operation(payload)
    res["success"] = True
    return res


def main():
    parser = argparse.ArgumentParser(
        description="Motor matemático determinístico para auditoria de artigos científicos."
    )
    parser.add_argument("--input", "-i", help="Arquivo JSON de entrada (opcional; se omitido, lê de stdin).")
    parser.add_argument("--out", "-o", help="Arquivo JSON de saída (opcional; se omitido, imprime em stdout).")
    args = parser.parse_args()

    try:
        if args.input:
            raw_json = Path(args.input).read_text(encoding="utf-8")
            request = json.loads(raw_json)
        else:
            request = json.load(sys.stdin)

        result = process_payload(request)
        sanitized = _sanitize_for_json(result)
        serialized = json.dumps(sanitized, ensure_ascii=False, indent=2, allow_nan=False)

        if args.out:
            Path(args.out).write_text(serialized, encoding="utf-8")
            print(f"Resultado matemático salvo em: {args.out}")
        else:
            print(serialized)

    except Exception as error:
        err_out = json.dumps(
            {
                "success": False,
                "error_type": type(error).__name__,
                "error": str(error),
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
