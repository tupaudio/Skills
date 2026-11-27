#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Motor de verificação normativa versionada (Revisão Hostil v8.0-beta.6).

Trabalha sobre o catálogo versionado em `references/norms/<JURISDICTION>/...` (Passo 6.4).

REGRA DE SEGURANÇA INEGOCIÁVEL:
Se a versão vigente, jurisdição, fonte oficial ou aplicabilidade de uma norma não puder ser
confirmada (`official_source_verified != True`, norma ausente do catálogo ou sem data de referência),
o resultado é `unverified` com achado em estado `NAO_VERIFICADO` — NUNCA conformidade presumida.
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

import yaml

from scripts.common import SCHEMA_VERSION
from scripts.common.evidence import create_evidence, create_finding, utc_now_iso
from scripts.common.validation import MAX_JSON_PAYLOAD_BYTES, read_bounded_json, sanitize_for_json

MOTOR_ID = "motor_normas"
MOTOR_VERSION = "0.1.0-beta.6"
DEFAULT_NORMS_DIR = _REPO_ROOT / "references" / "norms"


def load_norms_catalog(norms_dir: str | Path | None = None) -> dict[str, dict[str, Any]]:
    base = Path(norms_dir) if norms_dir else DEFAULT_NORMS_DIR
    catalog: dict[str, dict[str, Any]] = {}
    if not base.exists():
        return catalog
    for path in sorted(base.rglob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("norm_id"):
            data["_catalog_file"] = path.relative_to(base).as_posix()
            catalog[str(data["norm_id"]).upper()] = data
    return catalog


def verify_norm_citation(
    norm_id: str,
    *,
    jurisdiction: str | None = None,
    reference_date: str | None = None,
    cited_edition: str | None = None,
    catalog: dict[str, dict[str, Any]] | None = None,
    norms_dir: str | Path | None = None,
) -> dict[str, Any]:
    cat = catalog if catalog is not None else load_norms_catalog(norms_dir)
    key = norm_id.strip().upper()

    if key not in cat:
        return {
            "operation": "verify_norm_citation",
            "norm_id": norm_id,
            "found_in_catalog": False,
            "official_source_verified": False,
            "certifies_legal_compliance": False,
            "status": "unverified",
            "reason": f"Norma '{norm_id}' não localizada no catálogo versionado; vigência e aplicabilidade não verificadas.",
        }

    rec = cat[key]
    ref_dt = date.fromisoformat(reference_date.strip()[:10]) if reference_date else None
    eff_dt = date.fromisoformat(str(rec["effective_from"])[:10]) if rec.get("effective_from") else None
    rev_dt = date.fromisoformat(str(rec["revoked_on"])[:10]) if rec.get("revoked_on") else None

    issues: list[str] = []
    if jurisdiction and str(rec.get("jurisdiction", "")).upper() != jurisdiction.strip().upper():
        issues.append(
            f"Jurisdição incompatível: citada '{jurisdiction}', catálogo registra '{rec.get('jurisdiction')}'."
        )
    if ref_dt and rev_dt and ref_dt >= rev_dt:
        issues.append(
            f"Norma '{norm_id}' foi revogada em {rev_dt.isoformat()} (substituída por: {rec.get('replaced_by')}), antes da data de referência {ref_dt.isoformat()}."
        )
    if ref_dt and eff_dt and ref_dt < eff_dt:
        issues.append(
            f"Norma '{norm_id}' entra em vigência em {eff_dt.isoformat()}, após a data de referência {ref_dt.isoformat()}."
        )
    if cited_edition and rec.get("edition") and cited_edition.strip() != str(rec["edition"]).strip():
        issues.append(
            f"Edição citada ('{cited_edition}') difere da registrada no catálogo ('{rec['edition']}')."
        )

    if issues:
        return {
            "operation": "verify_norm_citation",
            "norm_id": norm_id,
            "found_in_catalog": True,
            "jurisdiction": rec.get("jurisdiction"),
            "edition": rec.get("edition"),
            "official_source": rec.get("official_source"),
            "official_source_verified": bool(rec.get("official_source_verified", False)),
            "certifies_legal_compliance": False,
            "issues": issues,
            "status": "discrepancy_detected",
        }

    if not rec.get("official_source_verified", False) or ref_dt is None:
        reason = (
            "Fonte oficial ainda não confirmada para a data da auditoria (`official_source_verified=False`)."
            if not rec.get("official_source_verified", False)
            else "Data de referência ausente; impossível confirmar vigência temporal."
        )
        return {
            "operation": "verify_norm_citation",
            "norm_id": norm_id,
            "found_in_catalog": True,
            "jurisdiction": rec.get("jurisdiction"),
            "edition": rec.get("edition"),
            "official_source": rec.get("official_source"),
            "official_source_verified": bool(rec.get("official_source_verified", False)),
            "certifies_legal_compliance": False,
            "status": "unverified",
            "reason": reason,
        }

    return {
        "operation": "verify_norm_citation",
        "norm_id": norm_id,
        "found_in_catalog": True,
        "jurisdiction": rec.get("jurisdiction"),
        "edition": rec.get("edition"),
        "official_source": rec.get("official_source"),
        "official_source_verified": True,
        "reference_date": ref_dt.isoformat(),
        "certifies_legal_compliance": False,
        "status": "ok",
    }


def run_motor(payload: Any, *, run_id: str | None = None, artefato_alvo: str | None = None) -> dict[str, Any]:
    inner = payload["payload"] if isinstance(payload, dict) and "payload" in payload and "motor_id" in payload else payload
    citations = inner.get("citations") if isinstance(inner, dict) and "citations" in inner else [inner]
    norms_dir = inner.get("norms_dir") if isinstance(inner, dict) else None
    catalog = load_norms_catalog(norms_dir)

    results: list[dict[str, Any]] = []
    achados: list[dict[str, Any]] = []
    for idx, cit in enumerate(citations, start=1):
        op_id = str(cit.get("id") or f"NRM_{idx:03d}")
        try:
            res = verify_norm_citation(
                cit["norm_id"],
                jurisdiction=cit.get("jurisdiction"),
                reference_date=cit.get("reference_date"),
                cited_edition=cit.get("cited_edition"),
                catalog=catalog,
            )
            res["id"] = op_id
            res["success"] = True
            results.append(res)
            if res["status"] == "discrepancy_detected":
                ev = create_evidence(
                    f"EV-NRM-{idx:03d}",
                    "normativa",
                    artefato_alvo or "citacoes_normativas",
                    op_id,
                    "; ".join(res.get("issues", [])),
                    motor_origem=MOTOR_ID,
                )
                achados.append(
                    create_finding(
                        f"ACH-NRM-{idx:03d}",
                        f"Inconsistência normativa em {cit['norm_id']}",
                        "norma_inconsistencia",
                        "CRITICO",
                        "ALTA",
                        op_id,
                        "; ".join(res.get("issues", [])),
                        [ev],
                        estado="CONFIRMADO",
                        portao="G12",
                        origem_componente=MOTOR_ID,
                    )
                )
            elif res["status"] == "unverified":
                ev = create_evidence(
                    f"EV-NRM-{idx:03d}",
                    "normativa",
                    artefato_alvo or "citacoes_normativas",
                    op_id,
                    res.get("reason", "Vigência/edição não verificada."),
                    motor_origem=MOTOR_ID,
                )
                achados.append(
                    create_finding(
                        f"ACH-NRM-{idx:03d}",
                        f"Norma não verificada: {cit['norm_id']}",
                        "norma_nao_verificada",
                        "MODERADO",
                        "MEDIA",
                        op_id,
                        res.get("reason", "Vigência/edição não confirmada; nunca presumir conformidade."),
                        [ev],
                        estado="NAO_VERIFICADO",
                        portao="G12",
                        origem_componente=MOTOR_ID,
                    )
                )
        except Exception as err:
            results.append({"id": op_id, "success": False, "status": "error", "error": str(err)})

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
            "metricas": {"total_citacoes": len(results), "sucesso": len(results) - failed, "falhas": failed, "total_achados": len(achados)},
            "resultados": {"results": results},
            "achados": achados,
            "limitacoes": [
                "O motor verifica metadados de vigência e jurisdição contra o catálogo versionado; jamais certifica conformidade jurídica ou técnica sem avaliação presencial/profissional."
            ],
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Motor de normas versionadas (Revisão Hostil v8.0-beta.6).")
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
