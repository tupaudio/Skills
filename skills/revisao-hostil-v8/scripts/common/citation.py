"""Utilitários de extração e checagem de citações e referências cruzadas (Core v8.0)."""

from __future__ import annotations

import re

LATEX_CITE_RE = re.compile(r"\\cite(?:p|t|online|author|year|alp|alt)?(?:\[[^\]]*\])*\{([^}]+)\}")
LATEX_REF_RE = re.compile(r"\\(?:eq)?ref\{([^}]+)\}")
LATEX_LABEL_RE = re.compile(r"\\label\{([^}]+)\}")
CROSS_REF_PROSE_RE = re.compile(
    r"\b(?:Equa[çc][ãa]o|Equation|Eq\.|Tabela|Table|Figura|Figure|Fig\.|Se[çc][ãa]o|Section)\s+\d+",
    re.IGNORECASE,
)


def extract_latex_citations(text: str) -> list[str]:
    keys: list[str] = []
    for match in LATEX_CITE_RE.finditer(text):
        for raw_key in match.group(1).split(","):
            key = raw_key.strip()
            if key:
                keys.append(key)
    return keys


def extract_latex_refs_and_labels(text: str) -> dict[str, list[str]]:
    return {
        "refs": [m.group(1).strip() for m in LATEX_REF_RE.finditer(text)],
        "labels": [m.group(1).strip() for m in LATEX_LABEL_RE.finditer(text)],
    }


def check_bijection(cited_keys: set[str], bib_keys: set[str]) -> dict[str, list[str] | bool]:
    """Verifica bijeção 1:1 entre chaves citadas no corpo e entradas na bibliografia."""
    ghost_citations = sorted(cited_keys - bib_keys)
    orphan_references = sorted(bib_keys - cited_keys)
    return {
        "bijection_ok": not ghost_citations and not orphan_references,
        "ghost_citations": ghost_citations,
        "orphan_references": orphan_references,
    }
