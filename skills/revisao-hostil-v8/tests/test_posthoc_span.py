import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "benchmark"
sys.path.insert(0, str(ROOT))
import bench  # noqa: E402
import posthoc_span as ps  # noqa: E402
from tests.test_benchmark import mk, finding  # noqa: E402


class PosthocSpanTests(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = Path(self._t.name)

    def tearDown(self):
        self._t.cleanup()

    def test_span_5_kept_and_span_6_discarded(self):
        f5 = {"document": "A04", "line_start": 10, "line_end": 14, "status": "TRIAGEM", "category": "x"}
        f6 = {"document": "A04", "line_start": 10, "line_end": 15, "status": "TRIAGEM", "category": "x"}
        kept, drop_doc, drop_span = ps.filter_findings([f5, f6], doc_id="A04", max_span=5)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["line_end"], 14)
        self.assertEqual(drop_doc, 0)
        self.assertEqual(drop_span, 1)

    def test_wrong_document_discarded(self):
        f_a03 = {"document": "A03", "line_start": 1, "line_end": 1, "status": "TRIAGEM", "category": "x"}
        f_a04 = {"document": "A04", "line_start": 1, "line_end": 1, "status": "TRIAGEM", "category": "x"}
        kept, drop_doc, drop_span = ps.filter_findings([f_a03, f_a04], doc_id="A04", max_span=5)
        self.assertEqual(len(kept), 1)
        self.assertEqual(drop_doc, 1)
        self.assertEqual(drop_span, 0)

    def test_evaluate_posthoc_does_not_mutate_bench_evaluate(self):
        _, _, docs, cases, _ = mk(self.tmp)
        raw = [finding(4, "D")]
        direct = bench.evaluate(docs, cases, raw, "calibracao")
        ph = ps.evaluate_posthoc(docs, cases, raw, split="calibracao", doc_id="D", max_span=5)
        self.assertEqual(ph["recall"], direct["total"]["recall"]["valor"])
        self.assertEqual(ph["especificidade"], direct["total"]["especificidade"]["valor"])
        self.assertEqual(ph["descartados_span"], 0)
        self.assertEqual(ph["descartados_doc"], 0)

    def test_collect_builtin_adapters_path(self):
        root, _, docs, _, _ = mk(self.tmp)
        nothing = ps._collect_builtin_or_estrutural(docs, bench.load_adapter("builtin:nothing", root))
        every = ps._collect_builtin_or_estrutural(docs, bench.load_adapter("builtin:every_line", root))
        self.assertEqual(nothing, [])
        self.assertGreater(len(every), 0)


if __name__ == "__main__":
    unittest.main()
