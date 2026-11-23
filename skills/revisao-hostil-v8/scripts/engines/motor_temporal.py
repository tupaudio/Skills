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
    """Valida estritamente data (YYYY-MM-DD) ou data+hora ISO-8601 completa sem truncamento (ACH-005/ACH-009).
    NUNCA presume UTC silenciosamente para horários sem fuso (mantém datetime naive com has_timezone=False).
    """
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"Marca temporal vazia ou inválida: {raw!r}")
    s = raw.strip()
    if _DATE_ONLY_RE.match(s):
        d = date.fromisoformat(s)
        return datetime(d.year, d.month, d.day), "day", False
    if _DATETIME_RE.match(s):
        normalized = s[:-1] + "+00:00" if s.endswith("Z") else s
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is not None:
            return dt.astimezone(timezone.utc), "datetime", True
        return dt, "datetime", False
    raise ValueError(f"Formato ISO-8601 inválido (conteúdo extra ou sintaxe incorreta): {raw!r}")


def _compare_events(
    a: tuple[datetime, str, bool],
    b: tuple[datetime, str, bool],
    *,
    naive_policy: str = "strict",
) -> int | None:
    """Compara dois marcos temporais sem presumir UTC silenciosamente (ACH-009).
    Retorna -1 (a < b), 0 (a == b), 1 (a > b), ou None quando houver ambiguidade de fuso (NAO_VERIFICADO).
    """
    dt_a, prec_a, tz_a = a
    dt_b, prec_b, tz_b = b
    if prec_a == "day" or prec_b == "day":
        da, db = dt_a.date(), dt_b.date()
        return -1 if da < db else (1 if da > db else 0)

    if tz_a == tz_b:
        return -1 if dt_a < dt_b else (1 if dt_a > dt_b else 0)

    # Mistura de datetime naive e datetime timezone-aware
    if naive_policy == "utc_explicit":
        ua = dt_a if tz_a else dt_a.replace(tzinfo=timezone.utc)
        ub = dt_b if tz_b else dt_b.replace(tzinfo=timezone.utc)
        return -1 if ua < ub else (1 if ua > ub else 0)

    # Política estrita: fuso real de um naive pode variar em [-12h, +14h] (janela de ambiguidade = 26h)
    naive_as_utc_a = dt_a if tz_a else dt_a.replace(tzinfo=timezone.utc)
    naive_as_utc_b = dt_b if tz_b else dt_b.replace(tzinfo=timezone.utc)
    diff_hours = abs((naive_as_utc_a - naive_as_utc_b).total_seconds()) / 3600.0
    if diff_hours <= 26.0:
        return None
    return -1 if naive_as_utc_a < naive_as_utc_b else 1


def check_chronology(
    events: dict[str, str],
    precedence_rules: list[list[str]],
    *,
    validity_windows: list[dict[str, Any]] | None = None,
    reference_date: str | None = None,
    naive_policy: str = "strict",
) -> dict[str, Any]:
    if naive_policy not in ("strict", "utc_explicit"):
        raise ValueError(f"naive_policy inválida: {naive_policy}. Use 'strict' ou 'utc_explicit'.")
    parsed_events = {k: _parse_iso_temporal(v) for k, v in events.items()}
    violations: list[dict[str, Any]] = []
    ambiguities: list[dict[str, Any]] = []

    for rule in precedence_rules:
        if len(rule) != 2:
            raise ValueError(f"Regra de precedência deve conter [antes, depois]: {rule}")
        before, after = rule
        if before in parsed_events and after in parsed_events:
            cmp_res = _compare_events(parsed_events[before], parsed_events[after], naive_policy=naive_policy)
            if cmp_res is None:
                ambiguities.append(
                    {
                        "type": "ambiguous_timezone",
                        "before": before,
                        "before_timestamp": events[before],
                        "after": after,
                        "after_timestamp": events[after],
                        "detail": (
                            f"Ordenação ambígua entre '{before}' ({events[before]}) e '{after}' ({events[after]}): "
                            "mistura de horário sem fuso e com fuso dentro da janela de 26h."
                        ),
                    }
                )
            elif cmp_res > 0:
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
            if eff:
                c_eff = _compare_events(ref_parsed, eff, naive_policy=naive_policy)
                if c_eff is None:
                    ambiguities.append({"type": "ambiguous_timezone", "id": item_id, "detail": f"Ambiguidade de fuso ao checar início de vigência de '{item_id}'."})
                elif c_eff < 0:
                    violations.append(
                        {"type": "not_yet_effective", "id": item_id, "detail": f"'{item_id}' só entra em vigência em {win['effective_from']}, após referência {reference_date}."}
                    )
            if rev:
                c_rev = _compare_events(ref_parsed, rev, naive_policy=naive_policy)
                if c_rev is None:
                    ambiguities.append({"type": "ambiguous_timezone", "id": item_id, "detail": f"Ambiguidade de fuso ao checar revogação de '{item_id}'."})
                elif c_rev >= 0:
                    violations.append(
                        {"type": "revoked_before_reference", "id": item_id, "detail": f"'{item_id}' foi revogada em {win['revoked_on']}, antes da referência {reference_date}."}
                    )

    timeline = sorted(
        [
            {
                "event": k,
                "timestamp": events[k],
                "precision": v[1],
                "has_timezone": v[2],
                "_sort": v[0] if v[2] else v[0].replace(tzinfo=timezone.utc),
            }
            for k, v in parsed_events.items()
        ],
        key=lambda x: x["_sort"],
    )
    for item in timeline:
        item.pop("_sort", None)

    if violations:
        status = "discrepancy_detected"
    elif ambiguities:
        status = "unverified"
    else:
        status = "ok"

    return {
        "operation": "check_chronology",
        "naive_policy": naive_policy,
        "timeline": timeline,
        "violations": violations,
        "ambiguities": ambiguities,
        "infers_causality_from_order": False,
        "status": status,
    }


def run_motor(payload: Any, *, run_id: str | None = None, artefato_alvo: str | None = None) -> dict[str, Any]:
    inner = payload["payload"] if isinstance(payload, dict) and "payload" in payload and "motor_id" in payload else payload
    res = check_chronology(
        inner.get("events", {}),
        inner.get("precedence_rules", []),
        validity_windows=inner.get("validity_windows"),
        reference_date=inner.get("reference_date"),
        naive_policy=inner.get("naive_policy", "strict"),
    )
    achados: list[dict[str, Any]] = []
    seq = 0
    for v in res["violations"]:
        seq += 1
        ev = create_evidence(
            f"EV-TMP-{seq:03d}",
            "textual",
            artefato_alvo or "cronologia",
            v.get("id") or f"{v.get('before')}->{v.get('after')}",
            v["detail"],
            motor_origem=MOTOR_ID,
        )
        achados.append(
            create_finding(
                f"ACH-TMP-{seq:03d}",
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
    for amb in res.get("ambiguities", []):
        seq += 1
        ev = create_evidence(
            f"EV-TMP-{seq:03d}",
            "textual",
            artefato_alvo or "cronologia",
            amb.get("id") or f"{amb.get('before')}->{amb.get('after')}",
            amb["detail"],
            motor_origem=MOTOR_ID,
        )
        achados.append(
            create_finding(
                f"ACH-TMP-{seq:03d}",
                "Ambiguidade de fuso horário na ordenação temporal",
                "temporal_ambiguous_timezone",
                "MODERADO",
                "MEDIA",
                amb.get("id") or "cronologia",
                amb["detail"],
                [ev],
                estado="NAO_VERIFICADO",
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
