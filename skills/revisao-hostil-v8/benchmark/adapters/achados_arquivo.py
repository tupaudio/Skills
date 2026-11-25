"""Le achados de uma revisao cega (arquivo JSON) e normaliza para o benchmark.

Formato esperado em results/blind_<DOC_ID>.json:
{
  "document": "A04",
  "document_sha256": "<sha256 do .md revisado>",
  "reviewer": {
    "reviewer_model": "<modelo>",
    "session_id": "<id da sessao>",
    "saw_gabarito": false,
    "saw_pareceres": false,
    "saw_auditor_results": false
  },
  "findings": [
    {"line_start": 99, "line_end": 99, "category": "resultado_numerico",
     "status": "TRIAGEM", "excerpt": "trecho opcional"}
  ]
}
Falha fechado: hash divergente, atestacao ausente ou verdadeira, linha fora do
documento e status desconhecido levantam BenchError.
"""
import json
import re
from pathlib import Path

from bench import BenchError, need, sha256_file

ACCEPTED_STATUS = {"TRIAGEM", "CONFIRMADO", "NAO_VERIFICADO"}
BLIND_FLAGS = ("saw_gabarito", "saw_pareceres", "saw_auditor_results")
META_KEYS = ("reviewer_model", "session_id")


def parse_blind(data, doc_id, doc_sha, n_lines):
    need(isinstance(data, dict), "arquivo de achados nao e um objeto JSON")
    need(data.get("document") == doc_id,
         f"documento do arquivo ({data.get('document')!r}) difere de {doc_id}")
    need(str(data.get("document_sha256", "")).lower() == doc_sha.lower(),
         "hash do documento revisado difere do documento do benchmark")
    meta = data.get("reviewer")
    need(isinstance(meta, dict), "bloco 'reviewer' ausente")
    for k in META_KEYS:
        need(isinstance(meta.get(k), str) and meta[k].strip(),
             f"reviewer.{k} ausente")
    for k in BLIND_FLAGS:
        need(meta.get(k) is False,
             f"reviewer.{k} deve ser false (revisao nao cega)")
    items = data.get("findings")
    need(isinstance(items, list), "campo 'findings' ausente ou nao e lista")
    out = []
    for i, it in enumerate(items):
        need(isinstance(it, dict), f"achado #{i} nao e objeto")
        ls = it.get("line_start")
        need(isinstance(ls, int) and not isinstance(ls, bool)
             and 1 <= ls <= n_lines,
             f"achado #{i}: line_start invalido ({ls!r})")
        le = it.get("line_end", ls)
        need(isinstance(le, int) and not isinstance(le, bool)
             and ls <= le <= n_lines,
             f"achado #{i}: line_end invalido ({le!r})")
        cat = it.get("category")
        need(isinstance(cat, str) and cat.strip(),
             f"achado #{i}: category ausente")
        st = it.get("status")
        need(st in ACCEPTED_STATUS, f"achado #{i}: status invalido ({st!r})")
        out.append({"line_start": ls, "line_end": le,
                    "excerpt": it.get("excerpt"),
                    "category": cat, "status": st})
    return out


def achados_arquivo(path, doc_id):
    need(re.fullmatch(r"[A-Za-z0-9_-]+", doc_id or ""), "doc_id invalido")
    rp = Path(__file__).resolve().parents[1] / "results" / f"blind_{doc_id}.json"
    need(rp.is_file(), f"arquivo de achados ausente: results/blind_{doc_id}.json")
    try:
        data = json.loads(rp.read_text(encoding="utf-8"))
    except ValueError as e:
        raise BenchError(f"JSON invalido em {rp.name}: {e}")
    doc = Path(path)
    n = len(doc.read_text(encoding="utf-8").splitlines())
    return parse_blind(data, doc_id, sha256_file(doc), n)
