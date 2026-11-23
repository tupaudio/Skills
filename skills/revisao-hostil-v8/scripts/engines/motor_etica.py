#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Motor de triagem ética e integridade científica (Revisão Hostil v8.0-beta.5).

Verifica (Passo 5.1):
- Presença de declarações: aprovação ética (CEP/IRB/CEUA), consentimento informado (TCLE),
  conflito de interesses, financiamento, proteção de dados (LGPD/GDPR) e autoria;
- Similaridade textual (n-gram Jaccard) contra textos de referência autorizados.

RESTRIÇÕES OBRIGATÓRIAS:
- Similaridade textual NÃO equivale a plágio comprovado (`declares_plagiarism: False`);
- Anomalia NÃO equivale a fraude (`declares_fraud: False`);
- Identificação de protocolo CEP/IRB NÃO certifica conformidade ética/legal (`certifies_compliance: False`).
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
from scripts.common.validation import sanitize_for_json

MOTOR_ID = "motor_etica"
MOTOR_VERSION = "0.1.0-beta.5"

DECLARATION_PATTERNS: dict[str, re.Pattern[str]] = {
    "aprovacao_etica": re.compile(r"\b(CEP|CAAE|IRB|CEUA|comit[êe]\s+de\s+[ée]tica|ethics\s+committee|ethical\s+approval)\b", re.IGNORECASE),
    "consentimento_informado": re.compile(r"\b(TCLE|consentimento\s+(?:livre\s+e\s+)?esclarecido|informed\s+consent)\b", re.IGNORECASE),
    "conflito_interesse": re.compile(r"\b(conflito\s+de\s+interess|competing\s+interests?|conflict\s+of\s+interest|declaram\s+n[ãa]o\s+haver)\b", re.IGNORECASE),
    "financiamento": re.compile(r"\b(financiamento|fomento|CNPq|CAPES|FAPESP|FINEP|funding|grant\s+number|supported\s+by)\b", re.IGNORECASE),
    "protecao_dados": re.compile(r"\b(LGPD|GDPR|anonimiza[çc][ãa]o|pseudonimiza[çc][ãa]o|data\s+protection|privacy)\b", re.IGNORECASE),
    "autoria": re.compile(r"\b(contribui[çc][ãa]o\s+dos\s+autores|author\s+contributions?|CRediT)\b", re.IGNORECASE),
}


def screen_ethics_declarations(
    text: str,
    *,
    involves_humans_or_animals: bool = False,
    required_declarations: list[str] | None = None,
) -> dict[str, Any]:
    found: dict[str, bool] = {}
    for key, pattern in DECLARATION_PATTERNS.items():
        found[key] = bool(pattern.search(text))

    req = list(required_declarations or ["conflito_interesse", "financiamento"])
    if involves_humans_or_animals:
        for k in ("aprovacao_etica", "consentimento_informado", "protecao_dados"):
            if k not in req:
                req.append(k)

    missing = [k for k in req if not found.get(k, False)]
    return {
        "operation": "screen_ethics_declarations",
        "declarations_detected": found,
        "required_declarations": req,
        "missing_declarations": missing,
        "certifies_compliance": False,
        "declares_fraud": False,
        "status": "discrepancy_detected" if missing else "ok",
    }


def _shingles(text: str, n: int = 5) -> set[tuple[str, ...]]:
    tokens = re.findall(r"\b\w+\b", text.lower())
    if len(tokens) < n:
        return {tuple(tokens)} if tokens else set()
    return {tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


def check_text_similarity(
    text: str,
    reference_texts: dict[str, str],
    *,
    ngram_size: int = 5,
    alert_threshold: float = 0.25,
) -> dict[str, Any]:
    src = _shingles(text, ngram_size)
    comparisons = []
    flagged = []
    for ref_id, ref_text in reference_texts.items():
        ref = _shingles(ref_text, ngram_size)
        union = src | ref
        jaccard = float(len(src & ref) / len(union)) if union else 0.0
        rec = {"reference_id": ref_id, "jaccard_similarity": round(jaccard, 4), "flagged_for_review": jaccard >= alert_threshold}
        comparisons.append(rec)
        if rec["flagged_for_review"]:
            flagged.append(rec)
    return {
        "operation": "check_text_similarity",
        "ngram_size": ngram_size,
        "alert_threshold": alert_threshold,
        "comparisons": comparisons,
        "flagged_count": len(flagged),
        "declares_plagiarism": False,
        "methodological_note": "Similaridade textual é apenas insumo de triagem e jamais equivale a plágio comprovado.",
        "status": "discrepancy_detected" if flagged else "ok",
    }


def execute_single_operation(request: dict[str, Any]) -> dict[str, Any]:
    op = request.get("operation")
    if op == "screen_ethics_declarations":
        return screen_ethics_declarations(
            request["text"],
            involves_humans_or_animals=request.get("involves_humans_or_animals", False),
            required_declarations=request.get("required_declarations"),
        )
    if op == "check_text_similarity":
        return check_text_similarity(
            request["text"],
            request["reference_texts"],
            ngram_size=request.get("ngram_size", 5),
            alert_threshold=request.get("alert_threshold", 0.25),
        )
    raise ValueError(f"Operação ética desconhecida: {op}")


def run_motor(payload: Any, *, run_id: str | None = None, artefato_alvo: str | None = None) -> dict[str, Any]:
    inner = payload["payload"] if isinstance(payload, dict) and "payload" in payload and "motor_id" in payload else payload
    items = inner.get("operations", []) if isinstance(inner, dict) and inner.get("operation") == "batch" else (inner if isinstance(inner, list) else [inner])

    results: list[dict[str, Any]] = []
    achados: list[dict[str, Any]] = []
    for idx, item in enumerate(items, start=1):
        op_id = str(item.get("id") or f"ETI_{idx:03d}")
        try:
            res = execute_single_operation(item)
            res["id"] = op_id
            res["success"] = True
            results.append(res)
            if res.get("status") == "discrepancy_detected":
                ev = create_evidence(
                    f"EV-ETI-{idx:03d}",
                    "textual",
                    artefato_alvo or "manuscrito",
                    op_id,
                    json.dumps(res, ensure_ascii=False)[:800],
                    motor_origem=MOTOR_ID,
                )
                achados.append(
                    create_finding(
                        f"ACH-ETI-{idx:03d}",
                        f"Sinalização de triagem ética em {op_id}",
                        f"etica_{res['operation']}",
                        "MAIOR",
                        "MEDIA",
                        op_id,
                        "Declaração ética ausente ou similaridade textual acima do limiar de triagem (encaminhar ao auditor_etico).",
                        [ev],
                        estado="ABERTO",
                        portao="G10",
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
                "Similaridade textual não equivale a plágio comprovado; anomalias não equivalem a fraude.",
                "Identificação de protocolo CEP/IRB não certifica conformidade ética ou legal.",
            ],
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Motor de triagem ética (Revisão Hostil v8.0-beta.5).")
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
