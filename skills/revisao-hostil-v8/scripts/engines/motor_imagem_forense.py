#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Motor de análise forense de imagem (Revisão Hostil v8.0-beta.4).

Responsabilidade exclusiva (Passo 4.3):
- Extração de metadados (EXIF, PNG info, formato, modo de cor, compressão);
- Hash SHA-256 e perceptual dHash (detecção de imagens duplicadas ou quase idênticas no manuscrito);
- Triagem de software de edição presente em metadados.

RESTRIÇÃO METODOLÓGICA OBRIGATÓRIA:
Nunca classifica uma imagem como adulterada apenas por apresentar compressões diferentes,
metadados ausentes ou artefatos de edição (`declares_manipulation` é sempre `False`).
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

import numpy as np
from PIL import ExifTags, Image

from scripts.common import SCHEMA_VERSION
from scripts.common.evidence import create_evidence, create_finding, utc_now_iso
from scripts.common.provenance import sha256_file
from scripts.common.validation import MAX_JSON_PAYLOAD_BYTES, read_bounded_json, sanitize_for_json, validate_safe_file_path

MOTOR_ID = "motor_imagem_forense"
MOTOR_VERSION = "0.1.0-beta.4.1"


def _compute_dhash(img: Image.Image, hash_size: int = 8) -> str:
    gray = img.convert("L").resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
    arr = np.asarray(gray, dtype=np.int16)
    diff = arr[:, 1:] > arr[:, :-1]
    bits = "".join("1" if b else "0" for b in diff.flatten())
    return f"{int(bits, 2):0{hash_size * hash_size // 4}x}"


def _hamming_hex(h1: str, h2: str) -> int:
    return bin(int(h1, 16) ^ int(h2, 16)).count("1")


def inspect_image_forensics(file_path: str | Path) -> dict[str, Any]:
    resolved = validate_safe_file_path(file_path)
    fhash = sha256_file(resolved)

    with Image.open(resolved) as img:
        fmt = img.format
        mode = img.mode
        size = list(img.size)
        dhash = _compute_dhash(img)
        info_keys = sorted(str(k) for k in img.info.keys())
        software_tag = None

        exif_clean: dict[str, str] = {}
        try:
            exif_obj = img.getexif()
            if exif_obj:
                for tag_id, val in exif_obj.items():
                    tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                    exif_clean[tag_name] = str(val)[:200]
                    if tag_name.lower() == "software":
                        software_tag = str(val)[:200]
        except Exception:
            pass

        if not software_tag and "Software" in img.info:
            software_tag = str(img.info["Software"])[:200]

    return {
        "operation": "inspect_image_forensics",
        "file": resolved.name,
        "sha256": fhash,
        "dhash": dhash,
        "format": fmt,
        "mode": mode,
        "size_px": size,
        "info_keys": info_keys,
        "exif_tag_count": len(exif_clean),
        "exif_summary": exif_clean,
        "editing_software_detected": software_tag,
        "declares_manipulation": False,
        "methodological_note": (
            "Ausência de metadados, diferença de compressão ou tag de software de edição não provam "
            "adulteração; servem apenas como insumos objetivos para revisão humana."
        ),
        "status": "ok",
    }


def check_image_duplicates(file_paths: list[str | Path], *, hamming_threshold: int = 4) -> dict[str, Any]:
    records = [inspect_image_forensics(p) for p in file_paths]
    exact_dups: list[dict[str, Any]] = []
    near_dups: list[dict[str, Any]] = []

    for i in range(len(records)):
        for j in range(i + 1, len(records)):
            a, b = records[i], records[j]
            if a["sha256"] == b["sha256"]:
                exact_dups.append({"file_a": a["file"], "file_b": b["file"], "sha256": a["sha256"]})
            else:
                dist = _hamming_hex(a["dhash"], b["dhash"])
                if dist <= hamming_threshold:
                    near_dups.append({"file_a": a["file"], "file_b": b["file"], "dhash_distance": dist})

    flagged = bool(exact_dups or near_dups)
    return {
        "operation": "check_image_duplicates",
        "inspected_count": len(records),
        "exact_duplicates": exact_dups,
        "near_duplicates": near_dups,
        "declares_manipulation": False,
        "status": "discrepancy_detected" if flagged else "ok",
    }


def execute_single_operation(request: dict[str, Any]) -> dict[str, Any]:
    op = request.get("operation")
    if op == "inspect_image_forensics":
        return inspect_image_forensics(request["file_path"])
    if op == "check_image_duplicates":
        return check_image_duplicates(request["file_paths"], hamming_threshold=request.get("hamming_threshold", 4))
    raise ValueError(f"Operação de imagem forense desconhecida: {op}")


def run_motor(payload: Any, *, run_id: str | None = None, artefato_alvo: str | None = None) -> dict[str, Any]:
    inner = payload["payload"] if isinstance(payload, dict) and "payload" in payload and "motor_id" in payload else payload
    items = inner.get("operations", []) if isinstance(inner, dict) and inner.get("operation") == "batch" else (inner if isinstance(inner, list) else [inner])

    results: list[dict[str, Any]] = []
    achados: list[dict[str, Any]] = []
    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            results.append(
                {
                    "id": f"IMF_{idx:03d}",
                    "operation": "unknown",
                    "success": False,
                    "status": "error",
                    "error": f"Item de lote inválido no índice {idx}: esperado objeto/dicionário, recebido {type(item).__name__}.",
                }
            )
            continue

        op_id = str(item.get("id") or f"IMF_{idx:03d}")
        try:
            res = execute_single_operation(item)
            res["id"] = op_id
            res["success"] = True
            results.append(res)
            if res.get("status") == "discrepancy_detected":
                ev = create_evidence(
                    f"EV-IMF-{idx:03d}",
                    "visual",
                    artefato_alvo or "conjunto_imagens",
                    op_id,
                    f"Duplicatas exatas={len(res.get('exact_duplicates', []))}, quase-duplicatas={len(res.get('near_duplicates', []))}",
                    motor_origem=MOTOR_ID,
                )
                achados.append(
                    create_finding(
                        f"ACH-IMF-{idx:03d}",
                        f"Possível reutilização/duplicação de imagem em {op_id}",
                        "duplicacao_imagem_triagem",
                        "MAIOR",
                        "MEDIA",
                        op_id,
                        "Imagens idênticas ou visualmente muito semelhantes detectadas para verificação pelo auditor_visual.",
                        [ev],
                        estado="ABERTO",
                        portao="G10",
                        origem_componente=MOTOR_ID,
                    )
                )
        except Exception as err:
            results.append({"id": op_id, "operation": item.get("operation"), "success": False, "status": "error", "error": str(err)})

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
            "metricas": {"total_operacoes": len(results), "sucesso": len(results) - failed, "falhas": failed, "total_achados": len(achados)},
            "resultados": {"results": results},
            "achados": achados,
            "limitacoes": [
                "Este motor nunca declara manipulação ou fraude de forma automática; apenas reporta metadados e similaridade de hash para revisão humana."
            ],
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Motor de análise forense de imagem (Revisão Hostil v8.0-beta.4).")
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
