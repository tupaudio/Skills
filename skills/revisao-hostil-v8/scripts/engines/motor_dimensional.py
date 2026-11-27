#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Motor dimensional determinístico (Revisão Hostil v8.0-beta.3).

Implementa:
- Análise dimensional de expressões simbólicas;
- Homogeneidade dimensional de equações (lhs == rhs);
- Conversão de unidades simples e compostas;
- Temperatura absoluta (K, degC, degF) vs. diferença de temperatura (delta_K, delta_degC, delta_degF);
- Detecção de confusão entre potência (W/kW/MW) e energia (J/Wh/kWh/MWh).

Baseado em vetores SI-7 exatos: (M, L, T, I, Theta, N, J) — 100% determinístico e sem dependências frágeis.
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

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.common import SCHEMA_VERSION
from scripts.common.evidence import create_evidence, create_finding, utc_now_iso
from scripts.common.validation import MAX_JSON_PAYLOAD_BYTES, read_bounded_json, require_finite_number, sanitize_for_json

MOTOR_ID = "motor_dimensional"
MOTOR_VERSION = "0.1.0-beta.3.1"

# Vetor dimensional SI-7: (M, L, T, I, Theta, N, J)
DimVec = tuple[float, float, float, float, float, float, float]
DIM_NAMES = ("M", "L", "T", "I", "Theta", "N", "J")

DIM_ONE: DimVec = (0, 0, 0, 0, 0, 0, 0)
DIM_MASS: DimVec = (1, 0, 0, 0, 0, 0, 0)
DIM_LEN: DimVec = (0, 1, 0, 0, 0, 0, 0)
DIM_TIME: DimVec = (0, 0, 1, 0, 0, 0, 0)
DIM_CURR: DimVec = (0, 0, 0, 1, 0, 0, 0)
DIM_TEMP: DimVec = (0, 0, 0, 0, 1, 0, 0)
DIM_MOL: DimVec = (0, 0, 0, 0, 0, 1, 0)
DIM_LUM: DimVec = (0, 0, 0, 0, 0, 0, 1)

DIM_AREA: DimVec = (0, 2, 0, 0, 0, 0, 0)
DIM_VOL: DimVec = (0, 3, 0, 0, 0, 0, 0)
DIM_VEL: DimVec = (0, 1, -1, 0, 0, 0, 0)
DIM_ACC: DimVec = (0, 1, -2, 0, 0, 0, 0)
DIM_FREQ: DimVec = (0, 0, -1, 0, 0, 0, 0)
DIM_FORCE: DimVec = (1, 1, -2, 0, 0, 0, 0)
DIM_PRESSURE: DimVec = (1, -1, -2, 0, 0, 0, 0)
DIM_ENERGY: DimVec = (1, 2, -2, 0, 0, 0, 0)
DIM_POWER: DimVec = (1, 2, -3, 0, 0, 0, 0)
DIM_CHARGE: DimVec = (0, 0, 1, 1, 0, 0, 0)
DIM_VOLTAGE: DimVec = (1, 2, -3, -1, 0, 0, 0)
DIM_RESIST: DimVec = (1, 2, -3, -2, 0, 0, 0)
DIM_CAP: DimVec = (-1, -2, 4, 2, 0, 0, 0)
DIM_IND: DimVec = (1, 2, -2, -2, 0, 0, 0)

# Mapa: unidade -> (fator_SI, dimensão_SI, offset_afim_para_K_ou_None)
UNIT_TABLE: dict[str, tuple[float, DimVec, float | None]] = {
    "1": (1.0, DIM_ONE, None),
    "dimensionless": (1.0, DIM_ONE, None),
    "rad": (1.0, DIM_ONE, None),
    "deg": (math.pi / 180.0, DIM_ONE, None),
    "%": (0.01, DIM_ONE, None),
    # Massa
    "kg": (1.0, DIM_MASS, None),
    "g": (1e-3, DIM_MASS, None),
    "mg": (1e-6, DIM_MASS, None),
    "t": (1e3, DIM_MASS, None),
    # Comprimento
    "m": (1.0, DIM_LEN, None),
    "km": (1e3, DIM_LEN, None),
    "cm": (1e-2, DIM_LEN, None),
    "mm": (1e-3, DIM_LEN, None),
    "um": (1e-6, DIM_LEN, None),
    "nm": (1e-9, DIM_LEN, None),
    # Tempo
    "s": (1.0, DIM_TIME, None),
    "ms": (1e-3, DIM_TIME, None),
    "us": (1e-6, DIM_TIME, None),
    "ns": (1e-9, DIM_TIME, None),
    "min": (60.0, DIM_TIME, None),
    "h": (3600.0, DIM_TIME, None),
    "day": (86400.0, DIM_TIME, None),
    # Corrente e Elétrica
    "A": (1.0, DIM_CURR, None),
    "mA": (1e-3, DIM_CURR, None),
    "uA": (1e-6, DIM_CURR, None),
    "C": (1.0, DIM_CHARGE, None),
    "Ah": (3600.0, DIM_CHARGE, None),
    "mAh": (3.6, DIM_CHARGE, None),
    "V": (1.0, DIM_VOLTAGE, None),
    "mV": (1e-3, DIM_VOLTAGE, None),
    "kV": (1e3, DIM_VOLTAGE, None),
    "Ohm": (1.0, DIM_RESIST, None),
    "kOhm": (1e3, DIM_RESIST, None),
    "MOhm": (1e6, DIM_RESIST, None),
    "F": (1.0, DIM_CAP, None),
    "uF": (1e-6, DIM_CAP, None),
    "nF": (1e-9, DIM_CAP, None),
    "pF": (1e-12, DIM_CAP, None),
    "H": (1.0, DIM_IND, None),
    "mH": (1e-3, DIM_IND, None),
    "uH": (1e-6, DIM_IND, None),
    # Frequência
    "Hz": (1.0, DIM_FREQ, None),
    "kHz": (1e3, DIM_FREQ, None),
    "MHz": (1e6, DIM_FREQ, None),
    "GHz": (1e9, DIM_FREQ, None),
    # Mecânica
    "N": (1.0, DIM_FORCE, None),
    "kN": (1e3, DIM_FORCE, None),
    "Pa": (1.0, DIM_PRESSURE, None),
    "kPa": (1e3, DIM_PRESSURE, None),
    "MPa": (1e6, DIM_PRESSURE, None),
    "GPa": (1e9, DIM_PRESSURE, None),
    "bar": (1e5, DIM_PRESSURE, None),
    "atm": (101325.0, DIM_PRESSURE, None),
    # Energia
    "J": (1.0, DIM_ENERGY, None),
    "kJ": (1e3, DIM_ENERGY, None),
    "MJ": (1e6, DIM_ENERGY, None),
    "GJ": (1e9, DIM_ENERGY, None),
    "Wh": (3600.0, DIM_ENERGY, None),
    "kWh": (3.6e6, DIM_ENERGY, None),
    "MWh": (3.6e9, DIM_ENERGY, None),
    "eV": (1.602176634e-19, DIM_ENERGY, None),
    # Potência
    "W": (1.0, DIM_POWER, None),
    "mW": (1e-3, DIM_POWER, None),
    "kW": (1e3, DIM_POWER, None),
    "MW": (1e6, DIM_POWER, None),
    "GW": (1e9, DIM_POWER, None),
    # Volume
    "L": (1e-3, DIM_VOL, None),
    "mL": (1e-6, DIM_VOL, None),
    # Temperatura absoluta (K, degC, degF) e diferença (delta_K, delta_degC, delta_degF)
    "K": (1.0, DIM_TEMP, 0.0),
    "degC": (1.0, DIM_TEMP, 273.15),
    "degF": (5.0 / 9.0, DIM_TEMP, 459.67 * 5.0 / 9.0),
    "delta_K": (1.0, DIM_TEMP, None),
    "delta_degC": (1.0, DIM_TEMP, None),
    "delta_degF": (5.0 / 9.0, DIM_TEMP, None),
    # Mol e luminosidade
    "mol": (1.0, DIM_MOL, None),
    "cd": (1.0, DIM_LUM, None),
}

ABSOLUTE_TEMP_UNITS = {"K", "degC", "degF"}
DELTA_TEMP_UNITS = {"delta_K", "delta_degC", "delta_degF"}


def _dim_add(a: DimVec, b: DimVec) -> DimVec:
    return tuple(x + y for x, y in zip(a, b))  # type: ignore[return-value]


def _dim_sub(a: DimVec, b: DimVec) -> DimVec:
    return tuple(x - y for x, y in zip(a, b))  # type: ignore[return-value]


def _dim_scale(a: DimVec, k: float) -> DimVec:
    return tuple(x * k for x in a)  # type: ignore[return-value]


def _dim_equal(a: DimVec, b: DimVec, tol: float = 1e-9) -> bool:
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def format_dim(dim: DimVec) -> str:
    parts = []
    for name, exp in zip(DIM_NAMES, dim):
        if abs(exp) > 1e-9:
            if abs(exp - round(exp)) < 1e-9:
                e_int = int(round(exp))
                parts.append(name if e_int == 1 else f"{name}^{e_int}")
            else:
                parts.append(f"{name}^{exp:g}")
    return " * ".join(parts) if parts else "1 (adimensional)"


def parse_unit(unit_expr: str) -> tuple[float, DimVec, bool]:
    """Faz parsing seguro de unidade simples ou composta (ex.: 'W/(m^2*K^4)').
    Retorna (fator_SI, dimensão_SI, is_affine_temp).
    """
    cleaned = (
        unit_expr.strip()
        .replace("°C", "degC")
        .replace("°F", "degF")
        .replace("Δ°C", "delta_degC")
        .replace("ΔK", "delta_K")
        .replace("²", "**2")
        .replace("³", "**3")
        .replace("⁴", "**4")
        .replace("·", "*")
        .replace("^", "**")
    )
    if cleaned in UNIT_TABLE:
        factor, dim, offset = UNIT_TABLE[cleaned]
        return factor, dim, (offset is not None and offset != 0.0)

    tree = ast.parse(cleaned, mode="eval")

    def _eval(node: ast.AST) -> tuple[float, DimVec]:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            if float(node.value) == 1.0:
                return 1.0, DIM_ONE
            return float(node.value), DIM_ONE
        if isinstance(node, ast.Name):
            if node.id not in UNIT_TABLE:
                raise ValueError(f"Unidade desconhecida: '{node.id}'")
            factor, dim, offset = UNIT_TABLE[node.id]
            if offset is not None and offset != 0.0:
                raise ValueError(
                    f"Temperatura afim '{node.id}' não pode ser multiplicada/dividida em unidade composta; "
                    f"use 'K' ou 'delta_{node.id}'."
                )
            return factor, dim
        if isinstance(node, ast.BinOp):
            if isinstance(node.op, ast.Mult):
                f1, d1 = _eval(node.left)
                f2, d2 = _eval(node.right)
                return f1 * f2, _dim_add(d1, d2)
            if isinstance(node.op, ast.Div):
                f1, d1 = _eval(node.left)
                f2, d2 = _eval(node.right)
                return f1 / f2, _dim_sub(d1, d2)
            if isinstance(node.op, ast.Pow):
                f1, d1 = _eval(node.left)
                if isinstance(node.right, ast.Constant) and isinstance(node.right.value, (int, float)):
                    exp = float(node.right.value)
                elif (
                    isinstance(node.right, ast.UnaryOp)
                    and isinstance(node.right.op, ast.USub)
                    and isinstance(node.right.operand, ast.Constant)
                ):
                    exp = -float(node.right.operand.value)
                else:
                    raise ValueError("Expoente de unidade deve ser constante numérica.")
                return f1**exp, _dim_scale(d1, exp)
        raise ValueError(f"Expressão de unidade inválida: '{unit_expr}'")

    factor, dim = _eval(tree.body)
    return factor, dim, False


def convert_unit(value: float, from_unit: str, to_unit: str) -> dict[str, Any]:
    val = require_finite_number(value, name="value")
    fu = from_unit.strip().replace("°C", "degC").replace("°F", "degF")
    tu = to_unit.strip().replace("°C", "degC").replace("°F", "degF")

    # Proíbe conversão ambígua entre temperatura absoluta e diferença de temperatura
    if (fu in ABSOLUTE_TEMP_UNITS and tu in DELTA_TEMP_UNITS) or (
        fu in DELTA_TEMP_UNITS and tu in ABSOLUTE_TEMP_UNITS
    ):
        return {
            "operation": "convert_unit",
            "compatible": False,
            "status": "discrepancy_detected",
            "error": (
                f"Incompatibilidade conceitual: '{from_unit}' (temperatura absoluta/diferença) "
                f"não deve ser convertida diretamente para '{to_unit}'."
            ),
        }

    # Caso especial: temperatura absoluta afim
    if fu in ABSOLUTE_TEMP_UNITS and tu in ABSOLUTE_TEMP_UNITS:
        f_from, d_from, off_from = UNIT_TABLE[fu]
        f_to, d_to, off_to = UNIT_TABLE[tu]
        val_k = val * f_from + (off_from or 0.0)
        converted = (val_k - (off_to or 0.0)) / f_to
        return {
            "operation": "convert_unit",
            "value": val,
            "from_unit": from_unit,
            "to_unit": to_unit,
            "converted_value": converted,
            "dimension": format_dim(d_from),
            "compatible": True,
            "status": "ok",
        }

    f1, d1, _ = parse_unit(fu)
    f2, d2, _ = parse_unit(tu)
    if not _dim_equal(d1, d2):
        return {
            "operation": "convert_unit",
            "value": val,
            "from_unit": from_unit,
            "to_unit": to_unit,
            "from_dimension": format_dim(d1),
            "to_dimension": format_dim(d2),
            "compatible": False,
            "status": "discrepancy_detected",
            "error": f"Dimensões incompatíveis: {format_dim(d1)} != {format_dim(d2)}.",
        }

    return {
        "operation": "convert_unit",
        "value": val,
        "from_unit": from_unit,
        "to_unit": to_unit,
        "converted_value": val * f1 / f2,
        "dimension": format_dim(d1),
        "compatible": True,
        "status": "ok",
    }


def analyze_expression_dimension(expression: str, variable_units: dict[str, str]) -> dict[str, Any]:
    """Inferência dimensional determinística separando dimensão física e natureza de temperatura
    ('absolute' vs 'interval' vs 'standard') — correção ACH-003.
    """
    var_info: dict[str, tuple[DimVec, str]] = {}
    for var, u in variable_units.items():
        u_clean = u.strip().replace("°C", "degC").replace("°F", "degF").replace("Δ°C", "delta_degC").replace("ΔK", "delta_K")
        _, dim, is_affine = parse_unit(u_clean)
        if is_affine:
            raise ValueError(
                f"Variável '{var}' usa temperatura afim '{u}'. Converta para 'K' ou 'delta_degC' antes de usar em equações."
            )
        if u_clean in ABSOLUTE_TEMP_UNITS:
            kind = "absolute"
        elif u_clean in DELTA_TEMP_UNITS:
            kind = "interval"
        else:
            kind = "standard"
        var_info[var] = (dim, kind)

    cleaned = expression.strip().replace("^", "**")
    tree = ast.parse(cleaned, mode="eval")
    incompatibilities: list[str] = []

    def _infer(node: ast.AST) -> tuple[DimVec, str]:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return DIM_ONE, "standard"
        if isinstance(node, ast.Name):
            if node.id in ("pi", "E"):
                return DIM_ONE, "standard"
            if node.id not in var_info:
                raise ValueError(f"Unidade não informada para a variável '{node.id}'.")
            return var_info[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            return _infer(node.operand)
        if isinstance(node, ast.BinOp):
            d_left, k_left = _infer(node.left)
            d_right, k_right = _infer(node.right)
            if isinstance(node.op, (ast.Add, ast.Sub)):
                if not _dim_equal(d_left, d_right):
                    incompatibilities.append(
                        f"Soma/subtração entre dimensões incompatíveis: [{format_dim(d_left)}] e [{format_dim(d_right)}]."
                    )
                    return d_left, k_left
                # Regras algébricas para temperatura absoluta vs intervalo (ACH-003)
                if _dim_equal(d_left, DIM_TEMP):
                    if isinstance(node.op, ast.Add):
                        if k_left == "absolute" and k_right == "absolute":
                            incompatibilities.append(
                                "Soma de duas temperaturas absolutas (K + K) é fisicamente inválida; "
                                "use temperatura absoluta + diferença de temperatura (delta_K/delta_degC)."
                            )
                            return d_left, "absolute"
                        if "absolute" in (k_left, k_right):
                            return d_left, "absolute"
                        return d_left, "interval"
                    # Subtração
                    if k_left == "absolute" and k_right == "absolute":
                        return d_left, "interval"
                    if k_left == "absolute" and k_right == "interval":
                        return d_left, "absolute"
                    if k_left == "interval" and k_right == "absolute":
                        incompatibilities.append(
                            "Subtração (diferença de temperatura - temperatura absoluta) é fisicamente inválida."
                        )
                        return d_left, "absolute"
                    return d_left, "interval"
                return d_left, "standard"
            if isinstance(node.op, ast.Mult):
                return _dim_add(d_left, d_right), "standard"
            if isinstance(node.op, ast.Div):
                return _dim_sub(d_left, d_right), "standard"
            if isinstance(node.op, ast.Pow):
                if not _dim_equal(d_right, DIM_ONE):
                    incompatibilities.append(
                        f"Expoente deve ser adimensional, recebido [{format_dim(d_right)}]."
                    )
                    return d_left, "standard"
                if isinstance(node.right, ast.Constant) and isinstance(node.right.value, (int, float)):
                    exp = float(node.right.value)
                elif (
                    isinstance(node.right, ast.UnaryOp)
                    and isinstance(node.right.op, ast.USub)
                    and isinstance(node.right.operand, ast.Constant)
                ):
                    exp = -float(node.right.operand.value)
                else:
                    raise ValueError("Expoente em análise dimensional deve ser constante numérica.")
                return _dim_scale(d_left, exp), "standard"
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            fname = node.func.id
            arg_results = [_infer(a) for a in node.args]
            if fname == "sqrt" and len(arg_results) == 1:
                return _dim_scale(arg_results[0][0], 0.5), "standard"
            if fname in ("abs", "Abs") and len(arg_results) == 1:
                return arg_results[0]
            if fname in ("sin", "cos", "tan", "exp", "log", "ln", "log10", "sinh", "cosh", "tanh"):
                if len(arg_results) == 1 and not _dim_equal(arg_results[0][0], DIM_ONE):
                    incompatibilities.append(
                        f"Função transcendental '{fname}' recebeu argumento com dimensão [{format_dim(arg_results[0][0])}]."
                    )
                return DIM_ONE, "standard"
        raise ValueError(f"Construção não suportada na análise dimensional: {ast.dump(node)}")

    dim, temp_kind = _infer(tree.body)
    return {
        "operation": "expression_dimension",
        "expression": expression,
        "dimension_vector": list(dim),
        "dimension": format_dim(dim),
        "quantity_nature": temp_kind,
        "homogeneous": len(incompatibilities) == 0,
        "incompatibilities": incompatibilities,
        "status": "ok" if not incompatibilities else "discrepancy_detected",
    }


def check_equation_homogeneity(lhs: str, rhs: str, variable_units: dict[str, str]) -> dict[str, Any]:
    l_res = analyze_expression_dimension(lhs, variable_units)
    r_res = analyze_expression_dimension(rhs, variable_units)
    d_l = tuple(l_res["dimension_vector"])
    d_r = tuple(r_res["dimension_vector"])
    incompat = list(l_res["incompatibilities"]) + list(r_res["incompatibilities"])
    sides_match = _dim_equal(d_l, d_r)  # type: ignore[arg-type]
    if not sides_match:
        incompat.append(f"LHS [{l_res['dimension']}] != RHS [{r_res['dimension']}].")
    elif _dim_equal(d_l, DIM_TEMP) and l_res["quantity_nature"] != r_res["quantity_nature"]:  # type: ignore[arg-type]
        if {l_res["quantity_nature"], r_res["quantity_nature"]} == {"absolute", "interval"}:
            incompat.append(
                f"Incompatibilidade de natureza térmica: LHS ({l_res['quantity_nature']}) != RHS ({r_res['quantity_nature']})."
            )
    homogeneous = len(incompat) == 0
    return {
        "operation": "equation_homogeneity",
        "lhs": lhs,
        "rhs": rhs,
        "lhs_dimension": l_res["dimension"],
        "rhs_dimension": r_res["dimension"],
        "lhs_nature": l_res["quantity_nature"],
        "rhs_nature": r_res["quantity_nature"],
        "homogeneous": homogeneous,
        "incompatibilities": incompat,
        "status": "ok" if homogeneous else "discrepancy_detected",
    }


def check_power_vs_energy(quantity_kind: str, unit: str) -> dict[str, Any]:
    """Verifica se a grandeza declarada ('power' ou 'energy') corresponde à unidade informada."""
    _, dim, _ = parse_unit(unit)
    expected = DIM_POWER if quantity_kind.lower() in ("power", "potencia", "potência") else DIM_ENERGY
    matches = _dim_equal(dim, expected)
    return {
        "operation": "power_vs_energy",
        "declared_kind": quantity_kind,
        "unit": unit,
        "unit_dimension": format_dim(dim),
        "expected_dimension": format_dim(expected),
        "consistent": matches,
        "status": "ok" if matches else "discrepancy_detected",
    }


def execute_single_operation(request: dict[str, Any]) -> dict[str, Any]:
    op = request.get("operation")
    if op == "convert_unit":
        return convert_unit(request["value"], request["from_unit"], request["to_unit"])
    if op == "expression_dimension":
        return analyze_expression_dimension(request["expression"], request.get("variable_units", {}))
    if op == "equation_homogeneity":
        return check_equation_homogeneity(request["lhs"], request["rhs"], request.get("variable_units", {}))
    if op == "power_vs_energy":
        return check_power_vs_energy(request["quantity_kind"], request["unit"])
    raise ValueError(f"Operação dimensional desconhecida: {op}")


def run_motor(payload: Any, *, run_id: str | None = None, artefato_alvo: str | None = None) -> dict[str, Any]:
    inner = payload["payload"] if isinstance(payload, dict) and "payload" in payload and "motor_id" in payload else payload
    items = inner.get("operations", []) if isinstance(inner, dict) and inner.get("operation") == "batch" else (inner if isinstance(inner, list) else [inner])

    results: list[dict[str, Any]] = []
    achados: list[dict[str, Any]] = []
    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            results.append(
                {
                    "id": f"DIM_{idx:03d}",
                    "operation": "unknown",
                    "success": False,
                    "status": "error",
                    "error": f"Item de lote inválido no índice {idx}: esperado objeto/dicionário, recebido {type(item).__name__}.",
                }
            )
            continue

        op_id = str(item.get("id") or f"DIM_{idx:03d}")
        try:
            res = execute_single_operation(item)
            res["id"] = op_id
            res["success"] = True
            results.append(res)
            if res.get("status") == "discrepancy_detected":
                ev = create_evidence(
                    f"EV-DIM-{idx:03d}",
                    "simbolica",
                    artefato_alvo or "payload_inline",
                    op_id,
                    json.dumps(res, ensure_ascii=False)[:800],
                    motor_origem=MOTOR_ID,
                )
                achados.append(
                    create_finding(
                        f"ACH-DIM-{idx:03d}",
                        f"Incompatibilidade dimensional em {op_id}",
                        "incompatibilidade_dimensional",
                        "CRITICO",
                        "ALTA",
                        op_id,
                        res.get("error") or "; ".join(res.get("incompatibilities", [])) or "Incompatibilidade dimensional.",
                        [ev],
                        estado="CONFIRMADO",
                        portao="G03",
                        origem_componente=MOTOR_ID,
                    )
                )
        except Exception as err:
            results.append({"id": op_id, "operation": item.get("operation"), "success": False, "status": "error", "error": str(err)})

    failed = sum(1 for r in results if not r.get("success"))
    status = "ERRO_VALIDACAO" if failed == len(results) else ("PARCIAL" if failed > 0 else ("COM_ACHADOS" if achados else "OK"))
    return sanitize_for_json(
        {
            "schema_version": SCHEMA_VERSION,
            "motor_id": MOTOR_ID,
            "motor_version": MOTOR_VERSION,
            "run_id": run_id,
            "deterministico": True,
            "status": status,
            "timestamp": utc_now_iso(),
            "artefato_alvo": artefato_alvo,
            "hash_artefato": None,
            "metricas": {"total_operacoes": len(results), "sucesso": len(results) - failed, "falhas": failed, "total_achados": len(achados)},
            "resultados": {"results": results},
            "achados": achados,
            "limitacoes": [
                "Análise dimensional verifica coerência de unidades SI-7; não valida fatores numéricos adimensionais (ex.: 1/2 ou 2*pi)."
            ],
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Motor dimensional determinístico (Revisão Hostil v8.0-beta.3).")
    parser.add_argument("--input", "-i", help="Arquivo JSON de entrada (se omitido, lê de stdin).")
    parser.add_argument("--out", "-o", help="Arquivo JSON de saída (se omitido, imprime em stdout).")
    parser.add_argument("--run-id", help="Identificador opcional da campanha.")
    args = parser.parse_args()

    try:
        source = args.input if args.input else sys.stdin
        req, artefato = read_bounded_json(source, max_bytes=MAX_JSON_PAYLOAD_BYTES)
        out = run_motor(req, run_id=args.run_id, artefato_alvo=artefato)
        text = json.dumps(out, ensure_ascii=False, indent=2, allow_nan=False)
        if args.out:
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(text, encoding="utf-8")
        else:
            print(text)
        if isinstance(out, dict) and out.get("status") == "ERRO_VALIDACAO":
            sys.exit(1)
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
