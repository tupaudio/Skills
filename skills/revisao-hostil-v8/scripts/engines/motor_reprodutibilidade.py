#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Motor de reprodutibilidade científica (Revisão Hostil v8.0-beta.5).

Estritamente separado de motor_metadados.py (Passo 5.6):
- Verifica se dados, scripts, ambiente/dependências, sementes aleatórias e configurações
  permitem reconstruir independentemente os resultados;
- Detecta "números mágicos" (parâmetros declarados sem equação geradora, fonte ou dado).
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
from scripts.common.validation import sanitize_for_json

MOTOR_ID = "motor_reprodutibilidade"
MOTOR_VERSION = "0.1.0-beta.5"


def audit_reproducibility(
    *,
    has_data: bool,
    has_scripts: bool,
    has_environment_spec: bool,
    uses_stochastic_methods: bool = False,
    seeds_documented: bool = False,
    parameters: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    gaps: list[dict[str, str]] = []
    if not has_data:
        gaps.append({"type": "missing_data", "detail": "Dados primários/processados ausentes ou indisponíveis."})
    if not has_scripts:
        gaps.append({"type": "missing_scripts", "detail": "Scripts de análise/simulação não fornecidos."})
    if not has_environment_spec:
        gaps.append({"type": "missing_environment", "detail": "Especificação de ambiente/versões (requirements.txt, environment.yml, etc.) ausente."})
    if uses_stochastic_methods and not seeds_documented:
        gaps.append({"type": "missing_seeds", "detail": "Métodos estocásticos utilizados sem registro explícito das sementes aleatórias."})

    magic_numbers: list[dict[str, Any]] = []
    for p in parameters or []:
        has_provenance = bool(p.get("equation") or p.get("citation") or p.get("measurement_source"))
        if not has_provenance:
            magic_numbers.append(p)
            gaps.append(
                {
                    "type": "magic_number",
                    "detail": f"Parâmetro órfão '{p.get('name')}' = {p.get('value')} sem equação geradora, citação ou fonte experimental.",
                }
            )

    score = max(0.0, 10.0 - 2.0 * len(gaps))
    return {
        "operation": "audit_reproducibility",
        "reproducibility_score_0_10": round(score, 2),
        "gaps": gaps,
        "magic_numbers": magic_numbers,
        "status": "discrepancy_detected" if gaps else "ok",
    }


def run_motor(payload: Any, *, run_id: str | None = None, artefato_alvo: str | None = None) -> dict[str, Any]:
    inner = payload["payload"] if isinstance(payload, dict) and "payload" in payload and "motor_id" in payload else payload
    res = audit_reproducibility(
        has_data=bool(inner.get("has_data", False)),
        has_scripts=bool(inner.get("has_scripts", False)),
        has_environment_spec=bool(inner.get("has_environment_spec", False)),
        uses_stochastic_methods=bool(inner.get("uses_stochastic_methods", False)),
        seeds_documented=bool(inner.get("seeds_documented", False)),
        parameters=inner.get("parameters"),
    )

    achados: list[dict[str, Any]] = []
    for idx, gap in enumerate(res["gaps"], start=1):
        ev = create_evidence(
            f"EV-REP-{idx:03d}",
            "codigo",
            artefato_alvo or "pacote_reprodutibilidade",
            gap["type"],
            gap["detail"],
            motor_origem=MOTOR_ID,
        )
        achados.append(
            create_finding(
                f"ACH-REP-{idx:03d}",
                f"Lacuna de reprodutibilidade ({gap['type']})",
                f"reprodutibilidade_{gap['type']}",
                "MAIOR",
                "ALTA",
                gap["type"],
                gap["detail"],
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
            "metricas": {"nota_reprodutibilidade_0_10": res["reproducibility_score_0_10"], "lacunas": len(achados)},
            "resultados": res,
            "achados": achados,
            "limitacoes": ["A execução real dos scripts do manuscrito permanece isolada por segurança; este motor audita completude e proveniência."],
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Motor de reprodutibilidade (Revisão Hostil v8.0-beta.5).")
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
