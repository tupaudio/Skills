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
import re
import sys
from datetime import date, datetime, timezone
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

_DATE_ONLY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})?$")


def _parse_iso_temporal(raw: str) -> tuple[datetime, str, bool]:
    """Valida estritamente data (YYYY-MM-DD) ou data+hora ISO-8601 completa sem truncamento (ACH-005).
    Retorna (datetime_utc_ou_naive, precision='day'|'datetime', has_timezone).
    """
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"Marca temporal vazia ou inválida: {raw!r}")
    s = raw.strip()
    if _DATE_ONLY_RE.match(s):
        d = date.fromisoformat(s)
        return datetime(d.year, d.month, d.day, tzinfo=timezone.utc), "day", False
    if _DATETIME_RE.match(s):
        normalized = s[:-1] + "+00:00" if s.endswith("Z") else s
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is not None:
            return dt.astimezone(timezone.utc), "datetime", True
        return dt.replace(tzinfo=timezone.utc), "datetime", False
    raise ValueError(f"Formato ISO-8601 inválido (conteúdo extra ou sintaxe incorreta): {raw!r}")


def _compare_events(a: tuple[datetime, str, bool], b: tuple[datetime, str, bool]) -> int:
    """Compara dois marcos temporais respeitando precisão diária vs horária."""
    dt_a, prec_a, _ = a
    dt_b, prec_b, _ = b
    if prec_a == "day" or prec_b == "day":
        da, db = dt_a.date(), dt_b.date()
        return -1 if da < db else (1 if da > db else 0)
    return -1 if dt_a < dt_b else (1 if dt_a > dt_b else 0)


def check_chronology(
    events: dict[str, str],
    precedence_rules: list[list[str]],
    *,
    validity_windows: list[dict[str, Any]] | None = None,
    reference_date: str | None = None,
) -> dict[str, Any]:
    parsed_events = {k: _parse_iso_temporal(v) for k, v in events.items()}
    violations: list[dict[str, Any]] = []

    for rule in precedence_rules:
        if len(rule) != 2:
            raise ValueError(f"Regra de precedência deve conter [antes, depois]: {rule}")
        before, after = rule
        if before in parsed_events and after in parsed_events:
            if _compare_events(parsed_events[before], parsed_events[after]) > 0:
                violations.append(
                    {
                        "type": "precedence_violation",
                        "before": before,
                        "before_timestamp": events[before],
                        "after": after,
                        "after_timestamp": events[after],
                        "detail": f"'{before}' ({events[before]}) ocorreu após '{after}' ({events[after]}).",
                    }
                )

    ref_parsed = _parse_iso_temporal(reference_date) if reference_date else None
    for win in validity_windows or []:
        item_id = win.get("id", "norma")
        eff = _parse_iso_temporal(win["effective_from"]) if win.get("effective_from") else None
        rev = _parse_iso_temporal(win["revoked_on"]) if win.get("revoked_on") else None
        if ref_parsed:
            if eff and _compare_events(ref_parsed, eff) < 0:
                violations.append(
                    {"type": "not_yet_effective", "id": item_id, "detail": f"'{item_id}' só entra em vigência em {win['effective_from']}, após referência {reference_date}."}
                )
            if rev and _compare_events(ref_parsed, rev) >= 0:
                violations.append(
                    {"type": "revoked_before_reference", "id": item_id, "detail": f"'{item_id}' foi revogada em {win['revoked_on']}, antes da referência {reference_date}."}
                )

    timeline = sorted(
        [
            {"event": k, "timestamp": events[k], "precision": v[1], "has_timezone": v[2], "_sort": v[0]}
            for k, v in parsed_events.items()
        ],
        key=lambda x: x["_sort"],
    )
    for item in timeline:
        item.pop("_sort", None)

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
