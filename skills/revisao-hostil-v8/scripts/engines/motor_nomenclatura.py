#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Motor de nomenclatura, símbolos e glossário (Revisão Hostil v8.0-beta.5).

Verifica (Passo 5.5):
- Conflitos de notação (mesmo símbolo/sigla usado com significados divergentes);
- Variáveis usadas em equações sem entrada na lista de símbolos/glossário;
- Divergências frente ao vocabulário canônico do perfil.
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
from scripts.common.text_normalize import canonical_key
from scripts.common.validation import sanitize_for_json

MOTOR_ID = "motor_nomenclatura"
MOTOR_VERSION = "0.1.0-beta.5"


def audit_nomenclature(
    symbol_definitions: list[dict[str, str]],
    *,
    used_symbols: list[str] | None = None,
) -> dict[str, Any]:
    """Recebe lista de {symbol, meaning, location} e opcionalmente símbolos usados no texto."""
    by_symbol: dict[str, list[dict[str, str]]] = {}
    for entry in symbol_definitions:
        sym = str(entry["symbol"]).strip()
        by_symbol.setdefault(sym, []).append(entry)

    conflicts: list[dict[str, Any]] = []
    for sym, defs in by_symbol.items():
        norm_meanings = {canonical_key(d["meaning"]) for d in defs}
        if len(norm_meanings) > 1:
            conflicts.append(
                {
                    "symbol": sym,
                    "meanings": [d["meaning"] for d in defs],
                    "locations": [d.get("location", "desconhecida") for d in defs],
                }
            )

    undefined_symbols = sorted(set(used_symbols or []) - set(by_symbol.keys()))
    has_issues = bool(conflicts or undefined_symbols)
    return {
        "operation": "audit_nomenclature",
        "defined_symbol_count": len(by_symbol),
        "symbol_conflicts": conflicts,
        "undefined_symbols": undefined_symbols,
        "status": "discrepancy_detected" if has_issues else "ok",
    }


def run_motor(payload: Any, *, run_id: str | None = None, artefato_alvo: str | None = None) -> dict[str, Any]:
    inner = payload["payload"] if isinstance(payload, dict) and "payload" in payload and "motor_id" in payload else payload
    res = audit_nomenclature(inner.get("symbol_definitions", []), used_symbols=inner.get("used_symbols"))

    achados: list[dict[str, Any]] = []
    seq = 0
    for c in res["symbol_conflicts"]:
        seq += 1
        ev = create_evidence(
            f"EV-NOM-{seq:03d}",
            "textual",
            artefato_alvo or "nomenclatura",
            ", ".join(c["locations"]),
            f"Símbolo '{c['symbol']}' possui significados divergentes: {c['meanings']}",
            motor_origem=MOTOR_ID,
        )
        achados.append(
            create_finding(
                f"ACH-NOM-{seq:03d}",
                f"Conflito de notação para o símbolo '{c['symbol']}'",
                "nomenclatura_conflito_simbolo",
                "MAIOR",
                "ALTA",
                ", ".join(c["locations"]),
                f"O símbolo '{c['symbol']}' foi definido com múltiplos significados incompatíveis.",
                [ev],
                estado="CONFIRMADO",
                portao="G03",
                origem_componente=MOTOR_ID,
            )
        )
    for sym in res["undefined_symbols"]:
        seq += 1
        ev = create_evidence(
            f"EV-NOM-{seq:03d}",
            "textual",
            artefato_alvo or "nomenclatura",
            "lista_de_simbolos",
            f"Símbolo '{sym}' utilizado sem definição no glossário/notação.",
            motor_origem=MOTOR_ID,
        )
        achados.append(
            create_finding(
                f"ACH-NOM-{seq:03d}",
                f"Símbolo não definido: '{sym}'",
                "nomenclatura_simbolo_indefinido",
                "MODERADO",
                "ALTA",
                "lista_de_simbolos",
                f"Definir explicitamente '{sym}' na lista de símbolos e na primeira ocorrência.",
                [ev],
                estado="CONFIRMADO",
                portao="G08",
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
            "metricas": {"simbolos_definidos": res["defined_symbol_count"], "conflitos": len(res["symbol_conflicts"]), "indefinidos": len(res["undefined_symbols"])},
            "resultados": res,
            "achados": achados,
            "limitacoes": ["A detecção de conflito compara significados normalizados; sinonímias legítimas devem ser revisadas pelo auditor_clareza."],
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Motor de nomenclatura (Revisão Hostil v8.0-beta.5).")
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
