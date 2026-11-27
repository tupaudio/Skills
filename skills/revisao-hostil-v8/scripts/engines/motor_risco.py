#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Motor especializado de análise de risco e exposição ocupacional (Revisão Hostil v8.0-beta.6).

Ativado pelo perfil `seguranca_trabalho`:
- Matriz de risco (Severidade 1..5 × Probabilidade 1..5) e auditoria de hierarquia de controles;
- Cálculo determinístico de razão de exposição ocupacional (C / LT) e soma de efeitos aditivos (Σ Ci/LTi).

RESTRIÇÃO: não substitui laudo técnico (LTCAT/PGR) nem certifica conformidade legal automática.
"""

from __future__ import annotations

import argparse
import json
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
from scripts.common.validation import require_finite_number, sanitize_for_json

MOTOR_ID = "motor_risco"
MOTOR_VERSION = "0.1.0-beta.6"

CONTROL_HIERARCHY_RANK = {
    "eliminacao": 1,
    "substituicao": 2,
    "engenharia": 3,
    "administrativo": 4,
    "epi": 5,
}


def evaluate_risk_matrix(
    hazard: str,
    severity: int,
    probability: int,
    *,
    controls: list[str] | None = None,
) -> dict[str, Any]:
    if not (1 <= int(severity) <= 5 and 1 <= int(probability) <= 5):
        raise ValueError("severity e probability devem estar no intervalo inteiro [1, 5].")
    score = int(severity) * int(probability)
    if score >= 15:
        band = "CRITICO"
    elif score >= 10:
        band = "ALTO"
    elif score >= 5:
        band = "MODERADO"
    else:
        band = "BAIXO"

    ctrl_list = [c.lower().strip() for c in (controls or [])]
    epi_only_for_high_risk = bool(band in ("ALTO", "CRITICO") and ctrl_list and set(ctrl_list) == {"epi"})
    no_controls_high_risk = bool(band in ("ALTO", "CRITICO") and not ctrl_list)

    return {
        "operation": "evaluate_risk_matrix",
        "hazard": hazard,
        "severity": int(severity),
        "probability": int(probability),
        "risk_score": score,
        "risk_band": band,
        "controls": ctrl_list,
        "epi_only_warning": epi_only_for_high_risk,
        "no_controls_warning": no_controls_high_risk,
        "certifies_safety_compliance": False,
        "status": "discrepancy_detected" if (epi_only_for_high_risk or no_controls_high_risk) else "ok",
    }


def evaluate_exposure_index(agents: list[dict[str, Any]]) -> dict[str, Any]:
    """Avalia exposição individual (C/LT) e índice aditivo (Σ Ci/LTi) com nível de ação >= 0.5."""
    if not agents:
        raise ValueError("agents deve conter pelo menos um agente com measured e limit.")
    items = []
    additive_index = 0.0
    for ag in agents:
        measured = require_finite_number(ag["measured"], f"{ag.get('name', 'agent')}.measured")
        limit = require_finite_number(ag["limit"], f"{ag.get('name', 'agent')}.limit")
        if measured < 0 or limit <= 0:
            raise ValueError("measured deve ser >= 0 e limit > 0.")
        ratio = measured / limit
        additive_index += ratio
        items.append(
            {
                "name": ag.get("name", "agente"),
                "measured": measured,
                "limit": limit,
                "unit": ag.get("unit"),
                "ratio": ratio,
                "exceeds_action_level_0_5": bool(ratio >= 0.5),
                "exceeds_limit_1_0": bool(ratio >= 1.0),
            }
        )
    exceeded = any(i["exceeds_limit_1_0"] for i in items) or additive_index >= 1.0
    return {
        "operation": "evaluate_exposure_index",
        "agents": items,
        "additive_exposure_index": float(additive_index),
        "exceeds_limit": exceeded,
        "certifies_legal_compliance": False,
        "status": "discrepancy_detected" if exceeded else "ok",
    }


def execute_single_operation(request: dict[str, Any]) -> dict[str, Any]:
    op = request.get("operation")
    if op == "evaluate_risk_matrix":
        return evaluate_risk_matrix(
            request["hazard"], request["severity"], request["probability"], controls=request.get("controls")
        )
    if op == "evaluate_exposure_index":
        return evaluate_exposure_index(request["agents"])
    raise ValueError(f"Operação de risco desconhecida: {op}")


def run_motor(payload: Any, *, run_id: str | None = None, artefato_alvo: str | None = None) -> dict[str, Any]:
    inner = payload["payload"] if isinstance(payload, dict) and "payload" in payload and "motor_id" in payload else payload
    items = inner.get("operations", []) if isinstance(inner, dict) and inner.get("operation") == "batch" else (inner if isinstance(inner, list) else [inner])

    results: list[dict[str, Any]] = []
    achados: list[dict[str, Any]] = []
    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            results.append(
                {
                    "id": f"RSK_{idx:03d}",
                    "operation": "unknown",
                    "success": False,
                    "status": "error",
                    "error": f"Item de lote inválido no índice {idx}: esperado objeto/dicionário, recebido {type(item).__name__}.",
                }
            )
            continue

        op_id = str(item.get("id") or f"RSK_{idx:03d}")
        try:
            res = execute_single_operation(item)
            res["id"] = op_id
            res["success"] = True
            results.append(res)
            if res.get("status") == "discrepancy_detected":
                ev = create_evidence(
                    f"EV-RSK-{idx:03d}",
                    "numerica",
                    artefato_alvo or "avaliacao_risco",
                    op_id,
                    json.dumps(res, ensure_ascii=False)[:800],
                    motor_origem=MOTOR_ID,
                )
                achados.append(
                    create_finding(
                        f"ACH-RSK-{idx:03d}",
                        f"Alerta crítico de risco/exposição em {op_id}",
                        f"risco_{res['operation']}",
                        "CRITICO",
                        "ALTA",
                        op_id,
                        "Limite de exposição excedido ou risco alto/crítico sem controles de engenharia/coletivos adequados.",
                        [ev],
                        estado="CONFIRMADO",
                        portao="G12",
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
                "Cálculos determinísticos de matriz de risco e índice de exposição não substituem PGR, LTCAT ou avaliação por profissional habilitado."
            ],
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Motor de risco ocupacional (Revisão Hostil v8.0-beta.6).")
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
