#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Motor de integridade de metadados e pacote (Revisão Hostil v8.0-beta.5).

Estritamente separado de motor_reprodutibilidade.py (Passo 5.6):
- Verifica integridade física do pacote: existência, tamanho não nulo, hashes SHA-256
  e comparação opcional contra hashes esperados (SHA256SUMS / manifesto).
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
from scripts.common.provenance import sha256_file
from scripts.common.validation import MAX_JSON_PAYLOAD_BYTES, read_bounded_json, sanitize_for_json

MOTOR_ID = "motor_metadados"
MOTOR_VERSION = "0.1.0-beta.5.1"


def audit_package_metadata(
    files: list[str | Path],
    *,
    expected_hashes: dict[str, str] | None = None,
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    exp = expected_hashes or {}

    for raw in files:
        p = Path(raw)
        if not p.exists() or not p.is_file():
            issues.append({"file": str(raw), "type": "missing_file", "detail": f"Arquivo ausente: {raw}"})
            records.append({"file": str(raw), "exists": False, "bytes": None, "sha256": None})
            continue
        size = p.stat().st_size
        digest = sha256_file(p)
        records.append({"file": p.name, "path": str(p.resolve()), "exists": True, "bytes": size, "sha256": digest})
        if size == 0:
            issues.append({"file": p.name, "type": "empty_file", "detail": f"Arquivo vazio (0 bytes): {p.name}"})
        if p.name in exp and exp[p.name].lower() != digest.lower():
            issues.append(
                {
                    "file": p.name,
                    "type": "hash_mismatch",
                    "detail": f"SHA-256 divergente em '{p.name}': esperado {exp[p.name]}, obtido {digest}.",
                }
            )

    return {
        "operation": "audit_package_metadata",
        "files": records,
        "issues": issues,
        "status": "discrepancy_detected" if issues else "ok",
    }


def run_motor(payload: Any, *, run_id: str | None = None, artefato_alvo: str | None = None) -> dict[str, Any]:
    inner = payload["payload"] if isinstance(payload, dict) and "payload" in payload and "motor_id" in payload else payload
    res = audit_package_metadata(inner.get("files", []), expected_hashes=inner.get("expected_hashes"))

    achados: list[dict[str, Any]] = []
    for idx, iss in enumerate(res["issues"], start=1):
        ev = create_evidence(
            f"EV-MET-{idx:03d}",
            "metadado",
            iss["file"],
            "pacote_arquivos",
            iss["detail"],
            motor_origem=MOTOR_ID,
        )
        grav = "CRITICO" if iss["type"] == "hash_mismatch" else "MAIOR"
        achados.append(
            create_finding(
                f"ACH-MET-{idx:03d}",
                f"Problema de integridade de pacote ({iss['type']})",
                f"metadados_{iss['type']}",
                grav,
                "ALTA",
                iss["file"],
                iss["detail"],
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
            "metricas": {"arquivos_inspecionados": len(res["files"]), "problemas": len(achados)},
            "resultados": res,
            "achados": achados,
            "limitacoes": ["Escopo restrito à integridade de arquivos e hashes; reconstrução científica pertence ao motor_reprodutibilidade."],
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Motor de metadados do pacote (Revisão Hostil v8.0-beta.5).")
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
