#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Motor de auditoria de mapas argumentativos estruturados (Revisão Hostil v8.0-beta.5).

Escopo real (ACH-007):
- Recebe mapas argumentativos pré-estruturados em JSON ({id, claim, premises, evidence, conclusion})
  e sinaliza candidatos determinísticos a argumentos sem sustentação, circularidade lexical
  e generalização indevida;
- NÃO realiza extração automática de argumentos a partir de texto livre (essa etapa é realizada
  pelo orquestrador/agente ou futuro extrator dedicado).

RESTRIÇÃO OBRIGATÓRIA: não é classificador definitivo de falácias (`is_definitive_fallacy_classifier: False`).
"""

from __future__ import annotations

import argparse
import json
import re
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
from scripts.common.validation import MAX_JSON_PAYLOAD_BYTES, read_bounded_json, sanitize_for_json

MOTOR_ID = "motor_argumentacao"
MOTOR_VERSION = "0.1.0-beta.5.1"

OVERGENERALIZATION_RE = re.compile(
    r"\b(todos\s+os\s+casos|em\s+qualquer\s+cen[áa]rio|universalmente|sem\s+exce[çc][ãa]o|always\s+holds|in\s+all\s+cases)\b",
    re.IGNORECASE,
)


def audit_argument_map(arguments: list[dict[str, Any]]) -> dict[str, Any]:
    """Audita uma lista estruturada de argumentos: {id, claim, premises, evidence, conclusion}."""
    if not isinstance(arguments, list) or not arguments:
        raise ValueError("arguments deve ser uma lista não vazia.")

    candidates: list[dict[str, Any]] = []
    for arg in arguments:
        aid = str(arg.get("id") or "ARG")
        claim = str(arg.get("claim", "")).strip()
        premises = [str(p).strip() for p in (arg.get("premises") or []) if str(p).strip()]
        evidence = [str(e).strip() for e in (arg.get("evidence") or []) if str(e).strip()]
        conclusion = str(arg.get("conclusion", "")).strip()

        if not evidence:
            candidates.append({"argument_id": aid, "candidate_type": "unsupported_claim", "detail": f"Alegação '{claim[:100]}' sem evidência vinculada."})
        if not premises:
            candidates.append({"argument_id": aid, "candidate_type": "missing_premises", "detail": f"Argumento '{aid}' sem premissas explícitas."})

        # Circularidade candidata: conclusão quase idêntica a uma premissa
        c_tokens = set(re.findall(r"\b\w{4,}\b", conclusion.lower()))
        if c_tokens:
            for prem in premises:
                p_tokens = set(re.findall(r"\b\w{4,}\b", prem.lower()))
                if p_tokens:
                    overlap = len(c_tokens & p_tokens) / max(1, len(c_tokens | p_tokens))
                    if overlap >= 0.80:
                        candidates.append(
                            {
                                "argument_id": aid,
                                "candidate_type": "possible_circularity",
                                "detail": f"Alta sobreposição lexical ({overlap:.2f}) entre premissa e conclusão.",
                            }
                        )
                        break

        if OVERGENERALIZATION_RE.search(claim) or OVERGENERALIZATION_RE.search(conclusion):
            candidates.append(
                {
                    "argument_id": aid,
                    "candidate_type": "possible_overgeneralization",
                    "detail": "Linguagem de generalização universal detectada; verificar escopo da evidência.",
                }
            )

    return {
        "operation": "audit_argument_map",
        "arguments_analyzed": len(arguments),
        "candidate_issues": candidates,
        "is_definitive_fallacy_classifier": False,
        "status": "discrepancy_detected" if candidates else "ok",
    }


def run_motor(payload: Any, *, run_id: str | None = None, artefato_alvo: str | None = None) -> dict[str, Any]:
    inner = payload["payload"] if isinstance(payload, dict) and "payload" in payload and "motor_id" in payload else payload

    if not isinstance(inner, dict) or "arguments" not in inner or not isinstance(inner["arguments"], list):
        return sanitize_for_json(
            {
                "schema_version": SCHEMA_VERSION,
                "motor_id": MOTOR_ID,
                "motor_version": MOTOR_VERSION,
                "run_id": run_id,
                "deterministico": True,
                "status": "ERRO_VALIDACAO",
                "timestamp": utc_now_iso(),
                "artefato_alvo": artefato_alvo,
                "hash_artefato": None,
                "metricas": {"argumentos": 0, "candidatos": 0, "erros": 1},
                "resultados": {
                    "error": "Payload inválido: esperado objeto contendo a lista obrigatória 'arguments'.",
                    "arguments_analyzed": 0,
                    "candidate_issues": [],
                },
                "achados": [],
                "limitacoes": [
                    "Este motor audita mapas argumentativos já estruturados em JSON; não realiza extração automática de argumentos a partir de prosa livre.",
                    "O motor não classifica falácias de forma definitiva; os candidatos exigem julgamento do auditor_metodologia ou auditor_adversarial.",
                ],
            }
        )

    res = audit_argument_map(inner["arguments"])

    achados: list[dict[str, Any]] = []
    for idx, cand in enumerate(res["candidate_issues"], start=1):
        ev = create_evidence(
            f"EV-ARG-{idx:03d}",
            "textual",
            artefato_alvo or "mapa_argumentativo",
            cand["argument_id"],
            cand["detail"],
            motor_origem=MOTOR_ID,
        )
        achados.append(
            create_finding(
                f"ACH-ARG-{idx:03d}",
                f"Candidato argumentativo ({cand['candidate_type']}) em {cand['argument_id']}",
                f"argumentacao_{cand['candidate_type']}",
                "MODERADO",
                "TRIAGEM",
                cand["argument_id"],
                cand["detail"],
                [ev],
                estado="ABERTO",
                portao="G01",
                origem_componente=MOTOR_ID,
            )
        )

    return sanitize_for_json(
        {
            "schema_version": SCHEMA_VERSION,
            "motor_id": MOTOR_ID,
            "motor_version": MOTOR_VERSION,
            "run_id": run_id,
            "deterministico": True,
            "status": "COM_ACHADOS" if achados else "OK",
            "timestamp": utc_now_iso(),
            "artefato_alvo": artefato_alvo,
            "hash_artefato": None,
            "metricas": {"argumentos": res["arguments_analyzed"], "candidatos": len(achados)},
            "resultados": res,
            "achados": achados,
            "limitacoes": [
                "Este motor audita mapas argumentativos já estruturados em JSON; não realiza extração automática de argumentos a partir de prosa livre.",
                "O motor não classifica falácias de forma definitiva; os candidatos exigem julgamento do auditor_metodologia ou auditor_adversarial.",
            ],
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Motor de argumentação (Revisão Hostil v8.0-beta.5).")
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
