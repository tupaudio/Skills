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


def test_ach008_pillow_in_requirements_and_all_18_engines_importable() -> None:
    import importlib
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    reqs = (root / "requirements.txt").read_text(encoding="utf-8")
    assert "Pillow" in reqs

    engine_names = [
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
    ]
    assert len(engine_names) == 18
    for name in engine_names:
        mod = importlib.import_module(f"scripts.engines.{name}")
        assert hasattr(mod, "run_motor"), f"{name} não expõe run_motor()"


def test_ach009_temporal_timezone_ambiguity_and_policies() -> None:
    # Mistura naive + UTC dentro de 26h sob política 'strict' -> NAO_VERIFICADO (nunca presume UTC!)
    amb = motor_temporal.run_motor(
        {
            "events": {"aprovacao": "2025-05-01T10:00:00", "coleta": "2025-05-01T12:00:00Z"},
            "precedence_rules": [["aprovacao", "coleta"]],
            "naive_policy": "strict",
        }
    )
    validate_contract(amb, "schema_motor.json")
    assert amb["resultados"]["status"] == "unverified"
    assert amb["achados"][0]["estado"] == "NAO_VERIFICADO"

    # Mistura naive + UTC separados por 5 dias -> ordenação inequívoca!
    clear = motor_temporal.check_chronology(
        {"aprovacao": "2025-05-01T10:00:00", "coleta": "2025-05-06T12:00:00Z"},
        [["aprovacao", "coleta"]],
        naive_policy="strict",
    )
    assert clear["status"] == "ok"

    # Política explícita utc_explicit permite comparar diretamente
    expl = motor_temporal.check_chronology(
        {"aprovacao": "2025-05-01T14:00:00", "coleta": "2025-05-01T12:00:00Z"},
        [["aprovacao", "coleta"]],
        naive_policy="utc_explicit",
    )
    assert expl["status"] == "discrepancy_detected"


def test_ach010_manifest_records_pillow_pytest_cov_and_explicit_params(tmp_path) -> None:
    from scripts.common.provenance import build_run_manifest

    f = tmp_path / "a.txt"
    f.write_text("ok", encoding="utf-8")
    m = build_run_manifest("RUN-ACH010", [f])
    deps = m["environment"]["dependencies"]
    assert deps["Pillow"] is not None
    assert deps["pytest-cov"] is not None
    assert deps["coverage"] is not None
    assert m["config"]["status"] == "no_custom_config_used"
    assert m["seeds"]["status"] == "no_stochastic_seed_used"


def test_geometric_and_data_extended_coverage() -> None:
    import math
    from scripts.engines import motor_dados, motor_geometrico

    # Sólidos 3D: box, sphere, cylinder, cone + rejeição de dimensão negativa
    assert math.isclose(motor_geometrico.solid_3d("box", {"lx": 2, "ly": 3, "lz": 4})["volume"], 24.0)
    assert math.isclose(motor_geometrico.solid_3d("sphere", {"radius": 1})["volume"], 4 * math.pi / 3)
    assert math.isclose(motor_geometrico.solid_3d("cylinder", {"radius": 1, "height": 2})["volume"], 2 * math.pi)
    assert math.isclose(motor_geometrico.solid_3d("cone", {"radius": 1, "height": 3})["volume"], math.pi)
    with pytest.raises(ValueError):
        motor_geometrico.solid_3d("box", {"lx": -1, "ly": 2, "lz": 3})

    # Colisão AABB 3D
    col = motor_geometrico.aabb_collision_3d([0, 0, 0], [2, 2, 2], [1, 1, 1], [3, 3, 3])
    assert col["collides"] is True and math.isclose(col["overlap_volume"], 1.0)
    disj = motor_geometrico.aabb_collision_3d([0, 0, 0], [1, 1, 1], [5, 5, 5], [6, 6, 6])
    assert disj["collides"] is False and disj["overlap_volume"] == 0.0

    # Stackup de tolerâncias
    stk = motor_geometrico.tolerance_stackup([10.0, 20.0], [0.3, 0.4])
    assert math.isclose(stk["worst_case_tolerance"], 0.7)
    assert math.isclose(stk["rss_tolerance"], 0.5)

    # Qualidade de malha triangular (válida e degenerada)
    mq_ok = motor_geometrico.mesh_quality_triangles([[0, 0], [1, 0], [0, 1]], [[0, 1, 2]])
    assert mq_ok["status"] == "ok" and mq_ok["degenerate_count"] == 0
    mq_deg = motor_geometrico.mesh_quality_triangles([[0, 0], [1, 0], [2, 0]], [[0, 1, 2]])
    assert mq_deg["status"] == "discrepancy_detected" and mq_deg["degenerate_count"] == 1

    # Polígono degenerado rejeitado
    with pytest.raises(ValueError, match="degenerado"):
        motor_geometrico.polygon_2d([[0, 0], [1, 0], [2, 0]])

    # motor_dados: outliers e sample_vs_reported
    out_iqr = motor_dados.detect_outliers([10, 11, 10, 12, 11, 10, 100])
    assert 6 in out_iqr["iqr_outlier_indices"]
    svr_bad = motor_dados.sample_vs_reported([10, 20, 30], {"mean": 99.0, "n": 3})
    assert svr_bad["status"] == "discrepancy_detected"


def test_ach011_two_naive_two_utc_and_different_timezones() -> None:
    # 1. Dois horários naive -> comparáveis entre si sem atribuir UTC
    r_naive = motor_temporal.check_chronology(
        {"a": "2025-05-01T08:00:00", "b": "2025-05-01T10:00:00"},
        [["a", "b"]],
    )
    assert r_naive["status"] == "ok"
    assert r_naive["chronological_order_verified"] is True
    assert [e["event"] for e in r_naive["timeline_verified"]] == ["a", "b"]
    assert all(e["has_timezone"] is False for e in r_naive["timeline_verified"])

    # 2. Dois horários UTC
    r_utc = motor_temporal.check_chronology(
        {"b": "2025-05-01T12:00:00Z", "a": "2025-05-01T09:00:00Z"},
        [["a", "b"]],
    )
    assert r_utc["status"] == "ok"
    assert [e["event"] for e in r_utc["timeline_verified"]] == ["a", "b"]

    # 3. Dois horários com fusos diferentes: 10:00-03:00 (=13:00Z) ocorre APÓS 14:00+02:00 (=12:00Z)
    r_tz = motor_temporal.check_chronology(
        {"sp": "2025-05-01T10:00:00-03:00", "berlim": "2025-05-01T14:00:00+02:00"},
        [],
    )
    assert r_tz["status"] == "ok"
    assert [e["event"] for e in r_tz["timeline_verified"]] == ["berlim", "sp"]


def test_ach011_ambiguous_without_and_with_precedence_rules_no_fake_order() -> None:
    # 4 & 5. Mistura naive + UTC SEM regras de precedência -> NÃO pode retornar ok nem inventar ordem factual!
    r_no_rules = motor_temporal.run_motor(
        {
            "events": {"ev_utc": "2025-05-01T12:00:00Z", "ev_naive": "2025-05-01T10:00:00"},
            "precedence_rules": [],
        }
    )
    validate_contract(r_no_rules, "schema_motor.json")
    res = r_no_rules["resultados"]
    assert res["status"] == "unverified"
    assert res["chronological_order_verified"] is False
    assert res["timeline_verified"] == []
    # Preserva estritamente a ordem de entrada em timeline_ambiguous (ev_utc antes de ev_naive!)
    assert [e["event"] for e in res["timeline_ambiguous"]] == ["ev_utc", "ev_naive"]
    assert r_no_rules["achados"][0]["estado"] == "NAO_VERIFICADO"

    # 6. Mistura ambígua COM regra de precedência
    r_with_rules = motor_temporal.check_chronology(
        {"ev_naive": "2025-05-01T10:00:00", "ev_utc": "2025-05-01T12:00:00Z"},
        [["ev_naive", "ev_utc"]],
    )
    assert r_with_rules["status"] == "unverified"
    assert r_with_rules["chronological_order_verified"] is False
    assert len(r_with_rules["ambiguities"]) == 1


def test_ach011_over_26h_and_mixed_day_vs_datetime() -> None:
    # 7. Naive e UTC separados por > 26 horas -> ordenação verificável!
    r_far = motor_temporal.check_chronology(
        {"ev_naive": "2025-05-01T10:00:00", "ev_utc": "2025-05-03T12:00:00Z"},
        [["ev_naive", "ev_utc"]],
    )
    assert r_far["status"] == "ok"
    assert r_far["chronological_order_verified"] is True
    assert [e["event"] for e in r_far["timeline_verified"]] == ["ev_naive", "ev_utc"]

    # 8. Data diária misturada com data+hora no MESMO dia -> ambíguo (hora do evento diário é desconhecida)
    r_same_day = motor_temporal.check_chronology(
        {"dia": "2025-05-01", "hora": "2025-05-01T14:00:00"},
        [],
    )
    assert r_same_day["status"] == "unverified"
    assert r_same_day["chronological_order_verified"] is False

    # Data diária e data+hora em dias bem separados -> verificável
    r_diff_day = motor_temporal.check_chronology(
        {"dia": "2025-05-01", "hora": "2025-05-05T14:00:00Z"},
        [["dia", "hora"]],
    )
    assert r_diff_day["status"] == "ok"
    assert r_diff_day["chronological_order_verified"] is True


def test_ach013_manifest_relative_paths_self_exclusion_and_git_dirty(tmp_path) -> None:
    from scripts.common.provenance import build_run_manifest

    sub = tmp_path / "scripts"
    sub.mkdir()
    f = sub / "sample.py"
    f.write_text("x = 1\n", encoding="utf-8")

    m = build_run_manifest(
        "RUN-ACH013",
        [f],
        self_excluded_files=["relatorios_execucao/run_manifest.json"],
        repo_root=tmp_path,
    )
    rec = m["inspected_files"][0]
    assert rec["relative_path"] == "scripts/sample.py"
    assert "path" not in rec
    assert "C:" not in rec["relative_path"] and "\\" not in rec["relative_path"]
    assert "relatorios_execucao/run_manifest.json" in m["self_excluded_files"]
    assert "git_dirty" in m
