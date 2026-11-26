"""Validações de entrada, sanitização JSON e segurança determinística (Core v8.0)."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np

MAX_EXPRESSION_LENGTH = 4096
MAX_AST_DEPTH = 40
MAX_AST_NODES = 1500
MAX_EXPONENT_ABS = 1000

# Limites centrais de recursos para o motor matemático e operações de entrada
MAX_JSON_PAYLOAD_BYTES = 10 * 1024 * 1024  # 10 MB para arquivos JSON / payloads de entrada
MAX_BATCH_OPERATIONS = 500  # Máximo de operações em um único lote
MAX_ARRAY_TOTAL_ELEMENTS = 100_000  # Máximo total de elementos em arrays (ex.: 1000x100 ou 1D de 100k)
MAX_MATRIX_DIMENSION = 500  # Dimensão máxima de cada eixo em matrizes 2D (500x500)
MAX_ODE_MESH_POINTS = 5_000  # Máximo de pontos em malhas / t_eval de ODEs
MAX_ODE_SYSTEM_ORDER = 50  # Máximo de equações diferenciais em um sistema ODE (dimensão de y)



def sanitize_for_json(obj: Any) -> Any:
    """Sanitiza recursivamente tipos NumPy e NaN/Inf para serialização JSON estrita."""
    if isinstance(obj, dict):
        return {str(k): sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize_for_json(v) for v in obj]
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        val = float(obj)
        if math.isnan(val):
            return "NaN"
        if math.isinf(val):
            return "Infinity" if val > 0 else "-Infinity"
        return val
    return obj


def require_finite_number(value: Any, name: str = "valor") -> float:
    """Garante que o valor seja numérico real e finito (não bool, não NaN, não Inf)."""
    if isinstance(value, bool) or not isinstance(value, (int, float, np.number)):
        raise ValueError(f"'{name}' deve ser um número real finito, recebido: {type(value).__name__}.")
    num = float(value)
    if not math.isfinite(num):
        raise ValueError(f"'{name}' deve ser finito (não NaN/Inf), recebido: {value}.")
    return num


def require_finite_array(
    data: Any,
    name: str = "array",
    ndim: int | None = None,
    max_total_elements: int = MAX_ARRAY_TOTAL_ELEMENTS,
    max_axis_dimension: int | None = None,
) -> np.ndarray:
    """Converte para ndarray float64 validando dimensão, não-vazio, limites de tamanho e finitude."""
    try:
        arr = np.asarray(data, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"'{name}' não pôde ser convertido para array numérico: {exc}") from exc

    if arr.size == 0:
        raise ValueError(f"'{name}' não pode ser vazio.")
    if ndim is not None and arr.ndim != ndim:
        raise ValueError(f"'{name}' deve ter dimensão {ndim}, recebido ndim={arr.ndim}.")
    if arr.size > max_total_elements:
        raise ValueError(
            f"'{name}' excede o número máximo permitido de elementos ({arr.size} > {max_total_elements})."
        )
    if max_axis_dimension is not None:
        for ax_idx, dim_size in enumerate(arr.shape):
            if dim_size > max_axis_dimension:
                raise ValueError(
                    f"'{name}' excede a dimensão máxima permitida no eixo {ax_idx} ({dim_size} > {max_axis_dimension})."
                )
    if not np.isfinite(arr).all():
        raise ValueError(f"'{name}' contém valores não finitos (NaN ou Inf).")
    return arr



def validate_safe_file_path(path: str | Path, max_bytes: int = 50 * 1024 * 1024) -> Path:
    """Valida existência, tipo de arquivo regular e limite de tamanho."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {p}")
    if not p.is_file():
        raise ValueError(f"Caminho não é um arquivo regular: {p}")
    size = p.stat().st_size
    if size > max_bytes:
        raise ValueError(f"Arquivo excede o limite de {max_bytes} bytes ({size} bytes): {p}")
    return p.resolve()
