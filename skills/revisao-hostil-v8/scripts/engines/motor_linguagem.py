#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Motor de linguagem científica determinístico (Revisão Hostil v8.0-beta.4).

Avalia (Passo 4.1):
- Clareza (sentenças excessivamente longas);
- Ambiguidade (termos vagos sem quantificação);
- Redundância (repetições consecutivas e pleonasmos);
- Definição de siglas na primeira ocorrência;
- Consistência terminológica frente a glossário opcional;
- Precisão epistêmica (termos dogmáticos).

Entrega apenas intervenções localizadas; nunca reescreve automaticamente o texto técnico.
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

MOTOR_ID = "motor_linguagem"
MOTOR_VERSION = "0.1.0-beta.4.1"

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
ACRONYM_RE = re.compile(r"\b([A-Z]{2,6})\b")
DUPLICATE_WORD_RE = re.compile(r"\b([a-zA-ZÀ-ÿ]{2,})\s+\1\b", re.IGNORECASE)
VAGUE_TERMS_RE = re.compile(
    r"\b(v[áa]rios|alguns|diversos|muitos|significativamente|consideravelmente|etc\.?|dentre\s+outros)\b",
    re.IGNORECASE,
)
DOGMATIC_RE = re.compile(
    r"\b(comprova\w*|proves?\s+that|incontest[áa]vel|indiscutivelmente|sem\s+d[úu]vida\s+alguma)\b",
    re.IGNORECASE,
)
COMMON_ACRONYMS_ALLOWLIST = {"SI", "OK", "II", "III", "IV", "VI", "VII", "VIII", "IX", "XI", "XII", "EQ", "FIG", "TAB"}


def analyze_language(
    text: str,
    *,
    max_sentence_words: int = 45,
    glossary_canonical: dict[str, list[str]] | None = None,
    allow_acronyms: list[str] | None = None,
) -> dict[str, Any]:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Texto de entrada deve ser string não vazia.")

    interventions: list[dict[str, Any]] = []
    sentences = [s.strip() for s in SENTENCE_SPLIT_RE.split(text.strip()) if s.strip()]

    # 1. Comprimento de sentenças (clareza)
    long_sentences = []
    for idx, sent in enumerate(sentences, start=1):
        words = re.findall(r"\b\w+\b", sent)
        if len(words) > max_sentence_words:
            long_sentences.append({"sentence_index": idx, "word_count": len(words), "excerpt": sent[:160]})
            interventions.append(
                {
                    "type": "long_sentence",
                    "location": f"Sentença {idx}",
                    "excerpt": sent[:160],
                    "suggestion": f"Sentença com {len(words)} palavras (> {max_sentence_words}). Considere dividir em dois períodos preservando o conteúdo técnico.",
                }
            )

    # 2. Repetição consecutiva de palavras (redundância)
    for m in DUPLICATE_WORD_RE.finditer(text):
        interventions.append(
            {
                "type": "duplicate_word",
                "location": f"pos {m.start()}",
                "excerpt": m.group(0),
                "suggestion": f"Palavra repetida consecutivamente ('{m.group(0)}').",
            }
        )

    # 3. Termos vagos / ambiguidade
    vague_hits = []
    for m in VAGUE_TERMS_RE.finditer(text):
        vague_hits.append(m.group(0))
        interventions.append(
            {
                "type": "ambiguity_vague_term",
                "location": f"pos {m.start()}",
                "excerpt": text[max(0, m.start() - 25) : min(len(text), m.end() + 25)],
                "suggestion": f"Termo vago ('{m.group(0)}'): especificar quantidade, intervalo ou métrica exata quando aplicável.",
            }
        )

    # 4. Precisão epistêmica
    for m in DOGMATIC_RE.finditer(text):
        interventions.append(
            {
                "type": "epistemic_precision",
                "location": f"pos {m.start()}",
                "excerpt": text[max(0, m.start() - 25) : min(len(text), m.end() + 25)],
                "suggestion": f"Termo dogmático ('{m.group(0)}'): calibrar força epistêmica conforme tipo de evidência.",
            }
        )

    # 5. Definição de siglas na primeira ocorrência (ex.: "... (SIGLA)" ou "SIGLA (...)")
    allowed = set(COMMON_ACRONYMS_ALLOWLIST) | set(allow_acronyms or [])
    undefined_acronyms: list[str] = []
    seen_acronyms: set[str] = set()
    for m in ACRONYM_RE.finditer(text):
        acr = m.group(1)
        if acr in allowed or acr in seen_acronyms:
            continue
        seen_acronyms.add(acr)
        # Verifica padrão "(ACR)" ou "ACR ("
        defined_before = re.search(rf"\(\s*{re.escape(acr)}\s*\)", text[: m.end() + 2])
        defined_after = re.search(rf"\b{re.escape(acr)}\s*\([^)]+\)", text[m.start() : m.end() + 80])
        if not defined_before and not defined_after:
            undefined_acronyms.append(acr)
            interventions.append(
                {
                    "type": "undefined_acronym",
                    "location": f"pos {m.start()}",
                    "excerpt": acr,
                    "suggestion": f"Sigla '{acr}' utilizada sem definição explícita na primeira ocorrência.",
                }
            )

    # 6. Consistência terminológica contra glossário canônico
    terminology_issues: list[dict[str, Any]] = []
    for canonical, variants in (glossary_canonical or {}).items():
        for var in variants:
            if re.search(rf"\b{re.escape(var)}\b", text, re.IGNORECASE):
                terminology_issues.append({"canonical": canonical, "variant_found": var})
                interventions.append(
                    {
                        "type": "terminology_inconsistency",
                        "location": "texto",
                        "excerpt": var,
                        "suggestion": f"Variante '{var}' detectada; padronizar para termo canônico '{canonical}'.",
                    }
                )

    total_words = len(re.findall(r"\b\w+\b", text))
    return {
        "operation": "analyze_language",
        "word_count": total_words,
        "sentence_count": len(sentences),
        "long_sentence_count": len(long_sentences),
        "undefined_acronyms": undefined_acronyms,
        "vague_term_count": len(vague_hits),
        "terminology_issues": terminology_issues,
        "interventions": interventions,
        "auto_rewritten": False,
        "status": "discrepancy_detected" if interventions else "ok",
    }


def run_motor(payload: Any, *, run_id: str | None = None, artefato_alvo: str | None = None) -> dict[str, Any]:
    inner = payload["payload"] if isinstance(payload, dict) and "payload" in payload and "motor_id" in payload else payload

    if not isinstance(inner, dict) or "text" not in inner or not isinstance(inner["text"], str):
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
                "metricas": {
                    "word_count": 0,
                    "sentence_count": 0,
                    "total_intervencoes": 0,
                    "erros": 1,
                },
                "resultados": {
                    "error": "Payload inválido: esperado objeto contendo a string obrigatória 'text'.",
                    "interventions": [],
                    "word_count": 0,
                    "sentence_count": 0,
                },
                "achados": [],
                "limitacoes": [
                    "O motor produz apenas intervenções localizadas e nunca reescreve automaticamente o texto técnico.",
                    "Julgamento semântico profundo de progressão argumentativa cabe ao auditor_clareza.",
                ],
            }
        )

    res = analyze_language(
        inner["text"],
        max_sentence_words=inner.get("max_sentence_words", 45),
        glossary_canonical=inner.get("glossary_canonical"),
        allow_acronyms=inner.get("allow_acronyms"),
    )

    achados: list[dict[str, Any]] = []
    for idx, itv in enumerate(res["interventions"], start=1):
        ev = create_evidence(
            f"EV-LNG-{idx:03d}",
            "textual",
            artefato_alvo or "texto_inline",
            itv["location"],
            itv["excerpt"],
            motor_origem=MOTOR_ID,
        )
        grav = "MODERADO" if itv["type"] in ("epistemic_precision", "terminology_inconsistency") else "MENOR"
        achados.append(
            create_finding(
                f"ACH-LNG-{idx:03d}",
                f"Intervenção de linguagem ({itv['type']})",
                f"linguagem_{itv['type']}",
                grav,
                "ALTA",
                itv["location"],
                itv["suggestion"],
                [ev],
                estado="ABERTO",
                portao="G01",
                acao_recomendada=itv["suggestion"],
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
            "metricas": {
                "word_count": res["word_count"],
                "sentence_count": res["sentence_count"],
                "total_intervencoes": len(achados),
            },
            "resultados": res,
            "achados": achados,
            "limitacoes": [
                "O motor produz apenas intervenções localizadas e nunca reescreve automaticamente o texto técnico.",
                "Julgamento semântico profundo de progressão argumentativa cabe ao auditor_clareza.",
            ],
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Motor de linguagem científica (Revisão Hostil v8.0-beta.4).")
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
