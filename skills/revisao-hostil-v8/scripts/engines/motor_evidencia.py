#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Motor de qualidade de evidência configurável por framework (Revisão Hostil v8.0-beta.5).

Suporta frameworks distintos escolhidos pelo perfil (Passo 5.3):
- GRADE (saúde/clínica);
- OXFORD_CEBM (níveis 1 a 5);
- PRISMA (revisões sistemáticas);
- ENGENHARIA_EMPIRICA (bancada/HIL/campo vs simulação vs analítico);
- QUALITATIVO_DOCUMENTAL (triangulação, fontes primárias, auditabilidade).

Nunca impõe uma única hierarquia universal entre disciplinas.
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

MOTOR_ID = "motor_evidencia"
MOTOR_VERSION = "0.1.0-beta.5"

EVIDENCE_FRAMEWORKS: dict[str, dict[str, str]] = {
    "GRADE": {
        "rct": "ALTA (inicia em Alta no GRADE; sujeita a rebaixamento por viés/inconsistência/imprecisão)",
        "observational": "BAIXA (inicia em Baixa no GRADE; pode subir por grande magnitude de efeito)",
        "case_series": "MUITO_BAIXA",
    },
    "OXFORD_CEBM": {
        "systematic_review_rct": "Nivel 1",
        "rct": "Nivel 2",
        "cohort": "Nivel 3",
        "case_series": "Nivel 4",
        "expert_opinion": "Nivel 5",
    },
    "PRISMA": {
        "systematic_review": "Requer protocolo registrado, estratégia de busca reproduzível, fluxo PRISMA e avaliação de viés.",
    },
    "ENGENHARIA_EMPIRICA": {
        "field_experiment": "Evidência empírica de campo (mais próxima do ambiente operacional)",
        "hil_bench": "Evidência experimental em bancada / Hardware-in-the-Loop",
        "numerical_simulation": "Evidência computacional (não substitui validação experimental)",
        "analytical_derivation": "Evidência dedutiva sob hipóteses explícitas",
    },
    "QUALITATIVO_DOCUMENTAL": {
        "triangulated_primary": "Fontes primárias trianguladas com trilha de auditoria",
        "single_source_interview": "Fonte qualitativa única (requer contexto e reflexividade)",
        "documentary_secondary": "Fonte documental secundária",
    },
}


def evaluate_evidence_framework(
    framework: str,
    study_design: str,
    *,
    claimed_strength: str | None = None,
    limitations_reported: list[str] | None = None,
) -> dict[str, Any]:
    fw = framework.upper()
    if fw not in EVIDENCE_FRAMEWORKS:
        raise ValueError(f"Framework de evidência desconhecido: {framework}. Suportados: {sorted(EVIDENCE_FRAMEWORKS)}")
    mapping = EVIDENCE_FRAMEWORKS[fw]
    design_key = study_design.lower()
    if design_key not in mapping:
        return {
            "operation": "evaluate_evidence_framework",
            "framework": fw,
            "study_design": study_design,
            "classification": "NAO_MAPEADO_NO_FRAMEWORK",
            "overclaim_warning": False,
            "status": "ok",
        }

    classification = mapping[design_key]
    overclaim = False
    if claimed_strength and design_key in ("numerical_simulation", "observational", "case_series", "expert_opinion"):
        if claimed_strength.lower() in ("prova_definitiva", "certeza_absoluta", "causalidade_comprovada"):
            overclaim = True

    return {
        "operation": "evaluate_evidence_framework",
        "framework": fw,
        "study_design": study_design,
        "classification": classification,
        "limitations_reported_count": len(limitations_reported or []),
        "overclaim_warning": overclaim,
        "status": "discrepancy_detected" if overclaim else "ok",
    }


def run_motor(payload: Any, *, run_id: str | None = None, artefato_alvo: str | None = None) -> dict[str, Any]:
    inner = payload["payload"] if isinstance(payload, dict) and "payload" in payload and "motor_id" in payload else payload
    res = evaluate_evidence_framework(
        inner["framework"],
        inner["study_design"],
        claimed_strength=inner.get("claimed_strength"),
        limitations_reported=inner.get("limitations_reported"),
    )
    achados: list[dict[str, Any]] = []
    if res["status"] == "discrepancy_detected":
        ev = create_evidence(
            "EV-EVI-001",
            "textual",
            artefato_alvo or "desenho_estudo",
            res["framework"],
            f"Desenho '{res['study_design']}' ({res['classification']}) com força alegada incompatível.",
            motor_origem=MOTOR_ID,
        )
        achados.append(
            create_finding(
                "ACH-EVI-001",
                "Descompasso entre desenho de estudo e força epistêmica alegada",
                "descompasso_evidencia",
                "MAIOR",
                "ALTA",
                res["framework"],
                "A força da conclusão excede o nível suportado pelo desenho no framework selecionado.",
                [ev],
                estado="CONFIRMADO",
                portao="G02",
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
            "metricas": {"total_achados": len(achados)},
            "resultados": res,
            "achados": achados,
            "limitacoes": [
                "A escolha do framework de evidência é definida pelo perfil disciplinar; nenhuma hierarquia única é imposta universalmente."
            ],
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Motor de evidência (Revisão Hostil v8.0-beta.5).")
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
