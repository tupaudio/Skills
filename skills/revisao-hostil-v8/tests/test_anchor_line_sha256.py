import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "benchmark"
sys.path.insert(0, str(ROOT))
import bench  # noqa: E402

LINES = [
    "linha um",
    "conteudo repetido",
    "linha tres com espaco final ",
    "linha quatro",
    "conteudo repetido",
]


def _sha(lines, ls, le=None):
    le = le or ls
    return hashlib.sha256("\n".join(lines[ls - 1:le]).encode("utf-8")).hexdigest()


class AnchorLineSha256Tests(unittest.TestCase):
    def test_1_valid_hash_on_correct_line_resolves(self):
        anc = {"line_start": 1, "line_end": 1, "line_sha256": _sha(LINES, 1)}
        self.assertEqual(bench.resolve_anchor(LINES, anc), (1, 1))

    def test_2_wrong_hash_raises(self):
        anc = {"line_start": 1, "line_end": 1, "line_sha256": "0" * 64}
        with self.assertRaises(bench.BenchError):
            bench.resolve_anchor(LINES, anc)

    def test_3_line_out_of_bounds_raises(self):
        anc = {"line_start": 99, "line_end": 99, "line_sha256": _sha(LINES, 1)}
        with self.assertRaises(bench.BenchError):
            bench.resolve_anchor(LINES, anc)

    def test_4_line_start_greater_than_line_end_raises(self):
        anc = {"line_start": 4, "line_end": 2, "line_sha256": _sha(LINES, 2, 4)}
        with self.assertRaises(bench.BenchError):
            bench.resolve_anchor(LINES, anc)

    def test_5_edited_document_fails_validate(self):
        edited = list(LINES)
        edited[0] = "linha um modificada"
        docs = {"D": {"status": "OK", "lines": edited}}
        cases = [{
            "id": "C1", "document": "D", "type": "DEFECT", "domain": "cientifico",
            "category": "x", "split": "validacao", "adjudicated": False,
            "anchor": {"line_start": 1, "line_end": 1, "line_sha256": _sha(LINES, 1)},
        }]
        problems, _ = bench.validate(docs, cases)
        self.assertTrue(any("line_sha256 divergente" in p for p in problems))

    def test_6_invalid_hex_format_raises(self):
        for bad in ("abc", "z" * 64, "", 12345):
            anc = {"line_start": 1, "line_end": 1, "line_sha256": bad}
            with self.assertRaises(bench.BenchError):
                bench.resolve_anchor(LINES, anc)

    def test_7_both_quote_and_line_sha256_both_validated(self):
        # Ambos validos: passa
        anc_ok = {"line_start": 1, "line_end": 1, "quote": "linha um",
                  "line_sha256": _sha(LINES, 1)}
        self.assertEqual(bench.resolve_anchor(LINES, anc_ok), (1, 1))
        # Quote valido mas line_sha256 errado: falha
        anc_bad_sha = {"line_start": 1, "line_end": 1, "quote": "linha um",
                       "line_sha256": "0" * 64}
        with self.assertRaises(bench.BenchError):
            bench.resolve_anchor(LINES, anc_bad_sha)
        # line_sha256 valido mas quote errado: falha
        anc_bad_q = {"line_start": 1, "line_end": 1, "quote": "outra coisa",
                     "line_sha256": _sha(LINES, 1)}
        with self.assertRaises(bench.BenchError):
            bench.resolve_anchor(LINES, anc_bad_q)

    def test_8_multiline_span_and_trailing_space_preserved(self):
        anc = {"line_start": 3, "line_end": 4, "line_sha256": _sha(LINES, 3, 4)}
        self.assertEqual(bench.resolve_anchor(LINES, anc), (3, 4))
        # Remover espaco final da linha 3 deve falhar
        stripped = hashlib.sha256("linha tres com espaco final\nlinha quatro".encode("utf-8")).hexdigest()
        with self.assertRaises(bench.BenchError):
            bench.resolve_anchor(LINES, {"line_start": 3, "line_end": 4, "line_sha256": stripped})

    def test_9_repeated_content_binds_by_line_number_not_hash_only(self):
        # Linhas 2 e 5 tem o mesmo conteudo; ancora na linha 5 resolve (5, 5), nao (2, 2)
        h = _sha(LINES, 5)
        self.assertEqual(h, _sha(LINES, 2))
        self.assertEqual(
            bench.resolve_anchor(LINES, {"line_start": 5, "line_end": 5, "line_sha256": h}),
            (5, 5),
        )


if __name__ == "__main__":
    unittest.main()
