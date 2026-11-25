import json
import tempfile
import unittest
from pathlib import Path

from tests.test_benchmark import mk
import bench


class LockFrozenTests(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = Path(self._t.name)

    def tearDown(self):
        self._t.cleanup()

    def _locked(self):
        root, manifest, docs, cases, _ = mk(self.tmp)
        (self.tmp / "f.py").write_text("x = 1\n", encoding="utf-8")
        manifest["frozen_files"] = ["f.py"]
        (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        thr = {
            "min_defects": 1, "min_negatives": 1, "max_span_lines": 10,
            "recall_lower_bound_min": 0.5, "specificity_lower_bound_min": 0.5,
            "precision_pessimistic_min": 0.5, "recompute_tolerance_rel": 0.01,
        }
        (root / "thresholds.json").write_text(json.dumps(thr), encoding="utf-8")
        for c in cases:
            c["split"] = "validacao"
        bench.cmd_lock(root, cases, thr)
        return root, cases

    def test_unchanged_passes(self):
        root, cases = self._locked()
        bench.check_lock(root, cases)

    def test_changed_frozen_file_is_rejected(self):
        root, cases = self._locked()
        (self.tmp / "f.py").write_text("x = 2\n", encoding="utf-8")
        with self.assertRaises(bench.BenchError):
            bench.check_lock(root, cases)

    def test_removed_frozen_file_is_rejected(self):
        root, cases = self._locked()
        (self.tmp / "f.py").unlink()
        with self.assertRaises(bench.BenchError):
            bench.check_lock(root, cases)

    def test_lock_requires_frozen_files_in_manifest(self):
        root, manifest, docs, cases, thr = mk(self.tmp)
        thr = {k: 0.5 for k in bench.THRESHOLD_KEYS}
        for c in cases:
            c["split"] = "validacao"
        with self.assertRaises(bench.BenchError):
            bench.cmd_lock(root, cases, thr)


if __name__ == "__main__":
    unittest.main()
