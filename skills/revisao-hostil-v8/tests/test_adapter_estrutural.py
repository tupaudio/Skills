import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "benchmark"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "adapters"))
import bench  # noqa: E402
import estrutural_json as ej  # noqa: E402

LINES = ["# Titulo", "", "**Autores:** Fulano$^1$", "Texto do resumo com afirmacao forte."]
SHA = "a" * 64


def item(i, loc, content, conf="TRIAGEM", grav="MENOR", cat="epistemic_overclaim", sha=SHA):
    return {"id": f"ACH-{i}", "categoria": cat, "gravidade": grav, "confianca": conf,
            "localizacao": loc,
            "evidencias": [{"conteudo": content, "hash_arquivo": sha}]}


def data(items, top=SHA):
    d = {"achados": items}
    if top:
        d["hash_artefato"] = top
    return d


class AdapterTests(unittest.TestCase):
    def test_ok(self):
        out = ej.parse_findings(data([item(1, "linha 3", LINES[2])]), LINES, SHA)
        self.assertEqual(out[0]["line_start"], 3)
        self.assertEqual(out[0]["status"], "TRIAGEM")
        self.assertEqual(out[0]["category"], "epistemic_overclaim")

    def test_hash_mismatch(self):
        with self.assertRaises(bench.BenchError):
            ej.parse_findings(data([item(1, "linha 3", LINES[2])]), LINES, "b" * 64)

    def test_missing_hash(self):
        with self.assertRaises(bench.BenchError):
            ej.parse_findings(data([item(1, "linha 3", LINES[2], sha=None)], top=None), LINES, SHA)

    def test_line_off_by_one(self):
        with self.assertRaises(bench.BenchError):
            ej.parse_findings(data([item(1, "linha 4", LINES[2])]), LINES, SHA)

    def test_line_out_of_range(self):
        with self.assertRaises(bench.BenchError):
            ej.parse_findings(data([item(1, "linha 99", LINES[2])]), LINES, SHA)

    def test_unknown_confidence(self):
        with self.assertRaises(bench.BenchError):
            ej.parse_findings(data([item(1, "linha 3", LINES[2], conf="ALTA")]), LINES, SHA)

    def test_missing_achados(self):
        with self.assertRaises(bench.BenchError):
            ej.parse_findings({"hash_artefato": SHA}, LINES, SHA)

    def test_non_line_location_keeps_excerpt(self):
        out = ej.parse_findings(data([item(1, "Tabela 1, Linha 2", "trecho x")]), LINES, SHA)
        self.assertIsNone(out[0]["line_start"])
        self.assertEqual(out[0]["excerpt"], "trecho x")

    def test_filter_drops_informativo(self):
        items = [item(1, "linha 3", LINES[2], grav="INFORMATIVO", cat="equation_candidate"),
                 item(2, "linha 4", LINES[3], grav="MENOR")]
        out = ej.parse_findings(data(items), LINES, SHA,
                                lambda it: it.get("gravidade") != "INFORMATIVO")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["line_start"], 4)


if __name__ == "__main__":
    unittest.main()
