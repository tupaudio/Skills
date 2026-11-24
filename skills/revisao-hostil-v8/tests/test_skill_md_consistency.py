"""Consistência entre SKILL.md e o código/catálogos reais.

Falha se o SKILL.md afirmar algo que não existe (motor, agente implementado,
caminho de arquivo, flag de CLI) ou omitir um motor que existe.
Roda com pytest ou diretamente: python tests/test_skill_md_consistency.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "SKILL.md"


def _skill_text() -> str:
    return SKILL.read_text(encoding="utf-8")


def _row(text: str, stem: str) -> str:
    rows = [l for l in text.splitlines() if l.startswith(f"| `{stem}`")]
    assert rows, f"{stem}: sem linha na tabela de motores do SKILL.md"
    return rows[0]


def _engine_files() -> set[str]:
    return {p.stem for p in (ROOT / "scripts" / "engines").glob("motor_*.py")}


def test_frontmatter_has_name_and_description() -> None:
    text = _skill_text()
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    assert m, "SKILL.md precisa de frontmatter YAML"
    meta = yaml.safe_load(m.group(1))
    assert meta.get("name") == "revisao-hostil-v8"
    assert isinstance(meta.get("description"), str) and len(meta["description"]) > 40


def test_every_mentioned_engine_exists_or_is_declared_planned() -> None:
    text = _skill_text()
    catalog = yaml.safe_load((ROOT / "references" / "catalogo_motores.yaml").read_text(encoding="utf-8"))
    planned = {m["id"] for m in catalog["motores"] if m.get("status") == "planejado"}
    mentioned = set(re.findall(r"`(motor_[a-z_]+)`", text))
    unknown = mentioned - _engine_files() - planned
    assert not unknown, f"SKILL.md cita motores inexistentes: {sorted(unknown)}"
    # motores planejados só podem aparecer na frase de planejados
    for name in planned & mentioned:
        for line in text.splitlines():
            if f"`{name}`" in line:
                assert "planejados" in line.lower(), f"{name} citado fora do contexto 'planejado'"


def test_every_existing_engine_is_documented() -> None:
    mentioned = set(re.findall(r"`(motor_[a-z_]+)`", _skill_text()))
    missing = _engine_files() - mentioned
    assert not missing, f"Motores existentes ausentes do SKILL.md: {sorted(missing)}"


def test_engine_versions_match_code() -> None:
    text = _skill_text()
    for stem in _engine_files():
        src = (ROOT / "scripts" / "engines" / f"{stem}.py").read_text(encoding="utf-8")
        version = re.search(r'MOTOR_VERSION\s*=\s*"([^"]+)"', src).group(1)
        row = _row(text, stem)
        assert f"`{version}`" in row, f"{stem}: versão do SKILL.md diverge do código ({version})"


def test_declared_operations_exist_in_code() -> None:
    text = _skill_text()
    for stem in _engine_files():
        src = (ROOT / "scripts" / "engines" / f"{stem}.py").read_text(encoding="utf-8")
        row = _row(text, stem)
        ops = re.findall(r"`([a-z_0-9]+)`", row.split("|")[4]) if row.count("|") >= 5 else []
        for op in ops:
            assert op in src, f"{stem}: operação `{op}` do SKILL.md não existe no código"


def test_all_agents_listed_and_none_claimed_implemented() -> None:
    text = _skill_text()
    cat = yaml.safe_load((ROOT / "references" / "catalogo_agentes.yaml").read_text(encoding="utf-8"))
    for ag in cat["agentes"]:
        assert f"{ag['id']}" in text, f"agente {ag['id']} ausente do SKILL.md"
        assert ag["status"] == "planejado", (
            f"{ag['id']} mudou de status no catálogo; atualize a seção de agentes do SKILL.md"
        )


def test_profiles_listed_match_files() -> None:
    text = _skill_text()
    profiles = {p.stem for p in (ROOT / "references" / "profiles").glob("*.yaml") if p.stem != "schema_profile"}
    for name in profiles:
        assert f"`{name}`" in text, f"perfil {name} ausente do SKILL.md"


def test_referenced_paths_exist() -> None:
    paths = set(re.findall(r"`((?:scripts|references|tests|docs)/[A-Za-z0-9_./*-]+)`", _skill_text()))
    for rel in paths:
        if "*" in rel or rel.endswith("/"):
            assert (ROOT / rel.rstrip("/")).exists(), f"diretório citado não existe: {rel}"
            continue
        assert (ROOT / rel).exists(), f"caminho citado no SKILL.md não existe: {rel}"


def test_documented_cli_flags_exist() -> None:
    aud = (ROOT / "scripts" / "auditor.py").read_text(encoding="utf-8")
    for flag in ("--out", "--engineering-preset"):
        assert flag in _skill_text() and f'"{flag}"' in aud, f"flag {flag} inconsistente"


def test_states_and_severities_match_evidence_module() -> None:
    ev = (ROOT / "scripts" / "common" / "evidence.py").read_text(encoding="utf-8")
    text = _skill_text()
    for state in ("ABERTO", "EM_ANALISE", "CONFIRMADO", "NAO_VERIFICADO", "REJEITADO",
                  "FORA_DE_ESCOPO", "PATCH_PROPOSTO", "PATCH_APROVADO", "PATCH_APLICADO", "FECHADO"):
        assert f'"{state}"' in ev and state in text
    for sev in ("CRITICO", "MAIOR", "MODERADO", "MENOR", "INFORMATIVO"):
        assert f'"{sev}"' in ev and sev in text


if __name__ == "__main__":  # execução sem pytest
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as exc:
                failed += 1
                print(f"FAIL {name}: {exc}")
    sys.exit(1 if failed else 0)
