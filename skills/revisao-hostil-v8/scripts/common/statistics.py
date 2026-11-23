"""Funções estatísticas descritivas base compartilhadas pelo Core v8.0."""

from __future__ import annotations

from typing import Any

import numpy as np

from .validation import require_finite_array


def descriptive_summary(values: Any) -> dict[str, float | int]:
    """Calcula estatísticas descritivas determinísticas sem NaN/Inf silenciosos."""
    arr = require_finite_array(values, name="values", ndim=1)
    n = int(arr.size)
    ddof = 1 if n > 1 else 0
    return {
        "n": n,
        "mean": float(np.mean(arr)),
        "median": float(np.median(arr)),
        "std": float(np.std(arr, ddof=ddof)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "q25": float(np.percentile(arr, 25)),
        "q75": float(np.percentile(arr, 75)),
    }


def relative_change_pct(reference: float, new_value: float) -> float:
    """Calcula variação relativa percentual (new - ref) / |ref| * 100."""
    if reference == 0:
        raise ValueError("Valor de referência não pode ser zero para cálculo de variação percentual.")
    return float((new_value - reference) / abs(reference) * 100.0)
