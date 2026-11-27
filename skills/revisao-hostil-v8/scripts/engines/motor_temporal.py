#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Motor temporal determinístico (Revisão Hostil v8.0-beta.5.2).

Verifica (Passo 5.4 + ACH-005 + ACH-009 + ACH-011):
- Validação estrita de ISO-8601 (precisão 'day' vs 'datetime', rejeitando conteúdo extra);
- Política explícita para horários sem fuso ('strict' padrão | 'utc_explicit'):
  NUNCA presume UTC silenciosamente para ordenação ou comparação;
- Separação rigorosa entre eventos com cronologia verificável (`timeline_verified`)
  e eventos com ordenação ambígua (`timeline_ambiguous`, preservando ordem de entrada);
- Detecção automática de ambiguidade entre eventos mesmo sem `precedence_rules`;
- Tratamento explícito de precisão diária misturada com timestamp horário no mesmo dia;
- Janelas de vigência de normas/documentos frente à data de referência.

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
MOTOR_VERSION = "0.2.0-beta.5.2"

_DATE_ONLY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})?$")


def _parse_iso_temporal(raw: str) -> tuple[datetime, str, bool]:
    """Valida estritamente data (YYYY-MM-DD) ou data+hora ISO-8601 completa sem truncamento.
    NUNCA atribui UTC a horários sem fuso (mantém datetime naive com has_timezone=False).
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
) -> tuple[int | None, str | None]:
    """Compara dois marcos temporais sem presumir UTC silenciosamente.
    Retorna (cmp, ambiguity_reason):
      - cmp in (-1, 0, 1) com ambiguity_reason=None quando a ordenação é verificável;
      - (None, reason) quando a ordenação depende de hipótese não declarada (fuso ou hora do dia).
    """
    dt_a, prec_a, tz_a = a
    dt_b, prec_b, tz_b = b

    # Ambos precisão diária -> comparação exata por data
    if prec_a == "day" and prec_b == "day":
        da, db = dt_a.date(), dt_b.date()
        return (-1 if da < db else (1 if da > db else 0)), None

    # Mistura de precisão diária com timestamp horário
    if prec_a != prec_b:
        da, db = dt_a.date(), dt_b.date()
        day_diff = abs((da - db).days)
        # Se ambos têm fuso ou ambos sem fuso e estão em dias distintos com folga >= 2 dias (ou >= 1 dia se sem fuso)
        if tz_a != tz_b and naive_policy == "strict":
            if day_diff <= 1:
                return None, "mixed_day_and_tz_aware_within_ambiguity_window"
            return (-1 if da < db else 1), None
        if da == db:
            return None, "mixed_day_and_datetime_same_calendar_day"
        return (-1 if da < db else 1), None

    # Ambos precisão datetime e mesma condição de fuso (ambos aware em UTC ou ambos naive)
    if tz_a == tz_b:
        return (-1 if dt_a < dt_b else (1 if dt_a > dt_b else 0)), None

    # Mistura de datetime naive e datetime timezone-aware
    if naive_policy == "utc_explicit":
        ua = dt_a if tz_a else dt_a.replace(tzinfo=timezone.utc)
        ub = dt_b if tz_b else dt_b.replace(tzinfo=timezone.utc)
        return (-1 if ua < ub else (1 if ua > ub else 0)), None

    # Política estrita: fuso real de um naive pode variar em [-12h, +14h] (janela = 26h)
    ua = dt_a if tz_a else dt_a.replace(tzinfo=timezone.utc)
    ub = dt_b if tz_b else dt_b.replace(tzinfo=timezone.utc)
    diff_hours = abs((ua - ub).total_seconds()) / 3600.0
    if diff_hours <= 26.0:
        return None, "mixed_naive_and_tz_aware_within_26h"
    return (-1 if ua < ub else 1), None


def _build_verified_and_ambiguous_timelines(
    events: dict[str, str],
    parsed_events: dict[str, tuple[datetime, str, bool]],
    *,
    naive_policy: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Separa eventos cuja ordenação é totalmente verificável dos eventos envolvidos em pares ambíguos.
    NUNCA inventa ordenação cronológica atribuindo UTC artificial a horários naive (ACH-011).
    """
    keys = list(events.keys())
    ambiguous_keys: set[str] = set()
    pairwise_ambiguities: list[dict[str, Any]] = []

    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            ka, kb = keys[i], keys[j]
            cmp_res, reason = _compare_events(parsed_events[ka], parsed_events[kb], naive_policy=naive_policy)
            if cmp_res is None:
                ambiguous_keys.add(ka)
                ambiguous_keys.add(kb)
                pairwise_ambiguities.append(
                    {
                        "type": reason or "ambiguous_chronology",
                        "event_a": ka,
                        "timestamp_a": events[ka],
                        "event_b": kb,
                        "timestamp_b": events[kb],
                        "detail": (
                            f"Ordenação cronológica ambígua entre '{ka}' ({events[ka]}) e '{kb}' ({events[kb]}): "
                            f"{reason}."
                        ),
                    }
                )

    def _rec(k: str) -> dict[str, Any]:
        _, prec, has_tz = parsed_events[k]
        return {"event": k, "timestamp": events[k], "precision": prec, "has_timezone": has_tz}

    # Eventos verificáveis: todos os que não participam de nenhum par ambíguo, ordenados por _compare_events
    verified_keys = [k for k in keys if k not in ambiguous_keys]
    # Insertion sort usando _compare_events (determinístico, sem UTC artificial)
    ordered_verified: list[str] = []
    for k in verified_keys:
        inserted = False
        for idx, existing in enumerate(ordered_verified):
            cmp_res, _ = _compare_events(parsed_events[k], parsed_events[existing], naive_policy=naive_policy)
            if cmp_res is not None and cmp_res < 0:
                ordered_verified.insert(idx, k)
                inserted = True
                break
        if not inserted:
            ordered_verified.append(k)

    # Eventos ambíguos: preservam estritamente a ordem de entrada (sem ordenar cronologicamente!)
    ambiguous_list = [_rec(k) for k in keys if k in ambiguous_keys]
    verified_list = [_rec(k) for k in ordered_verified]
    return verified_list, ambiguous_list, pairwise_ambiguities


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
    seen_amb_pairs: set[tuple[str, str]] = set()

    for rule in precedence_rules:
        if len(rule) != 2:
            raise ValueError(f"Regra de precedência deve conter [antes, depois]: {rule}")
        before, after = rule
        if before in parsed_events and after in parsed_events:
            cmp_res, reason = _compare_events(parsed_events[before], parsed_events[after], naive_policy=naive_policy)
            if cmp_res is None:
                pair_key = tuple(sorted((before, after)))
                seen_amb_pairs.add(pair_key)  # type: ignore[arg-type]
                ambiguities.append(
                    {
                        "type": reason or "ambiguous_timezone",
                        "before": before,
                        "before_timestamp": events[before],
                        "after": after,
                        "after_timestamp": events[after],
                        "detail": (
                            f"Ordenação ambígua entre '{before}' ({events[before]}) e '{after}' ({events[after]}): "
                            f"{reason}."
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
                c_eff, r_eff = _compare_events(ref_parsed, eff, naive_policy=naive_policy)
                if c_eff is None:
                    ambiguities.append({"type": r_eff or "ambiguous_timezone", "id": item_id, "detail": f"Ambiguidade temporal ao checar início de vigência de '{item_id}'."})
                elif c_eff < 0:
                    violations.append(
                        {"type": "not_yet_effective", "id": item_id, "detail": f"'{item_id}' só entra em vigência em {win['effective_from']}, após referência {reference_date}."}
                    )
            if rev:
                c_rev, r_rev = _compare_events(ref_parsed, rev, naive_policy=naive_policy)
                if c_rev is None:
                    ambiguities.append({"type": r_rev or "ambiguous_timezone", "id": item_id, "detail": f"Ambiguidade temporal ao checar revogação de '{item_id}'."})
                elif c_rev >= 0:
                    violations.append(
                        {"type": "revoked_before_reference", "id": item_id, "detail": f"'{item_id}' foi revogada em {win['revoked_on']}, antes da referência {reference_date}."}
                    )

    timeline_verified, timeline_ambiguous, pairwise_ambs = _build_verified_and_ambiguous_timelines(
        events, parsed_events, naive_policy=naive_policy
    )
    for pamb in pairwise_ambs:
        pair_key = tuple(sorted((pamb["event_a"], pamb["event_b"])))
        if pair_key not in seen_amb_pairs:
            ambiguities.append(pamb)

    chronological_order_verified = len(timeline_ambiguous) == 0
    if violations:
        status = "discrepancy_detected"
    elif ambiguities or not chronological_order_verified:
        status = "unverified"
    else:
        status = "ok"

    return {
        "operation": "check_chronology",
        "naive_policy": naive_policy,
        "chronological_order_verified": chronological_order_verified,
        "timeline": timeline_verified,
        "timeline_verified": timeline_verified,
        "timeline_ambiguous": timeline_ambiguous,
        "violations": violations,
        "ambiguities": ambiguities,
        "infers_causality_from_order": False,
        "status": status,
    }


def run_motor(payload: Any, *, run_id: str | None = None, artefato_alvo: str | None = None) -> dict[str, Any]:
    inner = payload["payload"] if isinstance(payload, dict) and "payload" in payload and "motor_id" in payload else payload

    events = inner.get("events") if isinstance(inner, dict) else None
    if not isinstance(inner, dict) or events is None or not isinstance(events, dict):
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
                    "eventos_verificados": 0,
                    "eventos_ambiguos": 0,
                    "violacoes": 0,
                    "ambiguidades": 0,
                    "erros": 1,
                },
                "resultados": {
                    "error": "Payload inválido: esperado objeto contendo o dicionário obrigatório 'events'.",
                    "timeline_verified": {},
                    "timeline_ambiguous": {},
                    "violations": [],
                    "ambiguities": [],
                    "status": "error",
                },
                "achados": [],
                "limitacoes": [
                    "Precedência temporal é condição necessária, mas não suficiente, para inferência causal.",
                    "Na política padrão ('strict'), horários sem fuso nunca recebem UTC artificial para ordenação.",
                ],
            }
        )

    res = check_chronology(
        events,
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
        loc = amb.get("id") or (
            f"{amb.get('before')}->{amb.get('after')}" if "before" in amb else f"{amb.get('event_a')}<->{amb.get('event_b')}"
        )
        ev = create_evidence(
            f"EV-TMP-{seq:03d}",
            "textual",
            artefato_alvo or "cronologia",
            loc,
            amb["detail"],
            motor_origem=MOTOR_ID,
        )
        achados.append(
            create_finding(
                f"ACH-TMP-{seq:03d}",
                f"Ambiguidade temporal ({amb['type']})",
                "temporal_ambiguous_chronology",
                "MODERADO",
                "MEDIA",
                loc,
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
            "metricas": {
                "eventos_verificados": len(res["timeline_verified"]),
                "eventos_ambiguos": len(res["timeline_ambiguous"]),
                "violacoes": len(res["violations"]),
                "ambiguidades": len(res["ambiguities"]),
            },
            "resultados": res,
            "achados": achados,
            "limitacoes": [
                "Precedência temporal é condição necessária, mas não suficiente, para inferência causal.",
                "Na política padrão ('strict'), horários sem fuso nunca recebem UTC artificial para ordenação.",
            ],
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Motor temporal (Revisão Hostil v8.0-beta.5.2).")
    parser.add_argument("--input", "-i")
    parser.add_argument("--out", "-o")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    try:
        req = json.loads(Path(args.input).read_text(encoding="utf-8")) if args.input else json.load(sys.stdin)
        out = run_motor(req, run_id=args.run_id, artefato_alvo=args.input or "stdin")
        text = json.dumps(out, ensure_ascii=False, indent=2, allow_nan=False)
        if args.out:
            Path(args.out).write_text(text, encoding="utf-8")
        else:
            print(text)
        if out.get("status") == "ERRO_VALIDACAO":
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
