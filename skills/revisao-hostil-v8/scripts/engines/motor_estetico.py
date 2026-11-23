#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Motor especializado de análise composicional e estética (Revisão Hostil v8.0-beta.6).

Ativado exclusivamente pelo perfil `artes` (e opcional em `musica_acustica`).
Estritamente separado de `motor_figuras.py` (gráficos científicos) e `motor_imagem_forense.py`.

Extrai métricas composicionais objetivas (proporção, balanço de luminância, entropia tonal)
como insumo para o `auditor_artistico` — NUNCA emite juízo de valor artístico automático (`declares_artistic_value: False`).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import numpy as np
from PIL import Image

from scripts.common import SCHEMA_VERSION
from scripts.common.evidence import utc_now_iso
from scripts.common.provenance import sha256_file
from scripts.common.validation import sanitize_for_json, validate_safe_file_path

MOTOR_ID = "motor_estetico"
MOTOR_VERSION = "0.1.0-beta.6"
PHI = (1.0 + math.sqrt(5.0)) / 2.0


def analyze_composition(file_path: str | Path) -> dict[str, Any]:
    resolved = validate_safe_file_path(file_path)
    fhash = sha256_file(resolved)
    with Image.open(resolved) as img:
        width, height = img.size
        gray = np.asarray(img.convert("L"), dtype=float)
        rgb = np.asarray(img.convert("RGB"), dtype=float)

    aspect = float(width / height) if height > 0 else 0.0
    phi_dist = min(abs(aspect - PHI), abs(aspect - 1.0 / PHI)) if aspect > 0 else None

    mid_x, mid_y = max(1, width // 2), max(1, height // 2)
    lr_balance = float(np.mean(gray[:, :mid_x]) - np.mean(gray[:, mid_x:]))
    tb_balance = float(np.mean(gray[:mid_y, :]) - np.mean(gray[mid_y:, :]))

    hist, _ = np.histogram(gray, bins=256, range=(0, 256), density=False)
    probs = hist[hist > 0] / float(gray.size)
    shannon_entropy = float(-np.sum(probs * np.log2(probs)))

    return {
        "operation": "analyze_composition",
        "file": resolved.name,
        "sha256": fhash,
        "dimensions_px": [width, height],
        "aspect_ratio": aspect,
        "golden_ratio_distance": phi_dist,
        "luminance_mean": float(np.mean(gray)),
        "luminance_std": float(np.std(gray)),
        "left_right_luminance_delta": lr_balance,
        "top_bottom_luminance_delta": tb_balance,
        "tonal_entropy_bits": shannon_entropy,
        "rgb_channel_means": [float(np.mean(rgb[:, :, c])) for c in range(3)],
        "declares_artistic_value": False,
        "status": "ok",
    }


def run_motor(payload: Any, *, run_id: str | None = None, artefato_alvo: str | None = None) -> dict[str, Any]:
    inner = payload["payload"] if isinstance(payload, dict) and "payload" in payload and "motor_id" in payload else payload
    res = analyze_composition(inner["file_path"])
    return sanitize_for_json(
        {
            "schema_version": SCHEMA_VERSION,
            "motor_id": MOTOR_ID,
            "motor_version": MOTOR_VERSION,
            "run_id": run_id,
            "deterministico": True,
            "status": "OK",
            "timestamp": utc_now_iso(),
            "artefato_alvo": artefato_alvo or res["file"],
            "hash_artefato": res["sha256"],
            "metricas": {"tonal_entropy_bits": res["tonal_entropy_bits"], "aspect_ratio": res["aspect_ratio"]},
            "resultados": res,
            "achados": [],
            "limitacoes": [
                "Métricas composicionais são descritivas e não substituem a interpretação estética e hermenêutica do auditor_artistico."
            ],
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Motor composicional e estético (Revisão Hostil v8.0-beta.6).")
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
