"""Testes de aceitação da Fase 6 (v8.0-beta.6): perfis multidisciplinares, motor_normas, motor_risco e motor_estetico."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from scripts.common.profile_loader import list_available_profiles, load_profile
from scripts.common.schema_validator import validate_contract
from scripts.engines import (
    motor_argumentacao,
    motor_consistencia_cruzada,
    motor_dados,
    motor_dimensional,
    motor_estetico,
    motor_estatistico,
    motor_etica,
    motor_evidencia,
    motor_incerteza,
    motor_linguagem,
    motor_matematico,
    motor_normas,
    motor_qualitativo,
    motor_reprodutibilidade,
    motor_risco,
    motor_temporal,
)


def test_all_seven_pilot_profiles_load_and_validate() -> None:
    expected = {
        "artes",
        "direito",
        "engenharia_geral",
        "musica_acustica",
        "pesquisa_qualitativa",
        "seguranca_trabalho",
        "sistemas_espaciais",
    }
    available = set(list_available_profiles())
    assert expected <= available

    families = set()
    for pid in expected:
        prof = load_profile(pid)
        assert prof["profile_id"] == pid
        assert prof["profile_status"] == "active"
        assert "_resolved" in prof
        families.add(prof["domain"]["epistemological_family"])

    # Pelo menos 4 famílias epistemológicas distintas configuradas
    assert len(families) >= 4


def test_motor_normas_safety_rule_never_presumes_compliance(tmp_path: Path) -> None:
    # 1. Norma ausente do catálogo -> NAO_VERIFICADO
    out_missing = motor_normas.run_motor(
        {"citations": [{"id": "N1", "norm_id": "NR-999-INEXISTENTE", "jurisdiction": "BR", "reference_date": "2026-11-23"}]}
    )
    validate_contract(out_missing, "schema_motor.json")
    assert out_missing["resultados"]["results"][0]["status"] == "unverified"
    assert out_missing["achados"][0]["estado"] == "NAO_VERIFICADO"

    # 2. NR-15 presente no catálogo mas com official_source_verified=False -> NAO_VERIFICADO (nunca ok!)
    out_nr15 = motor_normas.run_motor(
        {"citations": [{"id": "N2", "norm_id": "NR-15", "jurisdiction": "BR", "reference_date": "2026-11-23"}]}
    )
    validate_contract(out_nr15, "schema_motor.json")
    assert out_nr15["resultados"]["results"][0]["status"] == "unverified"
    assert out_nr15["achados"][0]["estado"] == "NAO_VERIFICADO"

    # 3. ISO-IEC-17025 (official_source_verified=True) com data válida -> ok, mas certifies_legal_compliance=False
    out_iso = motor_normas.run_motor(
        {"citations": [{"id": "N3", "norm_id": "ISO-IEC-17025", "jurisdiction": "INTERNATIONAL", "reference_date": "2026-11-23"}]}
    )
    validate_contract(out_iso, "schema_motor.json")
    assert out_iso["status"] == "OK"
    assert out_iso["resultados"]["results"][0]["certifies_legal_compliance"] is False

    # 4. Norma revogada antes da data de referência -> CRITICO CONFIRMADO
    rev_yaml = tmp_path / "revogada.yaml"
    rev_yaml.write_text(
        "norm_id: LEI-REV-1\njurisdiction: BR\nedition: '2010'\neffective_from: '2010-01-01'\n"
        "revoked_on: '2022-01-01'\nreplaced_by: 'LEI-NOVA-2'\nofficial_source_verified: true\n",
        encoding="utf-8",
    )
    out_rev = motor_normas.run_motor(
        {
            "norms_dir": str(tmp_path),
            "citations": [{"id": "N4", "norm_id": "LEI-REV-1", "jurisdiction": "BR", "reference_date": "2026-11-23"}],
        }
    )
    validate_contract(out_rev, "schema_motor.json")
    assert out_rev["achados"][0]["gravidade"] == "CRITICO"
    assert out_rev["achados"][0]["estado"] == "CONFIRMADO"


def test_motor_risco_and_motor_estetico(tmp_path: Path) -> None:
    # motor_risco: risco alto usando apenas EPI + exposição acima do limite
    rsk_out = motor_risco.run_motor(
        {
            "operation": "batch",
            "operations": [
                {"id": "R1", "operation": "evaluate_risk_matrix", "hazard": "Arco elétrico", "severity": 5, "probability": 3, "controls": ["epi"]},
                {"id": "R2", "operation": "evaluate_exposure_index", "agents": [{"name": "Ruído", "measured": 90.0, "limit": 85.0, "unit": "dB(A)"}]},
            ],
        }
    )
    validate_contract(rsk_out, "schema_motor.json")
    assert rsk_out["status"] == "COM_ACHADOS"
    assert len(rsk_out["achados"]) == 2
    assert rsk_out["resultados"]["results"][0]["certifies_safety_compliance"] is False

    # motor_estetico: métricas composicionais objetivas sem juízo artístico automático
    img_path = tmp_path / "obra.png"
    grad = np.tile(np.linspace(0, 255, 640, dtype=np.uint8), (400, 1))
    Image.fromarray(grad).save(img_path)
    est_out = motor_estetico.run_motor({"file_path": str(img_path)})
    validate_contract(est_out, "schema_motor.json")
    assert est_out["status"] == "OK"
    assert est_out["resultados"]["declares_artistic_value"] is False
    assert est_out["resultados"]["tonal_entropy_bits"] > 0.0


def test_exit_criterion_four_epistemological_families_execute_without_core_changes() -> None:
    """Critério de saída da Fase 6: >= 3 perfis de famílias epistemológicas distintas
    executam seus conjuntos de motores corretamente sem alterações no Core.
    """
    # Família 1: exatas_engenharia (engenharia_geral)
    p_eng = load_profile("engenharia_geral")
    assert p_eng["_resolved"]["loaded_vocabulary"] is not None
    assert len(p_eng["_resolved"]["loaded_checklists"]) == 1
    out_m1 = motor_matematico.run_motor({"operation": "plug_in", "expression": "V/R", "substitutions": {"V": 12, "R": 4}, "reported_value": 3.0})
    out_m2 = motor_dimensional.run_motor({"operation": "equation_homogeneity", "lhs": "P", "rhs": "V*I", "variable_units": {"P": "W", "V": "V", "I": "A"}})
    out_m3 = motor_incerteza.run_motor({"operation": "propagate_gum", "expression": "V*I", "variables": {"V": {"value": 12.0, "u": 0.1}, "I": {"value": 3.0, "u": 0.05}}})
    for o in (out_m1, out_m2, out_m3):
        validate_contract(o, "schema_motor.json")
        assert o["status"] == "OK"

    # Família 2: seguranca_risco (seguranca_trabalho)
    p_sst = load_profile("seguranca_trabalho")
    assert "motor_risco" in p_sst["engines"]["required"]
    out_s1 = motor_risco.run_motor({"operation": "evaluate_risk_matrix", "hazard": "Ruído", "severity": 2, "probability": 2, "controls": ["engenharia"]})
    out_s2 = motor_normas.run_motor({"citations": [{"norm_id": "ISO-IEC-17025", "jurisdiction": "INTERNATIONAL", "reference_date": "2026-11-23"}]})
    for o in (out_s1, out_s2):
        validate_contract(o, "schema_motor.json")
        assert o["status"] == "OK"

    # Família 3: normativo_juridico (direito)
    p_dir = load_profile("direito")
    assert "motor_normas" in p_dir["engines"]["required"]
    out_d1 = motor_temporal.run_motor({"events": {"lei": "2020-01-01", "fato": "2025-01-01"}, "precedence_rules": [["lei", "fato"]]})
    out_d2 = motor_argumentacao.run_motor({"arguments": [{"id": "J1", "claim": "Tese", "premises": ["Norma vigente"], "evidence": ["Art. 1"], "conclusion": "Aplicável"}]})
    out_d3 = motor_evidencia.run_motor({"framework": p_dir["evidence_framework"], "study_design": "triangulated_primary"})
    for o in (out_d1, out_d2, out_d3):
        validate_contract(o, "schema_motor.json")
        assert o["status"] == "OK"

    # Família 4: qualitativo_social (pesquisa_qualitativa)
    p_qua = load_profile("pesquisa_qualitativa")
    assert "motor_qualitativo" in p_qua["engines"]["required"]
    out_q1 = motor_qualitativo.run_motor({"operation": "cohens_kappa", "coder_a": ["C1", "C2", "C1"], "coder_b": ["C1", "C2", "C1"]})
    out_q2 = motor_etica.run_motor({"operation": "screen_ethics_declarations", "text": "Aprovado pelo CEP, TCLE assinado, LGPD, CNPq, sem conflito de interesses.", "involves_humans": True})
    for o in (out_q1, out_q2):
        validate_contract(o, "schema_motor.json")
        assert o["status"] == "OK"


def test_ach_b6_002_profile_loader_rejects_planned_required_engines_and_negative_inputs(tmp_path: Path) -> None:
    # Perfil exigindo motor ainda 'planejado' (motor_integracao) deve ser rejeitado!
    bad_prof = tmp_path / "planned_req.yaml"
    bad_prof.write_text(
        "profile_id: teste_planejado\nprofile_version: '1.0.0'\nprofile_status: active\n"
        "domain: {name: Teste}\nengines:\n  required: [motor_integracao]\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="ainda não implementados"):
        load_profile(bad_prof)

    # Casos negativos dos 3 novos motores
    with pytest.raises(ValueError, match="intervalo inteiro"):
        motor_risco.evaluate_risk_matrix("Choque", 6, 3)
    with pytest.raises(ValueError, match="limit > 0"):
        motor_risco.evaluate_exposure_index([{"name": "Ruído", "measured": 80.0, "limit": 0.0}])
    with pytest.raises(FileNotFoundError):
        motor_estetico.analyze_composition(tmp_path / "nao_existe.png")
