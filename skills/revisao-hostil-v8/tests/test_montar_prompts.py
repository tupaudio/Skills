"""Testes unitarios para benchmark/prompts/montar_prompts.py (dados sinteticos)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "benchmark" / "prompts"
if str(PROMPTS_DIR) not in sys.path:
    sys.path.insert(0, str(PROMPTS_DIR))

import montar_prompts as mp  # noqa: E402

REAL_BLOCKS_DIR = PROMPTS_DIR / "revisor_v0.2"


def _make_plan(tmp: Path, max_linhas=10, max_achados=40, seed=7, include_c=True):
    f1 = tmp / "doc1_num.txt"
    f1.write_text("1: Linha sintetica alfa\n2: Valor = 42\n", encoding="utf-8")
    execs = [
        {"doc_id": "D1", "arquivo_numerado": str(f1), "modelo": "M1", "sessao": "S1A", "braco": "A", "rodada": 1},
    ]
    if include_c:
        execs.append(
            {"doc_id": "D1", "arquivo_numerado": str(f1), "modelo": "M1", "sessao": "S1C", "braco": "C", "rodada": 1}
        )
    plan = {"ordem_seed": seed, "execucoes": execs}
    if max_linhas is not ...:
        plan["max_linhas"] = max_linhas
    if max_achados is not ...:
        plan["max_achados"] = max_achados
    p = tmp / "plano.json"
    p.write_text(json.dumps(plan), encoding="utf-8")
    return p, f1


class TestMontarPrompts(unittest.TestCase):
    def test_build_differs_only_in_method_block(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            mp.build_models(REAL_BLOCKS_DIR, out)
            a_lines = (out / "revisor_A_v0.2.txt").read_text(encoding="utf-8").splitlines()
            c_lines = (out / "revisor_C_v0.2.txt").read_text(encoding="utf-8").splitlines()
            b1 = (REAL_BLOCKS_DIR / "bloco1_cabecalho.txt").read_text(encoding="utf-8").splitlines()
            b4 = (REAL_BLOCKS_DIR / "bloco4_saida.txt").read_text(encoding="utf-8").splitlines()
            self.assertEqual(a_lines[: len(b1)], b1)
            self.assertEqual(c_lines[: len(b1)], b1)
            self.assertEqual(a_lines[-len(b4) :], b4)
            self.assertEqual(c_lines[-len(b4) :], b4)
            self.assertNotEqual(a_lines, c_lines)

    def test_crlf_normalized_and_bom_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            bdir = Path(td) / "blocos"
            bdir.mkdir()
            for name in mp.BLOCK_NAMES:
                raw = (REAL_BLOCKS_DIR / name).read_text(encoding="utf-8").replace("\n", "\r\n")
                (bdir / name).write_bytes(raw.encode("utf-8"))
            out = Path(td) / "out"
            mp.build_models(bdir, out)
            self.assertNotIn(b"\r\n", (out / "revisor_A_v0.2.txt").read_bytes())

            # Inject BOM in bloco1 -> must raise PromptBuildError
            b1_bytes = (bdir / "bloco1_cabecalho.txt").read_bytes()
            (bdir / "bloco1_cabecalho.txt").write_bytes(mp.UTF8_BOM + b1_bytes)
            with self.assertRaises(mp.PromptBuildError):
                mp.build_models(bdir, out)

    def test_fill_validations(self):
        tpl = "Doc={{DOC_ID}} Max={{MAX_LINHAS}}\n"
        # Missing key
        with self.assertRaises(mp.PromptBuildError):
            mp.fill_template_text(tpl, [("DOC_ID", "D1")])
        # Unknown key
        with self.assertRaises(mp.PromptBuildError):
            mp.fill_template_text(tpl, [("DOC_ID", "D1"), ("MAX_LINHAS", "10"), ("EXTRA", "1")])
        # Duplicate key
        with self.assertRaises(mp.PromptBuildError):
            mp.fill_template_text(tpl, [("DOC_ID", "D1"), ("DOC_ID", "D2"), ("MAX_LINHAS", "10")])
        # Value with {{
        with self.assertRaises(mp.PromptBuildError):
            mp.fill_template_text(tpl, [("DOC_ID", "D1{{X}}"), ("MAX_LINHAS", "10")])
        # Value with newline
        with self.assertRaises(mp.PromptBuildError):
            mp.fill_template_text(tpl, [("DOC_ID", "D1\nL2"), ("MAX_LINHAS", "10")])
        # Leftover {{ in template
        with self.assertRaises(mp.PromptBuildError):
            mp.fill_template_text("Doc={{DOC_ID}} {{bad}}\n", [("DOC_ID", "D1")])

    def test_batch_invalid_max_linhas_and_incomplete_pair(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            for bad in (..., None, 0, True, "10"):
                p, _ = _make_plan(tmp, max_linhas=bad)
                with self.assertRaises(mp.PromptBuildError):
                    mp.run_batch(p, tmp / "out_bad", dir_blocos=REAL_BLOCKS_DIR)
            # Incomplete A/C pair
            p_inc, _ = _make_plan(tmp, include_c=False)
            with self.assertRaises(mp.PromptBuildError):
                mp.run_batch(p_inc, tmp / "out_inc", dir_blocos=REAL_BLOCKS_DIR)

    def test_batch_refuses_output_inside_git_repo(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            p, _ = _make_plan(tmp)
            git_dir = Path(__file__).resolve().parents[1] / "benchmark" / "tmp_forbidden_out"
            with self.assertRaises(mp.PromptBuildError):
                mp.run_batch(p, git_dir, dir_blocos=REAL_BLOCKS_DIR)

    def test_batch_order_seed_sha_and_no_manuscript_text(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            f1 = tmp / "d1.txt"
            f2 = tmp / "d2.txt"
            f1.write_text("1: SEGREDO_MANUSCRITO_ALFA\n", encoding="utf-8")
            f2.write_text("1: SEGREDO_MANUSCRITO_BETA\n", encoding="utf-8")
            execs = [
                {"doc_id": "D1", "arquivo_numerado": str(f1), "modelo": "M1", "sessao": "S1A", "braco": "A", "rodada": 1},
                {"doc_id": "D1", "arquivo_numerado": str(f1), "modelo": "M1", "sessao": "S1C", "braco": "C", "rodada": 1},
                {"doc_id": "D2", "arquivo_numerado": str(f2), "modelo": "M1", "sessao": "S2A", "braco": "A", "rodada": 1},
                {"doc_id": "D2", "arquivo_numerado": str(f2), "modelo": "M1", "sessao": "S2C", "braco": "C", "rodada": 1},
            ]
            p1 = tmp / "p1.json"
            p2 = tmp / "p2.json"
            p1.write_text(json.dumps({"max_linhas": 10, "max_achados": 40, "ordem_seed": 123, "execucoes": execs}), encoding="utf-8")
            p2.write_text(json.dumps({"max_linhas": 10, "max_achados": 40, "ordem_seed": 999, "execucoes": execs}), encoding="utf-8")

            out1a = tmp / "out1a"
            out1b = tmp / "out1b"
            out2 = tmp / "out2"
            idx1a = mp.run_batch(p1, out1a, dir_blocos=REAL_BLOCKS_DIR)
            idx1b = mp.run_batch(p1, out1b, dir_blocos=REAL_BLOCKS_DIR)
            idx2 = mp.run_batch(p2, out2, dir_blocos=REAL_BLOCKS_DIR)

            ord1a = [e["sessao"] for e in idx1a["execucoes"]]
            ord1b = [e["sessao"] for e in idx1b["execucoes"]]
            ord2 = [e["sessao"] for e in idx2["execucoes"]]
            self.assertEqual(ord1a, ord1b)
            self.assertNotEqual(ord1a, ord2)

            # Verify INDICE.json hashes match written files and contain NO manuscript text
            raw_idx = (out1a / "INDICE.json").read_text(encoding="utf-8")
            self.assertNotIn("SEGREDO_MANUSCRITO", raw_idx)
            for e in idx1a["execucoes"]:
                pf = out1a / e["arquivo_prompt"]
                self.assertEqual(mp.sha256_file(pf), e["sha256_prompt"])
                self.assertNotIn("{{", pf.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
