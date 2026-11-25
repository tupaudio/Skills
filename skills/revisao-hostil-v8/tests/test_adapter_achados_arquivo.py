import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "benchmark"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "adapters"))
import bench  # noqa: E402
import achados_arquivo as aa  # noqa: E402

SHA = "a" * 64


def good():
    return {
        "document": "D", "document_sha256": SHA,
        "reviewer": {"reviewer_model": "m", "session_id": "s1",
                     "saw_gabarito": False, "saw_pareceres": False,
                     "saw_auditor_results": False},
        "findings": [{"line_start": 3, "category": "x", "status": "TRIAGEM"}],
    }


def parse(d, sha=SHA, n=10):
    return aa.parse_blind(d, "D", sha, n)


class BlindAdapterTests(unittest.TestCase):
    def test_ok(self):
        out = parse(good())
        self.assertEqual(out[0]["line_start"], 3)
        self.assertEqual(out[0]["line_end"], 3)

    def test_hash_mismatch(self):
        with self.assertRaises(bench.BenchError):
            parse(good(), sha="b" * 64)

    def test_not_blind_rejected(self):
        for flag in aa.BLIND_FLAGS:
            d = good()
            d["reviewer"][flag] = True
            with self.assertRaises(bench.BenchError):
                parse(d)

    def test_missing_flag_rejected(self):
        d = good()
        del d["reviewer"]["saw_pareceres"]
        with self.assertRaises(bench.BenchError):
            parse(d)

    def test_wrong_document(self):
        d = good()
        d["document"] = "OUTRO"
        with self.assertRaises(bench.BenchError):
            parse(d)

    def test_line_out_of_range(self):
        d = good()
        d["findings"][0]["line_start"] = 99
        with self.assertRaises(bench.BenchError):
            parse(d)

    def test_bool_is_not_a_line(self):
        d = good()
        d["findings"][0]["line_start"] = True
        with self.assertRaises(bench.BenchError):
            parse(d)

    def test_unknown_status(self):
        d = good()
        d["findings"][0]["status"] = "OK"
        with self.assertRaises(bench.BenchError):
            parse(d)

    def test_missing_findings(self):
        d = good()
        del d["findings"]
        with self.assertRaises(bench.BenchError):
            parse(d)


if __name__ == "__main__":
    unittest.main()
