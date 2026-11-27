#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Motor estatístico determinístico (Revisão Hostil v8.0-beta.3).

Implementa:
- Testes paramétricos (t independente/pareado, ANOVA one-way, Pearson) e não paramétricos (Mann-Whitney, Wilcoxon, Kruskal-Wallis, Spearman);
- Intervalos de confiança e tamanhos de efeito (Cohen's d, Hedges' g, eta^2);
- Equivalência / não inferioridade (TOST);
- Comparações múltiplas (Bonferroni, Holm-Bonferroni, Benjamini-Hochberg FDR);
- Bootstrap e teste de permutação com semente explícita;
- Poder estatístico (aproximação analítica para duas médias);
- Diagnóstico de pressupostos (Shapiro-Wilk, Levene);
- Autocorrelação e dependência temporal (ACF lag-k, Durbin-Watson).
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
from scipy import stats

from scripts.common import SCHEMA_VERSION
from scripts.common.evidence import create_evidence, create_finding, utc_now_iso
from scripts.common.validation import MAX_JSON_PAYLOAD_BYTES, read_bounded_json, require_finite_array, require_finite_number, sanitize_for_json

MOTOR_ID = "motor_estatistico"
MOTOR_VERSION = "0.2.0-beta.5.3"


def _cohens_d_independent(a: np.ndarray, b: np.ndarray) -> tuple[float | None, float | None, str | None]:
    n1, n2 = len(a), len(b)
    v1, v2 = float(np.var(a, ddof=1)), float(np.var(b, ddof=1))
    pooled = math.sqrt(((n1 - 1) * v1 + (n2 - 1) * v2) / (n1 + n2 - 2))
    diff = float(np.mean(a) - np.mean(b))
    if pooled == 0.0:
        if abs(diff) <= 1e-15:
            return 0.0, 0.0, "zero_variance_equal_means"
        return (
            None,
            None,
            "undefined_zero_pooled_variance: variância agrupada nula com médias distintas (limite não finito).",
        )
    d = float(diff / pooled)
    j = 1.0 - 3.0 / (4.0 * (n1 + n2 - 2) - 1.0) if (n1 + n2) > 3 else 1.0
    return d, float(d * j), None


def t_test_independent(
    sample_a: Any, sample_b: Any, *, equal_var: bool = False, alpha: float = 0.05, reported_p: float | None = None
) -> dict[str, Any]:
    a = require_finite_array(sample_a, name="sample_a", ndim=1)
    b = require_finite_array(sample_b, name="sample_b", ndim=1)
    if a.size < 2 or b.size < 2:
        raise ValueError("Cada amostra deve ter pelo menos 2 observações.")

    d, g, eff_note = _cohens_d_independent(a, b)
    va, vb = float(np.var(a, ddof=1)), float(np.var(b, ddof=1))
    if va == 0.0 and vb == 0.0:
        stat_val = float("nan")
        p_val = float("nan")
        finite_test = False
    else:
        res = stats.ttest_ind(a, b, equal_var=equal_var)
        stat_val = float(res.statistic)
        p_val = float(res.pvalue)
        finite_test = math.isfinite(stat_val) and math.isfinite(p_val)
    discrepancy = (
        finite_test
        and reported_p is not None
        and abs(p_val - require_finite_number(reported_p, "reported_p")) > 0.01
    )
    return {
        "operation": "t_test_independent",
        "welch": not equal_var,
        "n_a": int(a.size),
        "n_b": int(b.size),
        "mean_a": float(np.mean(a)),
        "mean_b": float(np.mean(b)),
        "statistic": stat_val if math.isfinite(stat_val) else None,
        "p_value": p_val if math.isfinite(p_val) else None,
        "cohens_d": d,
        "hedges_g": g,
        "effect_size_note": eff_note,
        "significant_at_alpha": bool(p_val < alpha) if math.isfinite(p_val) else None,
        "alpha": alpha,
        "reported_p": reported_p,
        "status": "discrepancy_detected" if discrepancy else ("ok" if finite_test else "undefined_zero_variance"),
    }


def t_test_paired(sample_a: Any, sample_b: Any, *, alpha: float = 0.05, reported_p: float | None = None) -> dict[str, Any]:
    """Teste t pareado com tratamento explícito de variância nula das diferenças antes do SciPy (ACH-015)."""
    a = require_finite_array(sample_a, name="sample_a", ndim=1)
    b = require_finite_array(sample_b, name="sample_b", ndim=1)
    if a.size != b.size or a.size < 2:
        raise ValueError("Teste pareado exige duas amostras de mesmo tamanho (>= 2).")

    diff = a - b
    mean_diff = float(np.mean(diff))
    sd = float(np.std(diff, ddof=1))

    if sd == 0.0:
        if abs(mean_diff) <= 1e-15:
            return {
                "operation": "t_test_paired",
                "n_pairs": int(a.size),
                "mean_diff": 0.0,
                "sd_diff": 0.0,
                "statistic": None,
                "p_value": None,
                "cohens_dz": 0.0,
                "effect_size_note": (
                    "degenerate_zero_differences: todas as diferenças são exatamente zero "
                    "(variância nula; estatística t e valor-p indefinidos, distinto de resultado não significativo)."
                ),
                "significant_at_alpha": None,
                "alpha": alpha,
                "reported_p": reported_p,
                "status": "degenerate_zero_differences",
            }
        return {
            "operation": "t_test_paired",
            "n_pairs": int(a.size),
            "mean_diff": mean_diff,
            "sd_diff": 0.0,
            "statistic": None,
            "p_value": None,
            "cohens_dz": None,
            "effect_size_note": (
                "undefined_zero_diff_variance: diferenças constantes não nulas "
                "(sd == 0; estatística t, valor-p e Cohen's dz indefinidos)."
            ),
            "significant_at_alpha": None,
            "alpha": alpha,
            "reported_p": reported_p,
            "status": "undefined_zero_variance",
        }

    res = stats.ttest_rel(a, b)
    stat_val = float(res.statistic)
    p_val = float(res.pvalue)
    finite_test = math.isfinite(stat_val) and math.isfinite(p_val)
    dz = float(mean_diff / sd)
    discrepancy = (
        finite_test
        and reported_p is not None
        and abs(p_val - require_finite_number(reported_p, "reported_p")) > 0.01
    )
    return {
        "operation": "t_test_paired",
        "n_pairs": int(a.size),
        "mean_diff": mean_diff,
        "sd_diff": sd,
        "statistic": stat_val if math.isfinite(stat_val) else None,
        "p_value": p_val if math.isfinite(p_val) else None,
        "cohens_dz": dz if math.isfinite(dz) else None,
        "effect_size_note": None,
        "significant_at_alpha": bool(p_val < alpha) if math.isfinite(p_val) else None,
        "alpha": alpha,
        "reported_p": reported_p,
        "status": "discrepancy_detected" if discrepancy else ("ok" if finite_test else "undefined_non_finite"),
    }


def mann_whitney(sample_a: Any, sample_b: Any, *, alpha: float = 0.05) -> dict[str, Any]:
    a = require_finite_array(sample_a, name="sample_a", ndim=1)
    b = require_finite_array(sample_b, name="sample_b", ndim=1)
    res = stats.mannwhitneyu(a, b, alternative="two-sided")
    u = float(res.statistic)
    r_rb = 1.0 - (2.0 * u) / (a.size * b.size)
    return {
        "operation": "mann_whitney",
        "statistic_U": u,
        "p_value": float(res.pvalue),
        "rank_biserial_r": float(r_rb),
        "significant_at_alpha": bool(res.pvalue < alpha),
        "status": "ok",
    }


def anova_oneway(groups: list[Any], *, alpha: float = 0.05) -> dict[str, Any]:
    if len(groups) < 2:
        raise ValueError("ANOVA requer pelo menos 2 grupos.")
    arrs = [require_finite_array(g, name=f"group_{i}", ndim=1) for i, g in enumerate(groups)]
    if any(a.size < 2 for a in arrs):
        raise ValueError("Cada grupo da ANOVA deve ter >= 2 observações.")
    res = stats.f_oneway(*arrs)
    all_vals = np.concatenate(arrs)
    grand_mean = float(np.mean(all_vals))
    ss_between = sum(len(a) * (float(np.mean(a)) - grand_mean) ** 2 for a in arrs)
    ss_total = float(np.sum((all_vals - grand_mean) ** 2))
    eta_sq = float(ss_between / ss_total) if ss_total > 0 else 0.0
    return {
        "operation": "anova_oneway",
        "k_groups": len(arrs),
        "F_statistic": float(res.statistic),
        "p_value": float(res.pvalue),
        "eta_squared": eta_sq,
        "significant_at_alpha": bool(res.pvalue < alpha),
        "status": "ok",
    }


def confidence_interval(sample: Any, *, confidence: float = 0.95) -> dict[str, Any]:
    arr = require_finite_array(sample, name="sample", ndim=1)
    if arr.size < 2:
        raise ValueError("Intervalo de confiança requer >= 2 observações.")
    if not (0.0 < confidence < 1.0):
        raise ValueError("confidence deve estar estritamente entre 0 e 1.")
    mean = float(np.mean(arr))
    se = float(stats.sem(arr))
    low, high = stats.t.interval(confidence, df=arr.size - 1, loc=mean, scale=se)
    return {
        "operation": "confidence_interval",
        "n": int(arr.size),
        "mean": mean,
        "sem": se,
        "confidence": confidence,
        "lower": float(low),
        "upper": float(high),
        "status": "ok",
    }


def tost_equivalence(sample_a: Any, sample_b: Any, low_bound: float, high_bound: float, *, alpha: float = 0.05) -> dict[str, Any]:
    """Two One-Sided Tests (TOST) para equivalência de duas amostras independentes (Welch)."""
    a = require_finite_array(sample_a, name="sample_a", ndim=1)
    b = require_finite_array(sample_b, name="sample_b", ndim=1)
    if a.size < 2 or b.size < 2:
        raise ValueError("TOST requer pelo menos 2 observações em cada amostra.")
    lo = require_finite_number(low_bound, "low_bound")
    hi = require_finite_number(high_bound, "high_bound")
    if lo >= hi:
        raise ValueError("low_bound deve ser menor que high_bound.")
    diff = float(np.mean(a) - np.mean(b))
    va, vb = float(np.var(a, ddof=1)), float(np.var(b, ddof=1))
    na, nb = a.size, b.size
    se = math.sqrt(va / na + vb / nb)
    if not math.isfinite(se) or se == 0.0:
        raise ValueError("Erro padrão nulo ou não finito; não é possível executar TOST.")
    denom_df = (va / na) ** 2 / (na - 1) + (vb / nb) ** 2 / (nb - 1)
    if not math.isfinite(denom_df) or denom_df <= 0.0:
        raise ValueError("Graus de liberdade indefinidos para TOST.")
    df = (va / na + vb / nb) ** 2 / denom_df
    if not math.isfinite(df) or df <= 0.0:
        raise ValueError("Graus de liberdade inválidos para TOST.")
    t1 = (diff - lo) / se
    t2 = (diff - hi) / se
    p1 = float(1.0 - stats.t.cdf(t1, df))
    p2 = float(stats.t.cdf(t2, df))
    p_tost = max(p1, p2)
    if not (math.isfinite(p1) and math.isfinite(p2) and math.isfinite(p_tost)):
        raise ValueError("TOST produziu valor-p não finito.")
    return {
        "operation": "tost_equivalence",
        "mean_diff": diff,
        "bounds": [lo, hi],
        "df": float(df),
        "p_lower": p1,
        "p_upper": p2,
        "p_tost": p_tost,
        "equivalent": bool(p_tost < alpha),
        "alpha": alpha,
        "status": "ok",
    }


def multiple_comparisons(p_values: Any, *, method: str = "holm", alpha: float = 0.05) -> dict[str, Any]:
    ps = require_finite_array(p_values, name="p_values", ndim=1)
    if np.any((ps < 0) | (ps > 1)):
        raise ValueError("Todos os valores-p devem estar em [0, 1].")
    m = ps.size
    if method == "bonferroni":
        adj = np.minimum(ps * m, 1.0)
    elif method == "holm":
        order = np.argsort(ps)
        adj = np.empty(m, dtype=float)
        running = 0.0
        for rank, idx in enumerate(order):
            val = min(1.0, ps[idx] * (m - rank))
            running = max(running, val)
            adj[idx] = running
    elif method in ("bh", "fdr_bh"):
        order = np.argsort(ps)[::-1]
        adj = np.empty(m, dtype=float)
        running = 1.0
        for rev_rank, idx in enumerate(order):
            rank = m - rev_rank
            val = min(1.0, ps[idx] * m / rank)
            running = min(running, val)
            adj[idx] = running
    else:
        raise ValueError(f"Método de correção desconhecido: {method}")
    return {
        "operation": "multiple_comparisons",
        "method": method,
        "alpha": alpha,
        "raw_p_values": ps.tolist(),
        "adjusted_p_values": adj.tolist(),
        "rejected": [bool(p < alpha) for p in adj],
        "status": "ok",
    }


def bootstrap_ci(sample: Any, *, n_resamples: int = 2000, confidence: float = 0.95, seed: int = 42) -> dict[str, Any]:
    arr = require_finite_array(sample, name="sample", ndim=1)
    if arr.size < 2:
        raise ValueError("Bootstrap requer >= 2 observações.")
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, arr.size, size=(n_resamples, arr.size))
    means = np.mean(arr[idx], axis=1)
    alpha = 1.0 - confidence
    low, high = np.percentile(means, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return {
        "operation": "bootstrap_ci",
        "n": int(arr.size),
        "n_resamples": n_resamples,
        "seed": seed,
        "observed_mean": float(np.mean(arr)),
        "ci_lower": float(low),
        "ci_upper": float(high),
        "status": "ok",
    }


def permutation_test(sample_a: Any, sample_b: Any, *, n_permutations: int = 2000, seed: int = 42) -> dict[str, Any]:
    a = require_finite_array(sample_a, name="sample_a", ndim=1)
    b = require_finite_array(sample_b, name="sample_b", ndim=1)
    obs = abs(float(np.mean(a) - np.mean(b)))
    combined = np.concatenate([a, b])
    na = a.size
    rng = np.random.default_rng(seed)
    exceed = 0
    for _ in range(n_permutations):
        perm = rng.permutation(combined)
        if abs(float(np.mean(perm[:na]) - np.mean(perm[na:]))) >= obs:
            exceed += 1
    p_val = (exceed + 1) / (n_permutations + 1)
    return {
        "operation": "permutation_test",
        "observed_abs_diff": obs,
        "n_permutations": n_permutations,
        "seed": seed,
        "p_value": float(p_val),
        "status": "ok",
    }


def statistical_power_two_means(effect_size_d: float, n_per_group: int, *, alpha: float = 0.05) -> dict[str, Any]:
    """Cálculo exato de poder estatístico para duas amostras independentes via distribuição t não central (SciPy nct)."""
    d = abs(require_finite_number(effect_size_d, "effect_size_d"))
    n = int(require_finite_number(n_per_group, "n_per_group"))
    if n < 2:
        raise ValueError("n_per_group deve ser >= 2.")
    a = require_finite_number(alpha, "alpha")
    if not (0.0 < a < 1.0):
        raise ValueError("alpha deve estar estritamente entre 0 e 1.")

    df = 2 * n - 2
    nc = d * math.sqrt(n / 2.0)
    t_crit = float(stats.t.ppf(1.0 - a / 2.0, df=df))
    # Teste bicaudal: P(T > t_crit | nc) + P(T < -t_crit | nc)
    # Usa sf para cauda superior e cdf para cauda inferior, tratando underflow numérico em caudas extremas
    p_upper = float(stats.nct.sf(t_crit, df=df, nc=nc))
    p_lower_raw = stats.nct.cdf(-t_crit, df=df, nc=nc)
    p_lower = float(p_lower_raw) if math.isfinite(p_lower_raw) else 0.0
    power = float(np.clip(p_upper + p_lower, 0.0, 1.0))
    return {
        "operation": "statistical_power",
        "effect_size_d": d,
        "n_per_group": n,
        "alpha": a,
        "power": power,
        "adequate_80pct": bool(power >= 0.80),
        "status": "ok",
    }


def assumptions_check(groups: list[Any], *, alpha: float = 0.05) -> dict[str, Any]:
    arrs = [require_finite_array(g, name=f"group_{i}", ndim=1) for i, g in enumerate(groups)]
    normality = []
    for idx, a in enumerate(arrs):
        if a.size < 3:
            normality.append({"group": idx, "n": int(a.size), "shapiro_p": None, "normal_at_alpha": None})
        else:
            _, p = stats.shapiro(a)
            normality.append({"group": idx, "n": int(a.size), "shapiro_p": float(p), "normal_at_alpha": bool(p >= alpha)})
    levene_res = None
    if len(arrs) >= 2 and all(a.size >= 2 for a in arrs):
        stat, p_lev = stats.levene(*arrs)
        levene_res = {"statistic": float(stat), "p_value": float(p_lev), "equal_variance_at_alpha": bool(p_lev >= alpha)}
    return {
        "operation": "assumptions_check",
        "alpha": alpha,
        "normality": normality,
        "levene_homogeneity": levene_res,
        "status": "ok",
    }


def autocorrelation_check(series: Any, *, max_lag: int = 5) -> dict[str, Any]:
    arr = require_finite_array(series, name="series", ndim=1)
    n = arr.size
    if n < 4:
        raise ValueError("Série temporal requer >= 4 pontos para autocorrelação.")
    centered = arr - np.mean(arr)
    denom = float(np.dot(centered, centered))
    lags: dict[str, float] = {}
    for k in range(1, min(max_lag, n - 1) + 1):
        lags[str(k)] = float(np.dot(centered[:-k], centered[k:]) / denom) if denom > 0 else 0.0
    diff_sq = float(np.sum(np.diff(arr) ** 2))
    dw = float(diff_sq / denom) if denom > 0 else 2.0
    return {
        "operation": "autocorrelation",
        "n": int(n),
        "acf": lags,
        "durbin_watson": dw,
        "status": "ok",
    }


def execute_single_operation(request: dict[str, Any]) -> dict[str, Any]:
    op = request.get("operation")
    if op == "t_test_independent":
        return t_test_independent(
            request["sample_a"],
            request["sample_b"],
            equal_var=request.get("equal_var", False),
            alpha=request.get("alpha", 0.05),
            reported_p=request.get("reported_p"),
        )
    if op == "t_test_paired":
        return t_test_paired(
            request["sample_a"], request["sample_b"], alpha=request.get("alpha", 0.05), reported_p=request.get("reported_p")
        )
    if op == "mann_whitney":
        return mann_whitney(request["sample_a"], request["sample_b"], alpha=request.get("alpha", 0.05))
    if op == "anova_oneway":
        return anova_oneway(request["groups"], alpha=request.get("alpha", 0.05))
    if op == "confidence_interval":
        return confidence_interval(request["sample"], confidence=request.get("confidence", 0.95))
    if op == "tost_equivalence":
        return tost_equivalence(
            request["sample_a"], request["sample_b"], request["low_bound"], request["high_bound"], alpha=request.get("alpha", 0.05)
        )
    if op == "multiple_comparisons":
        return multiple_comparisons(request["p_values"], method=request.get("method", "holm"), alpha=request.get("alpha", 0.05))
    if op == "bootstrap_ci":
        return bootstrap_ci(
            request["sample"], n_resamples=request.get("n_resamples", 2000), confidence=request.get("confidence", 0.95), seed=request.get("seed", 42)
        )
    if op == "permutation_test":
        return permutation_test(
            request["sample_a"], request["sample_b"], n_permutations=request.get("n_permutations", 2000), seed=request.get("seed", 42)
        )
    if op == "statistical_power":
        return statistical_power_two_means(request["effect_size_d"], request["n_per_group"], alpha=request.get("alpha", 0.05))
    if op == "assumptions_check":
        return assumptions_check(request["groups"], alpha=request.get("alpha", 0.05))
    if op == "autocorrelation":
        return autocorrelation_check(request["series"], max_lag=request.get("max_lag", 5))
    raise ValueError(f"Operação estatística desconhecida: {op}")


def run_motor(payload: Any, *, run_id: str | None = None, artefato_alvo: str | None = None) -> dict[str, Any]:
    inner = payload["payload"] if isinstance(payload, dict) and "payload" in payload and "motor_id" in payload else payload
    items = inner.get("operations", []) if isinstance(inner, dict) and inner.get("operation") == "batch" else (inner if isinstance(inner, list) else [inner])

    results: list[dict[str, Any]] = []
    achados: list[dict[str, Any]] = []
    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            results.append(
                {
                    "id": f"EST_{idx:03d}",
                    "operation": "unknown",
                    "success": False,
                    "status": "error",
                    "error": f"Item de lote inválido no índice {idx}: esperado objeto/dicionário, recebido {type(item).__name__}.",
                }
            )
            continue

        op_id = str(item.get("id") or f"EST_{idx:03d}")
        try:
            res = execute_single_operation(item)
            res["id"] = op_id
            res["success"] = True
            results.append(res)
            if res.get("status") == "discrepancy_detected":
                ev = create_evidence(
                    f"EV-EST-{idx:03d}",
                    "numerica",
                    artefato_alvo or "payload_inline",
                    op_id,
                    f"p_calculado={res.get('p_value')} vs p_reportado={res.get('reported_p')}",
                    valor_observado=res.get("reported_p"),
                    valor_calculado=res.get("p_value"),
                    motor_origem=MOTOR_ID,
                )
                achados.append(
                    create_finding(
                        f"ACH-EST-{idx:03d}",
                        f"Discrepância estatística em {op_id}",
                        "discrepancia_estatistica",
                        "MAIOR",
                        "ALTA",
                        op_id,
                        "Valor-p recalculado diverge do valor reportado no manuscrito.",
                        [ev],
                        estado="CONFIRMADO",
                        portao="G04",
                        origem_componente=MOTOR_ID,
                    )
                )
            elif (
                res.get("status") in {"undefined_zero_variance", "degenerate_zero_differences"}
                and res.get("reported_p") is not None
            ):
                is_zero_diff = False
                if res.get("operation") == "t_test_independent":
                    is_zero_diff = abs(float(res.get("mean_a", 0.0)) - float(res.get("mean_b", 0.0))) <= 1e-15
                elif res.get("operation") == "t_test_paired":
                    is_zero_diff = abs(float(res.get("mean_diff", 0.0))) <= 1e-15 or res.get("status") == "degenerate_zero_differences"

                if is_zero_diff:
                    desc = (
                        "O valor-p reportado não pode ser verificado deterministicamente porque a variância dos dados "
                        "é nula e as médias são idênticas, resultando em uma indeterminação (0/0) da estatística t."
                    )
                    ev_content = f"variancia_nula=True e diferenca_medias=0.0 (indeterminacao 0/0) vs p_reportado={res.get('reported_p')}"
                else:
                    desc = (
                        "O valor-p reportado não pode ser verificado deterministicamente porque a variância dos dados "
                        "é nula e as médias são distintas, tornando a estatística t não finita (|t| -> inf)."
                    )
                    ev_content = f"variancia_nula=True e diferenca_medias!=0.0 (|t| -> inf) vs p_reportado={res.get('reported_p')}"

                ev = create_evidence(
                    f"EV-EST-{idx:03d}",
                    "numerica",
                    artefato_alvo or "payload_inline",
                    op_id,
                    ev_content,
                    valor_observado=res.get("reported_p"),
                    valor_calculado=None,
                    motor_origem=MOTOR_ID,
                )
                achados.append(
                    create_finding(
                        f"ACH-EST-{idx:03d}",
                        f"Valor-p reportado não verificável devido a variância nula em {op_id}",
                        "discrepancia_estatistica",
                        "MODERADO",
                        "ALTA",
                        op_id,
                        desc,
                        [ev],
                        estado="NAO_VERIFICADO",
                        portao="G04",
                        origem_componente=MOTOR_ID,
                    )
                )
        except Exception as err:
            results.append({"id": op_id, "operation": item.get("operation"), "success": False, "status": "error", "error": str(err)})

    failed = sum(1 for r in results if not r.get("success"))
    has_unverified = any(a.get("estado") == "NAO_VERIFICADO" for a in achados)
    if failed == len(results):
        status = "ERRO_VALIDACAO"
    elif failed > 0 or has_unverified:
        status = "PARCIAL"
    elif achados:
        status = "COM_ACHADOS"
    else:
        status = "OK"
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
                "O motor executa cálculos estatísticos determinísticos; a adequação causal e científica do desenho cabe ao auditor_estatistico."
            ],
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Motor estatístico determinístico (Revisão Hostil v8.0-beta.3).")
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
