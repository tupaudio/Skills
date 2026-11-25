#!/usr/bin/env python3
"""Analise POS-HOC da Rodada 3 (span 10, 5, 3 + variante 1-caso-por-achado).

Fora de frozen_files. NAO altera lock.json, cases.json, thresholds.json ou bench.py.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import bench  # noqa: E402


def _load_mod(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def eval_nearest_single_case(docs, cases, findings, split="validacao", max_span=10):
    """Variante POS-HOC: cada achado conta para no maximo UM caso (menor distancia ao centro)."""
    active = [c for c in cases if c.get("split") == split and c.get("adjudicated") is True]
    ranges = {c["id"]: bench.resolve_case_anchors(docs[c["document"]]["lines"], c) for c in active}
    by_doc = {}
    for c in active:
        by_doc.setdefault(c["document"], []).append(c)
    detected, neg_flagged = set(), set()
    for f in findings:
        did = f["document"]
        if did not in by_doc:
            continue
        ls, le = f.get("line_start"), f.get("line_end") or f.get("line_start")
        if ls is None or (le - ls + 1) > max_span:
            continue
        center = (ls + le) / 2.0
        touched = []
        for c in by_doc[did]:
            for cr in ranges[c["id"]]:
                if bench._overlap((ls, le), cr):
                    dist = abs(center - (cr[0] + cr[1]) / 2.0)
                    touched.append((dist, c["id"], c["type"]))
        if not touched:
            continue
        touched.sort(key=lambda x: (x[0], x[1]))
        _, cid, ctype = touched[0]
        if ctype == "DEFECT":
            detected.add(cid)
        elif ctype == "NEGATIVE_CONTROL":
            neg_flagged.add(cid)
    n_def = sum(1 for c in active if c["type"] == "DEFECT")
    n_neg = sum(1 for c in active if c["type"] == "NEGATIVE_CONTROL")
    return len(detected), n_def, n_neg - len(neg_flagged), n_neg, sorted(detected)


def main():
    mA = _load_mod(r"c:\ZZ - Antigravity\benchmark_privado\score_r3.py", "mA")
    mC = _load_mod(r"c:\ZZ - Antigravity\benchmark_privado\score_r3_armC.py", "mC")
    root, manifest, docs, cases, thr = bench._inputs(ROOT)

    runs = {}
    for mname, by_doc in mA.RAW.items():
        fs = []
        for did, payload in by_doc.items():
            for f in payload["findings"]:
                f2 = dict(f)
                for k in ("claimed_value", "recomputed_value"):
                    if isinstance(f2.get(k), str):
                        f2[k] = None
                fs.append(bench.normalize_finding(f2, did))
        runs[mname + "_A"] = fs
    for mname, by_doc in mC.ARM_C.items():
        fs = []
        for did, items in by_doc.items():
            for ls, le, cat, st in items:
                fs.append(bench.normalize_finding({"line_start": ls, "line_end": le, "category": cat, "status": st}, did))
        runs[mname] = fs

    print("=== POS-HOC SPAN SENSITIVITY (10, 5, 3) ===")
    for sp in (10, 5, 3):
        det_by = {}
        for name, fs in runs.items():
            r = bench.evaluate(docs, cases, fs, "validacao", max_span_lines=sp, recompute_tolerance_rel=thr["recompute_tolerance_rel"])
            t = r["total"]
            det_by[name] = set(r["detected_ids"])
            print(f"span<={sp:2d} | {name:20s} | rec={t['recall']['k']:2d}/{t['recall']['n']} | esp={t['especificidade']['k']:2d}/{t['especificidade']['n']} | drop_sp={r['achados']['nao_localizado_span']}")
        for base, kA, kC in [("DeepSeek", "DeepSeek_rotulado_A", "DeepSeek_ArmC"), ("Copilot", "Copilot_GPT5_A", "Copilot_GPT5_ArmC")]:
            print(f"  span<={sp:2d} DISCORDANT {base}: A_only={sorted(det_by[kA]-det_by[kC])} C_only={sorted(det_by[kC]-det_by[kA])}")

    print("\n=== POS-HOC NEAREST-CENTER SINGLE-CASE (span <= 10) ===")
    for name, fs in runs.items():
        dk, dn, nk, nn, _ = eval_nearest_single_case(docs, cases, fs, "validacao", max_span=10)
        print(f"1-case  | {name:20s} | rec={dk:2d}/{dn} | esp={nk:2d}/{nn}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
