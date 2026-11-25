#!/usr/bin/env python3
"""Benchmark da Revisao Hostil V8 (Etapa 2). Somente biblioteca padrao.

Comandos: validate | lock | run
Nao usa assert: validacoes levantam BenchError (igual sob python -O).
Exit codes: 0=PASS  1=FAIL  2=BLOCKED/erro  3=NOT_VERIFIED
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import platform
import re
import subprocess
import sys
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

BENCH_VERSION = "0.1.0"
TYPES = ("DEFECT", "NEGATIVE_CONTROL", "INCONCLUSIVE")
SPLITS = ("calibracao", "validacao")
DOMAINS = ("cientifico", "proveniencia")
STATUS = ("CONFIRMADO", "TRIAGEM", "NAO_VERIFICADO")
THRESHOLD_KEYS = (
    "min_defects",
    "min_negatives",
    "recall_lower_bound_min",
    "specificity_lower_bound_min",
    "precision_pessimistic_min",
)


class BenchError(Exception):
    pass


def need(cond, msg):
    if not cond:
        raise BenchError(msg)


# ---------------------------------------------------------------- utilidades
def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def git_info(root):
    try:
        commit = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout.strip()
        dirty = bool(subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout.strip())
        return {"commit": commit, "dirty": dirty}
    except Exception:
        return {"commit": None, "dirty": None}


# ------------------------------------------------------------------ entradas
def load_docs(root: Path, manifest: dict) -> dict:
    docs = {}
    for did, d in manifest["documents"].items():
        p = (root / d["path"]).resolve()
        try:
            p.relative_to(root)
        except ValueError:
            raise BenchError(f"{did}: caminho fora do diretorio do benchmark")
        entry = {"path": p, "kind": d.get("kind"), "origin": d.get("origin"),
                 "registered_sha256": d.get("sha256"), "actual_sha256": None,
                 "lines": [], "status": "OK"}
        if not p.is_file():
            entry["status"] = "AUSENTE"
        else:
            entry["actual_sha256"] = sha256_file(p)
            if not d.get("sha256") or d["sha256"] == "PREENCHER":
                entry["status"] = "SEM_HASH_REGISTRADO"
            elif entry["actual_sha256"] != d["sha256"]:
                entry["status"] = "HASH_DIVERGENTE"
            try:
                entry["lines"] = p.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError:
                entry["status"] = "ENCODING_INVALIDO"
        docs[did] = entry
    return docs


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().casefold()


def locate(lines, quote, max_span=8):
    """Devolve lista de (inicio, fim) 1-based onde a citacao ocorre."""
    nq = _norm(quote)
    need(nq, "citacao vazia")
    hits = []
    for i in range(len(lines)):
        if not lines[i].strip():
            continue
        first = len(_norm(lines[i]))
        acc = lines[i]
        for j in range(i, min(i + max_span, len(lines))):
            if j > i:
                acc = acc + " " + lines[j]
            n = _norm(acc)
            pos = n.find(nq)
            if pos != -1 and pos <= first:
                hits.append((i + 1, j + 1))
                break
    return hits


def _overlap(a, b):
    return a[0] <= b[1] and b[0] <= a[1]


def resolve_anchor(lines, anchor):
    need(isinstance(anchor, dict) and anchor, "ancora ausente")
    quote = anchor.get("quote")
    ls = anchor.get("line_start")
    hits = locate(lines, quote) if quote else []
    if ls is not None:
        le = anchor.get("line_end") or ls
        need(isinstance(ls, int) and isinstance(le, int) and 1 <= ls <= le <= len(lines),
             "line_start/line_end fora do documento")
        if quote:
            need(any(_overlap(h, (ls, le)) for h in hits),
                 "citacao nao encontrada no intervalo de linhas informado")
        lsha = anchor.get("line_sha256")
        if lsha:
            actual = sha256_bytes("\n".join(lines[ls - 1:le]).encode("utf-8"))
            need(actual == str(lsha).lower(),
                 f"line_sha256 divergente nas linhas {ls}-{le}")
        return (ls, le)
    need(quote, "ancora sem quote nem line_start")
    need(len(hits) >= 1, "citacao nao encontrada no documento")
    need(len(hits) == 1, f"citacao ambigua ({len(hits)} ocorrencias): informe line_start")
    return hits[0]


def finding_range(lines, f):
    ls = f.get("line_start")
    if ls is not None:
        if ls > len(lines):
            return None
        le = f.get("line_end") or ls
        return (ls, min(max(le, ls), len(lines)))
    if f.get("excerpt"):
        hits = locate(lines, str(f["excerpt"]))
        if hits:
            return hits[0]
    return None


def normalize_finding(f, did):
    need(isinstance(f, dict), "adapter devolveu item que nao e dict")
    st = f.get("status")
    need(st in STATUS, f"status de achado invalido: {st!r}")
    out = {"document": did, "status": st,
           "category": str(f.get("category") or "sem_categoria"),
           "excerpt": f.get("excerpt")}
    for k in ("line_start", "line_end"):
        v = f.get(k)
        need(v is None or (isinstance(v, int) and not isinstance(v, bool) and v >= 1),
             f"{k} invalido")
        out[k] = v
    return out


def validate(docs, cases):
    problems, warnings, seen = [], [], set()
    for c in cases:
        cid = c.get("id", "<sem id>")
        if cid in seen:
            problems.append(f"{cid}: id duplicado")
        seen.add(cid)
        if c.get("document") not in docs:
            problems.append(f"{cid}: documento desconhecido")
            continue
        for key, allowed in (("type", TYPES), ("split", SPLITS), ("domain", DOMAINS)):
            if c.get(key) not in allowed:
                problems.append(f"{cid}: {key} invalido ({c.get(key)!r})")
        if not c.get("category"):
            problems.append(f"{cid}: category ausente")
        if not isinstance(c.get("adjudicated"), bool):
            problems.append(f"{cid}: adjudicated deve ser true/false")
        if c.get("adjudicated") is True and not (c.get("validated_by") and c.get("evidence")):
            problems.append(f"{cid}: adjudicado sem validated_by/evidence")
        db = c.get("detectable_by")
        if db is not None:
            if c.get("type") != "DEFECT":
                problems.append(f"{cid}: detectable_by so se aplica a DEFECT")
            elif not (isinstance(db, list)
                      and all(isinstance(x, str) and x.strip() for x in db)):
                problems.append(f"{cid}: detectable_by deve ser lista de categorias")
        d = docs[c["document"]]
        if d["status"] != "OK":
            warnings.append(f"{cid}: documento {d['status']} - ancora NOT_VERIFIED")
            continue
        try:
            resolve_anchor(d["lines"], c.get("anchor"))
        except BenchError as e:
            problems.append(f"{cid}: {e}")
    return problems, warnings


# ------------------------------------------------------------------ metricas
def wilson(k, n, z=1.96):
    if n == 0:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    a = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - a) / d, (c + a) / d)


def _ratio(k, n):
    if n == 0:
        return {"valor": None, "k": 0, "n": 0, "ic95": [None, None]}
    lo, hi = wilson(k, n)
    return {"valor": k / n, "k": k, "n": n, "ic95": [lo, hi]}


def _safe(a, b):
    return None if b == 0 else a / b


def _fmt(v):
    return {
        "recall": _ratio(v["detected"], v["defects"]),
        "recall_categoria": _ratio(v["cat_detected"], v["cat_defects"]),
        "especificidade": _ratio(v["negs"] - v["negs_flagged"], v["negs"]),
        "excesso_confianca_inconclusivos": _ratio(v["incs_over"], v["incs"]),
    }


def _group(active, detected, neg_flagged, over, keyfn, detected_cat=None):
    detected_cat = detected_cat if detected_cat is not None else {}
    zero = lambda: dict(defects=0, detected=0, cat_defects=0, cat_detected=0,
                        negs=0, negs_flagged=0, incs=0, incs_over=0)
    g = defaultdict(zero)
    for c in active:
        v = g[keyfn(c)]
        if c["type"] == "DEFECT":
            v["defects"] += 1
            v["detected"] += 1 if c["id"] in detected else 0
            if c.get("detectable_by"):
                v["cat_defects"] += 1
                v["cat_detected"] += 1 if c["id"] in detected_cat else 0
        elif c["type"] == "NEGATIVE_CONTROL":
            v["negs"] += 1
            v["negs_flagged"] += 1 if c["id"] in neg_flagged else 0
        else:
            v["incs"] += 1
            v["incs_over"] += 1 if c["id"] in over else 0
    return {k: _fmt(v) for k, v in g.items()}, _fmt(zero())


def evaluate(docs, cases, findings, split):
    need(split in SPLITS, "split invalido")
    ranges, excluded, active = {}, [], []
    for c in cases:
        d = docs[c["document"]]
        if d["status"] != "OK":
            excluded.append({"id": c["id"], "motivo": "documento " + d["status"]})
            continue
        ranges[c["id"]] = resolve_anchor(d["lines"], c["anchor"])
        if c.get("adjudicated") is not True:
            excluded.append({"id": c["id"], "motivo": "nao adjudicado"})
            continue
        if c["split"] == split:
            active.append(c)
    active_ids = {c["id"] for c in active}
    by_doc = defaultdict(list)
    for c in cases:
        if c["id"] in ranges:
            by_doc[c["document"]].append(c)

    detected, neg_flagged, over = defaultdict(list), defaultdict(list), defaultdict(list)
    detected_cat = defaultdict(list)
    tp, fp, ov_set, unadj, unloc, ign, handled, blocked = (set() for _ in range(8))
    for k, f in enumerate(findings):
        d = docs.get(f["document"])
        if d is None or d["status"] != "OK":
            blocked.add(k)
            continue
        r = finding_range(d["lines"], f)
        if r is None:
            unloc.add(k)
            continue
        ov = [c for c in by_doc[f["document"]] if _overlap(r, ranges[c["id"]])]
        scoped = [c for c in ov if c["id"] in active_ids]
        if ov and not scoped:
            ign.add(k)
            continue
        defects = [c for c in scoped if c["type"] == "DEFECT"]
        negs = [c for c in scoped if c["type"] == "NEGATIVE_CONTROL"]
        incs = [c for c in scoped if c["type"] == "INCONCLUSIVE"]
        if defects:
            tp.add(k)
            for c in defects:
                detected[c["id"]].append(k)
                if f["category"] in (c.get("detectable_by") or ()):
                    detected_cat[c["id"]].append(k)
        elif negs:
            fp.add(k)
            for c in negs:
                neg_flagged[c["id"]].append(k)
        elif incs:
            if f["status"] == "CONFIRMADO":
                ov_set.add(k)
                for c in incs:
                    over[c["id"]].append(k)
            else:
                handled.add(k)
        else:
            unadj.add(k)

    por_cat, _ = _group(active, detected, neg_flagged, over, lambda c: c["category"], detected_cat)
    por_dom, _ = _group(active, detected, neg_flagged, over, lambda c: c["domain"], detected_cat)
    tot, empty = _group(active, detected, neg_flagged, over, lambda c: "TOTAL", detected_cat)
    total = tot.get("TOTAL", empty)

    n_tp, n_fp, n_ov, n_un = len(tp), len(fp), len(ov_set), len(unadj)
    prec_opt = _safe(n_tp, n_tp + n_fp + n_ov)
    prec_pes = _safe(n_tp, n_tp + n_fp + n_ov + n_un)
    rec = total["recall"]["valor"]
    f1 = None
    if prec_pes is not None and rec is not None and (prec_pes + rec) > 0:
        f1 = 2 * prec_pes * rec / (prec_pes + rec)
    return {
        "split": split,
        "total": total,
        "por_categoria": por_cat,
        "por_dominio": por_dom,
        "achados": {
            "total": len(findings),
            "em_defeito_conhecido": n_tp,
            "em_controle_negativo": n_fp,
            "confirmado_em_inconclusivo": n_ov,
            "inconclusivo_tratado": len(handled),
            "sem_rotulo": n_un,
            "nao_localizaveis": len(unloc),
            "fora_do_escopo_da_execucao": len(ign),
            "em_documento_bloqueado": len(blocked),
        },
        "precisao_otimista": prec_opt,
        "precisao_pessimista": prec_pes,
        "f1_pessimista": f1,
        "excluidos": excluded,
        "active_ids": sorted(active_ids),
        "detected_ids": sorted(detected),
        "detected_cat_ids": sorted(detected_cat),
        "neg_flagged_ids": sorted(neg_flagged),
    }


def stability(runs):
    if len(runs) < 2:
        return None
    ids = set(runs[0]["active_ids"])
    if not ids:
        return None
    stable = 0
    for cid in ids:
        flags = {(cid in r["detected_ids"], cid in r["neg_flagged_ids"]) for r in runs}
        stable += 1 if len(flags) == 1 else 0
    return {"estaveis": stable, "total": len(ids), "fracao": stable / len(ids)}


def gate(res, thr):
    missing = [k for k in THRESHOLD_KEYS if thr.get(k) is None]
    if missing:
        return "NOT_VERIFIED", [f"limiar nao definido: {k}" for k in missing]
    t = res["total"]
    reasons = []
    if t["recall"]["n"] < thr["min_defects"]:
        reasons.append(f"defeitos adjudicados insuficientes ({t['recall']['n']} < {thr['min_defects']})")
    if t["especificidade"]["n"] < thr["min_negatives"]:
        reasons.append(f"controles negativos insuficientes ({t['especificidade']['n']} < {thr['min_negatives']})")
    if reasons:
        return "NOT_VERIFIED", reasons
    fails = []
    if t["recall"]["ic95"][0] < thr["recall_lower_bound_min"]:
        fails.append("limite inferior do recall abaixo do minimo")
    if t["especificidade"]["ic95"][0] < thr["specificity_lower_bound_min"]:
        fails.append("limite inferior da especificidade abaixo do minimo")
    pp = res["precisao_pessimista"]
    if pp is None or pp < thr["precision_pessimistic_min"]:
        fails.append("precisao pessimista abaixo do minimo")
    return ("FAIL", fails) if fails else ("PASS", [])


# ------------------------------------------------------------------- adapters
def _builtin_nothing(path, did):
    return []


def _builtin_every_line(path, did):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [{"line_start": i, "line_end": i, "excerpt": l, "category": "baseline",
             "status": "TRIAGEM"} for i, l in enumerate(lines, 1) if l.strip()]


BUILTINS = {"nothing": _builtin_nothing, "every_line": _builtin_every_line}


def load_adapter(spec, root):
    if spec.startswith("builtin:"):
        name = spec[len("builtin:"):]
        need(name in BUILTINS, f"builtin desconhecido: {name}")
        return BUILTINS[name]
    mod, _, fn = spec.partition(":")
    need(mod and fn, "adapter deve ser modulo:funcao ou builtin:nome")
    sys.path.insert(0, str(Path(root) / "adapters"))
    sys.path.insert(0, str(root))
    return getattr(importlib.import_module(mod), fn)


# ---------------------------------------------------------------------- lock
def _frozen(root, manifest):
    files = manifest.get("frozen_files")
    need(isinstance(files, list) and files, "manifest.json sem frozen_files")
    base = Path(root).resolve().parent
    out = {}
    for rel in files:
        p = (Path(root) / rel).resolve()
        try:
            p.relative_to(base)
        except ValueError:
            raise BenchError(f"frozen_files fora do diretorio da skill: {rel}")
        need(p.is_file(), f"arquivo congelado ausente: {rel}")
        out[rel] = sha256_file(p)
    return out


def _digests(root, cases):
    sub = sorted((c for c in cases if c.get("split") == "validacao"),
                 key=lambda c: c["id"])
    return {
        "validation_cases_sha256": sha256_bytes(canon(sub).encode("utf-8")),
        "thresholds_sha256": sha256_file(root / "thresholds.json"),
        "manifest_sha256": sha256_file(root / "manifest.json"),
        "frozen_files_sha256": _frozen(root, load_json(root / "manifest.json")),
    }


def cmd_lock(root, cases, thr):
    missing = [k for k in THRESHOLD_KEYS if thr.get(k) is None]
    need(not missing, f"defina os limiares antes do lock: {missing}")
    lock = _digests(root, cases)
    lock["created_utc"] = datetime.now(timezone.utc).isoformat()
    lock["git"] = git_info(root)
    (root / "lock.json").write_text(json.dumps(lock, indent=2), encoding="utf-8")
    return lock


def check_lock(root, cases):
    p = root / "lock.json"
    need(p.is_file(), "lock.json ausente: rode 'lock' e faca commit antes de medir a validacao")
    lock, now = load_json(p), _digests(root, cases)
    for k, v in now.items():
        if k == "frozen_files_sha256":
            old = lock.get(k) or {}
            changed = sorted(f for f in set(old) | set(v) if old.get(f) != v.get(f))
            need(not changed, f"arquivos congelados mudaram apos o lock: {changed}")
        else:
            need(lock.get(k) == v, f"lock divergente em {k}: casos/limiares/manifesto mudaram apos o lock")
    return lock


# ------------------------------------------------------------------------ CLI
def _inputs(root):
    root = Path(root).resolve()
    manifest = load_json(root / "manifest.json")
    cases = load_json(root / "cases.json")
    thr = load_json(root / "thresholds.json")
    return root, manifest, load_docs(root, manifest), cases, thr


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent))
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate")
    sub.add_parser("lock")
    r = sub.add_parser("run")
    r.add_argument("--split", required=True, choices=SPLITS)
    r.add_argument("--adapter", required=True)
    r.add_argument("--repeat", type=int, default=1)
    r.add_argument("--out", default=None)
    a = ap.parse_args(argv)

    try:
        root, manifest, docs, cases, thr = _inputs(a.root)
        problems, warnings = validate(docs, cases)
        for w in warnings:
            print("AVISO:", w)
        if problems:
            for p in problems:
                print("ERRO:", p)
            return 2
        if a.cmd == "validate":
            print(f"OK: {len(cases)} casos, {len(docs)} documentos, {len(warnings)} avisos")
            return 0
        if a.cmd == "lock":
            print(json.dumps(cmd_lock(root, cases, thr), indent=2))
            return 0

        need(a.repeat >= 1, "--repeat deve ser >= 1")
        lock = check_lock(root, cases) if a.split == "validacao" else None
        adapter = load_adapter(a.adapter, root)
        runs = []
        for _ in range(a.repeat):
            findings = []
            for did, d in docs.items():
                if d["status"] != "OK":
                    continue
                try:
                    for f in adapter(d["path"], did):
                        findings.append(normalize_finding(f, did))
                except BenchError as e:
                    d["status"] = "RESULTADO_INCOMPATIVEL"
                    d["motivo"] = str(e)
                    print(f"BLOQUEADO {did}: {e}")
            runs.append(evaluate(docs, cases, findings, a.split))
        verdict, reasons = gate(runs[0], thr)
        report = {
            "run_id": str(uuid.uuid4()),
            "started_utc": datetime.now(timezone.utc).isoformat(),
            "bench_version": BENCH_VERSION,
            "python": sys.version,
            "platform": platform.platform(),
            "git": git_info(root),
            "adapter": a.adapter,
            "split": a.split,
            "repeat": a.repeat,
            "lock": lock,
            "documentos": {k: {"status": v["status"], "motivo": v.get("motivo"),
                               "registrado": v["registered_sha256"],
                               "real": v["actual_sha256"], "kind": v["kind"]}
                           for k, v in docs.items()},
            "resultado": runs[0],
            "recall_por_execucao": [x["total"]["recall"]["valor"] for x in runs],
            "estabilidade": stability(runs),
            "gate": {"veredito": verdict, "motivos": reasons,
                     "aplicavel": a.split == "validacao"},
        }
        text = json.dumps(report, indent=2, ensure_ascii=False)
        if a.out:
            Path(a.out).write_text(text, encoding="utf-8")
        t = runs[0]["total"]
        print(f"split={a.split} adapter={a.adapter} run_id={report['run_id']}")
        print(f"recall={t['recall']['valor']} ic95={t['recall']['ic95']} (n={t['recall']['n']})")
        print(f"especificidade={t['especificidade']['valor']} (n={t['especificidade']['n']})")
        print(f"precisao otimista={runs[0]['precisao_otimista']} pessimista={runs[0]['precisao_pessimista']}")
        print(f"achados={runs[0]['achados']}")
        print(f"gate={verdict} {reasons}" + ("" if report["gate"]["aplicavel"] else " (calibracao: informativo)"))
        return {"PASS": 0, "FAIL": 1, "NOT_VERIFIED": 3}[verdict]
    except BenchError as e:
        print("BLOCKED:", e)
        return 2


if __name__ == "__main__":
    sys.exit(main())
