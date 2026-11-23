"""Testes de aceitação da Fase 4 (v8.0-beta.4): linguagem, figuras, imagem forense e consistência cruzada."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from scripts.common.schema_validator import validate_contract
from scripts.engines import (
    motor_consistencia_cruzada,
    motor_figuras,
    motor_imagem_forense,
    motor_linguagem,
)


def test_motor_linguagem_interventions_without_auto_rewrite() -> None:
    text = (
        "O modelo MPC comprova que vários resultados resultados melhoram. "
        "O sistema Controle Preditivo (CP) reduz perdas, enquanto o módulo XYZ opera em paralelo."
    )
    out = motor_linguagem.run_motor(
        {
            "text": text,
            "glossary_canonical": {"Controle Preditivo Baseado em Modelo": ["modelo MPC"]},
        },
        run_id="TEST-LNG-01",
    )
    validate_contract(out, "schema_motor.json")
    assert out["status"] == "COM_ACHADOS"
    assert out["resultados"]["auto_rewritten"] is False
    assert "XYZ" in out["resultados"]["undefined_acronyms"]
    assert "CP" not in out["resultados"]["undefined_acronyms"]
    cats = {a["categoria"] for a in out["achados"]}
    assert "linguagem_duplicate_word" in cats
    assert "linguagem_epistemic_precision" in cats
    assert "linguagem_terminology_inconsistency" in cats


def test_motor_figuras_resolution_dpi_and_visual_inventory(tmp_path: Path) -> None:
    # Figura de baixa resolução e baixo contraste
    low_img = tmp_path / "low_fig.png"
    arr = np.full((200, 300, 3), 128, dtype=np.uint8)
    Image.fromarray(arr).save(low_img, dpi=(72, 72))

    # Figura de alta resolução e alto contraste
    hi_img = tmp_path / "hi_fig.png"
    grad = np.tile(np.linspace(0, 255, 1000, dtype=np.uint8), (600, 1))
    Image.fromarray(grad).save(hi_img, dpi=(300, 300))

    out = motor_figuras.run_motor(
        {
            "operation": "batch",
            "operations": [
                {"id": "FIG-001", "operation": "inspect_figure", "file_path": str(low_img), "caption": "", "has_axes_units": False},
                {"id": "FIG-002", "operation": "inspect_figure", "file_path": str(hi_img), "caption": "Perfil térmico (K)", "has_axes_units": True},
                {
                    "id": "INV-001",
                    "operation": "build_visual_inventory",
                    "items": [
                        {"kind": "figure", "source_file": "hi_fig.png", "page": 12, "caption": "Perfil térmico"},
                        {"kind": "table", "source_file": "main.tex", "page": 14, "caption": "Resumo"},
                        {"kind": "equation", "source_file": "main.tex", "page": 10},
                        {"kind": "algorithm", "source_file": "main.tex", "page": 15},
                    ],
                },
            ],
        }
    )
    validate_contract(out, "schema_motor.json")
    assert out["status"] == "COM_ACHADOS"
    res_list = out["resultados"]["results"]
    assert res_list[0]["status"] == "discrepancy_detected"
    assert res_list[1]["status"] == "ok"
    ids = [obj["object_id"] for obj in res_list[2]["objects"]]
    assert ids == ["FIG-001", "TAB-001", "EQ-001", "ALG-001"]


def test_motor_imagem_forense_duplicates_and_no_auto_fraud(tmp_path: Path) -> None:
    arr = np.tile(np.linspace(0, 255, 128, dtype=np.uint8), (128, 1))
    f1 = tmp_path / "img1.png"
    f2 = tmp_path / "img2.png"
    Image.fromarray(arr).save(f1)
    Image.fromarray(arr).save(f2)

    out = motor_imagem_forense.run_motor(
        {"id": "DUP-01", "operation": "check_image_duplicates", "file_paths": [str(f1), str(f2)]}
    )
    validate_contract(out, "schema_motor.json")
    assert out["status"] == "COM_ACHADOS"
    res = out["resultados"]["results"][0]
    assert len(res["exact_duplicates"]) == 1
    assert res["declares_manipulation"] is False


def test_motor_consistencia_cruzada_domino_and_legitimate_conversions() -> None:
    # Caso do Plano Mestre: código/planilha/tabela = 78.4 °C, gráfico = 351.55 K (equivalente!), texto = 82.4 °C (divergência!)
    out = motor_consistencia_cruzada.run_motor(
        {
            "quantities": [
                {
                    "quantity_id": "T_max",
                    "observations": [
                        {"source_type": "codigo", "location": "sim.py:L42", "object_id": "COD-001", "value": 78.4, "unit": "°C"},
                        {"source_type": "planilha", "location": "dados.csv:B10", "object_id": "DAT-001", "value": 78.4, "unit": "°C"},
                        {"source_type": "tabela", "location": "Tabela 2", "object_id": "TAB-002", "value": 78.4, "unit": "°C"},
                        {"source_type": "grafico", "location": "Figura 3", "object_id": "FIG-003", "value": 351.55, "unit": "K"},
                        {"source_type": "texto", "location": "Seção 4.2, p. 38", "object_id": "TXT-014", "value": 82.4, "unit": "°C"},
                    ],
                },
                {
                    "quantity_id": "eficiencia",
                    "observations": [
                        {"source_type": "codigo", "location": "sim.py:L88", "value": 0.9234, "unit": "1"},
                        {"source_type": "texto", "location": "Resumo", "value": 92.3, "unit": "%", "decimals": 1},
                    ],
                },
            ]
        },
        run_id="TEST-XCS-01",
    )
    validate_contract(out, "schema_motor.json")
    assert out["status"] == "COM_ACHADOS"
    q_temp, q_eff = out["resultados"]["quantities"]
    assert q_temp["consistent"] is False
    assert len(q_temp["divergences"]) == 1
    assert q_temp["divergences"][0]["divergent_location"] == "Seção 4.2, p. 38"
    assert q_eff["consistent"] is True
    assert len(out["achados"]) == 1
    assert out["achados"][0]["gravidade"] == "CRITICO"
