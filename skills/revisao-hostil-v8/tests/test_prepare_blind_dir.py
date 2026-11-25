import contextlib
import hashlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "benchmark"
sys.path.insert(0, str(ROOT))
import prepare_blind_dir as pbd  # noqa: E402

DOC_TEXT = "# Titulo\nTexto neutro do manuscrito.\n"
DOC_SHA = hashlib.sha256(DOC_TEXT.encode("utf-8")).hexdigest()


def make_skill(tmp: Path, doc_sha=DOC_SHA):
    skill = tmp / "skill"
    (skill / "scripts" / "engines").mkdir(parents=True)
    (skill / "scripts" / "__pycache__").mkdir()
    (skill / "benchmark").mkdir()
    (skill / "SKILL.md").write_text("# Skill\nUsa o auditor.\n", encoding="utf-8")
    (skill / "scripts" / "auditor.py").write_text("x = 1\n", encoding="utf-8")
    (skill / "scripts" / "engines" / "m.py").write_text("y = 2\n", encoding="utf-8")
    (skill / "scripts" / "__pycache__" / "a.cpython-312.pyc").write_bytes(b"\x00\x01")
    (skill / "benchmark" / "manifest.json").write_text(
        '{"documents": {"A04": {"sha256": "%s"}}}' % doc_sha, encoding="utf-8")
    outside = tmp / "outside"
    outside.mkdir()
    doc = outside / "artigo04.md"
    doc.write_text(DOC_TEXT, encoding="utf-8", newline="\n")
    return skill, doc


class PrepareBlindDirTests(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = Path(self._t.name)
        self.skill, self.doc = make_skill(self.tmp)
        self.dest = self.tmp / "blind"

    def tearDown(self):
        self._t.cleanup()

    def _prep(self, **kw):
        args = dict(skill_dir=self.skill, doc=self.doc, dest=self.dest, doc_id="A04")
        args.update(kw)
        return pbd.prepare(**args)

    def test_ok_copies_only_allowed(self):
        rep = self._prep()
        got = {p.relative_to(self.dest).as_posix()
               for p in self.dest.rglob("*") if p.is_file()}
        self.assertEqual(got, {"SKILL.md", "scripts/auditor.py",
                               "scripts/engines/m.py", "artigo04.md"})
        self.assertEqual(rep["document"]["sha256"], DOC_SHA)
        self.assertEqual(rep["document"]["lines_splitlines"], 2)
        self.assertIsNotNone(rep["auditor_py_sha256"])

    def test_pycache_not_copied(self):
        self._prep()
        self.assertFalse(any("__pycache__" in str(p) for p in self.dest.rglob("*")))

    def test_hash_mismatch_blocks_and_creates_nothing(self):
        with self.assertRaises(pbd.PrepError):
            self._prep(doc_id=None, expected_sha="0" * 64)
        self.assertFalse(self.dest.exists())

    def test_manifest_placeholder_rejected(self):
        (self.skill / "benchmark" / "manifest.json").write_text(
            '{"documents": {"A04": {"sha256": "PREENCHER"}}}', encoding="utf-8")
        with self.assertRaises(pbd.PrepError):
            self._prep()

    def test_expected_and_manifest_must_agree(self):
        with self.assertRaises(pbd.PrepError):
            self._prep(expected_sha="1" * 64)

    def test_requires_some_expected_hash(self):
        with self.assertRaises(pbd.PrepError):
            self._prep(doc_id=None, expected_sha=None)

    def test_dest_inside_git_repo_rejected(self):
        (self.tmp / "repo" / ".git").mkdir(parents=True)
        with self.assertRaises(pbd.PrepError):
            self._prep(dest=self.tmp / "repo" / "blind")

    def test_dest_inside_skill_rejected(self):
        with self.assertRaises(pbd.PrepError):
            self._prep(dest=self.skill / "blind")

    def test_dest_not_empty_rejected(self):
        self.dest.mkdir()
        (self.dest / "x.txt").write_text("x", encoding="utf-8")
        with self.assertRaises(pbd.PrepError):
            self._prep()

    def test_empty_existing_dest_ok(self):
        self.dest.mkdir()
        self._prep()
        self.assertTrue((self.dest / "artigo04.md").is_file())

    def test_forbidden_name_in_scripts(self):
        (self.skill / "scripts" / "cases_old.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(pbd.PrepError):
            self._prep()
        self.assertFalse(self.dest.exists())

    def test_allow_overrides_name_and_is_reported(self):
        (self.skill / "scripts" / "cases_old.json").write_text("{}", encoding="utf-8")
        rep = self._prep(allow=["scripts/cases_old.json"])
        self.assertEqual(rep["allowed_names_used"], ["scripts/cases_old.json"])

    def test_block_is_not_lock(self):
        (self.skill / "scripts" / "block_utils.py").write_text("z = 3\n", encoding="utf-8")
        self._prep()  # 'block' nao e o token 'lock'

    def test_forbidden_dir_in_scripts(self):
        (self.skill / "scripts" / "results").mkdir()
        (self.skill / "scripts" / "results" / "a.txt").write_text("a", encoding="utf-8")
        with self.assertRaises(pbd.PrepError):
            self._prep()

    def test_content_marker_in_scripts(self):
        (self.skill / "scripts" / "auditor.py").write_text("# ver B04-001\n", encoding="utf-8")
        with self.assertRaises(pbd.PrepError):
            self._prep()
        self.assertFalse(self.dest.exists())

    def test_content_marker_in_document(self):
        text = DOC_TEXT + "ver PREREGISTRO\n"
        self.doc.write_text(text, encoding="utf-8", newline="\n")
        sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
        with self.assertRaises(pbd.PrepError):
            self._prep(doc_id=None, expected_sha=sha)

    def test_forbidden_include(self):
        with self.assertRaises(pbd.PrepError):
            self._prep(includes=("benchmark",))

    def test_include_extra_dir(self):
        (self.skill / "schemas").mkdir()
        (self.skill / "schemas" / "s.json").write_text("{}", encoding="utf-8")
        self._prep(includes=("scripts", "schemas"))
        self.assertTrue((self.dest / "schemas" / "s.json").is_file())

    def test_symlink_rejected(self):
        link = self.skill / "scripts" / "link.py"
        try:
            os.symlink(self.skill / "scripts" / "auditor.py", link)
        except (OSError, NotImplementedError):
            self.skipTest("symlink indisponivel nesta plataforma (SKIPPED, nao PASS)")
        with self.assertRaises(pbd.PrepError):
            self._prep()

    def test_record_out_inside_dest_rejected(self):
        with self.assertRaises(pbd.PrepError):
            self._prep(record_out=self.dest / "rec.json")

    def test_cli_exit_codes(self):
        base = ["--skill-dir", str(self.skill), "--doc", str(self.doc),
                "--doc-id", "A04", "--dest", str(self.dest)]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(pbd.main(base), 0)
        self.assertIn(DOC_SHA, out.getvalue())
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(pbd.main(base), 2)  # destino agora nao esta vazio
        self.assertIn("BLOQUEADO", err.getvalue())


if __name__ == "__main__":
    unittest.main()
