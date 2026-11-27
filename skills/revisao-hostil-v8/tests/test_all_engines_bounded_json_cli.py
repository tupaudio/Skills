"""Testes de runtime para verificar que todos os 21 motores utilizam read_bounded_json no CLI,
comportam-se corretamente nos limites exatos de bytes e rejeitam payloads excedentes."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from scripts.common.schema_validator import validate_contract
from scripts.common.validation import MAX_JSON_PAYLOAD_BYTES

_REPO_ROOT = Path(__file__).resolve().parents[1]
_ENGINES_DIR = _REPO_ROOT / "scripts" / "engines"

ENGINES_LIST = [
    "motor_argumentacao",
    "motor_consistencia_cruzada",
    "motor_dados",
    "motor_dimensional",
    "motor_estatistico",
    "motor_estetico",
    "motor_etica",
    "motor_evidencia",
    "motor_figuras",
    "motor_geometrico",
    "motor_imagem_forense",
    "motor_incerteza",
    "motor_linguagem",
    "motor_matematico",
    "motor_metadados",
    "motor_nomenclatura",
    "motor_normas",
    "motor_qualitativo",
    "motor_reprodutibilidade",
    "motor_risco",
    "motor_temporal",
]


@pytest.fixture(scope="module")
def valid_fixtures(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """Cria fixtures mínimas e temporárias para alimentar os 21 motores em execução normal."""
    tmp_dir = tmp_path_factory.mktemp("engine_fixtures")
    img_path = tmp_dir / "sample_test.png"
    img = Image.new("RGB", (32, 32), color=(128, 128, 128))
    img.save(img_path)

    return {
        "motor_argumentacao": {
            "arguments": [
                {
                    "id": "ARG-1",
                    "claim": "Hipótese de teste",
                    "premises": ["Premissa 1"],
                    "evidence": ["EV-1"],
                    "conclusion": "Conclusão 1",
                }
            ]
        },
        "motor_consistencia_cruzada": {
            "quantities": [
                {
                    "quantity_id": "Q_001",
                    "observations": [
                        {"location": "p.1", "value": 10.0, "unit": "m"},
                        {"location": "p.2", "value": 10.0, "unit": "m"},
                    ],
                }
            ]
        },
        "motor_dados": {
            "operation": "batch",
            "operations": [{"id": "op_valid", "operation": "tabular_quality", "rows": [{"col": 1}, {"col": 2}]}],
        },
        "motor_dimensional": {
            "operation": "batch",
            "operations": [
                {
                    "id": "op_valid",
                    "operation": "convert_unit",
                    "value": 1000.0,
                    "from_unit": "m",
                    "to_unit": "km",
                    "reported_value": 1.0,
                }
            ],
        },
        "motor_estatistico": {
            "operation": "batch",
            "operations": [{"id": "op_valid", "operation": "confidence_interval", "sample": [10, 11, 12, 10.5, 11.5]}],
        },
        "motor_estetico": {
            "file_path": str(img_path),
        },
        "motor_etica": {
            "operation": "batch",
            "operations": [
                {
                    "id": "op_valid",
                    "operation": "screen_ethics_declarations",
                    "text": "This study was approved by the Institutional Ethics Committee.",
                }
            ],
        },
        "motor_evidencia": {
            "framework": "GRADE",
            "study_design": "rct",
        },
        "motor_figuras": {
            "operation": "batch",
            "operations": [{"id": "op_valid", "operation": "build_visual_inventory", "items": []}],
        },
        "motor_geometrico": {
            "operation": "batch",
            "operations": [{"id": "op_valid", "operation": "solid_3d", "shape": "sphere", "dimensions": {"radius": 1.0}}],
        },
        "motor_imagem_forense": {
            "operation": "batch",
            "operations": [{"id": "op_valid", "operation": "check_image_duplicates", "file_paths": []}],
        },
        "motor_incerteza": {
            "operation": "batch",
            "operations": [
                {
                    "id": "op_valid",
                    "operation": "propagate_gum",
                    "expression": "x + y",
                    "variables": {
                        "x": {"value": 10.0, "standard_uncertainty": 0.1},
                        "y": {"value": 5.0, "standard_uncertainty": 0.2},
                    },
                }
            ],
        },
        "motor_linguagem": {
            "text": "Este artigo descreve um método muito bom e reprodutível.",
        },
        "motor_matematico": {
            "operation": "formula",
            "lhs": "y",
            "rhs": "x + 1",
            "substitutions": {"x": 2, "y": 3},
        },
        "motor_metadados": {
            "files": ["references/schemas/schema_motor.json"],
        },
        "motor_nomenclatura": {
            "symbol_definitions": [{"symbol": "x", "meaning": "variável", "location": "eq1"}],
        },
        "motor_normas": {
            "citations": [{"norm_id": "ABNT_NBR_6023", "id": "NRM_001"}],
        },
        "motor_qualitativo": {
            "operation": "batch",
            "operations": [{"id": "op_valid", "operation": "cohens_kappa", "coder_a": ["sim", "nao"], "coder_b": ["sim", "nao"]}],
        },
        "motor_reprodutibilidade": {
            "has_data": True,
            "has_scripts": True,
            "has_environment_spec": True,
        },
        "motor_risco": {
            "operation": "batch",
            "operations": [{"id": "op_valid", "operation": "evaluate_risk_matrix", "hazard": "Ruido", "probability": 2, "severity": 3}],
        },
        "motor_temporal": {
            "events": {"E1": "2020-01-01T00:00:00Z", "E2": "2021-01-01T00:00:00Z"},
        },
    }


def test_programmatic_verification_all_21_engines_use_read_bounded_json() -> None:
    """Verifica estaticamente por AST que todos os 21 motores chamam read_bounded_json."""
    engine_files = sorted(_ENGINES_DIR.glob("motor_*.py"))
    assert len(engine_files) == 21, f"Esperado exatamente 21 motores, encontrados: {len(engine_files)}"

    unprotected = []
    for f in engine_files:
        content = f.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(f))

        has_bounded_call = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id == "read_bounded_json":
                    has_bounded_call = True
                    break
        if not has_bounded_call:
            unprotected.append(f.name)

    assert not unprotected, f"Motores sem chamada a read_bounded_json detectados: {unprotected}"


@pytest.mark.parametrize("engine_name", ENGINES_LIST)
def test_all_21_engines_cli_valid_payload_stdin_and_input_file(
    engine_name: str,
    valid_fixtures: dict[str, Any],
    tmp_path: Path,
) -> None:
    """Testa execução normal via stdin e --input para todos os 21 motores, assegurando código 0 e schema válido."""
    script_path = _ENGINES_DIR / f"{engine_name}.py"
    payload = valid_fixtures[engine_name]
    raw_json = json.dumps(payload, ensure_ascii=False)

    # 1. Stdin válido
    proc_stdin = subprocess.run(
        [sys.executable, str(script_path)],
        input=raw_json,
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
    )
    assert proc_stdin.returncode == 0, (
        f"{engine_name} falhou com stdin válido (retorno {proc_stdin.returncode}). Stderr: {proc_stdin.stderr}"
    )
    assert "Traceback (most recent call last)" not in proc_stdin.stderr
    data_stdin = json.loads(proc_stdin.stdout)
    validate_contract(data_stdin, "schema_motor.json")
    assert data_stdin["status"] in ("OK", "COM_ACHADOS")

    # 2. Arquivo (--input) válido
    input_file = tmp_path / f"valid_{engine_name}.json"
    input_file.write_text(raw_json, encoding="utf-8")
    proc_file = subprocess.run(
        [sys.executable, str(script_path), "--input", str(input_file)],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
    )
    assert proc_file.returncode == 0, (
        f"{engine_name} falhou com --input válido (retorno {proc_file.returncode}). Stderr: {proc_file.stderr}"
    )
    assert "Traceback (most recent call last)" not in proc_file.stderr
    data_file = json.loads(proc_file.stdout)
    validate_contract(data_file, "schema_motor.json")
    assert data_file["status"] in ("OK", "COM_ACHADOS")


@pytest.mark.parametrize("engine_name", ENGINES_LIST)
def test_all_21_engines_cli_reject_oversized_payload(
    engine_name: str,
    tmp_path: Path,
) -> None:
    """Testa que payload com MAX_JSON_PAYLOAD_BYTES + 1 é rejeitado no stdin e no --input antes do parse."""
    script_path = _ENGINES_DIR / f"{engine_name}.py"

    # Constrói payload de tamanho exato MAX_JSON_PAYLOAD_BYTES + 1
    # {"k": "<padding>"}
    base_json = json.dumps({"k": ""})
    pad_len = (MAX_JSON_PAYLOAD_BYTES + 1) - len(base_json.encode("utf-8"))
    oversized_str = json.dumps({"k": "A" * pad_len})
    assert len(oversized_str.encode("utf-8")) == MAX_JSON_PAYLOAD_BYTES + 1

    # 1. Stdin excedente
    proc_stdin = subprocess.run(
        [sys.executable, str(script_path)],
        input=oversized_str,
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
    )
    assert proc_stdin.returncode == 1, (
        f"{engine_name} deveria ter retornado código 1 para stdin excedente, retornou {proc_stdin.returncode}"
    )
    assert not proc_stdin.stderr.strip(), (
        f"{engine_name} emitiu traceback/conteúdo em stderr para stdin excedente: {proc_stdin.stderr}"
    )
    out_stdin = json.loads(proc_stdin.stdout)
    validate_contract(out_stdin, "schema_motor.json")
    assert out_stdin["status"] == "ERRO_EXECUCAO"
    assert "excede o limite" in out_stdin["resultados"]["error"]

    # 2. Arquivo (--input) excedente
    oversized_file = tmp_path / "oversized_payload.json"
    oversized_file.write_text(oversized_str, encoding="utf-8")
    proc_file = subprocess.run(
        [sys.executable, str(script_path), "--input", str(oversized_file)],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
    )
    assert proc_file.returncode == 1, (
        f"{engine_name} deveria ter retornado código 1 para arquivo excedente, retornou {proc_file.returncode}"
    )
    assert not proc_file.stderr.strip(), (
        f"{engine_name} emitiu traceback/conteúdo em stderr para arquivo excedente: {proc_file.stderr}"
    )
    out_file = json.loads(proc_file.stdout)
    validate_contract(out_file, "schema_motor.json")
    assert out_file["status"] == "ERRO_EXECUCAO"
    assert "excede o limite" in out_file["resultados"]["error"]


def test_exact_limit_boundary_accepted_by_helper(tmp_path: Path) -> None:
    """Verifica que payload exatamente em MAX_JSON_PAYLOAD_BYTES não é rejeitado por limite de tamanho.

    Nota Metodológica:
    O teste de fronteira no limite exato de bytes (10.485.760 bytes) foi verificado diretamente
    no helper centralizado (`read_bounded_json`), tanto para stream quanto para arquivo regular,
    evitando a sobrecarga de subprocessos de 10 MB em cada um dos 21 CLIs. Os 21 CLIs são
    testados em runtime para rejeição de payload excedente (MAX_JSON_PAYLOAD_BYTES + 1) e
    para payloads válidos.
    """
    from scripts.common.validation import read_bounded_json
    import io

    base_json = json.dumps({"k": ""})
    pad_len = MAX_JSON_PAYLOAD_BYTES - len(base_json.encode("utf-8"))
    exact_str = json.dumps({"k": "A" * pad_len})
    assert len(exact_str.encode("utf-8")) == MAX_JSON_PAYLOAD_BYTES

    # Stdin stream exato
    s_in = io.StringIO(exact_str)
    res_stream, src_stream = read_bounded_json(s_in, max_bytes=MAX_JSON_PAYLOAD_BYTES)
    assert src_stream == "stdin"
    assert res_stream["k"] == "A" * pad_len

    # Arquivo exato
    f_in = tmp_path / "exact_limit.json"
    f_in.write_text(exact_str, encoding="utf-8")
    res_file, src_file = read_bounded_json(f_in, max_bytes=MAX_JSON_PAYLOAD_BYTES)
    assert str(f_in.resolve()) in src_file
    assert res_file["k"] == "A" * pad_len
