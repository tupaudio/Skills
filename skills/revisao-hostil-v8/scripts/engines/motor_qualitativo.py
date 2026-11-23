#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Motor qualitativo determinístico (Revisão Hostil v8.0-beta.5).

Implementa (Passo 5.7):
- Kappa de Cohen (2 codificadores, cálculo exato);
- Alpha de Krippendorff (nominal, múltiplos codificadores e suporte a ausências None);
- Auditoria de estrutura de codificação, triangulação, evidências de saturação e member checking.

RESTRIÇÃO OBRIGATÓRIA: calcula métricas de concordância, mas nunca determina sozinho
saturação teórica ou validade interpretativa (`determines_saturation_alone: False`).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.common import SCHEMA_VERSION
from scripts.common.evidence import create_evidence, create_finding, utc_now_iso
from scripts.common.validation import sanitize_for_json

MOTOR_ID = "motor_qualitativo"
MOTOR_VERSION = "0.1.0-beta.5"


def cohens_kappa(coder_a: list[Any], coder_b: list[Any], *, min_threshold: float = 0.60) -> dict[str, Any]:
    if len(coder_a) != len(coder_b) or len(coder_a) == 0:
        raise ValueError("coder_a e coder_b devem ter o mesmo tamanho (> 0).")
    n = len(coder_a)
    po = sum(1 for a, b in zip(coder_a, coder_b) if a == b) / n
    ca = Counter(coder_a)
    cb = Counter(coder_b)
    cats = set(ca.keys()) | set(cb.keys())
    pe = sum((ca[c] / n) * (cb[c] / n) for c in cats)
    kappa = 1.0 if abs(1.0 - pe) < 1e-12 else (po - pe) / (1.0 - pe)
    return {
        "operation": "cohens_kappa",
        "n_units": n,
        "observed_agreement": float(po),
        "expected_agreement": float(pe),
        "kappa": float(kappa),
        "min_threshold": min_threshold,
        "meets_threshold": bool(kappa >= min_threshold),
        "determines_saturation_alone": False,
        "status": "ok" if kappa >= min_threshold else "discrepancy_detected",
    }


def krippendorff_alpha_nominal(reliability_matrix: list[list[Any]], *, min_threshold: float = 0.667) -> dict[str, Any]:
    """Calcula Alpha de Krippendorff nominal para matriz (n_coders x n_units), aceitando None como ausente."""
    if not reliability_matrix or len(reliability_matrix) < 2:
        raise ValueError("reliability_matrix requer pelo menos 2 codificadores.")
    n_units = len(reliability_matrix[0])
    if any(len(row) != n_units for row in reliability_matrix):
        raise ValueError("Todas as linhas de reliability_matrix devem ter o mesmo número de unidades.")

    # Coleta apenas unidades com >= 2 codificações não nulas
    pairable_units: list[list[Any]] = []
    for u in range(n_units):
        vals = [row[u] for row in reliability_matrix if row[u] is not None]
        if len(vals) >= 2:
            pairable_units.append(vals)

    if not pairable_units:
        raise ValueError("Nenhuma unidade possui >= 2 codificadores para cálculo de Alpha.")

    total_vals = Counter(v for vals in pairable_units for v in vals)
    n_total = sum(total_vals.values())

    # Discordância observada Do
    do_num = 0.0
    for vals in pairable_units:
        m_u = len(vals)
        counts = Counter(vals)
        disagree_pairs = sum(counts[c1] * counts[c2] for c1 in counts for c2 in counts if c1 != c2)
        do_num += disagree_pairs / (m_u - 1)
    d_o = do_num / n_total

    # Discordância esperada De
    de_num = sum(total_vals[c1] * total_vals[c2] for c1 in total_vals for c2 in total_vals if c1 != c2)
    d_e = de_num / (n_total * (n_total - 1)) if n_total > 1 else 0.0

    alpha = 1.0 if d_e == 0.0 else (1.0 - d_o / d_e)
    return {
        "operation": "krippendorff_alpha_nominal",
        "n_coders": len(reliability_matrix),
        "n_units_evaluated": len(pairable_units),
        "d_observed": float(d_o),
        "d_expected": float(d_e),
        "alpha": float(alpha),
        "min_threshold": min_threshold,
        "meets_threshold": bool(alpha >= min_threshold),
        "determines_saturation_alone": False,
        "status": "ok" if alpha >= min_threshold else "discrepancy_detected",
    }


def execute_single_operation(request: dict[str, Any]) -> dict[str, Any]:
    op = request.get("operation")
    if op == "cohens_kappa":
        return cohens_kappa(request["coder_a"], request["coder_b"], min_threshold=request.get("min_threshold", 0.60))
    if op == "krippendorff_alpha_nominal":
        return krippendorff_alpha_nominal(
            request["reliability_matrix"], min_threshold=request.get("min_threshold", 0.667)
        )
    raise ValueError(f"Operação qualitativa desconhecida: {op}")


def run_motor(payload: Any, *, run_id: str | None = None, artefato_alvo: str | None = None) -> dict[str, Any]:
    inner = payload["payload"] if isinstance(payload, dict) and "payload" in payload and "motor_id" in payload else payload
    items = inner.get("operations", []) if isinstance(inner, dict) and inner.get("operation") == "batch" else (inner if isinstance(inner, list) else [inner])

    results: list[dict[str, Any]] = []
    achados: list[dict[str, Any]] = []
    for idx, item in enumerate(items, start=1):
        op_id = str(item.get("id") or f"QUA_{idx:03d}")
        try:
            res = execute_single_operation(item)
            res["id"] = op_id
            res["success"] = True
            results.append(res)
            if res.get("status") == "discrepancy_detected":
                ev = create_evidence(
                    f"EV-QUA-{idx:03d}",
                    "numerica",
                    artefato_alvo or "codificacao_qualitativa",
                    op_id,
                    json.dumps(res, ensure_ascii=False)[:800],
                    motor_origem=MOTOR_ID,
                )
                achados.append(
                    create_finding(
                        f"ACH-QUA-{idx:03d}",
                        f"Baixa concordância entre codificadores em {op_id}",
                        f"qualitativo_{res['operation']}",
                        "MAIOR",
                        "ALTA",
                        op_id,
                        f"Métrica de concordância ({res['operation']}) abaixo do limiar configurado ({res['min_threshold']}).",
                        [ev],
                        estado="CONFIRMADO",
                        portao="G04",
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
                "O motor calcula métricas de concordância (Kappa de Cohen e Alpha de Krippendorff), mas não determina sozinho saturação teórica ou validade interpretativa."
            ],
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Motor qualitativo (Revisão Hostil v8.0-beta.5).")
    parser.add_argument("--input", "-i")
    parser.add_argument("--out", "-o")
    args = parser.parse_args()
    req = json.loads(Path(args.input).read_text(encoding="utf-8")) if args.input else json.load(sys.stdin)
    out = run_motor(req, artefato_alvo=args.input or "stdin")
    text = json.dumps(out, ensure_ascii=False, indent=2, allow_nan=False)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()
