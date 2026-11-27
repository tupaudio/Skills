#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Motor de incerteza determinístico (Revisão Hostil v8.0-beta.3).

Implementa (Passo 3.4):
- Propagação de incertezas via coeficientes de sensibilidade (GUM, derivadas parciais simbólicas SymPy);
- Incertezas correlacionadas via matriz de correlação (validada simétrica e PSD);
- Separação entre incerteza aleatória (Tipo A) e sistemática (Tipo B);
- Simulação Monte Carlo determinística com semente explícita (normal, uniform, triangular);
- Análise de sensibilidade (% de contribuição na variância total);
- Intervalo de incerteza expandida (k * u_c) e análise de pior caso (worst-case).
"""

from __future__ import annotations

import argparse
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

import numpy as np
import sympy as sp

from scripts.common import SCHEMA_VERSION
from scripts.common.evidence import create_evidence, create_finding, utc_now_iso
from scripts.common.validation import MAX_JSON_PAYLOAD_BYTES, read_bounded_json, require_finite_array, require_finite_number, sanitize_for_json
from scripts.engines.motor_matematico import SafeExpressionParser

MOTOR_ID = "motor_incerteza"
MOTOR_VERSION = "0.1.0-beta.3"


def propagate_gum(
    expression: str,
    variables: dict[str, dict[str, Any]],
    *,
    correlation_matrix: Any = None,
    coverage_factor_k: float = 2.0,
    reported_uncertainty: float | None = None,
    rel_tolerance: float = 0.05,
) -> dict[str, Any]:
    """Propagação GUM de 1ª ordem com suporte a correlação e separação Tipo A / Tipo B."""
    if not variables:
        raise ValueError("É necessário informar ao menos uma variável com valor nominal e incerteza.")
    k_cov = require_finite_number(coverage_factor_k, "coverage_factor_k")
    if k_cov <= 0:
        raise ValueError("coverage_factor_k deve ser > 0.")

    var_names = list(variables.keys())
    sym_map = {name: sp.Symbol(name) for name in var_names}
    expr = SafeExpressionParser.parse(expression, sym_map, auto_declare=False)

    nominals = {}
    u_a = []
    u_b = []
    u_tot = []
    for name in var_names:
        spec = variables[name]
        if not isinstance(spec, dict):
            raise ValueError(
                f"Especificação da variável '{name}' deve ser um objeto/dicionário, recebido {type(spec).__name__}."
            )
        nominals[name] = require_finite_number(spec.get("value"), f"variables.{name}.value")

        has_ur = "u_random" in spec
        has_us = "u_systematic" in spec
        has_u = "u" in spec

        if not (has_ur or has_us or has_u):
            raise ValueError(
                f"Variável '{name}' não possui incerteza informada: esperado campo 'u' ou componentes 'u_random' / 'u_systematic'."
            )

        ua = require_finite_number(spec.get("u_random", 0.0), f"variables.{name}.u_random") if has_ur else 0.0
        ub = require_finite_number(spec.get("u_systematic", 0.0), f"variables.{name}.u_systematic") if has_us else 0.0

        if has_u and not has_ur and not has_us:
            ut = require_finite_number(spec["u"], f"variables.{name}.u")
            ua = ut
        else:
            ut = math.hypot(ua, ub)

        if ua < 0 or ub < 0 or ut < 0:
            raise ValueError(f"Incertezas da variável '{name}' não podem ser negativas.")
        u_a.append(ua)
        u_b.append(ub)
        u_tot.append(ut)

    subs_map = {sym_map[name]: sp.Float(nominals[name]) for name in var_names}
    nominal_out = float(complex(expr.evalf(subs=subs_map)).real)

    sensitivities = []
    for name in var_names:
        deriv = sp.diff(expr, sym_map[name])
        c_i = float(complex(deriv.evalf(subs=subs_map)).real)
        sensitivities.append(c_i)

    c_vec = np.asarray(sensitivities, dtype=float)
    u_vec = np.asarray(u_tot, dtype=float)
    ua_vec = np.asarray(u_a, dtype=float)
    ub_vec = np.asarray(u_b, dtype=float)

    n = len(var_names)
    if correlation_matrix is None:
        corr = np.eye(n, dtype=float)
    else:
        corr = require_finite_array(correlation_matrix, "correlation_matrix", ndim=2)
        if corr.shape != (n, n):
            raise ValueError(f"correlation_matrix deve ter forma ({n}, {n}).")
        if not np.allclose(corr, corr.T, atol=1e-8) or not np.allclose(np.diag(corr), 1.0, atol=1e-8):
            raise ValueError("correlation_matrix deve ser simétrica com diagonal igual a 1.")
        eigvals = np.linalg.eigvalsh(corr)
        if np.min(eigvals) < -1e-8:
            raise ValueError("correlation_matrix não é semidefinida positiva.")

    cov = np.outer(u_vec, u_vec) * corr
    var_total = float(c_vec @ cov @ c_vec)
    u_combined = math.sqrt(max(0.0, var_total))
    u_expanded = k_cov * u_combined
    u_random_combined = math.sqrt(float(np.sum((c_vec * ua_vec) ** 2)))
    u_systematic_combined = math.sqrt(float(np.sum((c_vec * ub_vec) ** 2)))
    worst_case_delta = float(np.sum(np.abs(c_vec) * u_vec))

    # Contribuição de variância individual (diagonal)
    diag_vars = (c_vec * u_vec) ** 2
    denom = float(np.sum(diag_vars))
    contributions = {
        name: float(diag_vars[i] / denom * 100.0) if denom > 0 else 0.0
        for i, name in enumerate(var_names)
    }

    discrepancy = False
    if reported_uncertainty is not None:
        rep = require_finite_number(reported_uncertainty, "reported_uncertainty")
        discrepancy = abs(u_combined - rep) > max(1e-9, abs(rep) * rel_tolerance)

    return {
        "operation": "propagate_gum",
        "expression": expression,
        "nominal_output": nominal_out,
        "sensitivity_coefficients": {name: float(c_vec[i]) for i, name in enumerate(var_names)},
        "u_combined": u_combined,
        "u_expanded": u_expanded,
        "coverage_factor_k": k_cov,
        "interval_expanded": [nominal_out - u_expanded, nominal_out + u_expanded],
        "u_random_combined": u_random_combined,
        "u_systematic_combined": u_systematic_combined,
        "worst_case_delta": worst_case_delta,
        "variance_contribution_pct": contributions,
        "reported_uncertainty": reported_uncertainty,
        "status": "discrepancy_detected" if discrepancy else "ok",
    }


def monte_carlo_propagation(
    expression: str,
    variables: dict[str, dict[str, Any]],
    *,
    n_samples: int = 10000,
    seed: int = 42,
    confidence: float = 0.95,
) -> dict[str, Any]:
    if n_samples < 100:
        raise ValueError("n_samples deve ser >= 100.")
    var_names = list(variables.keys())
    sym_map = {name: sp.Symbol(name) for name in var_names}
    expr = SafeExpressionParser.parse(expression, sym_map, auto_declare=False)
    func = sp.lambdify([sym_map[name] for name in var_names], expr, modules="numpy")

    rng = np.random.default_rng(seed)
    draws = []
    for name in var_names:
        spec = variables[name]
        if not isinstance(spec, dict):
            raise ValueError(
                f"Especificação da variável '{name}' deve ser um objeto/dicionário, recebido {type(spec).__name__}."
            )
        dist = spec.get("dist", "normal").lower()
        if "value" not in spec:
            raise ValueError(f"Campo obrigatório 'value' ausente para a variável '{name}'.")
        val = require_finite_number(spec["value"], f"variables.{name}.value")
        if dist == "normal":
            if "std" not in spec:
                raise ValueError(
                    f"Variável '{name}' com distribuição normal requer o campo obrigatório de desvio padrão 'std'."
                )
            sd = require_finite_number(spec["std"], f"variables.{name}.std")
            if sd < 0:
                raise ValueError(f"std negativo em '{name}'.")
            draws.append(rng.normal(val, sd, size=n_samples))
        elif dist == "uniform":
            if "half_width" not in spec:
                raise ValueError(
                    f"Variável '{name}' com distribuição uniforme requer o campo obrigatório 'half_width'."
                )
            half = require_finite_number(spec["half_width"], f"variables.{name}.half_width")
            if half < 0:
                raise ValueError(f"half_width negativo em '{name}'.")
            draws.append(rng.uniform(val - half, val + half, size=n_samples))
        elif dist == "triangular":
            if "half_width" not in spec:
                raise ValueError(
                    f"Variável '{name}' com distribuição triangular requer o campo obrigatório 'half_width'."
                )
            half = require_finite_number(spec["half_width"], f"variables.{name}.half_width")
            if half < 0:
                raise ValueError(f"half_width negativo em '{name}'.")
            draws.append(rng.triangular(val - half, val, val + half, size=n_samples))
        else:
            raise ValueError(f"Distribuição não suportada em '{name}': {dist}")

    out = np.asarray(func(*draws), dtype=float)
    if not np.isfinite(out).all():
        raise ValueError("Simulação Monte Carlo gerou valores não finitos (NaN ou Inf).")

    alpha = 1.0 - confidence
    low, high = np.percentile(out, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return {
        "operation": "monte_carlo",
        "expression": expression,
        "n_samples": n_samples,
        "seed": seed,
        "mean": float(np.mean(out)),
        "std": float(np.std(out, ddof=1)),
        "median": float(np.median(out)),
        "confidence": confidence,
        "ci_lower": float(low),
        "ci_upper": float(high),
        "min": float(np.min(out)),
        "max": float(np.max(out)),
        "status": "ok",
    }


def execute_single_operation(request: dict[str, Any]) -> dict[str, Any]:
    op = request.get("operation")
    if op == "propagate_gum":
        return propagate_gum(
            request["expression"],
            request["variables"],
            correlation_matrix=request.get("correlation_matrix"),
            coverage_factor_k=request.get("coverage_factor_k", 2.0),
            reported_uncertainty=request.get("reported_uncertainty"),
            rel_tolerance=request.get("rel_tolerance", 0.05),
        )
    if op == "monte_carlo":
        return monte_carlo_propagation(
            request["expression"],
            request["variables"],
            n_samples=request.get("n_samples", 10000),
            seed=request.get("seed", 42),
            confidence=request.get("confidence", 0.95),
        )
    raise ValueError(f"Operação de incerteza desconhecida: {op}")


def run_motor(payload: Any, *, run_id: str | None = None, artefato_alvo: str | None = None) -> dict[str, Any]:
    inner = payload["payload"] if isinstance(payload, dict) and "payload" in payload and "motor_id" in payload else payload
    items = inner.get("operations", []) if isinstance(inner, dict) and inner.get("operation") == "batch" else (inner if isinstance(inner, list) else [inner])

    results: list[dict[str, Any]] = []
    achados: list[dict[str, Any]] = []
    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            results.append(
                {
                    "id": f"INC_{idx:03d}",
                    "operation": "unknown",
                    "success": False,
                    "status": "error",
                    "error": f"Item de lote inválido no índice {idx}: esperado objeto/dicionário, recebido {type(item).__name__}.",
                }
            )
            continue

        op_id = str(item.get("id") or f"INC_{idx:03d}")
        try:
            res = execute_single_operation(item)
            res["id"] = op_id
            res["success"] = True
            results.append(res)
            if res.get("status") == "discrepancy_detected":
                ev = create_evidence(
                    f"EV-INC-{idx:03d}",
                    "numerica",
                    artefato_alvo or "payload_inline",
                    op_id,
                    f"u_combinada={res.get('u_combined')} vs u_reportada={res.get('reported_uncertainty')}",
                    valor_observado=res.get("reported_uncertainty"),
                    valor_calculado=res.get("u_combined"),
                    motor_origem=MOTOR_ID,
                )
                achados.append(
                    create_finding(
                        f"ACH-INC-{idx:03d}",
                        f"Discrepância de incerteza em {op_id}",
                        "discrepancia_incerteza",
                        "MAIOR",
                        "ALTA",
                        op_id,
                        "Incerteza propagada pelo método GUM diverge da incerteza declarada.",
                        [ev],
                        estado="CONFIRMADO",
                        portao="G06",
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
                "O método GUM de 1ª ordem assume linearidade local em torno do ponto nominal; para forte não linearidade, confronte com monte_carlo."
            ],
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Motor de incerteza determinístico (Revisão Hostil v8.0-beta.3).")
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
