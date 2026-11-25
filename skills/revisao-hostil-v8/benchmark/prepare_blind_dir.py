#!/usr/bin/env python3
"""Monta o diretorio limpo da revisao cega (Etapa 2). Somente biblioteca padrao.

Copia apenas: SKILL.md, scripts/ (mais --include extras) e o manuscrito.
Nao usa assert: as validacoes levantam PrepError (igual sob python -O).

Exit codes: 0 = diretorio pronto; 2 = bloqueado (nada fica no destino).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

PREP_VERSION = "0.1.0"

FORBIDDEN_DIRS = {
    ".git", "benchmark", "tests", "docs", "results", "versions",
    "benchmark_etapa2", "benchmark_privado",
}
FORBIDDEN_TOKENS = {
    "cases", "prereg", "preregistro", "parecer", "pareceres", "bench",
    "blind", "lock", "thresholds", "manifest", "gabarito", "relatorio",
    "benchmark", "results",
}
CONTENT_MARKERS = (
    "B04-", "B03-", "PREREGISTRO", "cases.json", "thresholds.json",
    "line_sha256", "ZZ - Antigravity", "benchmark_etapa2",
)
SKIP_SUFFIXES = (".pyc", ".pyo")
SKIP_NAMES = {".coverage"}
SHA_RE = re.compile(r"^[0-9a-fA-F]{64}$")


class PrepError(Exception):
    pass


def need(cond, msg):
    if not cond:
        raise PrepError(msg)


def sha256_file(p) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _tokens(name: str):
    stem = name.rsplit(".", 1)[0] if "." in name else name
    return {t for t in re.split(r"[^a-z0-9]+", stem.lower()) if t}


def _bad_name(rel: str):
    for part in Path(rel).parts:
        hit = _tokens(part) & FORBIDDEN_TOKENS
        if hit:
            return sorted(hit)
    return None


def expected_hash(skill_dir: Path, doc_id, expected_sha):
    manifest_sha = None
    if doc_id:
        mp = skill_dir / "benchmark" / "manifest.json"
        need(mp.is_file(), "benchmark/manifest.json ausente")
        try:
            data = json.loads(mp.read_text(encoding="utf-8"))
        except ValueError as e:
            raise PrepError(f"manifest.json invalido: {e}")
        docs = data.get("documents") or {}
        need(doc_id in docs, f"doc-id {doc_id!r} nao esta no manifest")
        manifest_sha = str(docs[doc_id].get("sha256") or "")
        need(SHA_RE.match(manifest_sha), f"hash do manifest para {doc_id} nao e um sha256 valido")
    if expected_sha:
        need(SHA_RE.match(expected_sha), "--expected-sha256 invalido")
    need(manifest_sha or expected_sha, "informe --doc-id ou --expected-sha256")
    if manifest_sha and expected_sha:
        need(manifest_sha.lower() == expected_sha.lower(),
             "--expected-sha256 difere do hash do manifest")
    return (manifest_sha or expected_sha).lower()


def check_dest(dest: Path, skill_dir: Path) -> Path:
    d, s = dest.resolve(), skill_dir.resolve()
    need(d != s and s not in d.parents and d not in s.parents,
         "destino dentro ou sobre a pasta da skill")
    for anc in [d, *d.parents]:
        need(not (anc / ".git").exists(), f"destino dentro de repositorio git: {anc}")
    if d.exists():
        need(d.is_dir() and not any(d.iterdir()), "destino existe e nao esta vazio")
    return d


def collect(skill_dir: Path, includes, allow):
    files, allowed_used = [], []
    sk = skill_dir / "SKILL.md"
    need(sk.is_file() and not sk.is_symlink(), "SKILL.md ausente ou e link simbolico")
    files.append(("SKILL.md", sk))
    for top in includes:
        need(top.lower() not in FORBIDDEN_DIRS and ".." not in Path(top).parts
             and not Path(top).is_absolute(), f"--include proibido: {top}")
        base = skill_dir / top
        need(base.is_dir() and not base.is_symlink(), f"pasta ausente ou link: {top}")
        for root, dirs, names in os.walk(base, followlinks=False):
            rootp = Path(root)
            for dname in list(dirs):
                p = rootp / dname
                need(not p.is_symlink(), f"link simbolico: {p}")
                if dname == "__pycache__":
                    dirs.remove(dname)
                    continue
                need(dname.lower() not in FORBIDDEN_DIRS, f"diretorio proibido: {p}")
            for n in names:
                p = rootp / n
                need(not p.is_symlink(), f"link simbolico: {p}")
                if n.endswith(SKIP_SUFFIXES) or n in SKIP_NAMES:
                    continue
                rel = p.relative_to(skill_dir).as_posix()
                bad = _bad_name(rel)
                if bad:
                    need(rel in allow, f"nome proibido {bad}: {rel} (use --allow {rel} se for legitimo)")
                    allowed_used.append(rel)
                files.append((rel, p))
    return files, allowed_used


def scan_markers(rel_paths_and_files):
    hits, binarios = [], []
    for rel, p in rel_paths_and_files:
        try:
            text = Path(p).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            binarios.append(rel)
            continue
        for m in CONTENT_MARKERS:
            if m in text:
                hits.append(f"{rel}: marcador {m!r}")
    return hits, binarios


def prepare(skill_dir, doc, dest, expected_sha=None, doc_id=None,
            includes=("scripts",), allow=(), record_out=None):
    skill_dir, doc, dest = Path(skill_dir), Path(doc), Path(dest)
    allow, includes = set(allow), list(includes)
    need(skill_dir.is_dir(), "pasta da skill inexistente")
    exp = expected_hash(skill_dir, doc_id, expected_sha)
    need(doc.is_file() and not doc.is_symlink(), "manuscrito ausente ou e link simbolico")
    doc_sha = sha256_file(doc)
    need(doc_sha == exp, f"hash do manuscrito ({doc_sha}) difere do esperado ({exp})")
    try:
        n_lines = len(doc.read_text(encoding="utf-8").splitlines())
    except UnicodeDecodeError:
        raise PrepError("manuscrito nao e UTF-8")
    d = check_dest(dest, skill_dir)
    if record_out:
        ro = Path(record_out).resolve()
        need(d != ro and d not in ro.parents, "--record-out nao pode ficar dentro do destino")

    files, allowed_used = collect(skill_dir, includes, allow)
    need(doc.name not in {rel for rel, _ in files}, f"nome do manuscrito colide com arquivo da skill: {doc.name}")
    hits, binarios = scan_markers(files + [(doc.name, doc)])
    need(not hits, "marcadores de vazamento encontrados: " + "; ".join(hits[:10]))

    created = not d.exists()
    d.mkdir(parents=True, exist_ok=True)
    try:
        expected_rel = {}
        for rel, src in files:
            out = d / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, out)
            expected_rel[rel] = sha256_file(src)
        shutil.copyfile(doc, d / doc.name)
        expected_rel[doc.name] = doc_sha

        found = {}
        for root, _dirs, fnames in os.walk(d, followlinks=False):
            for n in fnames:
                p = Path(root) / n
                need(not p.is_symlink(), f"link simbolico no destino: {p}")
                found[p.relative_to(d).as_posix()] = sha256_file(p)
        need(set(found) == set(expected_rel),
             f"lista de arquivos do destino diverge: extras={sorted(set(found) - set(expected_rel))} "
             f"faltando={sorted(set(expected_rel) - set(found))}")
        need(found == expected_rel, "hash de algum arquivo copiado diverge do original")
        need(found[doc.name] == exp, "hash do manuscrito no destino diverge")
    except BaseException:
        shutil.rmtree(d, ignore_errors=True)
        raise

    auditor = d / "scripts" / "auditor.py"
    report = {
        "prep_version": PREP_VERSION,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "dest": str(d),
        "dest_created_by_script": created,
        "document": {"name": doc.name, "sha256": doc_sha, "lines_splitlines": n_lines,
                     "bytes": doc.stat().st_size},
        "skill_md_sha256": expected_rel["SKILL.md"],
        "auditor_py_sha256": found.get("scripts/auditor.py") if auditor.is_file() else None,
        "includes": includes,
        "allowed_names_used": sorted(set(allowed_used)),
        "binary_files_not_scanned": binarios,
        "files": [{"path": k, "sha256": v} for k, v in sorted(found.items())],
        "marker_scan": {"markers": list(CONTENT_MARKERS), "hits": 0},
    }
    if record_out:
        Path(record_out).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skill-dir", default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument("--doc", required=True, help="caminho do manuscrito (ex.: artigo04.md)")
    ap.add_argument("--doc-id", help="id do documento no manifest.json (ex.: A04)")
    ap.add_argument("--expected-sha256")
    ap.add_argument("--dest", required=True, help="diretorio limpo, FORA de qualquer repositorio git")
    ap.add_argument("--include", action="append", default=None,
                    help="pasta extra da skill (padrao: scripts); repetivel")
    ap.add_argument("--allow", action="append", default=[],
                    help="caminho relativo cujo nome suspeito foi revisado e liberado; repetivel")
    ap.add_argument("--record-out", help="grava o registro JSON neste arquivo (fora do destino)")
    a = ap.parse_args(argv)
    try:
        rep = prepare(a.skill_dir, a.doc, a.dest, a.expected_sha256, a.doc_id,
                      a.include or ["scripts"], a.allow, a.record_out)
    except PrepError as e:
        print(f"BLOQUEADO: {e}", file=sys.stderr)
        return 2
    print(json.dumps(rep, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
