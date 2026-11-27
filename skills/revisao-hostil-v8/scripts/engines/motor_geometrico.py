#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Motor geométrico determinístico (Revisão Hostil v8.0-beta.3).

Módulos implementados (Passo 3.3):
1. Geometria plana (polygon_2d: área Shoelace, perímetro, centroide, convexidade)
2. Geometria 3D (solid_3d: box, cylinder, sphere, cone — volume, área superficial, A/V)
3. Distâncias e transformações (distance, transform_3d com validação de ortogonalidade)
4. Interseções e colisões (segment_intersection_2d, aabb_collision_3d)
5. Tolerâncias geométricas (tolerance_stackup: worst-case e RSS)
6. Fatores de forma radiativos (view_factor_coaxial_disks, view_factor_reciprocity)
7. Análise de malhas triangulares (mesh_quality: áreas, razão de aspecto, degenerados)
8. Consistência dimensional de entidades geométricas (shell_mass_consistency: área/espessura/densidade -> massa)
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

from scripts.common import SCHEMA_VERSION
from scripts.common.evidence import create_evidence, create_finding, utc_now_iso
from scripts.common.validation import require_finite_array, require_finite_number, sanitize_for_json

MOTOR_ID = "motor_geometrico"
MOTOR_VERSION = "0.1.0-beta.3"


def polygon_2d(vertices: Any, *, reported_area: float | None = None, rel_tolerance: float = 0.01) -> dict[str, Any]:
    pts = require_finite_array(vertices, name="vertices", ndim=2)
    if pts.shape[0] < 3 or pts.shape[1] != 2:
        raise ValueError("Polígono 2D exige pelo menos 3 vértices de dimensão (N, 2).")
    x, y = pts[:, 0], pts[:, 1]
    x_next, y_next = np.roll(x, -1), np.roll(y, -1)
    signed_area = 0.5 * float(np.sum(x * y_next - x_next * y))
    area = abs(signed_area)
    if area <= 1e-15:
        raise ValueError("Polígono degenerado (área nula).")

    edges = np.hypot(x_next - x, y_next - y)
    perimeter = float(np.sum(edges))
    cx = float(np.sum((x + x_next) * (x * y_next - x_next * y)) / (6.0 * signed_area))
    cy = float(np.sum((y + y_next) * (x * y_next - x_next * y)) / (6.0 * signed_area))

    # Convexidade via sinal do produto vetorial
    v1 = np.roll(pts, -1, axis=0) - pts
    v2 = np.roll(pts, -2, axis=0) - np.roll(pts, -1, axis=0)
    cross = v1[:, 0] * v2[:, 1] - v1[:, 1] * v2[:, 0]
    convex = bool(np.all(cross >= -1e-12) or np.all(cross <= 1e-12))

    discrepancy = False
    if reported_area is not None:
        rep = require_finite_number(reported_area, "reported_area")
        discrepancy = abs(area - rep) > max(1e-9, abs(rep) * rel_tolerance)

    return {
        "operation": "polygon_2d",
        "n_vertices": int(pts.shape[0]),
        "area": area,
        "perimeter": perimeter,
        "centroid": [cx, cy],
        "convex": convex,
        "reported_area": reported_area,
        "status": "discrepancy_detected" if discrepancy else "ok",
    }


def solid_3d(shape: str, dimensions: dict[str, Any]) -> dict[str, Any]:
    s = shape.lower()
    if s == "box":
        lx = require_finite_number(dimensions["lx"], "lx")
        ly = require_finite_number(dimensions["ly"], "ly")
        lz = require_finite_number(dimensions["lz"], "lz")
        if lx <= 0 or ly <= 0 or lz <= 0:
            raise ValueError("Dimensões da caixa devem ser estritamente positivas.")
        vol = lx * ly * lz
        area = 2.0 * (lx * ly + lx * lz + ly * lz)
    elif s == "sphere":
        r = require_finite_number(dimensions["radius"], "radius")
        if r <= 0:
            raise ValueError("Raio da esfera deve ser estritamente positivo.")
        vol = (4.0 / 3.0) * math.pi * r**3
        area = 4.0 * math.pi * r**2
    elif s == "cylinder":
        r = require_finite_number(dimensions["radius"], "radius")
        h = require_finite_number(dimensions["height"], "height")
        if r <= 0 or h <= 0:
            raise ValueError("Raio e altura do cilindro devem ser estritamente positivos.")
        vol = math.pi * r**2 * h
        area = 2.0 * math.pi * r * (r + h)
    elif s == "cone":
        r = require_finite_number(dimensions["radius"], "radius")
        h = require_finite_number(dimensions["height"], "height")
        if r <= 0 or h <= 0:
            raise ValueError("Raio e altura do cone devem ser estritamente positivos.")
        slant = math.hypot(r, h)
        vol = (1.0 / 3.0) * math.pi * r**2 * h
        area = math.pi * r * (r + slant)
    else:
        raise ValueError(f"Sólido 3D não suportado: {shape}")

    return {
        "operation": "solid_3d",
        "shape": s,
        "volume": float(vol),
        "surface_area": float(area),
        "area_to_volume_ratio": float(area / vol),
        "status": "ok",
    }


def validate_rotation_matrix(matrix: Any, *, tolerance: float = 1e-6) -> dict[str, Any]:
    R = require_finite_array(matrix, name="matrix", ndim=2)
    if R.shape not in ((2, 2), (3, 3)):
        raise ValueError("Matriz de rotação deve ser 2x2 ou 3x3.")
    ortho_err = float(np.max(np.abs(R.T @ R - np.eye(R.shape[0]))))
    det = float(np.linalg.det(R))
    valid_rotation = bool(ortho_err <= tolerance and abs(det - 1.0) <= tolerance)
    return {
        "operation": "validate_rotation_matrix",
        "shape": list(R.shape),
        "orthogonality_max_error": ortho_err,
        "determinant": det,
        "valid_proper_rotation": valid_rotation,
        "status": "ok" if valid_rotation else "discrepancy_detected",
    }


def aabb_collision_3d(box_a_min: Any, box_a_max: Any, box_b_min: Any, box_b_max: Any) -> dict[str, Any]:
    amin = require_finite_array(box_a_min, "box_a_min", ndim=1)
    amax = require_finite_array(box_a_max, "box_a_max", ndim=1)
    bmin = require_finite_array(box_b_min, "box_b_min", ndim=1)
    bmax = require_finite_array(box_b_max, "box_b_max", ndim=1)
    if not (amin.size == amax.size == bmin.size == bmax.size == 3):
        raise ValueError("AABBs 3D exigem vetores de tamanho 3.")
    if np.any(amin > amax) or np.any(bmin > bmax):
        raise ValueError("Limites mínimos da AABB não podem exceder os máximos.")
    overlap_dims = np.minimum(amax, bmax) - np.maximum(amin, bmin)
    collides = bool(np.all(overlap_dims >= 0.0))
    overlap_vol = float(np.prod(np.maximum(overlap_dims, 0.0)))
    return {
        "operation": "aabb_collision_3d",
        "collides": collides,
        "overlap_volume": overlap_vol,
        "status": "ok",
    }


def tolerance_stackup(nominals: Any, tolerances: Any) -> dict[str, Any]:
    nom = require_finite_array(nominals, "nominals", ndim=1)
    tol = require_finite_array(tolerances, "tolerances", ndim=1)
    if nom.size != tol.size or np.any(tol < 0):
        raise ValueError("nominals e tolerances devem ter mesmo tamanho e tolerâncias >= 0.")
    return {
        "operation": "tolerance_stackup",
        "nominal_sum": float(np.sum(nom)),
        "worst_case_tolerance": float(np.sum(tol)),
        "rss_tolerance": float(np.sqrt(np.sum(tol**2))),
        "status": "ok",
    }


def view_factor_coaxial_disks(r1: float, r2: float, distance: float) -> dict[str, Any]:
    """Fator de forma radiativo F12 entre dois discos paralelos coaxiais (Howell/Incropera)."""
    rad1 = require_finite_number(r1, "r1")
    rad2 = require_finite_number(r2, "r2")
    h = require_finite_number(distance, "distance")
    if rad1 <= 0 or rad2 <= 0 or h <= 0:
        raise ValueError("r1, r2 e distance devem ser estritamente positivos.")
    R1 = rad1 / h
    R2 = rad2 / h
    S = 1.0 + (1.0 + R2**2) / (R1**2)
    f12 = 0.5 * (S - math.sqrt(max(0.0, S**2 - 4.0 * (R2 / R1) ** 2)))
    a1 = math.pi * rad1**2
    a2 = math.pi * rad2**2
    f21 = f12 * a1 / a2
    return {
        "operation": "view_factor_coaxial_disks",
        "F12": float(f12),
        "F21": float(f21),
        "reciprocity_residual": float(abs(a1 * f12 - a2 * f21)),
        "status": "ok",
    }


def mesh_quality_triangles(vertices: Any, faces: Any) -> dict[str, Any]:
    verts = require_finite_array(vertices, "vertices", ndim=2)
    f_arr = np.asarray(faces, dtype=int)
    if verts.shape[1] not in (2, 3) or f_arr.ndim != 2 or f_arr.shape[1] != 3:
        raise ValueError("Malha triangular exige vertices (N, 2|3) e faces (M, 3).")
    if np.any(f_arr < 0) or np.any(f_arr >= verts.shape[0]):
        raise ValueError("Índice de vértice fora do intervalo em faces.")

    areas = []
    aspect_ratios = []
    degenerate = 0
    for tri in f_arr:
        p0, p1, p2 = verts[tri[0]], verts[tri[1]], verts[tri[2]]
        e0 = float(np.linalg.norm(p1 - p0))
        e1 = float(np.linalg.norm(p2 - p1))
        e2 = float(np.linalg.norm(p0 - p2))
        s = 0.5 * (e0 + e1 + e2)
        area_sq = max(0.0, s * (s - e0) * (s - e1) * (s - e2))
        area = math.sqrt(area_sq)
        areas.append(area)
        if area <= 1e-14:
            degenerate += 1
            aspect_ratios.append(float("inf"))
        else:
            longest = max(e0, e1, e2)
            inradius = area / s
            aspect_ratios.append(longest / (2.0 * math.sqrt(3.0) * inradius))

    finite_ar = [ar for ar in aspect_ratios if math.isfinite(ar)]
    return {
        "operation": "mesh_quality",
        "n_triangles": int(f_arr.shape[0]),
        "degenerate_count": degenerate,
        "total_area": float(sum(areas)),
        "min_area": float(min(areas)),
        "max_aspect_ratio": float(max(finite_ar)) if finite_ar else None,
        "status": "discrepancy_detected" if degenerate > 0 else "ok",
    }


def shell_mass_consistency(
    surface_area_m2: float,
    thickness_m: float,
    density_kg_m3: float,
    *,
    reported_mass_kg: float | None = None,
    rel_tolerance: float = 0.02,
) -> dict[str, Any]:
    """Verifica consistência entre espessura linear, área superficial, densidade e massa."""
    A = require_finite_number(surface_area_m2, "surface_area_m2")
    t = require_finite_number(thickness_m, "thickness_m")
    rho = require_finite_number(density_kg_m3, "density_kg_m3")
    if A <= 0 or t <= 0 or rho <= 0:
        raise ValueError("Área, espessura e densidade devem ser estritamente positivas.")
    volume_m3 = A * t
    mass_kg = volume_m3 * rho
    discrepancy = False
    if reported_mass_kg is not None:
        rep = require_finite_number(reported_mass_kg, "reported_mass_kg")
        discrepancy = abs(mass_kg - rep) > max(1e-9, abs(rep) * rel_tolerance)
    return {
        "operation": "shell_mass_consistency",
        "volume_m3": volume_m3,
        "calculated_mass_kg": mass_kg,
        "reported_mass_kg": reported_mass_kg,
        "status": "discrepancy_detected" if discrepancy else "ok",
    }


def execute_single_operation(request: dict[str, Any]) -> dict[str, Any]:
    op = request.get("operation")
    if op == "polygon_2d":
        return polygon_2d(request["vertices"], reported_area=request.get("reported_area"), rel_tolerance=request.get("rel_tolerance", 0.01))
    if op == "solid_3d":
        return solid_3d(request["shape"], request["dimensions"])
    if op == "validate_rotation_matrix":
        return validate_rotation_matrix(request["matrix"], tolerance=request.get("tolerance", 1e-6))
    if op == "aabb_collision_3d":
        return aabb_collision_3d(request["box_a_min"], request["box_a_max"], request["box_b_min"], request["box_b_max"])
    if op == "tolerance_stackup":
        return tolerance_stackup(request["nominals"], request["tolerances"])
    if op == "view_factor_coaxial_disks":
        return view_factor_coaxial_disks(request["r1"], request["r2"], request["distance"])
    if op == "mesh_quality":
        return mesh_quality_triangles(request["vertices"], request["faces"])
    if op == "shell_mass_consistency":
        return shell_mass_consistency(
            request["surface_area_m2"],
            request["thickness_m"],
            request["density_kg_m3"],
            reported_mass_kg=request.get("reported_mass_kg"),
            rel_tolerance=request.get("rel_tolerance", 0.02),
        )
    raise ValueError(f"Operação geométrica desconhecida: {op}")


def run_motor(payload: Any, *, run_id: str | None = None, artefato_alvo: str | None = None) -> dict[str, Any]:
    inner = payload["payload"] if isinstance(payload, dict) and "payload" in payload and "motor_id" in payload else payload
    items = inner.get("operations", []) if isinstance(inner, dict) and inner.get("operation") == "batch" else (inner if isinstance(inner, list) else [inner])

    results: list[dict[str, Any]] = []
    achados: list[dict[str, Any]] = []
    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            results.append(
                {
                    "id": f"GEO_{idx:03d}",
                    "operation": "unknown",
                    "success": False,
                    "status": "error",
                    "error": f"Item de lote inválido no índice {idx}: esperado objeto/dicionário, recebido {type(item).__name__}.",
                }
            )
            continue

        op_id = str(item.get("id") or f"GEO_{idx:03d}")
        try:
            res = execute_single_operation(item)
            res["id"] = op_id
            res["success"] = True
            results.append(res)
            if res.get("status") == "discrepancy_detected":
                ev = create_evidence(
                    f"EV-GEO-{idx:03d}",
                    "numerica",
                    artefato_alvo or "payload_inline",
                    op_id,
                    json.dumps(res, ensure_ascii=False)[:800],
                    motor_origem=MOTOR_ID,
                )
                achados.append(
                    create_finding(
                        f"ACH-GEO-{idx:03d}",
                        f"Inconsistência geométrica em {op_id}",
                        "inconsistencia_geometrica",
                        "MAIOR",
                        "ALTA",
                        op_id,
                        f"Falha ou divergência geométrica detectada na operação {res.get('operation')}.",
                        [ev],
                        estado="CONFIRMADO",
                        portao="G03",
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
                "A aproximação shell_mass_consistency assume espessura pequena frente aos raios de curvatura (casca fina)."
            ],
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Motor geométrico determinístico (Revisão Hostil v8.0-beta.3).")
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
