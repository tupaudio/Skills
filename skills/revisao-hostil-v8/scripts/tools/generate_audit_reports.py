#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Gerador reproduzível de relatórios de auditoria, cobertura, manifesto e SHA256SUMS (v8.0-beta.5.3)."""

from __future__ import annotations

import hashlib
import importlib
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.common.provenance import build_run_manifest, save_run_manifest
from scripts.common.schema_validator import validate_contract

ALL_ENGINE_NAMES = (
    "motor_matematico",
    "motor_dimensional",
    "motor_estatistico",
    "motor_geometrico",
    "motor_incerteza",
    "motor_dados",
    "motor_linguagem",
    "motor_figuras",
    "motor_imagem_forense",
    "motor_consistencia_cruzada",
    "motor_etica",
    "motor_argumentacao",
    "motor_evidencia",
    "motor_temporal",
    "motor_nomenclatura",
    "motor_metadados",
    "motor_reprodutibilidade",
    "motor_qualitativo",
    "motor_normas",
    "motor_risco",
    "motor_estetico",
)

REPORT_ARTIFACTS_REL = [
    "relatorios_execucao/pytest_verbose.txt",
    "relatorios_execucao/smoke_tests.txt",
    "relatorios_execucao/run_manifest.json",
    "SHA256SUMS",
]


def is_clean_file(p: pathlib.Path) -> bool:
    parts = set(p.relative_to(ROOT).parts)
    if "__pycache__" in parts or ".pytest_cache" in parts or ".git" in parts:
        return False
    if p.suffix == ".pyc" or p.name in ("SHA256SUMS", ".coverage"):
        return False
    return p.is_file()


def collect_live_engine_versions() -> dict[str, str]:
    """Lê MOTOR_VERSION diretamente de cada módulo publicado (previne deriva — ACH-016)."""
    import scripts.auditor as aud_mod

    versions: dict[str, str] = {aud_mod.MOTOR_ID: aud_mod.MOTOR_VERSION}
    for name in ALL_ENGINE_NAMES:
        mod = importlib.import_module(f"scripts.engines.{name}")
        versions[getattr(mod, "MOTOR_ID", name)] = getattr(mod, "MOTOR_VERSION", "unknown")
    return versions


def main() -> None:
    rep_dir = ROOT / "relatorios_execucao"
    rep_dir.mkdir(exist_ok=True)

    # 1. pytest -v + coverage (saída em LF)
    p_test = subprocess.run(
        [sys.executable, "-m", "pytest", "-v", "--cov=scripts", "--cov-report=term-missing"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    (rep_dir / "pytest_verbose.txt").write_text(
        (p_test.stdout + "\n" + p_test.stderr).replace("\r\n", "\n"),
        encoding="utf-8",
        newline="\n",
    )
    assert p_test.returncode == 0, f"pytest falhou:\n{p_test.stdout}\n{p_test.stderr}"

    # 2. Smoke tests de TODOS os 18 motores + auditor.py (com validação contra schema_motor.json)
    smoke_lines: list[str] = []
    # Importação e versão de todos os 18 motores
    live_versions = collect_live_engine_versions()
    for name in ALL_ENGINE_NAMES:
        mod = importlib.import_module(f"scripts.engines.{name}")
        smoke_lines.append(f"[IMPORT OK] {name}=={mod.MOTOR_VERSION}")

    smoke_cli_cases = [
        ("motor_matematico", ["scripts/engines/motor_matematico.py"], {"operation": "plug_in", "expression": "2*x+1", "substitutions": {"x": 5}, "reported_value": 11}),
        ("motor_dimensional", ["scripts/engines/motor_dimensional.py"], {"operation": "equation_homogeneity", "lhs": "F", "rhs": "m*a", "variable_units": {"F": "N", "m": "kg", "a": "m/s^2"}}),
        ("motor_estatistico", ["scripts/engines/motor_estatistico.py"], {"operation": "t_test_paired", "sample_a": [1, 2, 3, 4], "sample_b": [2, 3, 4, 6]}),
        ("motor_geometrico", ["scripts/engines/motor_geometrico.py"], {"operation": "solid_3d", "shape": "box", "dimensions": {"lx": 2, "ly": 3, "lz": 4}}),
        ("motor_incerteza", ["scripts/engines/motor_incerteza.py"], {"operation": "propagate_gum", "expression": "I*R", "variables": {"I": {"value": 2.0, "u": 0.1}, "R": {"value": 10.0, "u": 0.5}}}),
        ("motor_dados", ["scripts/engines/motor_dados.py"], {"operation": "sample_vs_reported", "values": [10, 20, 30], "reported": {"mean": 20.0, "n": 3}}),
        ("motor_linguagem", ["scripts/engines/motor_linguagem.py"], {"text": "O sistema opera em regime nominal."}),
        ("motor_consistencia_cruzada", ["scripts/engines/motor_consistencia_cruzada.py"], {"quantity_id": "T_max", "observations": [{"source_type": "codigo", "location": "sim.py", "value": 78.4, "unit": "°C"}, {"source_type": "texto", "location": "p.10", "value": 82.4, "unit": "°C"}]}),
        ("motor_etica", ["scripts/engines/motor_etica.py"], {"operation": "screen_ethics_declarations", "text": "Sem conflito de interesses e financiamento CNPq.", "involves_humans": False}),
        ("motor_argumentacao", ["scripts/engines/motor_argumentacao.py"], {"arguments": [{"id": "A1", "claim": "c", "premises": ["p"], "evidence": ["e"], "conclusion": "k"}]}),
        ("motor_evidencia", ["scripts/engines/motor_evidencia.py"], {"framework": "GRADE", "study_design": "rct"}),
        ("motor_temporal", ["scripts/engines/motor_temporal.py"], {"events": {"a": "2025-05-01T08:00:00Z", "b": "2025-05-01T10:00:00Z"}, "precedence_rules": [["a", "b"]]}),
        ("motor_nomenclatura", ["scripts/engines/motor_nomenclatura.py"], {"symbol_definitions": [{"symbol": "T", "meaning": "Temperatura", "location": "Sec 1"}], "used_symbols": ["T"]}),
        ("motor_metadados", ["scripts/engines/motor_metadados.py"], {"files": ["requirements.txt"]}),
        ("motor_reprodutibilidade", ["scripts/engines/motor_reprodutibilidade.py"], {"has_data": True, "has_scripts": True, "has_environment_spec": True}),
        ("motor_qualitativo", ["scripts/engines/motor_qualitativo.py"], {"operation": "cohens_kappa", "coder_a": ["A", "B", "A"], "coder_b": ["A", "B", "A"]}),
        ("motor_normas", ["scripts/engines/motor_normas.py"], {"citations": [{"norm_id": "ISO-IEC-17025", "jurisdiction": "INTERNATIONAL", "reference_date": "2026-11-23"}]}),
        ("motor_risco", ["scripts/engines/motor_risco.py"], {"operation": "evaluate_risk_matrix", "hazard": "Ruído", "severity": 2, "probability": 2, "controls": ["engenharia"]}),
    ]
    for name, cmd, payload in smoke_cli_cases:
        proc = subprocess.run([sys.executable] + cmd, cwd=ROOT, input=json.dumps(payload), text=True, capture_output=True)
        assert proc.returncode == 0, f"{name} CLI falhou: {proc.stderr}"
        out = json.loads(proc.stdout)
        validate_contract(out, "schema_motor.json")
        smoke_lines.append(f"[CLI OK] {name} -> status={out['status']}, achados={len(out['achados'])}, schema_motor.json=VALID")

    # Smoke tests de motor_figuras, motor_imagem_forense e motor_estetico
    import tempfile
    import numpy as np
    from PIL import Image
    import scripts.engines.motor_figuras as mfig
    import scripts.engines.motor_imagem_forense as mimf
    import scripts.engines.motor_estetico as mest

    fig_out = mfig.run_motor({"operation": "build_visual_inventory", "items": [{"kind": "figure", "source_file": "f1.png"}]})
    validate_contract(fig_out, "schema_motor.json")
    smoke_lines.append(f"[API OK] motor_figuras -> status={fig_out['status']}, schema_motor.json=VALID")

    with tempfile.TemporaryDirectory() as td:
        tmp_img = pathlib.Path(td) / "smoke.png"
        Image.fromarray(np.tile(np.linspace(0, 255, 64, dtype=np.uint8), (64, 1))).save(tmp_img)
        imf_out = mimf.run_motor({"operation": "inspect_image_forensics", "file_path": str(tmp_img)})
        validate_contract(imf_out, "schema_motor.json")
        smoke_lines.append(f"[API OK] motor_imagem_forense -> status={imf_out['status']}, schema_motor.json=VALID")
        est_out = mest.run_motor({"file_path": str(tmp_img)})
        validate_contract(est_out, "schema_motor.json")
        smoke_lines.append(f"[API OK] motor_estetico -> status={est_out['status']}, schema_motor.json=VALID")

    p_aud = subprocess.run([sys.executable, "scripts/auditor.py", "docs/ARQUITETURA_V8.md"], cwd=ROOT, text=True, capture_output=True)
    assert p_aud.returncode == 0, p_aud.stderr
    aud_out = json.loads(p_aud.stdout)
    validate_contract(aud_out, "schema_motor.json")
    smoke_lines.append(f"[CLI OK] auditor.py -> status={aud_out['status']}, pistas={len(aud_out['achados'])}, schema_motor.json=VALID")
    (rep_dir / "smoke_tests.txt").write_text("\n".join(smoke_lines) + "\n", encoding="utf-8", newline="\n")

    # 3. Carrega versões de todos os perfis-piloto ativos para o manifesto
    from scripts.common.profile_loader import list_available_profiles, load_profile
    profile_versions = {}
    for pid in list_available_profiles():
        prof = load_profile(pid)
        profile_versions[pid] = str(prof["profile_version"])

    # 4. run_manifest.json (caminhos relativos, autoexclusão e política transparente de git_dirty)
    manifest_rel = "relatorios_execucao/run_manifest.json"
    all_files = sorted(
        p for p in ROOT.rglob("*") if is_clean_file(p) and p.relative_to(ROOT).as_posix() != manifest_rel
    )
    manifest = build_run_manifest(
        "BETA6-HOMOLOGATION-2026-11-23",
        all_files,
        skill_version="8.0.0-beta.6",
        engine_versions=live_versions,
        profile_versions=profile_versions,
        config={
            "pytest_args": ["-v", "--cov=scripts", "--cov-report=term-missing"],
            "naive_timezone_policy": "strict",
            "engines_cataloged": 23,
            "engines_implemented": len(ALL_ENGINE_NAMES),
            "engines_planned_phase8": 2,
        },
        seeds={"bootstrap_default": 42, "monte_carlo_default": 42},
        self_excluded_files=[manifest_rel],
        excluded_dirty_paths=REPORT_ARTIFACTS_REL,
        limitations=[
            "SKILL.md da v8.0, motor_integracao e motor_meta serão integrados na Fase 8 (v6.0-legacy/SKILL.md preservado em versions/v6.0-legacy/)."
        ],
        repo_root=ROOT,
    )
    save_run_manifest(manifest, rep_dir / "run_manifest.json")

    # 4. SHA256SUMS na raiz (LF garantido) + verificação automática pós-geração
    final_files = sorted(p for p in ROOT.rglob("*") if is_clean_file(p))
    sha_lines = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(ROOT).as_posix()}" for p in final_files]
    sha_file = ROOT / "SHA256SUMS"
    sha_file.write_text("\n".join(sha_lines) + "\n", encoding="utf-8", newline="\n")

    for line in sha_file.read_text(encoding="utf-8").splitlines():
        expected, rel = line.split("  ", 1)
        actual = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
        assert actual == expected, f"Divergência de hash pós-geração em {rel}"

    gs = manifest["git_state"]
    print(
        f"AUDIT_REPORTS_OK | audited_code_commit={manifest['audited_code_commit']} "
        f"| git_dirty_raw={gs['git_dirty_raw']} | git_dirty_code={gs['git_dirty_code']} | files={len(final_files)}"
    )


if __name__ == "__main__":
    main()
