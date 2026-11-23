#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Motor temporal determinístico (Revisão Hostil v8.0-beta.5).

Verifica (Passo 5.4):
- Sequências cronológicas e relações de antecedência obrigatórias (ex.: aprovação ética < coleta < análise);
- Janelas de vigência de normas/documentos frente à data de referência;
- Contradições entre cronograma e datas citadas.

RESTRIÇÃO: ordem temporal nunca implica causalidade automática (`infers_causality_from_order: False`).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
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

MOTOR_ID = "motor_temporal"
MOTOR_VERSION = "0.1.0-beta.5"


def _parse_iso_date(raw: str) -> date:
    return date.fromisoformat(raw.strip()[:10])


def check_chronology(
    events: dict[str, str],
    precedence_rules: list[list[str]],
    *,
    validity_windows: list[dict[str, Any]] | None = None,
    reference_date: str | None = None,
) -> dict[str, Any]:
    parsed_events = {k: _parse_iso_date(v) for k, v in events.items()}
    violations: list[dict[str, Any]] = []

    for rule in precedence_rules:
        if len(rule) != 2:
            raise ValueError(f"Regra de precedência deve conter [antes, depois]: {rule}")
        before, after = rule
        if before in parsed_events and after in parsed_events:
            if parsed_events[before] > parsed_events[after]:
                violations.append(
                    {
                        "type": "precedence_violation",
                        "before": before,
                        "before_date": parsed_events[before].isoformat(),
                        "after": after,
                        "after_date": parsed_events[after].isoformat(),
                        "detail": f"'{before}' ({parsed_events[before]}) ocorreu após '{after}' ({parsed_events[after]}).",
                    }
                )

    ref_dt = _parse_iso_date(reference_date) if reference_date else None
    for win in validity_windows or []:
        item_id = win.get("id", "norma")
        eff = _parse_iso_date(win["effective_from"]) if win.get("effective_from") else None
        rev = _parse_iso_date(win["revoked_on"]) if win.get("revoked_on") else None
        if ref_dt:
            if eff and ref_dt < eff:
                violations.append(
                    {"type": "not_yet_effective", "id": item_id, "detail": f"'{item_id}' só entra em vigência em {eff}, após referência {ref_dt}."}
                )
            if rev and ref_dt >= rev:
                violations.append(
                    {"type": "revoked_before_reference", "id": item_id, "detail": f"'{item_id}' foi revogada em {rev}, antes da referência {ref_dt}."}
                )

    timeline = sorted(
        [{"event": k, "date": d.isoformat()} for k, d in parsed_events.items()],
        key=lambda x: x["date"],
    )
    return {
        "operation": "check_chronology",
        "timeline": timeline,
        "violations": violations,
        "infers_causality_from_order": False,
        "status": "discrepancy_detected" if violations else "ok",
    }


def run_motor(payload: Any, *, run_id: str | None = None, artefato_alvo: str | None = None) -> dict[str, Any]:
    inner = payload["payload"] if isinstance(payload, dict) and "payload" in payload and "motor_id" in payload else payload
    res = check_chronology(
        inner.get("events", {}),
        inner.get("precedence_rules", []),
        validity_windows=inner.get("validity_windows"),
        reference_date=inner.get("reference_date"),
    )
    achados: list[dict[str, Any]] = []
    for idx, v in enumerate(res["violations"], start=1):
        ev = create_evidence(
            f"EV-TMP-{idx:03d}",
            "textual",
            artefato_alvo or "cronologia",
            v.get("id") or f"{v.get('before')}->{v.get('after')}",
            v["detail"],
            motor_origem=MOTOR_ID,
        )
        achados.append(
            create_finding(
                f"ACH-TMP-{idx:03d}",
                f"Inconsistência temporal ({v['type']})",
                f"temporal_{v['type']}",
                "MAIOR",
                "ALTA",
                v.get("id") or "cronologia",
                v["detail"],
                [ev],
                estado="CONFIRMADO",
                portao="G05",
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
            "metricas": {"eventos": len(res["timeline"]), "violacoes": len(achados)},
            "resultados": res,
            "achados": achados,
            "limitacoes": [
                "Precedência temporal é condição necessária, mas não suficiente, para inferência causal."
            ],
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Motor temporal (Revisão Hostil v8.0-beta.5).")
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
