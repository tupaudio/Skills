import tempfile
import unittest
from pathlib import Path

from tests.test_benchmark import mk, finding
import bench


class DetectableByTests(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = Path(self._t.name)

    def tearDown(self):
        self._t.cleanup()

    def _setup(self):
        _, _, docs, cases, _ = mk(self.tmp)
        cases[0]["detectable_by"] = ["afirmacao_absoluta"]  # D1, linha 4
        return docs, cases

    def test_wrong_category_counts_only_for_line_recall(self):
        docs, cases = self._setup()
        r = bench.evaluate(docs, cases, [finding(4)], "calibracao")
        self.assertEqual(r["total"]["recall"]["k"], 1)
        self.assertEqual(r["total"]["recall_categoria"]["n"], 1)
        self.assertEqual(r["total"]["recall_categoria"]["k"], 0)

    def test_right_category_counts(self):
        docs, cases = self._setup()
        f = dict(finding(4), category="afirmacao_absoluta")
        r = bench.evaluate(docs, cases, [f], "calibracao")
        self.assertEqual(r["total"]["recall_categoria"]["k"], 1)
        self.assertEqual(r["total"]["recall_categoria"]["n"], 1)

    def test_defect_without_detectable_by_is_not_in_denominator(self):
        docs, cases = self._setup()
        r = bench.evaluate(docs, cases, [], "calibracao")
        self.assertEqual(r["total"]["recall"]["n"], 2)
        self.assertEqual(r["total"]["recall_categoria"]["n"], 1)

    def test_validate_rejects_bad_detectable_by(self):
        docs, cases = self._setup()
        cases[0]["detectable_by"] = "afirmacao_absoluta"  # string, nao lista
        problems, _ = bench.validate(docs, cases)
        self.assertTrue(any("detectable_by" in p for p in problems))

    def test_validate_rejects_detectable_by_on_negative_control(self):
        docs, cases = self._setup()
        neg = next(c for c in cases if c["type"] == "NEGATIVE_CONTROL")
        neg["detectable_by"] = ["x"]
        problems, _ = bench.validate(docs, cases)
        self.assertTrue(any("so se aplica a DEFECT" in p for p in problems))


if __name__ == "__main__":
    unittest.main()
