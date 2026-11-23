"""Testes unitários, regressão de regex e contrato do auditor.py (Beta 2)."""

from __future__ import annotations

from pathlib import Path

import docx

from scripts.auditor import run_auditor
from scripts.common.schema_validator import validate_contract


def test_def_a01_100_percent_and_epistemic_overclaim_detected(tmp_path: Path) -> None:
    md = tmp_path / "sample.md"
    md.write_text(
        "A simulação comprova 100% de eficiência em regime permanente.\n"
        "E = m * c^2\n"
        "Veja Figura 1 e Tabela 2 para redução de 100 W para 80 W.\n",
        encoding="utf-8",
    )

    report = run_auditor(md, run_id="TEST-AUD-01")
    validate_contract(report, "schema_motor.json")

    cats = report["metricas"]["contagem_por_categoria"]
    assert cats.get("absolute_claim", 0) >= 1, "DEF-A01: 100% deve ser detectado como absolute_claim"
    assert cats.get("epistemic_overclaim", 0) >= 1
    assert cats.get("equation_candidate", 0) >= 1
    assert cats.get("quantitative_comparison", 0) >= 1
    assert cats.get("cross_reference", 0) >= 1


def test_domain_rules_decoupled_from_generic_auditor(tmp_path: Path) -> None:
    txt = tmp_path / "eng.txt"
    txt.write_text(
        "O sistema apresenta potência de 10 kWh e estabilidade de Lyapunov com zero eclipse.\n",
        encoding="utf-8",
    )

    generic_report = run_auditor(txt, include_engineering_preset=False)
    validate_contract(generic_report, "schema_motor.json")
    assert "power_energy_confusion" not in generic_report["metricas"]["contagem_por_categoria"]

    eng_report = run_auditor(txt, include_engineering_preset=True)
    validate_contract(eng_report, "schema_motor.json")
    eng_cats = eng_report["metricas"]["contagem_por_categoria"]
    assert eng_cats.get("power_energy_confusion", 0) == 1
    assert eng_cats.get("method_review", 0) == 1
    assert eng_cats.get("absolute_claim_domain", 0) == 1


def test_docx_forensics_double_blind_and_latex_leak(tmp_path: Path) -> None:
    doc_path = tmp_path / "blind.docx"
    document = docx.Document()
    document.core_properties.author = "Autor Identificado"
    document.add_paragraph(r"Resultado calculado por \frac{a}{b} com **negrito cru**.")
    tbl = document.add_table(rows=2, cols=2)
    tbl.rows[0].cells[0].text = "Item"
    tbl.rows[0].cells[1].text = "Valor"
    tbl.rows[1].cells[0].text = "Total"
    tbl.rows[1].cells[1].text = "100 W"
    document.save(str(doc_path))

    report = run_auditor(doc_path)
    validate_contract(report, "schema_motor.json")
    cats = report["metricas"]["contagem_por_categoria"]
    assert cats.get("double_blind_violation", 0) == 1
    assert cats.get("formatting_leak", 0) == 1
    assert len(report["resultados"]["tables"]) == 1
