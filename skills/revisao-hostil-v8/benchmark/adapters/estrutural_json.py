"""Le o JSON do auditor_estrutural e normaliza para o formato do benchmark.

Schema observado em bench_art04.json: lista 'achados' com 'categoria',
'gravidade', 'confianca', 'localizacao' ("linha N") e
'evidencias'[0]['conteudo'/'hash_arquivo'].
Falha fechado: hash divergente, confianca desconhecida ou linha que nao
bate com o documento levantam BenchError (o bench bloqueia so aquele documento).
"""
import json
import re
from pathlib import Path

from bench import BenchError, need, sha256_file

RESULT_FILES = {
    "A04": "results/bench_art04.json",
    "A03": "results/bench_art03.json",
}
LINE_RE = re.compile(r"^\s*linha\s+(\d+)\s*$", re.IGNORECASE)
ACCEPTED_CONFIDENCE = {"TRIAGEM"}


def _norm(s):
    return re.sub(r"\s+", " ", str(s)).strip().casefold()


def parse_findings(data, doc_lines, doc_sha, keep=None):
    need(isinstance(data, dict), "JSON do auditor nao e um objeto")
    items = data.get("achados")
    need(isinstance(items, list),
         f"campo 'achados' ausente; chaves do topo: {sorted(data)}")

    hashes = set()
    if data.get("hash_artefato"):
        hashes.add(str(data["hash_artefato"]).lower())
    for it in items:
        for ev in (it.get("evidencias") or []):
            if ev.get("hash_arquivo"):
                hashes.add(str(ev["hash_arquivo"]).lower())
    need(hashes, "JSON sem hash do arquivo auditado: proveniencia nao verificavel")
    need(hashes == {doc_sha.lower()},
         f"hash do JSON {sorted(hashes)} difere do documento do benchmark {doc_sha}")

    out, mismatches = [], []
    for it in items:
        if keep is not None and not keep(it):
            continue
        conf = it.get("confianca")
        need(conf in ACCEPTED_CONFIDENCE,
             f"confianca {conf!r} sem mapeamento definido (achado {it.get('id')})")
        evid = it.get("evidencias") or []
        content = evid[0].get("conteudo") if evid else None
        m = LINE_RE.match(str(it.get("localizacao") or ""))
        line = int(m.group(1)) if m else None
        if line is not None:
            need(1 <= line <= len(doc_lines),
                 f"{it.get('id')}: linha {line} fora do documento ({len(doc_lines)} linhas)")
            if content:
                prefix = _norm(content)[:60]
                if prefix and prefix not in _norm(doc_lines[line - 1]):
                    mismatches.append(f"{it.get('id')} linha {line}")
        out.append({
            "line_start": line,
            "line_end": line,
            "excerpt": content,
            "category": it.get("categoria"),
            "status": "TRIAGEM",
        })
    need(not mismatches,
         f"{len(mismatches)} achados cujo conteudo nao esta na linha indicada "
         f"(numeracao divergente?): {mismatches[:5]}")
    return out


def _run(path, doc_id, keep):
    need(doc_id in RESULT_FILES, f"sem arquivo de resultado para {doc_id}")
    rp = Path(__file__).resolve().parents[1] / RESULT_FILES[doc_id]
    need(rp.is_file(), f"resultado ausente: {RESULT_FILES[doc_id]}")
    try:
        data = json.loads(rp.read_text(encoding="utf-8"))
    except ValueError as e:
        raise BenchError(f"JSON invalido em {RESULT_FILES[doc_id]}: {e}")
    doc = Path(path)
    lines = doc.read_text(encoding="utf-8").splitlines()
    return parse_findings(data, lines, sha256_file(doc), keep)


def estrutural(path, doc_id):
    """Todos os achados do auditor."""
    return _run(path, doc_id, None)


def estrutural_sem_informativos(path, doc_id):
    """Ablacao declarada: remove achados de gravidade INFORMATIVO."""
    return _run(path, doc_id, lambda it: it.get("gravidade") != "INFORMATIVO")
