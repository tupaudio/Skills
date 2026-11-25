import json, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "benchmark"
sys.path.insert(0, str(ROOT))
import bench  # noqa: E402

LINES = [
    "# Titulo",
    "A potencia nominal e 5.25 kW no ensaio.",
    "O resultado repete 5.35 kW na secao quatro.",
    "Isto comprova definitivamente a validade em qualquer condicao.",
    "Texto neutro sem problema algum aqui presente no documento.",
    "Outro paragrafo neutro sem problema algum, apenas descritivo.",
]


def mk(tmp, adjudicated=True, tamper=False):
    (tmp / "docs").mkdir()
    p = tmp / "docs" / "d.md"
    p.write_text("\n".join(LINES) + "\n", encoding="utf-8")
    sha = bench.sha256_file(p)
    if tamper:
        p.write_text("outro conteudo\n", encoding="utf-8")
    manifest = {"documents": {"D": {"path": "docs/d.md", "sha256": sha, "kind": "sintetico"}}}
    base = dict(document="D", domain="cientifico", split="calibracao",
                adjudicated=adjudicated, validated_by="t", evidence="t", rationale="t")
    cases = [
        dict(base, id="D1", type="DEFECT", category="afirmacao_absoluta",
             anchor={"quote": LINES[3], "line_start": 4}),
        dict(base, id="D2", type="DEFECT", category="inconsistencia_interna",
             anchor={"quote": LINES[2], "line_start": 3}),
        dict(base, id="N1", type="NEGATIVE_CONTROL", category="geral", anchor={"quote": LINES[4]}),
        dict(base, id="N2", type="NEGATIVE_CONTROL", category="geral", anchor={"quote": LINES[5]}),
        dict(base, id="I1", type="INCONCLUSIVE", category="geral", anchor={"quote": LINES[1]}),
    ]
    (tmp / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (tmp / "cases.json").write_text(json.dumps(cases), encoding="utf-8")
    (tmp / "thresholds.json").write_text(json.dumps({k: None for k in bench.THRESHOLD_KEYS}), encoding="utf-8")
    return bench._inputs(tmp)


def finding(line, status="TRIAGEM"):
    return {"document": "D", "line_start": line, "line_end": line, "excerpt": None,
            "category": "x", "status": status}


class BenchTests(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = Path(self._t.name)

    def tearDown(self):
        self._t.cleanup()

    def test_perfect_detector(self):
        _, _, docs, cases, _ = mk(self.tmp)
        r = bench.evaluate(docs, cases, [finding(3), finding(4)], "calibracao")
        self.assertEqual(r["total"]["recall"]["valor"], 1.0)
        self.assertEqual(r["total"]["especificidade"]["valor"], 1.0)
        self.assertEqual(r["precisao_pessimista"], 1.0)

    def test_empty_detector(self):
        _, _, docs, cases, _ = mk(self.tmp)
        r = bench.evaluate(docs, cases, [], "calibracao")
        self.assertEqual(r["total"]["recall"]["valor"], 0.0)
        self.assertIsNone(r["precisao_pessimista"])

    def test_flag_everything_is_penalized(self):
        _, _, docs, cases, _ = mk(self.tmp)
        fs = [bench.normalize_finding(f, "D") for f in
              bench._builtin_every_line(docs["D"]["path"], "D")]
        r = bench.evaluate(docs, cases, fs, "calibracao")
        self.assertEqual(r["total"]["recall"]["valor"], 1.0)
        self.assertEqual(r["total"]["especificidade"]["valor"], 0.0)
        self.assertLess(r["precisao_pessimista"], 0.5)

    def test_confirmed_on_inconclusive_is_overclaim(self):
        _, _, docs, cases, _ = mk(self.tmp)
        r = bench.evaluate(docs, cases, [finding(2, "CONFIRMADO")], "calibracao")
        self.assertEqual(r["total"]["excesso_confianca_inconclusivos"]["k"], 1)
        r2 = bench.evaluate(docs, cases, [finding(2, "TRIAGEM")], "calibracao")
        self.assertEqual(r2["total"]["excesso_confianca_inconclusivos"]["k"], 0)

    def test_unlabelled_region_is_not_precision_hit(self):
        _, _, docs, cases, _ = mk(self.tmp)
        r = bench.evaluate(docs, cases, [finding(4), finding(1)], "calibracao")
        self.assertEqual(r["achados"]["sem_rotulo"], 1)
        self.assertEqual(r["precisao_otimista"], 1.0)
        self.assertEqual(r["precisao_pessimista"], 0.5)

    def test_non_adjudicated_excluded(self):
        _, _, docs, cases, _ = mk(self.tmp, adjudicated=False)
        r = bench.evaluate(docs, cases, [finding(4)], "calibracao")
        self.assertEqual(r["total"]["recall"]["n"], 0)
        self.assertEqual(len(r["excluidos"]), 5)

    def test_hash_mismatch_blocks_document(self):
        _, _, docs, cases, _ = mk(self.tmp, tamper=True)
        self.assertEqual(docs["D"]["status"], "HASH_DIVERGENTE")
        r = bench.evaluate(docs, cases, [finding(4)], "calibracao")
        self.assertEqual(r["total"]["recall"]["n"], 0)
        self.assertEqual(r["achados"]["em_documento_bloqueado"], 1)

    def test_unresolvable_anchor_is_problem(self):
        _, _, docs, cases, _ = mk(self.tmp)
        cases[0]["anchor"] = {"quote": "texto que nao existe"}
        problems, _ = bench.validate(docs, cases)
        self.assertTrue(any("D1" in p for p in problems))

    def test_adjudicated_requires_evidence(self):
        _, _, docs, cases, _ = mk(self.tmp)
        cases[0]["evidence"] = ""
        problems, _ = bench.validate(docs, cases)
        self.assertTrue(any("sem validated_by/evidence" in p for p in problems))

    def test_gate_not_verified_without_thresholds(self):
        _, _, docs, cases, thr = mk(self.tmp)
        r = bench.evaluate(docs, cases, [finding(3), finding(4)], "calibracao")
        self.assertEqual(bench.gate(r, thr)[0], "NOT_VERIFIED")

    def test_gate_insufficient_data(self):
        _, _, docs, cases, _ = mk(self.tmp)
        thr = {"min_defects": 20, "min_negatives": 20, "recall_lower_bound_min": 0.5,
               "specificity_lower_bound_min": 0.5, "precision_pessimistic_min": 0.2}
        r = bench.evaluate(docs, cases, [finding(3), finding(4)], "calibracao")
        self.assertEqual(bench.gate(r, thr)[0], "NOT_VERIFIED")

    def test_validation_requires_lock(self):
        root, _, docs, cases, thr = mk(self.tmp)
        with self.assertRaises(bench.BenchError):
            bench.check_lock(root, cases)

    def test_lock_detects_change(self):
        root, manifest, docs, cases, _ = mk(self.tmp)
        (root / "f.py").write_text("x = 1\n", encoding="utf-8")
        manifest["frozen_files"] = ["f.py"]
        (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (root / "thresholds.json").write_text(json.dumps({
            "min_defects": 1, "min_negatives": 1, "max_span_lines": 10,
            "recall_lower_bound_min": 0.5, "specificity_lower_bound_min": 0.5,
            "precision_pessimistic_min": 0.5, "recompute_tolerance_rel": 0.01,
        }), encoding="utf-8")
        for c in cases:
            c["split"] = "validacao"
        bench.cmd_lock(root, cases, bench.load_json(root / "thresholds.json"))
        bench.check_lock(root, cases)
        cases[0]["rationale"] = "mudou depois do lock"
        with self.assertRaises(bench.BenchError):
            bench.check_lock(root, cases)

    def test_invalid_status_rejected(self):
        with self.assertRaises(bench.BenchError):
            bench.normalize_finding({"status": "OK", "line_start": 1}, "D")

    def test_stability(self):
        _, _, docs, cases, _ = mk(self.tmp)
        a = bench.evaluate(docs, cases, [finding(3), finding(4)], "calibracao")
        b = bench.evaluate(docs, cases, [finding(4)], "calibracao")
        self.assertEqual(bench.stability([a, a])["fracao"], 1.0)
        self.assertLess(bench.stability([a, b])["fracao"], 1.0)


if __name__ == "__main__":
    unittest.main()
