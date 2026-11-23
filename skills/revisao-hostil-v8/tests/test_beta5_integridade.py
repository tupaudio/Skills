"""Testes de aceitação da Fase 5 (v8.0-beta.5): integridade científica e metodologia."""

from __future__ import annotations

import math
from pathlib import Path

from scripts.common.provenance import sha256_file
from scripts.common.schema_validator import validate_contract
from scripts.engines import (
    motor_argumentacao,
    motor_etica,
    motor_evidencia,
    motor_metadados,
    motor_nomenclatura,
    motor_qualitativo,
    motor_reprodutibilidade,
    motor_temporal,
)


def test_motor_etica_declarations_similarity_and_guardrails() -> None:
    out = motor_etica.run_motor(
        {
            "operation": "batch",
            "operations": [
                {
                    "id": "ET-01",
                    "operation": "screen_ethics_declarations",
                    "text": "Este estudo contou com apoio do CNPq e não há conflito de interesses.",
                    "involves_humans_or_animals": True,
                },
                {
                    "id": "ET-02",
                    "operation": "check_text_similarity",
                    "text": "o metodo proposto reduz drasticamente o consumo de energia em sistemas embarcados criticos",
                    "reference_texts": {
                        "ref_a": "o metodo proposto reduz drasticamente o consumo de energia em sistemas embarcados criticos"
                    },
                },
            ],
        }
    )
    validate_contract(out, "schema_motor.json")
    assert out["status"] == "COM_ACHADOS"
    r1, r2 = out["resultados"]["results"]
    assert "aprovacao_etica" in r1["missing_declarations"]
    assert r1["certifies_compliance"] is False
    assert r2["flagged_count"] == 1
    assert r2["declares_plagiarism"] is False


def test_motor_argumentacao_and_evidencia() -> None:
    arg_out = motor_argumentacao.run_motor(
        {
            "arguments": [
                {
                    "id": "ARG-1",
                    "claim": "O algoritmo funciona em todos os casos sem exceção.",
                    "premises": ["O algoritmo converge rapidamente em sistemas lineares"],
                    "evidence": [],
                    "conclusion": "O algoritmo converge rapidamente em sistemas lineares",
                }
            ]
        }
    )
    validate_contract(arg_out, "schema_motor.json")
    assert arg_out["resultados"]["is_definitive_fallacy_classifier"] is False
    types = {c["candidate_type"] for c in arg_out["resultados"]["candidate_issues"]}
    assert {"unsupported_claim", "possible_circularity", "possible_overgeneralization"} <= types

    evi_out = motor_evidencia.run_motor(
        {
            "framework": "ENGENHARIA_EMPIRICA",
            "study_design": "numerical_simulation",
            "claimed_strength": "prova_definitiva",
        }
    )
    validate_contract(evi_out, "schema_motor.json")
    assert evi_out["status"] == "COM_ACHADOS"


def test_motor_temporal_and_nomenclatura() -> None:
    tmp_out = motor_temporal.run_motor(
        {
            "events": {"aprovacao_cep": "2025-06-01", "coleta_dados": "2025-03-01"},
            "precedence_rules": [["aprovacao_cep", "coleta_dados"]],
            "validity_windows": [{"id": "NR-15-old", "effective_from": "2000-01-01", "revoked_on": "2024-01-01"}],
            "reference_date": "2025-05-01",
        }
    )
    validate_contract(tmp_out, "schema_motor.json")
    assert tmp_out["status"] == "COM_ACHADOS"
    assert tmp_out["resultados"]["infers_causality_from_order"] is False
    assert len(tmp_out["achados"]) == 2

    nom_out = motor_nomenclatura.run_motor(
        {
            "symbol_definitions": [
                {"symbol": "T", "meaning": "Temperatura absoluta", "location": "Seção 2"},
                {"symbol": "T", "meaning": "Período orbital", "location": "Seção 4"},
            ],
            "used_symbols": ["T", "eta"],
        }
    )
    validate_contract(nom_out, "schema_motor.json")
    assert nom_out["status"] == "COM_ACHADOS"
    assert len(nom_out["resultados"]["symbol_conflicts"]) == 1
    assert nom_out["resultados"]["undefined_symbols"] == ["eta"]


def test_motor_metadados_separated_from_reprodutibilidade(tmp_path: Path) -> None:
    f = tmp_path / "dados.csv"
    f.write_text("x,y\n1,2\n", encoding="utf-8")
    good_hash = sha256_file(f)

    meta_ok = motor_metadados.run_motor({"files": [str(f)], "expected_hashes": {"dados.csv": good_hash}})
    validate_contract(meta_ok, "schema_motor.json")
    assert meta_ok["status"] == "OK"

    meta_bad = motor_metadados.run_motor({"files": [str(f)], "expected_hashes": {"dados.csv": "0" * 64}})
    validate_contract(meta_bad, "schema_motor.json")
    assert meta_bad["status"] == "COM_ACHADOS"
    assert meta_bad["achados"][0]["gravidade"] == "CRITICO"

    rep_out = motor_reprodutibilidade.run_motor(
        {
            "has_data": True,
            "has_scripts": True,
            "has_environment_spec": False,
            "uses_stochastic_methods": True,
            "seeds_documented": False,
            "parameters": [{"name": "k_magico", "value": 1.37}],
        }
    )
    validate_contract(rep_out, "schema_motor.json")
    assert rep_out["status"] == "COM_ACHADOS"
    assert len(rep_out["achados"]) == 3


def test_motor_qualitativo_kappa_and_krippendorff() -> None:
    # Kappa perfeito = 1.0
    k_perf = motor_qualitativo.cohens_kappa(["A", "B", "A", "C"], ["A", "B", "A", "C"])
    assert math.isclose(k_perf["kappa"], 1.0, rel_tol=1e-9)
    assert k_perf["determines_saturation_alone"] is False

    # Krippendorff Alpha nominal com 3 codificadores e dado ausente (None)
    mat = [
        ["A", "B", "C", "A", "B"],
        ["A", "B", "C", "A", None],
        ["A", "B", "C", "A", "B"],
    ]
    alpha_perf = motor_qualitativo.krippendorff_alpha_nominal(mat)
    assert math.isclose(alpha_perf["alpha"], 1.0, rel_tol=1e-9)

    out = motor_qualitativo.run_motor(
        {"id": "Q1", "operation": "cohens_kappa", "coder_a": ["A", "B", "A", "B"], "coder_b": ["B", "A", "B", "A"]}
    )
    validate_contract(out, "schema_motor.json")
    assert out["status"] == "COM_ACHADOS"
