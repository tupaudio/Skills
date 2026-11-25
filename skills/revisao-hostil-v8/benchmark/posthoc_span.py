#!/usr/bin/env python3
"""Analise POS-HOC (somente A04, filtro span <= 5 linhas).

NAO altera lock.json, cases.json, thresholds.json, manifest.json ou
benchmark/results/blind_A04.json. Nao substitui a tabela principal.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "adapters") not in sys.path:
    sys.path.insert(0, str(ROOT / "adapters"))

import bench  # noqa: E402
import achados_arquivo as aa  # noqa: E402
import estrutural_json as ej  # noqa: E402


def filter_findings(findings, doc_id="A04", max_span=5):
    """Filtra achados para um unico documento e span <= max_span.

    Retorna (mantidos, descartados_doc, descartados_span).
    """
    kept, drop_doc, drop_span = [], 0, 0
    for f in findings:
        if f.get("document") != doc_id:
            drop_doc += 1
            continue
        ls = f.get("line_start")
        le = f.get("line_end") if f.get("line_end") is not None else ls
        if ls is not None and le is not None and (le - ls + 1) > max_span:
            drop_span += 1
            continue
        kept.append(f)
    return kept, drop_doc, drop_span


def evaluate_posthoc(docs, cases, raw_findings, split="validacao",
                     doc_id="A04", max_span=5):
    kept, drop_doc, drop_span = filter_findings(raw_findings, doc_id, max_span)
    res = bench.evaluate(docs, cases, kept, split)
    t = res["total"]
    return {
        "recall": t["recall"]["valor"],
        "especificidade": t["especificidade"]["valor"],
        "excesso_confianca_inconclusivos": t["excesso_confianca_inconclusivos"]["valor"],
        "precisao_otimista": res["precisao_otimista"],
        "precisao_pessimista": res["precisao_pessimista"],
        "total_mantidos": len(kept),
        "descartados_doc": drop_doc,
        "descartados_span": drop_span,
        "detected_ids": res["detected_ids"],
        "neg_flagged_ids": res["neg_flagged_ids"],
    }


def _collect_builtin_or_estrutural(docs, fn):
    out = []
    for did, d in docs.items():
        if d["status"] != "OK":
            continue
        try:
            for f in fn(d["path"], did):
                out.append(bench.normalize_finding(f, did))
        except bench.BenchError:
            continue
    return out


def _collect_blind(docs, json_path, doc_id="A04"):
    d = docs[doc_id]
    data = json.loads(Path(json_path).read_text(encoding="utf-8"))
    raw = aa.parse_blind(data, doc_id, d["actual_sha256"], len(d["lines"]))
    return [bench.normalize_finding(f, doc_id) for f in raw]


def run_all(root=ROOT, max_span=5):
    root, manifest, docs, cases, _ = bench._inputs(root)
    results_dir = root / "results"
    rows = []

    sources = [
        ("builtin:nothing", lambda: _collect_builtin_or_estrutural(docs, bench.load_adapter("builtin:nothing", root))),
        ("builtin:every_line", lambda: _collect_builtin_or_estrutural(docs, bench.load_adapter("builtin:every_line", root))),
        ("estrutural_sem_informativos", lambda: _collect_builtin_or_estrutural(docs, ej.estrutural_sem_informativos)),
        ("estrutural", lambda: _collect_builtin_or_estrutural(docs, ej.estrutural)),
        ("Gemini 4 Neon (Low)", lambda: _collect_blind(docs, results_dir / "blind_A04__gemini4_neon_low.json")),
        ("DeepSeek (rotulado)", lambda: _collect_blind(docs, results_dir / "blind_A04__deepseek.json")),
        ("M365 Copilot GPT-5", lambda: _collect_blind(docs, results_dir / "blind_A04__copilot_gpt5.json")),
        ("Gemini 3.1 Pro", lambda: _collect_blind(docs, results_dir / "blind_A04__gemini31_pro.json")),
    ]
    for name, loader in sources:
        raw = loader()
        m = evaluate_posthoc(docs, cases, raw, split="validacao", doc_id="A04", max_span=max_span)
        rows.append((name, m))
    return rows


def main():
    print("POS-HOC (somente A04, span <= 5 linhas; nao substitui tabela principal)")
    for name, m in run_all():
        print(
            f"{name:28s} | rec={m['recall']} | esp={m['especificidade']} "
            f"| inc_ov={m['excesso_confianca_inconclusivos']} "
            f"| p_opt={m['precisao_otimista']} | p_pes={m['precisao_pessimista']} "
            f"| kept={m['total_mantidos']} | drop_doc={m['descartados_doc']} "
            f"| drop_span={m['descartados_span']} | det={m['detected_ids']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
