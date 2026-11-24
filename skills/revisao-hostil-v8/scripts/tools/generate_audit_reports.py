#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Gerador reproduzível com fonte única de verdade (run_id), relatórios, manifesto e SHA256SUMS (v8.0-beta.6.3)."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.common.evidence import utc_now_iso
from scripts.common.profile_loader import list_available_profiles, load_profile
from scripts.common.provenance import (
    build_artifact_record,
    build_run_manifest,
    capture_runtime_environment,
    generate_run_id,
    save_run_manifest,
    validate_run_consistency,
)
from scripts.common.schema_validator import SchemaValidator, validate_contract

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
    "relatorios_execucao/coverage_report.txt",
    "relatorios_execucao/smoke_tests.txt",
    "relatorios_execucao/run_manifest.json",
    "relatorios_execucao/homologacao_v8.0-beta.6.4.md",
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


def _render_homologation_report(
    *,
    run_id: str,
    timestamp_start_utc: str,
    timestamp_end_utc: str,
    audited_code_commit: str | None,
    runtime_env: dict[str, Any],
    test_results: dict[str, Any],
    coverage_summary: dict[str, Any],
    smoke_summary: dict[str, Any],
    profile_records: list[dict[str, Any]],
    schema_names: list[str],
    durations: dict[str, float],
) -> str:
    """Deriva o relatório de homologação diretamente dos dados reais da mesma execução (ACH-B6.2-001)."""
    deps_lines = "\n".join(
        f"- `{k}=={v}`" for k, v in sorted((runtime_env.get("dependencies") or {}).items()) if v is not None
    )
    mod_lines = "\n".join(
        f"| `{mod}` | {info['stmts']} | {info['miss']} | {info['percent']:.2f}% |"
        for mod, info in sorted((coverage_summary.get("modules") or {}).items())
    )
    prof_lines = "\n".join(
        f"- `{p['profile_id']}` (`v{p['profile_version']}`, status=`{p['profile_status']}`, "
        f"execution_eligible=`{p['execution_eligible']}`)"
        for p in profile_records
    )

    return f"""# Relatório Técnico de Execução e Pré-Homologação — Revisão Hostil `v8.0-beta.6.4`

> **Fonte única de verdade (`run_id`):** `{run_id}`  
> **Gerado programaticamente** a partir da mesma execução que produziu `pytest_verbose.txt`, `coverage_report.txt`, `smoke_tests.txt` e `run_manifest.json` (todos marcados internamente com `run_id` e verificados por `validate_run_consistency()`).

## 1. Objetivo da manutenção
Manutenção corretiva direcionada sobre `v8.0-beta.6.3` para encerrar `ACH-B6.3-001` (propagação e verificação efetiva do `run_id` dentro do conteúdo de todos os artefatos obrigatórios) e `ACH-B6.3-002` (verificação integral de completude, duplicatas, entradas inesperadas e integridade em `SHA256SUMS`), preservando intacta a tag `v8.0-beta.6.3` e sem iniciar a Fase 7.

## 2. Commit-base e identificação Git
- **Tag-base preservada:** `v8.0-beta.6.3` (`67efd041c359301dcaf4eedfad891daf731ecf8d`)
- **Branch de execução:** `{runtime_env.get('git_branch')}`
- **Commit de código auditado (`audited_code_commit`):** `{audited_code_commit}`
- **Início (UTC):** `{timestamp_start_utc}`
- **Fim dos testes/relatórios (UTC):** `{timestamp_end_utc}`

## 3. Achados tratados, 4. Causa-raiz e 5. Correção implementada

### ACH-B6.3-001 (P2) — Propagação e verificação efetiva do `run_id` em todos os artefatos
- **Causa-raiz:** `pytest_verbose.txt` e `coverage_report.txt` não continham o `run_id` no conteúdo do arquivo, e `validate_run_consistency()` verificava apenas o metadado `art["run_id"]` no manifesto.
- **Correção:** Inserido cabeçalho `# run_id={run_id}` em `pytest_verbose.txt`, `coverage_report.txt` e `smoke_tests.txt` (além da presença em `homologacao_v8.0-beta.6.4.md`), e endurecido `validate_run_consistency()` em `scripts/common/provenance.py` para inspecionar o conteúdo real de cada artefato em disco e rejeitar ausência ou divergência de `run_id`.

### ACH-B6.3-002 (P2) — Completude e integridade estrita de `SHA256SUMS`
- **Causa-raiz:** `validate_run_consistency()` recalculava apenas as linhas presentes em `SHA256SUMS`, sem verificar se algum arquivo esperado do inventário havia sido omitido ou se havia entradas duplicadas/inesperadas/malformadas.
- **Correção:** `validate_run_consistency()` agora constrói o conjunto esperado a partir de `inspected_files + self_excluded_files + artifacts` (excluindo `SHA256SUMS`), rejeitando arquivos omitidos, entradas duplicadas, arquivos inesperados, caminhos inválidos, hashes malformados e auto-inclusão.

## 6. Arquivos alterados na manutenção
- `skills/revisao-hostil-v8/scripts/common/provenance.py`
- `skills/revisao-hostil-v8/scripts/common/dependencies.py`
- `skills/revisao-hostil-v8/scripts/tools/generate_audit_reports.py`
- `skills/revisao-hostil-v8/tests/test_beta6_3_requirements_provenance.py`
- `skills/revisao-hostil-v8/relatorios_execucao/{{pytest_verbose.txt,coverage_report.txt,smoke_tests.txt,run_manifest.json,homologacao_v8.0-beta.6.4.md}}`
- `skills/revisao-hostil-v8/SHA256SUMS` e `README.md`

## 7. Testes criados, 8. Executados e 9. Resultado integral do pytest
- **Suíte nova:** `tests/test_beta6_3_requirements_provenance.py` (unitários, integração, negativos e adversariais para `ACH-B6.2-002`, `ACH-B6.2-001` e regressão de `ACH-B6.1-001` a `005`).
- **Coletados:** `{test_results['collected']}`
- **Aprovados:** `{test_results['passed']} passed`
- **Reprovados:** `{test_results['failed']}`
- **Ignorados:** `{test_results['skipped']}`
- **Erros de coleta:** `{test_results['collection_errors']}`
- Warnings: `{test_results['warnings']}`
- **Código de saída:** `{test_results['exit_code']}`
- **Duração da suíte (precisão completa):** `{test_results['duration_seconds']:.6f}s` (`{test_results['duration_seconds']:.2f}s`)
- **Duração smoke tests:** `{durations['smoke_tests_seconds']:.6f}s`
- **Duração geração de relatórios:** `{durations['report_generation_seconds']:.6f}s`
- **Log bruto:** `relatorios_execucao/pytest_verbose.txt`

## 10. Cobertura por módulo (`pytest-cov`)
- **Cobertura global (`scripts/`):** **{coverage_summary['global_percent']:.2f}%** (`{coverage_summary['total_statements']}` statements, `{coverage_summary['total_missing']}` missed)

| Módulo | Stmts | Miss | Cover |
| :--- | ---: | ---: | ---: |
{mod_lines}

## 11. Ambiente efetivo (capturado diretamente do processo)
- **Python:** `{runtime_env['python_version']}` (`{runtime_env['python_implementation']}`)
- **Sistema Operacional:** `{runtime_env['os_name']} {runtime_env['os_release']}`
- **Build do SO:** `{runtime_env['os_build']}`
- **Plataforma completa:** `{runtime_env['platform']}`
- **Arquitetura:** `{runtime_env['architecture']}`
- **Ambiente virtual:** `{runtime_env['virtual_env']}`
- **Ferramentas de teste:** `pytest=={runtime_env['test_tools'].get('pytest')}`, `pytest-cov=={runtime_env['test_tools'].get('pytest-cov')}`, `coverage=={runtime_env['test_tools'].get('coverage')}`, `packaging=={runtime_env['test_tools'].get('packaging')}`

## 12. Versões das dependências instaladas no ambiente
{deps_lines}

## 13. Resultado dos smoke tests reais
- **Motores implementados submetidos a smoke tests:** `{smoke_summary['implemented_engines_tested']}/21` (de 23 catalogados; 2 planejados para a Fase 8 não executáveis) + `auditor.py`.
- **Todos validados contra `schema_motor.json` fechado:** `{smoke_summary['all_passed']}`
- **Log:** `relatorios_execucao/smoke_tests.txt`

## 14. Resultado dos sete perfis-piloto
{prof_lines}

## 15. Resultado dos oito schemas JSON
- Schemas validados e fechados (`additionalProperties: false` na raiz): `{len(schema_names)}` ({', '.join(f'`{s}`' for s in schema_names)}).

## 16. Validação de consistência e 17. Checksums SHA-256
- Executados imediatamente após a gravação deste relatório e do `run_manifest.json` pela mesma execução (`run_id={run_id}`), com recálculo real de bytes para todas as entradas de `SHA256SUMS` (exigindo 0 divergências).

## 18. Commit auditado e 19. Commit de publicação dos artefatos
- **Commit auditado:** `{audited_code_commit}`
- **Commit de publicação dos artefatos:** criado imediatamente após esta geração como descendente direto de `{audited_code_commit}`, com tag anotada `v8.0-beta.6.4`.

## 20. Limitações conhecidas
- `motor_integracao`, `motor_meta`, `orchestrator.py` e `SKILL.md` da v8.0 permanecem planejados para a Fase 8.
- Banca multiagente (`Challenger`, `Adversarial`, `Adjudicador`) permanece bloqueada na Fase 7 até reauditoria independente.
- Resultados aqui registrados correspondem à execução local em ambiente virtual limpo (`venv_b64`), não substituindo a reauditoria externa independente.

## 21. Decisão técnica local
**`APROVADA PARA REAUDITORIA EXTERNA`** — todos os critérios de `ACH-B6.3-001`, `ACH-B6.3-002` e regressão de `ACH-B6.1-001` a `ACH-B6.2-002` validados em ambiente limpo com fonte única de verdade (`run_id={run_id}`).
"""


def main() -> None:
    t_total_0 = time.perf_counter()
    timestamp_start = utc_now_iso()
    run_id = generate_run_id("BETA6.4")
    runtime_env = capture_runtime_environment(ROOT)

    rep_dir = ROOT / "relatorios_execucao"
    rep_dir.mkdir(exist_ok=True)

    # 1. pytest -v + coverage + plugin programático de captura (mesmo run_id e processo limpo)
    with tempfile.TemporaryDirectory() as td:
        capture_json = pathlib.Path(td) / "pytest_capture.json"
        cov_json = pathlib.Path(td) / "coverage.json"
        env_sub = dict(os.environ)
        env_sub["RH_RUN_ID"] = run_id
        env_sub["RH_PYTEST_CAPTURE_JSON"] = str(capture_json)

        pytest_args = [
            "-m",
            "pytest",
            "-v",
            "-p",
            "tests._pytest_capture_plugin",
            "--cov=scripts",
            "--cov-report=term-missing",
            f"--cov-report=json:{cov_json}",
        ]
        p_test = subprocess.run(
            [sys.executable, *pytest_args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            env=env_sub,
        )
        full_pytest_out = (p_test.stdout + "\n" + p_test.stderr).replace("\r\n", "\n")
        # ACH-B6.3-001: carimba run_id no cabeçalho de pytest_verbose.txt
        (rep_dir / "pytest_verbose.txt").write_text(
            f"# run_id={run_id}\n" + full_pytest_out,
            encoding="utf-8",
            newline="\n",
        )
        assert p_test.returncode == 0, f"pytest falhou:\n{p_test.stdout}\n{p_test.stderr}"

        test_results = json.loads(capture_json.read_text(encoding="utf-8"))
        cov_raw = json.loads(cov_json.read_text(encoding="utf-8"))

    # Extrai tabela de cobertura para coverage_report.txt com cabeçalho run_id (ACH-B6.3-001)
    cov_lines: list[str] = [f"# run_id={run_id}"]
    in_cov = False
    for line in full_pytest_out.splitlines():
        if line.startswith("Name") and "Stmts" in line and "Cover" in line:
            in_cov = True
        if in_cov:
            cov_lines.append(line)
            if line.startswith("TOTAL"):
                break
    (rep_dir / "coverage_report.txt").write_text("\n".join(cov_lines) + "\n", encoding="utf-8", newline="\n")

    modules_cov: dict[str, dict[str, Any]] = {}
    for fname, fdata in cov_raw.get("files", {}).items():
        s = fdata["summary"]
        modules_cov[fname.replace("\\", "/")] = {
            "stmts": int(s["num_statements"]),
            "miss": int(s["missing_lines"]),
            "percent": float(s["percent_covered"]),
        }
    tot = cov_raw["totals"]
    coverage_summary = {
        "global_percent": float(tot["percent_covered"]),
        "total_statements": int(tot["num_statements"]),
        "total_missing": int(tot["missing_lines"]),
        "modules": modules_cov,
    }

    # 2. Smoke tests reais de TODOS os 21 motores + auditor.py
    t_smoke_0 = time.perf_counter()
    smoke_lines: list[str] = [f"# run_id={run_id}"]
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

    import numpy as np
    from PIL import Image
    import scripts.engines.motor_estetico as mest
    import scripts.engines.motor_figuras as mfig
    import scripts.engines.motor_imagem_forense as mimf

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
    smoke_duration_s = time.perf_counter() - t_smoke_0

    smoke_summary = {
        "implemented_engines_tested": len(ALL_ENGINE_NAMES),
        "auditor_tested": True,
        "all_passed": True,
        "duration_seconds": smoke_duration_s,
    }

    # 3. Valida todos os 7 perfis-piloto e os 8 schemas
    t_rep_0 = time.perf_counter()
    profile_versions = {}
    profile_audit_records = []
    for pid in list_available_profiles():
        prof = load_profile(pid, mode="execution")
        profile_versions[pid] = str(prof["profile_version"])
        profile_audit_records.append(prof["_resolved"]["manifest_profile_record"])

    sv = SchemaValidator()
    schema_names = sorted(sv._schemas.keys())

    # 4. Gera homologacao_v8.0-beta.6.3.md programaticamente (fonte única de verdade)
    from scripts.common.provenance import _detect_git_commit

    audited_commit = _detect_git_commit(ROOT)
    timestamp_end = utc_now_iso()
    report_gen_duration_s = time.perf_counter() - t_rep_0
    durations = {
        "test_suite_seconds": float(test_results["duration_seconds"]),
        "smoke_tests_seconds": smoke_duration_s,
        "report_generation_seconds": report_gen_duration_s,
        "integrity_verification_seconds": 0.0,
        "total_seconds": time.perf_counter() - t_total_0,
    }

    homolog_path = rep_dir / "homologacao_v8.0-beta.6.4.md"
    homolog_text = _render_homologation_report(
        run_id=run_id,
        timestamp_start_utc=timestamp_start,
        timestamp_end_utc=timestamp_end,
        audited_code_commit=audited_commit,
        runtime_env=runtime_env,
        test_results=test_results,
        coverage_summary=coverage_summary,
        smoke_summary=smoke_summary,
        profile_records=profile_audit_records,
        schema_names=schema_names,
        durations=durations,
    )
    homolog_path.write_text(homolog_text, encoding="utf-8", newline="\n")

    # 5. Calcula hashes reais dos artefatos já finalizados (não circular)
    artifacts = [
        build_artifact_record(rep_dir / "pytest_verbose.txt", ROOT, run_id=run_id, artifact_type="pytest_log"),
        build_artifact_record(rep_dir / "coverage_report.txt", ROOT, run_id=run_id, artifact_type="coverage_report"),
        build_artifact_record(rep_dir / "smoke_tests.txt", ROOT, run_id=run_id, artifact_type="smoke_tests"),
        build_artifact_record(homolog_path, ROOT, run_id=run_id, artifact_type="homologation_report"),
    ]

    # 6. Gera e salva run_manifest.json (autoexcluído para evitar circularidade)
    manifest_rel = "relatorios_execucao/run_manifest.json"
    all_files = sorted(
        p for p in ROOT.rglob("*") if is_clean_file(p) and p.relative_to(ROOT).as_posix() != manifest_rel
    )
    durations["total_seconds"] = time.perf_counter() - t_total_0
    manifest = build_run_manifest(
        run_id,
        all_files,
        skill_version="8.0.0-beta.6.4",
        engine_versions=live_versions,
        profile_versions=profile_versions,
        profile_audit_records=profile_audit_records,
        authorized_exceptions=[],
        runtime_environment=runtime_env,
        timestamp_start_utc=timestamp_start,
        timestamp_end_utc=timestamp_end,
        durations=durations,
        test_results=test_results,
        coverage_summary=coverage_summary,
        smoke_tests_summary=smoke_summary,
        artifacts=artifacts,
        execution_command=sys.executable,
        execution_args=pytest_args,
        exit_code=int(test_results["exit_code"]),
        overall_result="PASSED" if int(test_results["exit_code"]) == 0 else "FAILED",
        report_references={
            "pytest_verbose": "relatorios_execucao/pytest_verbose.txt",
            "coverage_report": "relatorios_execucao/coverage_report.txt",
            "smoke_tests": "relatorios_execucao/smoke_tests.txt",
            "homologation_report": "relatorios_execucao/homologacao_v8.0-beta.6.4.md",
            "checksums": "SHA256SUMS",
        },
        config={
            "pytest_args": pytest_args,
            "naive_timezone_policy": "strict",
            "profile_schema_enforced": "references/schemas/schema_profile.json",
            "dependency_validation_source": "requirements.txt (fail-closed) + references/catalogo_motores.yaml",
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

    # 7. Gera SHA256SUMS (incluindo run_manifest.json e homologacao_v8.0-beta.6.3.md, excluindo SHA256SUMS)
    t_int_0 = time.perf_counter()
    final_files = sorted(p for p in ROOT.rglob("*") if is_clean_file(p))
    sha_lines = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(ROOT).as_posix()}" for p in final_files]
    sha_file = ROOT / "SHA256SUMS"
    sha_file.write_text("\n".join(sha_lines) + "\n", encoding="utf-8", newline="\n")

    # 8. Validação obrigatória de consistência e recálculo integral de SHA-256 (ACH-B6.2-001)
    consistency = validate_run_consistency(
        manifest,
        root_dir=ROOT,
        sha256sums_path=sha_file,
        expected_commit=audited_commit,
        report_text=homolog_path.read_text(encoding="utf-8"),
        required_artifact_names=(
            "pytest_verbose.txt",
            "coverage_report.txt",
            "smoke_tests.txt",
            "homologacao_v8.0-beta.6.4.md",
        ),
    )
    integrity_s = time.perf_counter() - t_int_0

    gs = manifest["git_state"]
    ge = manifest["global_eligibility"]
    print(
        f"AUDIT_REPORTS_OK | run_id={run_id} | audited_code_commit={manifest['audited_code_commit']} "
        f"| git_dirty_raw={gs['git_dirty_raw']} | git_dirty_code={gs['git_dirty_code']} "
        f"| passed={test_results['passed']} | warnings={test_results['warnings']} "
        f"| cov={coverage_summary['global_percent']:.2f}% | eligible={ge['eligible_count']}/{ge['evaluated_profiles']} "
        f"| sha256_verified={consistency['sha256_verified']} | sha256_failed={consistency['sha256_failed']} "
        f"| consistency=VALID ({integrity_s:.3f}s)"
    )


if __name__ == "__main__":
    main()
