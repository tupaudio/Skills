"""Testes adversariais de regressão para todos os achados da auditoria externa (ACH-001 a ACH-007)."""

from __future__ import annotations

import pytest

from scripts.common.evidence import evaluate_freeze_gate, normalize_score
from scripts.common.schema_validator import validate_contract
from scripts.engines import (
    motor_argumentacao,
    motor_dimensional,
    motor_estatistico,
    motor_etica,
    motor_evidencia,
    motor_temporal,
)


def test_ach001_nan_and_inf_rejected_in_scoring_and_freeze_gate() -> None:
    with pytest.raises(ValueError, match="finito"):
        normalize_score(float("nan"))
    with pytest.raises(ValueError, match="finito"):
        normalize_score(float("inf"))
    with pytest.raises(ValueError, match="finito"):
        evaluate_freeze_gate(float("nan"), {"dominio": 9.5}, [], True)
    with pytest.raises(ValueError, match="finito"):
        evaluate_freeze_gate(9.8, {"dominio": float("nan")}, [], True)


def test_ach002_zero_pooled_variance_and_tost_unit_sample() -> None:
    # [1,1,1] vs [2,2,2]: médias distintas com variância agrupada nula -> efeito indefinido (None), nunca 0.0!
    res = motor_estatistico.t_test_independent([1.0, 1.0, 1.0], [2.0, 2.0, 2.0])
    assert res["cohens_d"] is None
    assert res["hedges_g"] is None
    assert "undefined_zero_pooled_variance" in (res["effect_size_note"] or "")

    # [1,1,1] vs [1,1,1]: médias iguais e variância nula -> efeito 0.0 com nota explícita
    res_eq = motor_estatistico.t_test_independent([1.0, 1.0, 1.0], [1.0, 1.0, 1.0])
    assert res_eq["cohens_d"] == 0.0
    assert res_eq["effect_size_note"] == "zero_variance_equal_means"

    # TOST com amostra unitária deve levantar ValueError (nunca retornar status ok com NaN)
    with pytest.raises(ValueError, match="pelo menos 2 observações"):
        motor_estatistico.tost_equivalence([1.0], [1.0, 2.0], -0.5, 0.5)


def test_ach003_kelvin_absolute_vs_interval_algebra() -> None:
    # Soma de duas temperaturas absolutas em Kelvin (K + K) é fisicamente inválida!
    bad_sum = motor_dimensional.analyze_expression_dimension("T1 + T2", {"T1": "K", "T2": "K"})
    assert bad_sum["homogeneous"] is False
    assert bad_sum["status"] == "discrepancy_detected"

    # Subtração de duas temperaturas absolutas (K - K) produz intervalo (delta_K) -> válida!
    ok_diff = motor_dimensional.check_equation_homogeneity("dT", "T2 - T1", {"dT": "delta_K", "T1": "K", "T2": "K"})
    assert ok_diff["homogeneous"] is True
    assert ok_diff["rhs_nature"] == "interval"

    # Temperatura absoluta + diferença de temperatura = temperatura absoluta -> válida!
    ok_shift = motor_dimensional.check_equation_homogeneity("T_final", "T0 + dT", {"T_final": "K", "T0": "K", "dT": "delta_degC"})
    assert ok_shift["homogeneous"] is True

    # Igualar temperatura absoluta a intervalo -> incompatível!
    bad_eq = motor_dimensional.check_equation_homogeneity("T_abs", "dT", {"T_abs": "K", "dT": "delta_K"})
    assert bad_eq["homogeneous"] is False

    # Stefan-Boltzmann (potência de K): q = sigma * T^4 -> válida!
    sb = motor_dimensional.check_equation_homogeneity(
        "q", "sigma * T^4", {"q": "W/m^2", "sigma": "W/(m^2*K^4)", "T": "K"}
    )
    assert sb["homogeneous"] is True


def test_ach004_ethics_separates_humans_animals_and_consent_waiver() -> None:
    # Pesquisa exclusivamente com animais: exige CEUA, NÃO exige TCLE nem LGPD!
    anim = motor_etica.screen_ethics_declarations(
        "Aprovado pela CEUA protocolo 123, financiamento CNPq, sem conflito de interesses.",
        involves_animals=True,
    )
    assert anim["status"] == "ok"
    assert "consentimento_informado" not in anim["required_declarations"]
    assert "protecao_dados" not in anim["required_declarations"]
    assert "aprovacao_etica_animal" in anim["required_declarations"]

    # Pesquisa com humanos com dispensa de TCLE documentada: não sinaliza ausência de TCLE!
    hum_waiver = motor_etica.screen_ethics_declarations(
        "Aprovado pelo CEP/CAAE 999, dados anonimizados conforme LGPD, financiamento CAPES, sem conflito de interesses.",
        involves_humans=True,
        consent_waiver_documented=True,
    )
    assert hum_waiver["status"] == "ok"
    assert "consentimento_informado" not in hum_waiver["required_declarations"]


def test_ach005_temporal_preserves_time_and_rejects_trailing_garbage() -> None:
    # Mesmo dia, horários diferentes: coleta às 14h antes da aprovação às 09h -> ok; invertido -> violação!
    bad_same_day = motor_temporal.check_chronology(
        {"aprovacao": "2025-05-01T14:00:00Z", "coleta": "2025-05-01T09:00:00Z"},
        [["aprovacao", "coleta"]],
    )
    assert bad_same_day["status"] == "discrepancy_detected"
    assert len(bad_same_day["violations"]) == 1

    # Lixo após a data deve ser rejeitado (sem truncamento silencioso [:10])
    with pytest.raises(ValueError, match="Formato ISO-8601 inválido"):
        motor_temporal.check_chronology({"e1": "2025-05-01-LIXO-INVALIDO"}, [])


def test_ach006_unmapped_study_design_returns_unverified() -> None:
    out = motor_evidencia.run_motor({"framework": "GRADE", "study_design": "estudo_ecologico_raro"})
    validate_contract(out, "schema_motor.json")
    assert out["resultados"]["status"] == "unverified"
    assert out["resultados"]["requires_human_review"] is True
    assert out["status"] == "COM_ACHADOS"
    assert out["achados"][0]["estado"] == "NAO_VERIFICADO"


def test_ach007_argumentation_scope_accurately_documented() -> None:
    out = motor_argumentacao.run_motor(
        {"arguments": [{"id": "A1", "claim": "x", "premises": ["p"], "evidence": ["e"], "conclusion": "c"}]}
    )
    validate_contract(out, "schema_motor.json")
    assert any("pré-estruturados" in lim or "já estruturados" in lim for lim in out["limitacoes"])
