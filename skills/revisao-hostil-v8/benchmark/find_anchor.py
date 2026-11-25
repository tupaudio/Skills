#!/usr/bin/env python3
"""Uso: python benchmark/find_anchor.py DOC_ID termo [termo ...]"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import bench  # noqa: E402


def main(argv):
    if len(argv) < 3:
        print("uso: find_anchor.py DOC_ID termo [termo ...]")
        return 2
    docs = bench.load_docs(ROOT, bench.load_json(ROOT / "manifest.json"))
    did = argv[1]
    if did not in docs:
        print(f"documento desconhecido: {did}")
        return 2
    d = docs[did]
    if d["status"] != "OK":
        print(f"documento {did} com status {d['status']}")
        return 2
    for term in argv[2:]:
        nt = bench._norm(term)
        print(f"== {term}")
        for i, line in enumerate(d["lines"], 1):
            if nt in bench._norm(line):
                print(f"{i}: {line[:200]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
