"""Validações de entrada, sanitização JSON e segurança determinística (Core v8.0)."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np

MAX_EXPRESSION_LENGTH = 4096
MAX_AST_DEPTH = 40
MAX_EXPONENT_ABS = 1000


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


def require_finite_array(data: Any, name: str = "array", ndim: int | None = None) -> np.ndarray:
    """Converte para ndarray float64 validando dimensão, não-vazio e finitude."""
    try:
        arr = np.asarray(data, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"'{name}' não pôde ser convertido para array numérico: {exc}") from exc

    if arr.size == 0:
        raise ValueError(f"'{name}' não pode ser vazio.")
    if ndim is not None and arr.ndim != ndim:
        raise ValueError(f"'{name}' deve ter dimensão {ndim}, recebido ndim={arr.ndim}.")
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
