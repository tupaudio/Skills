#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Gerador reproduzível de relatórios de auditoria, cobertura, manifesto e SHA256SUMS."""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.common.provenance import build_run_manifest, save_run_manifest
from scripts.common.schema_validator import validate_contract


def is_clean_file(p: pathlib.Path) -> bool:
    parts = set(p.relative_to(ROOT).parts)
    if "__pycache__" in parts or ".pytest_cache" in parts or ".git" in parts:
        return False
    if p.suffix == ".pyc" or p.name in ("SHA256SUMS", ".coverage"):
        return False
    return p.is_file()


def main() -> None:
    rep_dir = ROOT / "relatorios_execucao"
    rep_dir.mkdir(exist_ok=True)

    # 1. pytest -v + coverage
    p_test = subprocess.run(
        [sys.executable, "-m", "pytest", "-v", "--cov=scripts", "--cov-report=term-missing"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    (rep_dir / "pytest_verbose.txt").write_text(p_test.stdout + "\n" + p_test.stderr, encoding="utf-8")
    assert p_test.returncode == 0, f"pytest falhou:\n{p_test.stdout}\n{p_test.stderr}"

    # 2. Smoke tests via CLI com validação de schema
    smoke_lines: list[str] = []
    smoke_cases = [
        ("motor_matematico", ["scripts/engines/motor_matematico.py"], {"operation": "plug_in", "expression": "2*x+1", "substitutions": {"x": 5}, "reported_value": 11}),
        ("motor_dimensional", ["scripts/engines/motor_dimensional.py"], {"operation": "equation_homogeneity", "lhs": "F", "rhs": "m*a", "variable_units": {"F": "N", "m": "kg", "a": "m/s^2"}}),
        ("motor_consistencia_cruzada", ["scripts/engines/motor_consistencia_cruzada.py"], {"quantity_id": "T_max", "observations": [{"source_type": "codigo", "location": "sim.py", "value": 78.4, "unit": "°C"}, {"source_type": "texto", "location": "p.10", "value": 82.4, "unit": "°C"}]}),
        ("motor_etica", ["scripts/engines/motor_etica.py"], {"operation": "screen_ethics_declarations", "text": "Sem conflito de interesses e financiamento CNPq.", "involves_humans": False}),
    ]
    for name, cmd, payload in smoke_cases:
        proc = subprocess.run([sys.executable] + cmd, cwd=ROOT, input=json.dumps(payload), text=True, capture_output=True)
        assert proc.returncode == 0, f"{name} CLI falhou: {proc.stderr}"
        out = json.loads(proc.stdout)
        validate_contract(out, "schema_motor.json")
        smoke_lines.append(f"[OK] {name} CLI -> status={out['status']}, achados={len(out['achados'])}, schema_motor.json=VALID")

    p_aud = subprocess.run([sys.executable, "scripts/auditor.py", "docs/ARQUITETURA_V8.md"], cwd=ROOT, text=True, capture_output=True)
    assert p_aud.returncode == 0, p_aud.stderr
    aud_out = json.loads(p_aud.stdout)
    validate_contract(aud_out, "schema_motor.json")
    smoke_lines.append(f"[OK] auditor.py CLI -> status={aud_out['status']}, pistas={len(aud_out['achados'])}, schema_motor.json=VALID")
    (rep_dir / "smoke_tests.txt").write_text("\n".join(smoke_lines) + "\n", encoding="utf-8")

    # 3. run_manifest.json (exclui a si mesmo para evitar autorreferência defasada — ACH-013)
    manifest_rel = "relatorios_execucao/run_manifest.json"
    all_files = sorted(
        p for p in ROOT.rglob("*") if is_clean_file(p) and p.relative_to(ROOT).as_posix() != manifest_rel
    )
    manifest = build_run_manifest(
        "BETA5.2-HOMOLOGATION-2026-11-23",
        all_files,
        skill_version="8.0.0-beta.5.2",
        engine_versions={
            "auditor_estrutural": "8.0.0-beta.2",
            "motor_matematico": "8.0.0-beta.2",
            "motor_dimensional": "0.1.0-beta.3",
            "motor_estatistico": "0.1.0-beta.3",
            "motor_geometrico": "0.1.0-beta.3",
            "motor_incerteza": "0.1.0-beta.3",
            "motor_dados": "0.1.0-beta.3",
            "motor_linguagem": "0.1.0-beta.4",
            "motor_figuras": "0.1.0-beta.4",
            "motor_imagem_forense": "0.1.0-beta.4",
            "motor_consistencia_cruzada": "0.1.0-beta.4",
            "motor_etica": "0.1.0-beta.5",
            "motor_argumentacao": "0.1.0-beta.5",
            "motor_evidencia": "0.1.0-beta.5",
            "motor_temporal": "0.2.0-beta.5.2",
            "motor_nomenclatura": "0.1.0-beta.5",
            "motor_metadados": "0.1.0-beta.5",
            "motor_reprodutibilidade": "0.1.0-beta.5",
            "motor_qualitativo": "0.1.0-beta.5",
        },
        config={"pytest_args": ["-v", "--cov=scripts", "--cov-report=term-missing"], "naive_timezone_policy": "strict"},
        seeds={"bootstrap_default": 42, "monte_carlo_default": 42},
        self_excluded_files=[manifest_rel],
        limitations=[
            "SKILL.md da v8.0 será integrado na Fase 8 (v6.0-legacy/SKILL.md preservado em versions/v6.0-legacy/)."
        ],
        repo_root=ROOT,
    )
    save_run_manifest(manifest, rep_dir / "run_manifest.json")

    # 4. SHA256SUMS na raiz (LF garantido) + verificação automática pós-geração (ACH-013)
    final_files = sorted(p for p in ROOT.rglob("*") if is_clean_file(p))
    sha_lines = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(ROOT).as_posix()}" for p in final_files]
    sha_file = ROOT / "SHA256SUMS"
    sha_file.write_text("\n".join(sha_lines) + "\n", encoding="utf-8", newline="\n")

    for line in sha_file.read_text(encoding="utf-8").splitlines():
        expected, rel = line.split("  ", 1)
        actual = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
        assert actual == expected, f"Divergência de hash pós-geração em {rel}"

    print("AUDIT_REPORTS_OK | git_commit:", manifest.get("git_commit"), "| git_dirty:", manifest.get("git_dirty"), "| files:", len(final_files))


if __name__ == "__main__":
    main()
