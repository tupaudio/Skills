#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Motor de integridade dos dados determinístico (Revisão Hostil v8.0-beta.3).

Implementa (Passo 3.5):
- Dados faltantes (contagem e percentual por coluna, sem classificar MAR/MNAR automaticamente);
- Duplicações (linhas duplicadas exatas e chaves primárias duplicadas);
- Valores inválidos (não numéricos, NaN/Inf, fora de faixa declarada);
- Outliers (IQR e Z-score modificado por MAD);
- Consistência entre amostras e estatísticas declaradas (N, média, desvio-padrão, min/max);
- Triagem de vazamento de dados em ML (sobreposição de IDs/linhas entre treino, validação e teste; vazamento temporal);
- Triagem de padrões suspeitos de valores-p (apenas sinaliza investigação, nunca declara p-hacking/fraude).
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

from scripts.common import SCHEMA_VERSION
from scripts.common.evidence import create_evidence, create_finding, utc_now_iso
from scripts.common.statistics import descriptive_summary
from scripts.common.validation import MAX_JSON_PAYLOAD_BYTES, read_bounded_json, require_finite_array, require_finite_number, sanitize_for_json

MOTOR_ID = "motor_dados"
MOTOR_VERSION = "0.2.0-beta.1"


def _is_missing(val: Any) -> bool:
    if val is None:
        return True
    if isinstance(val, str) and val.strip().lower() in ("", "na", "nan", "null", "none"):
        return True
    if isinstance(val, float) and math.isnan(val):
        return True
    return False


def audit_tabular_quality(
    rows: list[dict[str, Any]],
    *,
    key_column: str | None = None,
    numeric_bounds: dict[str, dict[str, float]] | None = None,
) -> dict[str, Any]:
    if not isinstance(rows, list) or not rows:
        raise ValueError("rows deve ser uma lista não vazia de dicionários.")

    columns = sorted({k for row in rows for k in row.keys()})
    n_rows = len(rows)

    missing_by_col: dict[str, dict[str, Any]] = {}
    total_missing = 0
    for col in columns:
        cnt = sum(1 for r in rows if _is_missing(r.get(col)))
        total_missing += cnt
        missing_by_col[col] = {"count": cnt, "pct": round(cnt / n_rows * 100.0, 2)}

    # Linhas duplicadas exatas
    seen_rows: set[str] = set()
    duplicate_row_indices: list[int] = []
    for idx, r in enumerate(rows):
        sig = json.dumps(r, sort_keys=True, ensure_ascii=False, default=str)
        if sig in seen_rows:
            duplicate_row_indices.append(idx)
        else:
            seen_rows.add(sig)

    duplicate_keys: list[Any] = []
    if key_column:
        seen_keys: set[Any] = set()
        for r in rows:
            k = r.get(key_column)
            if not _is_missing(k):
                if k in seen_keys:
                    duplicate_keys.append(k)
                else:
                    seen_keys.add(k)

    invalid_values: list[dict[str, Any]] = []
    for col, bounds in (numeric_bounds or {}).items():
        for idx, r in enumerate(rows):
            raw = r.get(col)
            if _is_missing(raw):
                continue
            try:
                v = require_finite_number(raw, col)
            except ValueError:
                invalid_values.append({"row": idx, "column": col, "value": raw, "reason": "non_numeric_or_non_finite"})
                continue
            if "min" in bounds and v < bounds["min"]:
                invalid_values.append({"row": idx, "column": col, "value": v, "reason": f"< min ({bounds['min']})"})
            if "max" in bounds and v > bounds["max"]:
                invalid_values.append({"row": idx, "column": col, "value": v, "reason": f"> max ({bounds['max']})"})

    has_issues = total_missing > 0 or bool(duplicate_row_indices) or bool(duplicate_keys) or bool(invalid_values)
    return {
        "operation": "tabular_quality",
        "n_rows": n_rows,
        "columns": columns,
        "total_missing_cells": total_missing,
        "missing_by_column": missing_by_col,
        "missingness_mechanism_classified": False,
        "missingness_note": (
            "Apenas quantifica ausências; classificação MCAR/MAR/MNAR não pode ser inferida somente "
            "observando valores ausentes sem hipóteses e metadados de coleta."
        ),
        "duplicate_row_count": len(duplicate_row_indices),
        "duplicate_row_indices": duplicate_row_indices,
        "duplicate_key_count": len(duplicate_keys),
        "invalid_values": invalid_values,
        "status": "discrepancy_detected" if has_issues else "ok",
    }


def detect_outliers(values: Any, *, iqr_factor: float = 1.5, mad_threshold: float = 3.5) -> dict[str, Any]:
    arr = require_finite_array(values, name="values", ndim=1)
    if arr.size < 4:
        raise ValueError("Detecção de outliers requer >= 4 observações.")

    q1, q3 = float(np.percentile(arr, 25)), float(np.percentile(arr, 75))
    iqr = q3 - q1
    low_iqr = q1 - iqr_factor * iqr
    high_iqr = q3 + iqr_factor * iqr
    iqr_indices = [int(i) for i, v in enumerate(arr) if v < low_iqr or v > high_iqr]

    med = float(np.median(arr))
    mad = float(np.median(np.abs(arr - med)))
    if mad > 0:
        mod_z = 0.6745 * (arr - med) / mad
        mad_indices = [int(i) for i, z in enumerate(mod_z) if abs(z) > mad_threshold]
    else:
        mad_indices = []

    return {
        "operation": "detect_outliers",
        "summary": descriptive_summary(arr),
        "iqr_bounds": [low_iqr, high_iqr],
        "iqr_outlier_indices": iqr_indices,
        "mad_outlier_indices": mad_indices,
        "status": "ok",
    }


def sample_vs_reported(
    values: Any,
    reported: dict[str, float],
    *,
    rel_tolerance: float = 0.02,
    abs_tolerance: float = 1e-4,
) -> dict[str, Any]:
    calc = descriptive_summary(values)
    mismatches = []
    for key in ("n", "mean", "median", "std", "min", "max"):
        if key in reported:
            rep = require_finite_number(reported[key], f"reported.{key}")
            val = float(calc[key])
            abs_err = abs(val - rep)
            rel_err = abs_err / abs(rep) if abs(rep) > 1e-12 else abs_err
            if abs_err > abs_tolerance and rel_err > rel_tolerance:
                mismatches.append({"metric": key, "calculated": val, "reported": rep, "abs_error": abs_err})
    return {
        "operation": "sample_vs_reported",
        "calculated": calc,
        "reported": reported,
        "mismatches": mismatches,
        "status": "discrepancy_detected" if mismatches else "ok",
    }


def ml_leakage_audit(
    train_ids: list[Any],
    test_ids: list[Any],
    *,
    val_ids: list[Any] | None = None,
    train_timestamps: list[float] | None = None,
    test_timestamps: list[float] | None = None,
) -> dict[str, Any]:
    s_train = set(train_ids)
    s_test = set(test_ids)
    s_val = set(val_ids or [])

    overlap_train_test = sorted(s_train & s_test, key=str)
    overlap_train_val = sorted(s_train & s_val, key=str)
    overlap_val_test = sorted(s_val & s_test, key=str)

    temporal_leak = False
    if train_timestamps and test_timestamps:
        t_tr = require_finite_array(train_timestamps, "train_timestamps", ndim=1)
        t_te = require_finite_array(test_timestamps, "test_timestamps", ndim=1)
        if float(np.max(t_tr)) > float(np.min(t_te)):
            temporal_leak = True

    leak_detected = bool(overlap_train_test or overlap_train_val or overlap_val_test or temporal_leak)
    return {
        "operation": "ml_leakage_audit",
        "overlap_train_test_count": len(overlap_train_test),
        "overlap_train_val_count": len(overlap_train_val),
        "overlap_val_test_count": len(overlap_val_test),
        "overlap_train_test_sample": overlap_train_test[:20],
        "temporal_leakage_detected": temporal_leak,
        "leakage_detected": leak_detected,
        "status": "discrepancy_detected" if leak_detected else "ok",
    }


def pvalue_distribution_screen(p_values: Any, *, min_n: int = 10) -> dict[str, Any]:
    """Triagem exploratória de concentração de valores-p próximos de 0.05.
    RESTRIÇÃO METODOLÓGICA: nunca declara p-hacking ou fraude; apenas sinaliza investigação.
    min_n define a quantidade mínima de valores-p exigida para cálculo de razão estável (escolha de engenharia
    adotada para evitar alta variância amostral em conjuntos com poucas observações).
    """
    ps = require_finite_array(p_values, name="p_values", ndim=1)
    if np.any((ps < 0) | (ps > 1)):
        raise ValueError("Valores-p devem estar em [0, 1].")
    if isinstance(min_n, bool) or not isinstance(min_n, int):
        raise ValueError(f"'min_n' deve ser um número inteiro (int), recebido: {type(min_n).__name__}.")
    if min_n < 1:
        raise ValueError("min_n deve ser >= 1.")
    n_min = min_n
    if ps.size < n_min:
        return {
            "operation": "pvalue_distribution_screen",
            "total_p_values": int(ps.size),
            "min_n": n_min,
            "significant_below_0_05": int(np.sum(ps < 0.05)),
            "in_0_04_to_0_05": int(np.sum((ps >= 0.04) & (ps < 0.05))),
            "ratio_near_threshold": None,
            "investigation_recommended": False,
            "declares_phacking_or_fraud": False,
            "methodological_note": (
                f"Amostra insuficiente ({ps.size} < min_n={n_min}) para triagem de distribuição de valores-p."
            ),
            "status": "sample_too_small",
        }
    sig = ps[ps < 0.05]
    near_threshold = ps[(ps >= 0.04) & (ps < 0.05)]
    ratio_near = float(near_threshold.size / sig.size) if sig.size > 0 else 0.0
    flagged = bool(sig.size >= 5 and ratio_near >= 0.40)
    return {
        "operation": "pvalue_distribution_screen",
        "total_p_values": int(ps.size),
        "min_n": n_min,
        "significant_below_0_05": int(sig.size),
        "in_0_04_to_0_05": int(near_threshold.size),
        "ratio_near_threshold": ratio_near,
        "investigation_recommended": flagged,
        "declares_phacking_or_fraud": False,
        "methodological_note": (
            "Concentração de valores-p entre 0.04 e 0.05 indica necessidade de investigação metodológica "
            "pelo auditor_estatistico; jamais comprova p-hacking ou má conduta por si só."
        ),
        "status": "ok",
    }


def execute_single_operation(request: dict[str, Any]) -> dict[str, Any]:
    op = request.get("operation")
    if op == "tabular_quality":
        return audit_tabular_quality(
            request["rows"], key_column=request.get("key_column"), numeric_bounds=request.get("numeric_bounds")
        )
    if op == "detect_outliers":
        return detect_outliers(
            request["values"], iqr_factor=request.get("iqr_factor", 1.5), mad_threshold=request.get("mad_threshold", 3.5)
        )
    if op == "sample_vs_reported":
        return sample_vs_reported(
            request["values"],
            request["reported"],
            rel_tolerance=request.get("rel_tolerance", 0.02),
            abs_tolerance=request.get("abs_tolerance", 1e-4),
        )
    if op == "ml_leakage_audit":
        return ml_leakage_audit(
            request["train_ids"],
            request["test_ids"],
            val_ids=request.get("val_ids"),
            train_timestamps=request.get("train_timestamps"),
            test_timestamps=request.get("test_timestamps"),
        )
    if op == "pvalue_distribution_screen":
        min_n = request.get("min_n", 10)
        return pvalue_distribution_screen(request["p_values"], min_n=min_n)
    raise ValueError(f"Operação de dados desconhecida: {op}")


def run_motor(payload: Any, *, run_id: str | None = None, artefato_alvo: str | None = None) -> dict[str, Any]:
    inner = payload["payload"] if isinstance(payload, dict) and "payload" in payload and "motor_id" in payload else payload
    items = inner.get("operations", []) if isinstance(inner, dict) and inner.get("operation") == "batch" else (inner if isinstance(inner, list) else [inner])

    results: list[dict[str, Any]] = []
    achados: list[dict[str, Any]] = []
    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            results.append(
                {
                    "id": f"DAT_{idx:03d}",
                    "operation": "unknown",
                    "success": False,
                    "status": "error",
                    "error": f"Item de lote inválido no índice {idx}: esperado objeto/dicionário, recebido {type(item).__name__}.",
                }
            )
            continue

        op_id = str(item.get("id") or f"DAT_{idx:03d}")
        try:
            res = execute_single_operation(item)
            res["id"] = op_id
            res["success"] = True
            results.append(res)
            if res.get("status") == "discrepancy_detected":
                grav = "CRITICO" if res.get("operation") == "ml_leakage_audit" else "MAIOR"
                ev = create_evidence(
                    f"EV-DAT-{idx:03d}",
                    "tabular",
                    artefato_alvo or "payload_inline",
                    op_id,
                    json.dumps(res, ensure_ascii=False)[:800],
                    motor_origem=MOTOR_ID,
                )
                achados.append(
                    create_finding(
                        f"ACH-DAT-{idx:03d}",
                        f"Problema de integridade de dados em {op_id}",
                        f"dados_{res.get('operation')}",
                        grav,
                        "ALTA",
                        op_id,
                        f"Anomalia ou inconsistência detectada em {res.get('operation')}.",
                        [ev],
                        estado="CONFIRMADO",
                        portao="G04",
                        origem_componente=MOTOR_ID,
                    )
                )
        except Exception as err:
            results.append({"id": op_id, "operation": item.get("operation"), "success": False, "status": "error", "error": str(err)})

    failed = sum(1 for r in results if not r.get("success"))
    has_partial = any(r.get("status") == "sample_too_small" for r in results if r.get("success"))
    if failed == len(results):
        status = "ERRO_VALIDACAO"
    elif failed > 0 or has_partial:
        status = "PARCIAL"
    elif achados:
        status = "COM_ACHADOS"
    else:
        status = "OK"
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
                "O motor não declara dados como MAR ou MNAR apenas observando valores ausentes.",
                "Distribuições suspeitas de valores-p são sinalizadas para investigação e nunca equivalem a prova de p-hacking ou fraude.",
            ],
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Motor de integridade dos dados (Revisão Hostil v8.0-beta.3).")
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
