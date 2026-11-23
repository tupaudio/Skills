"""Normalização textual segura e consistente entre motores (Core v8.0)."""

from __future__ import annotations

import re
import unicodedata

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_whitespace(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def normalize_unicode(text: str, form: str = "NFC") -> str:
    return unicodedata.normalize(form, text)


def strip_accents(text: str) -> str:
    nfd = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")


def canonical_key(text: str) -> str:
    """Gera chave canônica minúscula, sem acentos e com espaços colapsados."""
    cleaned = normalize_whitespace(strip_accents(text)).lower()
    return re.sub(r"[^a-z0-9_]+", "_", cleaned).strip("_")
