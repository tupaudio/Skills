"""Verificacao exata de preservacao dos 199 IDs historicos (ACH-B7-R19-003)."""
import re
from pathlib import Path

REV20 = Path(__file__).resolve().parent.parent
DOCS = REV20.parent
ID_RE = re.compile(r"^\|\s*`(T-R(?:9-\d{3}-\d{2}|11-\d{3}|12-\d{3}|13-\d{3}|14-\d{3}|15-\d{3}|16-\d{3}|17-\d{3}|18-\d{3}|19-\d{3}|20-\d{3}))`\s*\|", re.M)


def _extract_ids(path: Path) -> set[str]:
    return set(ID_RE.findall(path.read_text(encoding="utf-8")))


def test_historical_id_sets_preserved():
    r17 = _extract_ids(DOCS / "fase7_rev17/MATRIZ_TESTES_ACEITACAO_REV17.md")
    r18 = _extract_ids(DOCS / "fase7_rev18/MATRIZ_TESTES_ACEITACAO_REV18.md")
    r19 = _extract_ids(DOCS / "fase7_rev19/MATRIZ_TESTES_ACEITACAO_REV19.md")
    if len(r17) != 164 or len(r18) != 194 or len(r19) != 199:
        raise AssertionError(f"Contagem inesperada: r17={len(r17)}, r18={len(r18)}, r19={len(r19)}")
    if not (r17 <= r18 <= r19):
        raise AssertionError("IDs historicos foram removidos entre revisoes")
