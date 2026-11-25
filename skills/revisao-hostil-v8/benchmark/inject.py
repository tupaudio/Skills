#!/usr/bin/env python3
"""Injeta defeitos deterministicos em um markdown LIMPO e gera fragmentos de manifest/cases."""
import argparse, json, random, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bench import sha256_file  # noqa: E402

UNIT = re.compile(r"\b(\d+(?:[.,]\d+)?)\s*(kWh|kW|MWh|MW)\b")
SWAP = {"kWh": "kW", "kW": "kWh", "MWh": "MW", "MW": "MWh"}
NUM = re.compile(r"(?<![\w.,])\d+[.,]\d+(?![\w])")
CLAIM = " Isto comprova definitivamente a validade do metodo em qualquer condicao."


def _eligible(l):
    return len(l) > 60 and not l.lstrip().startswith(("#", "|", "$", "```"))


def mut_unit(lines, rng, used):
    c = [i for i, l in enumerate(lines) if i not in used and UNIT.search(l)]
    if not c:
        return None
    i = rng.choice(c)
    m = UNIT.search(lines[i])
    new = lines[i][:m.start(2)] + SWAP[m.group(2)] + lines[i][m.end(2):]
    return i, new, "dimensional", "unidade trocada (potencia<->energia)", new.strip()


def mut_number(lines, rng, used):
    occ = {}
    for i, l in enumerate(lines):
        for t in set(NUM.findall(l)):
            occ.setdefault(t, []).append(i)
    c = sorted(t for t, v in occ.items() if len(v) >= 2 and occ[t][1] not in used)
    if not c:
        return None
    t = rng.choice(c)
    i = occ[t][1]
    new_t = t[:-1] + str((int(t[-1]) + 1) % 10)
    new = re.sub(r"(?<![\w.,])" + re.escape(t) + r"(?![\w])", new_t, lines[i], count=1)
    return i, new, "inconsistencia_interna", f"valor {t} alterado para {new_t} na 2a ocorrencia", new.strip()


def mut_claim(lines, rng, used):
    c = [i for i, l in enumerate(lines) if i not in used and _eligible(l)]
    if not c:
        return None
    i = rng.choice(c)
    return i, lines[i] + CLAIM, "afirmacao_absoluta", "afirmacao absoluta inserida", CLAIM.strip()


MUTS = [mut_unit, mut_number, mut_claim]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--doc-id", required=True)
    ap.add_argument("--out-doc", required=True)
    ap.add_argument("--out-fragment", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--n-defects", type=int, default=6)
    ap.add_argument("--n-negatives", type=int, default=6)
    ap.add_argument("--split", required=True, choices=["calibracao", "validacao"])
    ap.add_argument("--base-is-clean", action="store_true",
                    help="confirma que o texto base nao tem defeitos conhecidos")
    ap.add_argument("--validated-by", required=True)
    a = ap.parse_args()
    if not a.base_is_clean:
        sys.exit("BLOCKED: confirme com --base-is-clean que a base esta limpa")

    lines = Path(a.base).read_text(encoding="utf-8").splitlines()
    rng, used, cases = random.Random(a.seed), set(), []
    out = list(lines)
    for k in range(a.n_defects):
        for _ in range(20):
            r = MUTS[k % len(MUTS)](out, rng, used)
            if r:
                break
        else:
            sys.exit(f"BLOCKED: nao foi possivel injetar defeito #{k + 1}")
        i, new, cat, why, quote = r
        out[i] = new
        used.add(i)
        cases.append({"id": f"{a.doc_id}-INJ-{k + 1:03d}", "document": a.doc_id, "type": "DEFECT",
                      "domain": "cientifico", "category": cat, "split": a.split,
                      "anchor": {"quote": quote, "line_start": i + 1, "line_end": i + 1},
                      "rationale": why, "origin": "injetado", "adjudicated": True,
                      "validated_by": a.validated_by,
                      "evidence": f"defeito injetado por inject.py seed={a.seed}"})
    pool = [i for i, l in enumerate(out) if i not in used and _eligible(l)]
    rng.shuffle(pool)
    for k, i in enumerate(pool[:a.n_negatives]):
        cases.append({"id": f"{a.doc_id}-NEG-{k + 1:03d}", "document": a.doc_id,
                      "type": "NEGATIVE_CONTROL", "domain": "cientifico", "category": "geral",
                      "split": a.split,
                      "anchor": {"quote": out[i].strip(), "line_start": i + 1, "line_end": i + 1},
                      "rationale": "trecho original da base limpa", "origin": "controle",
                      "adjudicated": True, "validated_by": a.validated_by,
                      "evidence": "base declarada limpa via --base-is-clean"})
    if len(pool) < a.n_negatives:
        print(f"AVISO: so {len(pool)} controles negativos disponiveis", file=sys.stderr)

    Path(a.out_doc).write_text("\n".join(out) + "\n", encoding="utf-8")
    frag = {"manifest": {a.doc_id: {"path": str(a.out_doc), "sha256": sha256_file(a.out_doc),
                                    "kind": "sintetico", "origin": f"{a.base} seed={a.seed}"}},
            "cases": cases}
    Path(a.out_fragment).write_text(json.dumps(frag, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{len(cases)} casos gerados; sha256 do documento registrado no fragmento")


if __name__ == "__main__":
    main()
