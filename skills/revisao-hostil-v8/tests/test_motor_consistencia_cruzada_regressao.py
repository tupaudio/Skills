import pytest
import itertools
from scripts.common.schema_validator import validate_contract
from scripts.engines import motor_consistencia_cruzada


def test_order_invariance_and_symmetry_tied_authority():
    # Duas observações divergentes sem source_type (empate de autoridade 99)
    obs1 = {"name": "comprimento", "value": 100.0, "unit": "m", "location": "p. 5"}
    obs2 = {"name": "comprimento", "value": 150.0, "unit": "m", "location": "p. 12"}

    payload1 = {
        "operation": "quantity_consistency",
        "quantity_id": "comprimento",
        "observations": [obs1, obs2],
    }
    payload2 = {
        "operation": "quantity_consistency",
        "quantity_id": "comprimento",
        "observations": [obs2, obs1],
    }

    out1 = motor_consistencia_cruzada.run_motor(payload1)
    out2 = motor_consistencia_cruzada.run_motor(payload2)

    errors1 = validate_contract(out1, "schema_motor.json", raise_on_error=False)
    assert not errors1, f"Schema invalido out1: {errors1}"
    errors2 = validate_contract(out2, "schema_motor.json", raise_on_error=False)
    assert not errors2, f"Schema invalido out2: {errors2}"

    # Status deve ser idêntico
    assert out1["status"] == "COM_ACHADOS"
    assert out2["status"] == "COM_ACHADOS"

    # Achados devem ser estritamente simétricos e invariantes à ordem
    ach1 = out1["achados"][0]
    ach2 = out2["achados"][0]

    assert ach1["estado"] == "NAO_VERIFICADO"
    assert ach2["estado"] == "NAO_VERIFICADO"
    assert ach1["localizacao"] == ach2["localizacao"] == "p. 12, p. 5"
    assert ach1["titulo"] == ach2["titulo"]
    assert ach1["descricao"] == ach2["descricao"]
    assert "alinhar com a fonte primária" not in ach1.get("acao_recomendada", "").lower()


def test_same_source_type_tied_authority():
    # Ambas com mesmo source_type (ex: 'tabela')
    obs1 = {"value": 100.0, "unit": "m", "source_type": "tabela", "location": "Tab 1"}
    obs2 = {"value": 150.0, "unit": "m", "source_type": "tabela", "location": "Tab 2"}

    out = motor_consistencia_cruzada.run_motor({"quantities": [{"quantity_id": "L", "observations": [obs1, obs2]}]})
    validate_contract(out, "schema_motor.json")
    assert out["status"] == "COM_ACHADOS"
    ach = out["achados"][0]
    assert ach["estado"] == "NAO_VERIFICADO"
    assert ach["localizacao"] == "Tab 1, Tab 2"


def test_different_source_types_asymmetric_preserved():
    # Hierarquia clara: codigo (0) vs texto (4)
    obs_cod = {"value": 100.0, "unit": "m", "source_type": "codigo", "location": "main.py"}
    obs_txt = {"value": 150.0, "unit": "m", "source_type": "texto", "location": "Sec 2"}

    # Ordem codigo primeiro
    out1 = motor_consistencia_cruzada.run_motor({"quantities": [{"quantity_id": "L", "observations": [obs_cod, obs_txt]}]})
    # Ordem texto primeiro
    out2 = motor_consistencia_cruzada.run_motor({"quantities": [{"quantity_id": "L", "observations": [obs_txt, obs_cod]}]})

    for out in [out1, out2]:
        validate_contract(out, "schema_motor.json")
        assert out["status"] == "COM_ACHADOS"
        ach = out["achados"][0]
        # Aqui, a hierarquia assimétrica é legítima: codigo domina texto
        assert ach["estado"] == "CONFIRMADO"
        assert ach["localizacao"] == "Sec 2"
        assert "main.py" in ach["acao_recomendada"]


def test_three_or_more_observations_groups():
    # 3 observações com 2 valores distintos sem fonte primária dominante
    obs1 = {"value": 10.0, "unit": "kg", "location": "p. 1"}
    obs2 = {"value": 10.0, "unit": "kg", "location": "p. 3"}
    obs3 = {"value": 12.0, "unit": "kg", "location": "p. 7"}

    out = motor_consistencia_cruzada.run_motor({"quantities": [{"quantity_id": "massa", "observations": [obs1, obs2, obs3]}]})
    validate_contract(out, "schema_motor.json")
    assert out["status"] == "COM_ACHADOS"
    ach = out["achados"][0]
    assert ach["estado"] == "NAO_VERIFICADO"
    assert "p. 1" in ach["localizacao"] and "p. 3" in ach["localizacao"] and "p. 7" in ach["localizacao"]
    assert "valor 10" in ach["descricao"] and "valor 12" in ach["descricao"]
