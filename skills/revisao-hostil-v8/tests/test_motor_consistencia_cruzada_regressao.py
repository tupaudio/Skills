import pytest
import itertools
from scripts.common.schema_validator import validate_contract
from scripts.engines import motor_consistencia_cruzada


def test_order_invariance_and_symmetry_tied_authority():
    # Duas observações divergentes com mesmo source_type (empate de autoridade simétrico)
    obs1 = {"name": "comprimento", "value": 100.0, "unit": "m", "location": "p. 5", "source_type": "texto"}
    obs2 = {"name": "comprimento", "value": 150.0, "unit": "m", "location": "p. 12", "source_type": "texto"}

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
    obs1 = {"value": 10.0, "unit": "kg", "location": "p. 1", "source_type": "texto"}
    obs2 = {"value": 10.0, "unit": "kg", "location": "p. 3", "source_type": "texto"}
    obs3 = {"value": 12.0, "unit": "kg", "location": "p. 7", "source_type": "texto"}

    out = motor_consistencia_cruzada.run_motor({"quantities": [{"quantity_id": "massa", "observations": [obs1, obs2, obs3]}]})
    validate_contract(out, "schema_motor.json")
    assert out["status"] == "COM_ACHADOS"
    ach = out["achados"][0]
    assert ach["estado"] == "NAO_VERIFICADO"
    assert "p. 1" in ach["localizacao"] and "p. 3" in ach["localizacao"] and "p. 7" in ach["localizacao"]
    assert "valor 10" in ach["descricao"] and "valor 12" in ach["descricao"]


def test_source_type_required_missing_rejected_both_orders():
    # Observação sem source_type rejeitada em ambas as ordens de inserção
    # Ordem 1: obs1 válida, obs2 sem tipo
    p1 = {
        "quantities": [
            {
                "quantity_id": "Q_sem_tipo_1",
                "observations": [
                    {"location": "Sec1", "value": 10.0, "source_type": "texto"},
                    {"location": "Sec2", "value": 20.0},
                ],
            }
        ]
    }
    out1 = motor_consistencia_cruzada.run_motor(p1)
    validate_contract(out1, "schema_motor.json")
    assert out1["status"] == "ERRO_VALIDACAO"
    res1 = out1["resultados"]["quantities"][0]
    assert res1["success"] is False
    assert res1["status"] == "error"
    assert "Observação 2 da grandeza 'Q_sem_tipo_1' possui source_type inválido: None" in res1["error"]
    accepted_10 = ["codigo", "simulacao", "planilha", "dataset", "tabela", "figura", "grafico", "texto", "resumo", "conclusao"]
    for t in accepted_10:
        assert t in res1["error"]

    # Ordem 2: obs1 sem tipo, obs2 válida
    p2 = {
        "quantities": [
            {
                "quantity_id": "Q_sem_tipo_2",
                "observations": [
                    {"location": "Sec2", "value": 20.0},
                    {"location": "Sec1", "value": 10.0, "source_type": "texto"},
                ],
            }
        ]
    }
    out2 = motor_consistencia_cruzada.run_motor(p2)
    validate_contract(out2, "schema_motor.json")
    assert out2["status"] == "ERRO_VALIDACAO"
    res2 = out2["resultados"]["quantities"][0]
    assert res2["success"] is False
    assert res2["status"] == "error"
    assert "Observação 1 da grandeza 'Q_sem_tipo_2' possui source_type inválido: None" in res2["error"]
    for t in accepted_10:
        assert t in res2["error"]


def test_source_type_invalid_and_unknown_error_message():
    accepted_10 = ["codigo", "simulacao", "planilha", "dataset", "tabela", "figura", "grafico", "texto", "resumo", "conclusao"]

    # Caso 1: tipo desconhecido (string 'desconhecido')
    p_unk = {
        "quantities": [
            {
                "quantity_id": "Q_unk",
                "observations": [
                    {"location": "p.1", "value": 10.0, "source_type": "texto"},
                    {"location": "p.2", "value": 10.0, "source_type": "desconhecido"},
                ],
            }
        ]
    }
    out_unk = motor_consistencia_cruzada.run_motor(p_unk)
    validate_contract(out_unk, "schema_motor.json")
    assert out_unk["status"] == "ERRO_VALIDACAO"
    err_unk = out_unk["resultados"]["quantities"][0]["error"]
    # Confere índice (2), valor recebido ('desconhecido') e os 10 tipos aceitos
    assert "Observação 2" in err_unk
    assert "'desconhecido'" in err_unk
    for t in accepted_10:
        assert t in err_unk

    # Caso 2: tipo não-string (int 123)
    p_int = {
        "quantities": [
            {
                "quantity_id": "Q_int",
                "observations": [
                    {"location": "p.1", "value": 10.0, "source_type": 123},
                    {"location": "p.2", "value": 10.0, "source_type": "texto"},
                ],
            }
        ]
    }
    out_int = motor_consistencia_cruzada.run_motor(p_int)
    validate_contract(out_int, "schema_motor.json")
    assert out_int["status"] == "ERRO_VALIDACAO"
    err_int = out_int["resultados"]["quantities"][0]["error"]
    assert "Observação 1" in err_int
    assert "123" in err_int
    for t in accepted_10:
        assert t in err_int


def test_source_type_normalization_whitespace_and_case():
    # 'Texto' e ' texto ' devem ser aceitos por normalização strip().lower()
    p = {
        "quantities": [
            {
                "quantity_id": "Q_norm",
                "observations": [
                    {"location": "p.1", "value": 10.0, "source_type": "Texto"},
                    {"location": "p.2", "value": 10.0, "source_type": " texto "},
                ],
            }
        ]
    }
    out = motor_consistencia_cruzada.run_motor(p)
    validate_contract(out, "schema_motor.json")
    assert out["status"] == "OK"
    res = out["resultados"]["quantities"][0]
    assert res["success"] is True
    assert res["status"] == "ok"
    assert res["graph"]["nodes"][0]["source_type"] == "texto"
    assert res["graph"]["nodes"][1]["source_type"] == "texto"


def test_batch_mixed_valid_and_invalid_quantities_partial():
    # Lote com grandeza válida e grandeza inválida => PARCIAL
    p = {
        "quantities": [
            {
                "quantity_id": "Q_valida",
                "observations": [
                    {"location": "p.1", "value": 10.0, "source_type": "texto"},
                    {"location": "p.2", "value": 10.0, "source_type": "tabela"},
                ],
            },
            {
                "quantity_id": "Q_invalida",
                "observations": [
                    {"location": "p.1", "value": 10.0, "source_type": None},
                    {"location": "p.2", "value": 10.0, "source_type": "texto"},
                ],
            },
        ]
    }
    out = motor_consistencia_cruzada.run_motor(p)
    validate_contract(out, "schema_motor.json")
    assert out["status"] == "PARCIAL"
    assert out["metricas"]["sucesso"] == 1
    assert out["metricas"]["falhas"] == 1
    assert out["resultados"]["quantities"][0]["success"] is True
    assert out["resultados"]["quantities"][1]["success"] is False


def test_batch_all_invalid_quantities_erro_validacao():
    # Lote onde todas as grandezas falham => ERRO_VALIDACAO
    p = {
        "quantities": [
            {
                "quantity_id": "Q_inv1",
                "observations": [
                    {"location": "p.1", "value": 10.0},
                    {"location": "p.2", "value": 10.0, "source_type": "texto"},
                ],
            },
            {
                "quantity_id": "Q_inv2",
                "observations": [
                    {"location": "p.1", "value": 10.0, "source_type": "desconhecido"},
                    {"location": "p.2", "value": 10.0, "source_type": "texto"},
                ],
            },
        ]
    }
    out = motor_consistencia_cruzada.run_motor(p)
    validate_contract(out, "schema_motor.json")
    assert out["status"] == "ERRO_VALIDACAO"
    assert out["metricas"]["sucesso"] == 0
    assert out["metricas"]["falhas"] == 2


def test_single_observation_fails_by_len_less_than_two():
    # Grandeza isolada com 1 observação continua falhando com ValueError por len < 2
    import pytest
    with pytest.raises(ValueError, match="requer pelo menos 2 observações para comparação cruzada"):
        motor_consistencia_cruzada.check_quantity_consistency(
            "Q_single",
            [{"location": "p.1", "value": 10.0, "source_type": "texto"}],
        )

    # Via run_motor, retorna erro da grandeza e envelope ERRO_VALIDACAO
    out = motor_consistencia_cruzada.run_motor({
        "quantities": [
            {"quantity_id": "Q_single", "observations": [{"location": "p.1", "value": 10.0}]}
        ]
    })
    validate_contract(out, "schema_motor.json")
    assert out["status"] == "ERRO_VALIDACAO"
    assert "requer pelo menos 2 observações para comparação cruzada" in out["resultados"]["quantities"][0]["error"]


def test_observation_non_dict_rejected_in_batch_partial():
    # Observações que não são dict (None e string) em lote com grandeza válida => PARCIAL
    p = {
        "quantities": [
            {
                "quantity_id": "Q_valida",
                "observations": [
                    {"location": "p.1", "value": 10.0, "source_type": "texto"},
                    {"location": "p.2", "value": 10.0, "source_type": "tabela"},
                ],
            },
            {
                "quantity_id": "Q_obs_none",
                "observations": [
                    None,
                    {"location": "p.2", "value": 10.0, "source_type": "texto"},
                ],
            },
            {
                "quantity_id": "Q_obs_str",
                "observations": [
                    {"location": "p.1", "value": 10.0, "source_type": "texto"},
                    "observacao_invalida_string",
                ],
            },
        ]
    }
    out = motor_consistencia_cruzada.run_motor(p)
    validate_contract(out, "schema_motor.json")
    assert out["status"] == "PARCIAL"
    assert out["metricas"]["sucesso"] == 1
    assert out["metricas"]["falhas"] == 2

    # Verifica preservação da válida
    res_val = out["resultados"]["quantities"][0]
    assert res_val["success"] is True
    assert res_val["quantity_id"] == "Q_valida"

    # Verifica mensagens de erro com índice e type(obs).__name__
    res_none = out["resultados"]["quantities"][1]
    assert res_none["success"] is False
    assert "Observação 1 da grandeza 'Q_obs_none' inválida: esperado dict, recebido NoneType." in res_none["error"]

    res_str = out["resultados"]["quantities"][2]
    assert res_str["success"] is False
    assert "Observação 2 da grandeza 'Q_obs_str' inválida: esperado dict, recebido str." in res_str["error"]
