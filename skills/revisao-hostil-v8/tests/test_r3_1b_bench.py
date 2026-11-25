import hashlib
import json
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parents[1] / "benchmark"
sys.path.insert(0, str(BENCH_DIR))
sys.path.insert(0, str(BENCH_DIR / "adapters"))
import bench  # noqa: E402
import achados_arquivo as aa  # noqa: E402


def _valid_thr():
    return {
        "min_defects": 10,
        "min_negatives": 10,
        "recall_lower_bound_min": 0.5,
        "specificity_lower_bound_min": 0.7,
        "precision_pessimistic_min": 0.1,
        "max_span_lines": 10,
        "recompute_tolerance_rel": 0.01,
    }


def _make_env(tmp: Path):
    skill = tmp / "skill"
    root = skill / "benchmark"
    (root / "docs").mkdir(parents=True)
    (skill / "scripts" / "__pycache__").mkdir(parents=True)
    (skill / "scripts" / "a.py").write_text("x = 1\n", encoding="utf-8")
    (skill / "scripts" / "__pycache__" / "a.pyc").write_bytes(b"\x00")
    doc = root / "docs" / "d.md"
    doc.write_text("\n".join(f"L{i}" for i in range(1, 15)) + "\n", encoding="utf-8", newline="\n")
    manifest = {
        "documents": {"D": {"path": "docs/d.md", "sha256": hashlib.sha256(doc.read_bytes()).hexdigest(), "kind": "sintetico"}},
        "frozen_files": ["../scripts/"],
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    cases = [
        {"id": "D1", "document": "D", "type": "DEFECT", "domain": "cientifico", "category": "num",
         "split": "validacao", "anchor": {"line_start": 3, "line_end": 3},
         "claimed_value": 16.50, "truth_value": 16.17,
         "adjudicated": True, "validated_by": "t", "evidence": "e"},
        {"id": "D2", "document": "D", "type": "DEFECT", "domain": "cientifico", "category": "num",
         "split": "validacao", "anchor": {"line_start": 5, "line_end": 5},
         "claimed_value": 1.0, "truth_value": 0.0,
         "adjudicated": True, "validated_by": "t", "evidence": "e"},
        {"id": "D3", "document": "D", "type": "DEFECT", "domain": "cientifico", "category": "texto",
         "split": "validacao", "anchor": {"line_start": 7, "line_end": 7},
         "adjudicated": True, "validated_by": "t", "evidence": "e"},
    ]
    (root / "cases.json").write_text(json.dumps(cases), encoding="utf-8")
    (root / "thresholds.json").write_text(json.dumps(_valid_thr()), encoding="utf-8")
    return skill, root


class R31bTests(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = Path(self._t.name)

    def tearDown(self):
        self._t.cleanup()

    # --- B1: recall demonstrado ---
    def test_b1_demonstrated_within_outside_boundary_and_zero_truth(self):
        _, root = _make_env(self.tmp)
        _, _, docs, cases, _ = bench._inputs(root)
        # Dentro da tolerancia (16.17 +/- 1%) e truth=0 (abs <= 0.01)
        f1 = bench.normalize_finding({"line_start": 3, "line_end": 3, "status": "CONFIRMADO", "category": "num", "recomputed_value": 16.17 * 1.01}, "D")
        f2 = bench.normalize_finding({"line_start": 5, "line_end": 5, "status": "CONFIRMADO", "category": "num", "recomputed_value": 0.005}, "D")
        r = bench.evaluate(docs, cases, [f1, f2], "validacao", max_span_lines=5, recompute_tolerance_rel=0.01)
        self.assertEqual(r["total"]["recall_demonstrado"]["n"], 2)  # D3 nao numerico fora do denominador
        self.assertEqual(r["total"]["recall_demonstrado"]["k"], 2)
        # Fora da tolerancia
        f_out = bench.normalize_finding({"line_start": 3, "line_end": 3, "status": "CONFIRMADO", "category": "num", "recomputed_value": 17.0}, "D")
        r_out = bench.evaluate(docs, cases, [f_out], "validacao", max_span_lines=5, recompute_tolerance_rel=0.01)
        self.assertEqual(r_out["total"]["recall_demonstrado"]["k"], 0)
        self.assertEqual(r_out["achados"]["confirmado_fora_tolerancia"], 1)

    def test_b1_confirmado_sem_conta_triagem_and_out_of_span(self):
        _, root = _make_env(self.tmp)
        _, _, docs, cases, _ = bench._inputs(root)
        f_no = bench.normalize_finding({"line_start": 3, "line_end": 3, "status": "CONFIRMADO", "category": "num"}, "D")
        f_tr = bench.normalize_finding({"line_start": 5, "line_end": 5, "status": "TRIAGEM", "category": "num", "recomputed_value": 0.0}, "D")
        f_sp = bench.normalize_finding({"line_start": 1, "line_end": 10, "status": "CONFIRMADO", "category": "num", "recomputed_value": 16.17}, "D")
        r = bench.evaluate(docs, cases, [f_no, f_tr, f_sp], "validacao", max_span_lines=5, recompute_tolerance_rel=0.01)
        self.assertEqual(r["total"]["recall_demonstrado"]["k"], 0)
        self.assertEqual(r["achados"]["confirmado_sem_conta"], 1)

    def test_b1_invalid_numeric_values_rejected(self):
        for bad in (float("nan"), float("inf"), True, "16.17"):
            with self.assertRaises(bench.BenchError):
                bench.normalize_finding({"line_start": 1, "status": "CONFIRMADO", "recomputed_value": bad}, "D")

    # --- B2: achados_arquivo optional numeric fields & chaves_ignoradas ---
    def test_b2_achados_arquivo_numeric_and_ignored_keys(self):
        sha = "a" * 64
        data = {
            "document": "D", "document_sha256": sha,
            "reviewer": {"reviewer_model": "m", "session_id": "s", "saw_gabarito": False, "saw_pareceres": False, "saw_auditor_results": False},
            "findings": [{"line_start": 3, "category": "num", "status": "CONFIRMADO", "claimed_value": 16.5, "recomputed_value": 16.17, "extra_foo": 123}],
        }
        out = aa.parse_blind(data, "D", sha, 10)
        self.assertEqual(out[0]["recomputed_value"], 16.17)
        self.assertEqual(out[0]["chaves_ignoradas"], ["extra_foo"])
        # NaN rejeitado
        data["findings"][0]["recomputed_value"] = float("nan")
        with self.assertRaises(bench.BenchError):
            aa.parse_blind(data, "D", sha, 10)

    # --- B3: cmd_lock valida thresholds ---
    def test_b3_cmd_lock_rejects_invalid_max_span_and_tol(self):
        _, root = _make_env(self.tmp)
        _, _, _, cases, _ = bench._inputs(root)
        for bad_span in (0.5, "10", True, 0, -3, None):
            thr = _valid_thr()
            thr["max_span_lines"] = bad_span
            with self.assertRaises(bench.BenchError):
                bench.cmd_lock(root, cases, thr)
        for bad_tol in (0, -0.01, None, True, "0.01", float("nan")):
            thr = _valid_thr()
            thr["recompute_tolerance_rel"] = bad_tol
            with self.assertRaises(bench.BenchError):
                bench.cmd_lock(root, cases, thr)

    # --- B4: frozen_files com diretorios ---
    def test_b4_frozen_dir_expand_add_remove_modify_and_symlink(self):
        skill, root = _make_env(self.tmp)
        _, _, _, cases, thr = bench._inputs(root)
        lock = bench.cmd_lock(root, cases, thr)
        self.assertIn("../scripts/a.py", lock["frozen_files_sha256"])
        self.assertFalse(any("__pycache__" in k for k in lock["frozen_files_sha256"]))
        bench.check_lock(root, cases)
        # Arquivo acrescentado -> falha
        (skill / "scripts" / "b.py").write_text("y = 2\n", encoding="utf-8")
        with self.assertRaises(bench.BenchError):
            bench.check_lock(root, cases)
        (skill / "scripts" / "b.py").unlink()
        # Arquivo alterado -> falha
        (skill / "scripts" / "a.py").write_text("x = 2\n", encoding="utf-8")
        with self.assertRaises(bench.BenchError):
            bench.check_lock(root, cases)
        (skill / "scripts" / "a.py").write_text("x = 1\n", encoding="utf-8")
        # Arquivo removido -> falha
        (skill / "scripts" / "a.py").unlink()
        with self.assertRaises(bench.BenchError):
            bench.check_lock(root, cases)
        (skill / "scripts" / "a.py").write_text("x = 1\n", encoding="utf-8")
        # Symlink rejeitado
        link = skill / "scripts" / "sym.py"
        try:
            os.symlink(skill / "scripts" / "a.py", link)
        except (OSError, NotImplementedError):
            self.skipTest("symlink indisponivel (SKIPPED, nao PASS)")
        with self.assertRaises(bench.BenchError):
            bench.check_lock(root, cases)


if __name__ == "__main__":
    unittest.main()
