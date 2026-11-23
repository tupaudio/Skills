#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Motor de figuras científicas e inventário de objetos visuais (Revisão Hostil v8.0-beta.4).

Responsabilidade exclusiva (Passos 4.2, 4.3 e 4.5):
- Auditoria técnica de gráficos científicos, diagramas e ilustrações técnicas:
  resolução, DPI efetivo, dimensões, proporção, contraste, formato vetorial vs rasterizado,
  presença de legenda/eixos/unidades declarados;
- Construção do Inventário Permanente de Objetos Visuais (FIG-001, TAB-001, EQ-001, ALG-001).

Não realiza análise forense de manipulação (papel do motor_imagem_forense.py)
nem análise estética/artística (papel do motor_estetico.py).
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
from PIL import Image

from scripts.common import SCHEMA_VERSION
from scripts.common.evidence import create_evidence, create_finding, utc_now_iso
from scripts.common.provenance import sha256_file
from scripts.common.validation import sanitize_for_json, validate_safe_file_path

MOTOR_ID = "motor_figuras"
MOTOR_VERSION = "0.1.0-beta.4"

VECTOR_EXTENSIONS = {".svg", ".pdf", ".eps"}
RASTER_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}


def inspect_figure_file(
    file_path: str | Path,
    *,
    min_width_px: int = 800,
    min_dpi: float = 300.0,
    min_contrast_std: float = 15.0,
    caption: str | None = None,
    has_axes_units: bool | None = None,
) -> dict[str, Any]:
    resolved = validate_safe_file_path(file_path)
    ext = resolved.suffix.lower()
    fhash = sha256_file(resolved)
    issues: list[str] = []

    if ext in VECTOR_EXTENSIONS:
        res: dict[str, Any] = {
            "operation": "inspect_figure",
            "file": resolved.name,
            "path": str(resolved),
            "sha256": fhash,
            "format_kind": "vector",
            "extension": ext,
            "dpi": None,
            "dimensions_px": None,
            "aspect_ratio": None,
            "contrast_std": None,
            "caption_present": bool(caption and caption.strip()) if caption is not None else None,
            "has_axes_units": has_axes_units,
        }
    elif ext in RASTER_EXTENSIONS:
        with Image.open(resolved) as img:
            width, height = img.size
            dpi_raw = img.info.get("dpi")
            dpi_x = float(dpi_raw[0]) if isinstance(dpi_raw, (tuple, list)) and len(dpi_raw) >= 1 else None
            dpi_y = float(dpi_raw[1]) if isinstance(dpi_raw, (tuple, list)) and len(dpi_raw) >= 2 else None
            eff_dpi = min(dpi_x, dpi_y) if (dpi_x and dpi_y) else dpi_x
            gray = np.asarray(img.convert("L"), dtype=float)
            contrast_std = float(np.std(gray))
            aspect = float(width / height) if height > 0 else 0.0

        if width < min_width_px:
            issues.append(f"Largura baixa ({width} px < {min_width_px} px).")
        if eff_dpi is not None and eff_dpi < (min_dpi - 0.5):
            issues.append(f"DPI efetivo baixo ({eff_dpi:.1f} < {min_dpi:.1f} DPI).")
        if contrast_std < min_contrast_std:
            issues.append(f"Contraste muito baixo (std={contrast_std:.1f} < {min_contrast_std:.1f}).")
        if aspect > 5.0 or (0 < aspect < 0.2):
            issues.append(f"Proporção extrema (aspect_ratio={aspect:.2f}); risco de corte ou ilegibidade.")

        res = {
            "operation": "inspect_figure",
            "file": resolved.name,
            "path": str(resolved),
            "sha256": fhash,
            "format_kind": "raster",
            "extension": ext,
            "dpi": [dpi_x, dpi_y] if dpi_x is not None else None,
            "effective_dpi": eff_dpi,
            "dimensions_px": [width, height],
            "aspect_ratio": aspect,
            "contrast_std": contrast_std,
            "caption_present": bool(caption and caption.strip()) if caption is not None else None,
            "has_axes_units": has_axes_units,
        }
    else:
        raise ValueError(f"Formato de figura não suportado: {ext}")

    if caption is not None and not caption.strip():
        issues.append("Legenda ausente ou vazia.")
    if has_axes_units is False:
        issues.append("Eixos sem unidades ou rótulos incompletos reportados na inspeção.")

    res["issues"] = issues
    res["status"] = "discrepancy_detected" if issues else "ok"
    return res


def build_visual_inventory(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Constrói inventário permanente de objetos visuais (FIG-001, TAB-001, EQ-001, ALG-001)."""
    counters = {"FIG": 0, "TAB": 0, "EQ": 0, "ALG": 0}
    prefix_map = {"figure": "FIG", "figura": "FIG", "table": "TAB", "tabela": "TAB", "equation": "EQ", "equacao": "EQ", "algorithm": "ALG", "algoritmo": "ALG"}

    inventory: list[dict[str, Any]] = []
    for item in items:
        raw_kind = str(item.get("kind", "figure")).lower()
        prefix = prefix_map.get(raw_kind, "FIG")
        counters[prefix] += 1
        obj_id = item.get("object_id") or f"{prefix}-{counters[prefix]:03d}"
        inventory.append(
            {
                "object_id": obj_id,
                "kind": prefix,
                "source_file": item.get("source_file"),
                "page": item.get("page"),
                "caption": item.get("caption"),
                "section": item.get("section"),
                "data_source": item.get("data_source"),
                "generator_code": item.get("generator_code"),
                "values": item.get("values", {}),
                "related_objects": item.get("related_objects", []),
                "visual_inspection_status": item.get("visual_inspection_status", "pendente"),
            }
        )

    return {
        "operation": "build_visual_inventory",
        "counts": counters,
        "total_objects": len(inventory),
        "objects": inventory,
        "status": "ok",
    }


def execute_single_operation(request: dict[str, Any]) -> dict[str, Any]:
    op = request.get("operation")
    if op == "inspect_figure":
        return inspect_figure_file(
            request["file_path"],
            min_width_px=request.get("min_width_px", 800),
            min_dpi=request.get("min_dpi", 300.0),
            min_contrast_std=request.get("min_contrast_std", 15.0),
            caption=request.get("caption"),
            has_axes_units=request.get("has_axes_units"),
        )
    if op == "build_visual_inventory":
        return build_visual_inventory(request["items"])
    raise ValueError(f"Operação de figuras desconhecida: {op}")


def run_motor(payload: Any, *, run_id: str | None = None, artefato_alvo: str | None = None) -> dict[str, Any]:
    inner = payload["payload"] if isinstance(payload, dict) and "payload" in payload and "motor_id" in payload else payload
    items = inner.get("operations", []) if isinstance(inner, dict) and inner.get("operation") == "batch" else (inner if isinstance(inner, list) else [inner])

    results: list[dict[str, Any]] = []
    achados: list[dict[str, Any]] = []
    for idx, item in enumerate(items, start=1):
        op_id = str(item.get("id") or f"FIG_{idx:03d}")
        try:
            res = execute_single_operation(item)
            res["id"] = op_id
            res["success"] = True
            results.append(res)
            if res.get("status") == "discrepancy_detected":
                ev = create_evidence(
                    f"EV-FIG-{idx:03d}",
                    "visual",
                    res.get("file") or artefato_alvo or "figura",
                    op_id,
                    "; ".join(res.get("issues", [])),
                    hash_arquivo=res.get("sha256"),
                    motor_origem=MOTOR_ID,
                )
                achados.append(
                    create_finding(
                        f"ACH-FIG-{idx:03d}",
                        f"Problema técnico de figura em {op_id}",
                        "qualidade_figura",
                        "MODERADO",
                        "ALTA",
                        op_id,
                        "; ".join(res.get("issues", [])),
                        [ev],
                        estado="CONFIRMADO",
                        portao="G09",
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
                "A conferência semântica de que a figura comunica exatamente o que o texto afirma deve ser completada pelo auditor_visual."
            ],
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Motor de figuras científicas (Revisão Hostil v8.0-beta.4).")
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
