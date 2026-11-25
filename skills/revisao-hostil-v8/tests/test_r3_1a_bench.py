import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parents[1] / "benchmark"
sys.path.insert(0, str(BENCH_DIR))
import bench  # noqa: E402
from tests.test_benchmark import mk, finding  # noqa: E402


def _make_root(tmp: Path, include_doc_b=True, max_span=5):
    docs_dir = tmp / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    adapters_dir = tmp / "adapters"
    adapters_dir.mkdir(parents=True, exist_ok=True)
    text_a = "\n".join(f"linha A{i}" for i in range(1, 16)) + "\n"
    pa = docs_dir / "a.md"
    pa.write_text(text_a, encoding="utf-8", newline="\n")
    manifest = {
        "documents": {
            "A": {"path": "docs/a.md", "sha256": hashlib.sha256(pa.read_bytes()).hexdigest(), "kind": "sintetico"},
        },
        "frozen_files": ["manifest.json"],
    }
    if include_doc_b:
        text_b = "\n".join(f"linha B{i}" for i in range(1, 10)) + "\n"
        pb = docs_dir / "b.md"
        pb.write_text(text_b, encoding="utf-8", newline="\n")
        manifest["documents"]["B"] = {
            "path": "docs/b.md", "sha256": hashlib.sha256(pb.read_bytes()).hexdigest(), "kind": "sintetico"
        }
    (tmp / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    cases = [
        {"id": "D1", "document": "A", "type": "DEFECT", "domain": "cientifico", "category": "num",
         "split": "calibracao", "anchor": {"line_start": 3, "line_end": 3},
         "adjudicated": True, "validated_by": "t", "evidence": "e"},
        {"id": "N1", "document": "A", "type": "NEGATIVE_CONTROL", "domain": "cientifico", "category": "geral",
         "split": "calibracao", "anchor": {"line_start": 6, "line_end": 6},
         "adjudicated": True, "validated_by": "t", "evidence": "e"},
        {"id": "I1", "document": "A", "type": "INCONCLUSIVE", "domain": "cientifico", "category": "ext",
         "split": "calibracao", "anchor": {"line_start": 7, "line_end": 7},
         "adjudicated": True, "validated_by": "t", "evidence": "e"},
    ]
    (tmp / "cases.json").write_text(json.dumps(cases), encoding="utf-8")
    thr = {k: None for k in bench.THRESHOLD_KEYS}
    thr["max_span_lines"] = max_span
    (tmp / "thresholds.json").write_text(json.dumps(thr), encoding="utf-8")
    return tmp


class R31aBenchTests(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = Path(self._t.name)

    def tearDown(self):
        self._t.cleanup()

    # --- PASSO 1: ponto de entrada (dupla importacao) ---
    def test_p1_subprocess_bench_error_isolated_and_non_bench_error_fails(self):
        root = _make_root(self.tmp)
        (root / "adapters" / "syn.py").write_text(
            "from bench import BenchError\n"
            "def fail_b(path, did):\n"
            "    if did == 'B': raise BenchError('B bloqueado')\n"
            "    return [{'line_start': 3, 'line_end': 3, 'status': 'CONFIRMADO', 'category': 'num'}]\n"
            "def crash(path, did):\n"
            "    raise RuntimeError('erro inesperado')\n",
            encoding="utf-8",
        )
        out_sub = root / "out_sub.json"
        p = subprocess.run(
            [sys.executable, str(BENCH_DIR / "bench.py"), "--root", str(root),
             "run", "--split", "calibracao", "--adapter", "syn:fail_b", "--out", str(out_sub)],
            capture_output=True, text=True,
        )
        self.assertEqual(p.returncode, 3, msg=p.stdout + p.stderr)
        self.assertNotIn("Traceback", p.stderr)
        rep_sub = json.loads(out_sub.read_text(encoding="utf-8"))
        self.assertEqual(rep_sub["documentos"]["B"]["status"], "RESULTADO_INCOMPATIVEL")
        self.assertEqual(rep_sub["resultado"]["detected_ids"], ["D1"])

        # Mesmo cenario via import bench; bench.main(...)
        out_mod = root / "out_mod.json"
        rc_mod = bench.main(["--root", str(root), "run", "--split", "calibracao",
                             "--adapter", "syn:fail_b", "--out", str(out_mod)])
        self.assertEqual(rc_mod, 3)
        rep_mod = json.loads(out_mod.read_text(encoding="utf-8"))
        self.assertEqual(rep_mod["resultado"]["detected_ids"], rep_sub["resultado"]["detected_ids"])
        self.assertEqual(rep_mod["documentos"]["B"]["status"], "RESULTADO_INCOMPATIVEL")

        # Exception nao-BenchError nao e mascarada
        p_crash = subprocess.run(
            [sys.executable, str(BENCH_DIR / "bench.py"), "--root", str(root),
             "run", "--split", "calibracao", "--adapter", "syn:crash"],
            capture_output=True, text=True,
        )
        self.assertNotEqual(p_crash.returncode, 0)
        self.assertIn("RuntimeError", p_crash.stderr)

    # --- PASSO 2: limite de span ---
    def test_p2_span_limit_boundary_and_null_rejected(self):
        root = _make_root(self.tmp, include_doc_b=False, max_span=5)
        _, _, docs, cases, thr = bench._inputs(root)
        # span = 5 (linhas 1..5, toca D1 em L3) -> aceito
        f_ok = bench.normalize_finding({"line_start": 1, "line_end": 5, "status": "CONFIRMADO", "category": "num"}, "A")
        r_ok = bench.evaluate(docs, cases, [f_ok], "calibracao", max_span_lines=5)
        self.assertEqual(r_ok["detected_ids"], ["D1"])
        self.assertEqual(r_ok["achados"]["nao_localizado_span"], 0)
        # span = 6 (linhas 1..6, toca D1 e N1) -> descartado, nao detecta D1, nao penaliza N1, conta no pess
        f_big = bench.normalize_finding({"line_start": 1, "line_end": 6, "status": "CONFIRMADO", "category": "num"}, "A")
        r_big = bench.evaluate(docs, cases, [f_big], "calibracao", max_span_lines=5)
        self.assertEqual(r_big["detected_ids"], [])
        self.assertEqual(r_big["neg_flagged_ids"], [])
        self.assertEqual(r_big["achados"]["nao_localizado_span"], 1)
        self.assertEqual(r_big["achados"]["nao_localizado_span_por_documento"]["A"], 1)
        self.assertEqual(r_big["precisao_pessimista"], 0.0)
        # max_span_lines null -> BenchError
        with self.assertRaises(bench.BenchError):
            bench.parse_max_span({"max_span_lines": None})

    # --- PASSO 3: contagem simetrica ---
    def test_p3_symmetric_counting_and_multi_label(self):
        root = _make_root(self.tmp, include_doc_b=False, max_span=10)
        _, _, docs, cases, _ = bench._inputs(root)
        # 1. Toca D1 (L3) e N1 (L6)
        f_dn = bench.normalize_finding({"line_start": 3, "line_end": 6, "status": "CONFIRMADO", "category": "x"}, "A")
        r1 = bench.evaluate(docs, cases, [f_dn], "calibracao", max_span_lines=10)
        self.assertEqual(r1["detected_ids"], ["D1"])
        self.assertEqual(r1["neg_flagged_ids"], ["N1"])
        self.assertEqual(len(r1["achados_multi_rotulo"]), 1)
        # 2. CONFIRMADO que toca N1 (L6) e I1 (L7) -> ambos contados
        f_ni = bench.normalize_finding({"line_start": 6, "line_end": 7, "status": "CONFIRMADO", "category": "x"}, "A")
        r2 = bench.evaluate(docs, cases, [f_ni], "calibracao", max_span_lines=10)
        self.assertEqual(r2["neg_flagged_ids"], ["N1"])
        self.assertEqual(r2["total"]["excesso_confianca_inconclusivos"]["k"], 1)
        self.assertEqual(len(r2["achados_multi_rotulo"]), 1)
        # 3. TRIAGEM que toca I1 (L7) -> nao conta excesso
        f_it = bench.normalize_finding({"line_start": 7, "line_end": 7, "status": "TRIAGEM", "category": "x"}, "A")
        r3 = bench.evaluate(docs, cases, [f_it], "calibracao", max_span_lines=10)
        self.assertEqual(r3["total"]["excesso_confianca_inconclusivos"]["k"], 0)
        # 4. Linha sem rotulo (L12)
        f_un = bench.normalize_finding({"line_start": 12, "line_end": 12, "status": "TRIAGEM", "category": "x"}, "A")
        r4 = bench.evaluate(docs, cases, [f_un], "calibracao", max_span_lines=10)
        self.assertEqual(r4["achados"]["sem_rotulo"], 1)
        self.assertEqual(r4["total"]["recall"]["k"], 0)

    # --- PASSO 4: ancoras multiplas e colisao ---
    def test_p4_multiple_anchors_and_collision_warning(self):
        root = _make_root(self.tmp, include_doc_b=False, max_span=5)
        _, _, docs, cases, thr = bench._inputs(root)
        # Trocar D1 para 2 ancoras (L3 e L10)
        cases[0].pop("anchor")
        cases[0]["anchors"] = [{"line_start": 3, "line_end": 3}, {"line_start": 10, "line_end": 10}]
        probs, warns = bench.validate(docs, cases, thr)
        self.assertEqual(probs, [])
        # Tocado na 2a ancora conta 1; tocado nas duas tambem conta 1
        f3 = bench.normalize_finding({"line_start": 3, "line_end": 3, "status": "CONFIRMADO", "category": "num"}, "A")
        f10 = bench.normalize_finding({"line_start": 10, "line_end": 10, "status": "CONFIRMADO", "category": "num"}, "A")
        self.assertEqual(bench.evaluate(docs, cases, [f10], "calibracao", max_span_lines=5)["total"]["recall"]["k"], 1)
        self.assertEqual(bench.evaluate(docs, cases, [f3, f10], "calibracao", max_span_lines=5)["total"]["recall"]["k"], 1)
        # anchor + anchors juntos -> erro
        bad1 = [dict(cases[0], anchor={"line_start": 3})]
        self.assertTrue(bench.validate(docs, bad1, thr)[0])
        # anchors vazio -> erro
        bad2 = [dict(cases[0], anchors=[])]
        self.assertTrue(bench.validate(docs, bad2, thr)[0])
        # colisao entre casos -> aviso
        cases[1]["anchor"] = {"line_start": 10, "line_end": 10}
        _, warns_col = bench.validate(docs, cases, thr)
        self.assertTrue(any("colisao" in w and "D1" in w and "N1" in w for w in warns_col))

    # --- PASSO 5: documento sem casos ---
    def test_p5_document_without_cases_discarded_from_precision(self):
        root = _make_root(self.tmp, include_doc_b=True, max_span=5)
        _, _, docs, cases, _ = bench._inputs(root)
        fa = bench.normalize_finding({"line_start": 3, "line_end": 3, "status": "CONFIRMADO", "category": "num"}, "A")
        fb1 = bench.normalize_finding({"line_start": 1, "line_end": 1, "status": "TRIAGEM", "category": "x"}, "B")
        fb2 = bench.normalize_finding({"line_start": 2, "line_end": 2, "status": "TRIAGEM", "category": "x"}, "B")
        r_only_a = bench.evaluate(docs, cases, [fa], "calibracao", max_span_lines=5)
        r_with_b = bench.evaluate(docs, cases, [fa, fb1, fb2], "calibracao", max_span_lines=5)
        self.assertEqual(r_with_b["precisao_pessimista"], r_only_a["precisao_pessimista"])
        self.assertEqual(r_with_b["precisao_otimista"], r_only_a["precisao_otimista"])
        self.assertEqual(r_with_b["achados"]["descartados_documento_sem_casos"], {"B": 2})


if __name__ == "__main__":
    unittest.main()
