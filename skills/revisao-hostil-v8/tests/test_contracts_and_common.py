"""Testes dos contratos JSON, utilitários scripts/common/, estados, pontuação e manifesto."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.common.citation import check_bijection, extract_latex_citations
from scripts.common.evidence import (
    ESTADOS_ACHADO,
    create_evidence,
    create_finding,
    evaluate_freeze_gate,
    normalize_score,
    transition_finding_state,
)
from scripts.common.profile_loader import load_engine_catalog, load_profile
from scripts.common.provenance import build_run_manifest, save_run_manifest, sha256_file
from scripts.common.schema_validator import SchemaValidationError, SchemaValidator, validate_contract
from scripts.common.statistics import descriptive_summary, relative_change_pct
from scripts.common.text_normalize import canonical_key
from scripts.common.units import extract_numbers_with_units


def test_all_seven_schemas_load() -> None:
    validator = SchemaValidator()
    expected = [
        "schema_input.json",
        "schema_motor.json",
        "schema_achado.json",
        "schema_agente.json",
        "schema_evidencia.json",
        "schema_iteracao.json",
        "schema_relatorio_final.json",
    ]
    for name in expected:
        schema = validator.get_schema(name)
        assert "$schema" in schema


def test_finding_state_machine_and_reaudit_gate() -> None:
    assert len(ESTADOS_ACHADO) == 10
    ev = create_evidence("EV-001", "numerica", "main.tex", "Eq. 1", "Erro de 12%")
    finding = create_finding(
        "ACH-001",
        "Erro numérico na Eq. 1",
        "discrepancia_matematica",
        "CRITICO",
        "ALTA",
        "Eq. 1",
        "Valor impresso diverge do cálculo.",
        [ev],
    )
    validate_contract(finding, "schema_achado.json")

    transition_finding_state(finding, "CONFIRMADO", "Confirmado pelo motor")
    transition_finding_state(finding, "PATCH_PROPOSTO", "Patch sugerido")
    transition_finding_state(finding, "PATCH_APROVADO", "Autor aprovou")

    # Proibido pular direto de PATCH_APROVADO para FECHADO
    with pytest.raises(ValueError):
        transition_finding_state(finding, "FECHADO", "Tentativa indevida", reauditado=True)

    transition_finding_state(finding, "PATCH_APLICADO", "Patch aplicado no arquivo")

    # Proibido fechar sem reauditoria comprovada
    with pytest.raises(ValueError):
        transition_finding_state(finding, "FECHADO", "Sem reauditar", reauditado=False)

    transition_finding_state(finding, "FECHADO", "Reauditado com sucesso", reauditado=True)
    assert finding["estado"] == "FECHADO"
    validate_contract(finding, "schema_achado.json")


def test_unified_scoring_and_freeze_gate() -> None:
    score = normalize_score(9.6)
    assert score == {"nota_0_10": 9.6, "nota_0_100": 96.0}

    with pytest.raises(ValueError):
        normalize_score(10.5)

    ev = create_evidence("EV-002", "textual", "main.tex", "Seção 1", "Alegação")
    open_major = create_finding(
        "ACH-002", "Achado maior aberto", "metodo", "MAIOR", "ALTA", "Seção 1", "Descrição", [ev]
    )
    gate_blocked = evaluate_freeze_gate(9.7, {"dominio": 9.5, "clareza": 9.0}, [open_major], True)
    assert gate_blocked["pode_congelar"] is False
    assert gate_blocked["maiores_abertos"] == 1

    gate_ok = evaluate_freeze_gate(9.6, {"dominio": 9.2, "clareza": 8.8}, [], True)
    assert gate_ok["pode_congelar"] is True


def test_run_manifest_generation(tmp_path: Path) -> None:
    sample = tmp_path / "doc.tex"
    sample.write_text("x = 1\n", encoding="utf-8")
    manifest = build_run_manifest(
        "RUN-2026-001",
        [sample],
        engine_versions={"motor_matematico": "8.0.0-beta.2"},
        seeds={"global": 42},
    )
    out = save_run_manifest(manifest, tmp_path / "run_manifest.json")
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["run_id"] == "RUN-2026-001"
    assert loaded["inspected_files"][0]["sha256"] == sha256_file(sample)
    assert loaded["seeds"]["global"] == 42


def test_profile_loader_and_catalog(tmp_path: Path) -> None:
    catalog = load_engine_catalog()
    assert "motor_matematico" in catalog
    assert "motor_consistencia_cruzada" in catalog

    bad_profile = tmp_path / "bad.yaml"
    bad_profile.write_text(
        "profile_id: test_invalido\nprofile_version: '1.0.0'\nprofile_status: active\n"
        "effective_date: '2026-11-23'\n"
        "domain:\n  name: Teste\n  epistemological_family: exatas_engenharia\n"
        "reasoning_modes: [engineering]\n"
        "gates: [G01]\n"
        "engines:\n  required: [motor_inexistente]\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="não catalogados"):
        load_profile(bad_profile)


def test_schema_rejects_invalid_finding() -> None:
    with pytest.raises(SchemaValidationError):
        validate_contract({"id": "INVALIDO"}, "schema_achado.json")


def test_common_helpers() -> None:
    assert canonical_key("  Revisão Hostil v8.0! ") == "revisao_hostil_v8_0"
    cites = extract_latex_citations(r"Conforme \cite{silva2024, souza2025} e \citet{silva2024}.")
    assert set(cites) == {"silva2024", "souza2025"}
    bij = check_bijection({"a", "b"}, {"b", "c"})
    assert bij == {"bijection_ok": False, "ghost_citations": ["a"], "orphan_references": ["c"]}
    units = extract_numbers_with_units("Potência de 150 W e energia de 3,5 kWh (95%)")
    assert len(units) == 3
    summary = descriptive_summary([10, 20, 30])
    assert summary["mean"] == 20.0
    assert relative_change_pct(100.0, 80.0) == -20.0
