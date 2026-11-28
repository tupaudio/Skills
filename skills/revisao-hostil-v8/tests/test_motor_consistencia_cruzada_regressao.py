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


def test_location_required_invalid_values_both_orders():
    """Com 2+ observações, location ausente, None, vazio, espaços ou não-string gera erro nas duas ordens."""
    casos_invalidos = [
        ("ausente", None, False),
        ("none", None, True),
        ("vazio", "", True),
        ("espacos", "   ", True),
        ("nao_string", 123, True),
    ]
    for nome, bad_val, incluir_chave in casos_invalidos:
        obs_ok = {"location": "p.1", "value": 10.0, "source_type": "texto"}
        obs_bad = {"value": 12.0, "source_type": "texto"}
        if incluir_chave:
            obs_bad["location"] = bad_val
        expected_repr = repr(bad_val)

        # Ordem 1: inválida na posição 2
        out1 = motor_consistencia_cruzada.run_motor(
            {"quantities": [{"quantity_id": f"Q_{nome}_1", "observations": [obs_ok, obs_bad]}]}
        )
        validate_contract(out1, "schema_motor.json")
        assert out1["status"] == "ERRO_VALIDACAO"
        err1 = out1["resultados"]["quantities"][0]["error"]
        assert "Observação 2" in err1
        assert expected_repr in err1
        assert "location deve ser string não vazia" in err1

        # Ordem 2: inválida na posição 1
        out2 = motor_consistencia_cruzada.run_motor(
            {"quantities": [{"quantity_id": f"Q_{nome}_2", "observations": [obs_bad, obs_ok]}]}
        )
        validate_contract(out2, "schema_motor.json")
        assert out2["status"] == "ERRO_VALIDACAO"
        err2 = out2["resultados"]["quantities"][0]["error"]
        assert "Observação 1" in err2
        assert expected_repr in err2
        assert "location deve ser string não vazia" in err2


def test_location_batch_partial_and_all_invalid():
    """Lote misto (válida + sem location) => PARCIAL preservando a válida; todas inválidas => ERRO_VALIDACAO."""
    p_misto = {
        "quantities": [
            {
                "quantity_id": "Q_ok",
                "observations": [
                    {"location": "sim.py", "value": 10.0, "source_type": "codigo"},
                    {"location": "artigo.tex", "value": 10.0, "source_type": "texto"},
                ],
            },
            {
                "quantity_id": "Q_sem_loc",
                "observations": [
                    {"value": 10.0, "source_type": "codigo"},
                    {"location": "artigo.tex", "value": 12.0, "source_type": "texto"},
                ],
            },
        ]
    }
    out_misto = motor_consistencia_cruzada.run_motor(p_misto)
    validate_contract(out_misto, "schema_motor.json")
    assert out_misto["status"] == "PARCIAL"
    assert out_misto["metricas"]["sucesso"] == 1
    assert out_misto["metricas"]["falhas"] == 1
    assert out_misto["resultados"]["quantities"][0]["success"] is True
    assert out_misto["resultados"]["quantities"][1]["success"] is False

    p_todas_inv = {
        "quantities": [
            {
                "quantity_id": "Q_inv1",
                "observations": [
                    {"location": "", "value": 10.0, "source_type": "texto"},
                    {"location": "p.2", "value": 10.0, "source_type": "texto"},
                ],
            },
            {
                "quantity_id": "Q_inv2",
                "observations": [
                    {"location": "p.1", "value": 10.0, "source_type": "texto"},
                    {"location": 123, "value": 10.0, "source_type": "texto"},
                ],
            },
        ]
    }
    out_inv = motor_consistencia_cruzada.run_motor(p_todas_inv)
    validate_contract(out_inv, "schema_motor.json")
    assert out_inv["status"] == "ERRO_VALIDACAO"
    assert out_inv["metricas"]["sucesso"] == 0
    assert out_inv["metricas"]["falhas"] == 2


def test_cases_a_to_d_with_location_no_none_or_desconhecido():
    """Casos A-D com location preenchida: nenhum achado contém 'None' ou 'desconhecido' e estados preservados."""
    casos = [
        (
            "A",
            [
                {"location": "sim_a.py", "source_type": "codigo", "value": 10.0},
                {"location": "sim_b.py", "source_type": "codigo", "value": 12.0},
                {"location": "artigo.tex", "source_type": "texto", "value": 10.0},
            ],
            "NAO_VERIFICADO",
            1,
        ),
        (
            "B",
            [
                {"location": "sim.py", "source_type": "codigo", "value": 10.0},
                {"location": "sec1.tex", "source_type": "texto", "value": 10.0},
                {"location": "sec2.tex", "source_type": "texto", "value": 12.0},
            ],
            "CONFIRMADO",
            1,
        ),
        (
            "C",
            [
                {"location": "sim_a.py", "source_type": "codigo", "value": 10.0},
                {"location": "sim_b.py", "source_type": "codigo", "value": 12.0},
                {"location": "artigo.tex", "source_type": "texto", "value": 15.0},
            ],
            "NAO_VERIFICADO",
            1,
        ),
        (
            "D",
            [
                {"location": "sim.py", "source_type": "codigo", "value": 10.0},
                {"location": "tab.csv", "source_type": "tabela", "value": 12.0},
                {"location": "artigo.tex", "source_type": "texto", "value": 15.0},
            ],
            "CONFIRMADO",
            2,
        ),
    ]
    for nome, obs, estado_esperado, qtd_esperada in casos:
        for ordem in (obs, list(reversed(obs))):
            out = motor_consistencia_cruzada.run_motor(
                {"quantities": [{"quantity_id": f"potencia_{nome}", "observations": ordem}]}
            )
            validate_contract(out, "schema_motor.json")
            assert out["status"] == "COM_ACHADOS"
            assert len(out["achados"]) == qtd_esperada
            for ach in out["achados"]:
                assert ach["estado"] == estado_esperado
                for campo in ("localizacao", "descricao", "impacto", "acao_recomendada"):
                    assert "None" not in ach[campo], f"Caso {nome}: 'None' em {campo}: {ach[campo]}"
                    assert "desconhecido" not in ach[campo], f"Caso {nome}: 'desconhecido' em {campo}: {ach[campo]}"


def test_single_observation_without_location_still_fails_by_len():
    """1 observação sem location continua falhando primeiro por len < 2 (ordem de validação)."""
    out = motor_consistencia_cruzada.run_motor(
        {"quantities": [{"quantity_id": "Q_one", "observations": [{"value": 10.0, "source_type": "texto"}]}]}
    )
    validate_contract(out, "schema_motor.json")
    assert out["status"] == "ERRO_VALIDACAO"
    assert "requer pelo menos 2 observações para comparação cruzada" in out["resultados"]["quantities"][0]["error"]


def _strip_timestamps(obj):
    if isinstance(obj, dict):
        return {k: _strip_timestamps(v) for k, v in obj.items() if k != "timestamp"}
    if isinstance(obj, list):
        return [_strip_timestamps(item) for item in obj]
    return obj


def test_repeated_location_unique_node_ids_and_order_invariance():
    """Casos 2a, 2b e 2c nas duas ordens: node_id únicos, arestas não ambíguas, qualificação em 2a e invariância."""
    casos = [
        (
            "Q_2a",
            [
                {"source_type": "codigo", "location": "sim.py", "value": 10.0},
                {"source_type": "texto", "location": "sim.py", "value": 12.0},
            ],
            "COM_ACHADOS",
            "CONFIRMADO",
            True,
        ),
        (
            "Q_2b",
            [
                {"source_type": "texto", "location": "p.1", "value": 10.0},
                {"source_type": "texto", "location": "p.1", "value": 12.0},
            ],
            "COM_ACHADOS",
            "NAO_VERIFICADO",
            False,
        ),
        (
            "Q_2c",
            [
                {"source_type": "tabela", "location": "p. 5", "value": 10.0},
                {"source_type": "texto", "location": "p. 5", "value": 10.0},
            ],
            "OK",
            None,
            True,
        ),
    ]
    for qid, obs, expected_status, expected_estado, expect_edges in casos:
        out1 = motor_consistencia_cruzada.run_motor({"quantities": [{"quantity_id": qid, "observations": obs}]})
        out2 = motor_consistencia_cruzada.run_motor(
            {"quantities": [{"quantity_id": qid, "observations": list(reversed(obs))}]}
        )
        validate_contract(out1, "schema_motor.json")
        validate_contract(out2, "schema_motor.json")

        assert _strip_timestamps(out1) == _strip_timestamps(out2)
        assert out1["status"] == expected_status

        qres = out1["resultados"]["quantities"][0]
        node_ids = [n["node_id"] for n in qres["graph"]["nodes"]]
        assert len(node_ids) == 2
        assert len(set(node_ids)) == 2
        assert node_ids[0].endswith("#1")
        assert node_ids[1].endswith("#2")

        edges = qres["graph"]["edges"]
        if expect_edges:
            assert len(edges) == 1
            assert edges[0]["from"] != edges[0]["to"]
            assert edges[0]["from"] == node_ids[0]
            assert edges[0]["to"] == node_ids[1]
        else:
            assert edges == []

        if expected_estado is None:
            assert out1["achados"] == []
        else:
            assert len(out1["achados"]) == 1
            assert out1["achados"][0]["estado"] == expected_estado

        if qid == "Q_2a":
            ach = out1["achados"][0]
            assert "(codigo)" in ach["acao_recomendada"]
            assert "(texto)" in ach["acao_recomendada"]
            assert "Alinhar 'sim.py' com a fonte primária 'sim.py'" not in ach["acao_recomendada"]
            ev_loc = ach["evidencias"][0]["localizacao"]
            assert ev_loc == "sim.py (codigo) <-> sim.py (texto)"
            assert ev_loc != "sim.py <-> sim.py"


def test_distinct_locations_keep_exact_node_ids_without_suffix():
    """Sem colisão, node_id mantém exatamente '<quantity_id>:<location>' sem sufixo #1."""
    out_asym = motor_consistencia_cruzada.run_motor(
        {
            "quantities": [
                {
                    "quantity_id": "Q_asym",
                    "observations": [
                        {"source_type": "codigo", "location": "sim.py", "value": 10.0},
                        {"source_type": "texto", "location": "artigo.tex", "value": 12.0},
                    ],
                }
            ]
        }
    )
    validate_contract(out_asym, "schema_motor.json")
    nodes_asym = [n["node_id"] for n in out_asym["resultados"]["quantities"][0]["graph"]["nodes"]]
    assert nodes_asym == ["Q_asym:sim.py", "Q_asym:artigo.tex"]
    ach = out_asym["achados"][0]
    assert ach["acao_recomendada"] == "Alinhar 'artigo.tex' com a fonte primária 'sim.py' ou documentar a transformação."
    assert ach["evidencias"][0]["localizacao"] == "sim.py <-> artigo.tex"

    out_sym = motor_consistencia_cruzada.run_motor(
        {
            "quantities": [
                {
                    "quantity_id": "Q_sym",
                    "observations": [
                        {"source_type": "texto", "location": "p.1", "value": 10.0},
                        {"source_type": "texto", "location": "p.2", "value": 12.0},
                    ],
                }
            ]
        }
    )
    validate_contract(out_sym, "schema_motor.json")
    nodes_sym = [n["node_id"] for n in out_sym["resultados"]["quantities"][0]["graph"]["nodes"]]
    assert nodes_sym == ["Q_sym:p.1", "Q_sym:p.2"]


def test_identical_observations_order_independent():
    """Duas observações iguais em location, source_type e valor produzem saída idêntica nas duas ordens."""
    obs_a = {"source_type": "texto", "location": "p.1", "value": 10.0}
    obs_b = {"source_type": "texto", "location": "p.1", "value": 10.0}
    out1 = motor_consistencia_cruzada.run_motor({"quantities": [{"quantity_id": "Q_id", "observations": [obs_a, obs_b]}]})
    out2 = motor_consistencia_cruzada.run_motor({"quantities": [{"quantity_id": "Q_id", "observations": [obs_b, obs_a]}]})
    validate_contract(out1, "schema_motor.json")
    validate_contract(out2, "schema_motor.json")
    assert _strip_timestamps(out1) == _strip_timestamps(out2)
    assert out1["status"] == "OK"
    assert out1["achados"] == []
    node_ids = [n["node_id"] for n in out1["resultados"]["quantities"][0]["graph"]["nodes"]]
    assert node_ids == ["Q_id:p.1#1", "Q_id:p.1#2"]


def test_location_whitespace_stripped_direct_and_run_motor():
    """Espaços nas bordas (' p.1 ' e ' p.2 ') são removidos em nodes, divergences e achados."""
    obs_asym = [
        {"source_type": "codigo", "location": " p.1 ", "value": 10.0},
        {"source_type": "texto", "location": " p.2 ", "value": 12.0},
    ]
    direct_asym = motor_consistencia_cruzada.check_quantity_consistency("Q_sp_a", obs_asym)
    assert [n["location"] for n in direct_asym["graph"]["nodes"]] == ["p.1", "p.2"]
    assert [n["node_id"] for n in direct_asym["graph"]["nodes"]] == ["Q_sp_a:p.1", "Q_sp_a:p.2"]
    assert direct_asym["divergences"][0]["anchor_location"] == "p.1"
    assert direct_asym["divergences"][0]["divergent_location"] == "p.2"

    out_asym = motor_consistencia_cruzada.run_motor({"quantities": [{"quantity_id": "Q_sp_a", "observations": obs_asym}]})
    validate_contract(out_asym, "schema_motor.json")
    ach_a = out_asym["achados"][0]
    assert ach_a["localizacao"] == "p.2"
    assert ach_a["acao_recomendada"] == "Alinhar 'p.2' com a fonte primária 'p.1' ou documentar a transformação."
    assert ach_a["evidencias"][0]["localizacao"] == "p.1 <-> p.2"

    obs_sym = [
        {"source_type": "texto", "location": " p.1 ", "value": 10.0},
        {"source_type": "texto", "location": " p.2 ", "value": 12.0},
    ]
    direct_sym = motor_consistencia_cruzada.check_quantity_consistency("Q_sp_s", obs_sym)
    assert [n["location"] for n in direct_sym["graph"]["nodes"]] == ["p.1", "p.2"]
    assert [n["node_id"] for n in direct_sym["graph"]["nodes"]] == ["Q_sp_s:p.1", "Q_sp_s:p.2"]
    assert direct_sym["divergences"][0]["locations"] == ["p.1", "p.2"]

    out_sym = motor_consistencia_cruzada.run_motor({"quantities": [{"quantity_id": "Q_sp_s", "observations": obs_sym}]})
    validate_contract(out_sym, "schema_motor.json")
    ach_s = out_sym["achados"][0]
    assert ach_s["localizacao"] == "p.1, p.2"
    assert "[p.1]" in ach_s["descricao"] and "[p.2]" in ach_s["descricao"]


def test_location_non_string_types_rejected():
    """location como bool, float, list e dict gera erro da grandeza."""
    for nome, bad_loc in [
        ("bool_true", True),
        ("bool_false", False),
        ("float", 3.14),
        ("list", ["p.1"]),
        ("dict", {"loc": "p.1"}),
    ]:
        out = motor_consistencia_cruzada.run_motor(
            {
                "quantities": [
                    {
                        "quantity_id": f"Q_type_{nome}",
                        "observations": [
                            {"source_type": "texto", "location": "p.1", "value": 10.0},
                            {"source_type": "texto", "location": bad_loc, "value": 12.0},
                        ],
                    }
                ]
            }
        )
        validate_contract(out, "schema_motor.json")
        assert out["status"] == "ERRO_VALIDACAO"
        qres = out["resultados"]["quantities"][0]
        assert qres["success"] is False
        assert qres["status"] == "error"
        assert "location inválido" in qres["error"]
        assert "location deve ser string não vazia" in qres["error"]


def test_invalid_source_type_precedes_invalid_location():
    """Na mesma observação com source_type inválido e location inválido, o erro retornado é o de source_type."""
    for nome, bad_st, trecho_esperado in [
        ("st_none", None, "source_type inválido"),
        ("st_desconhecido", "blog", "source_type desconhecido"),
    ]:
        out = motor_consistencia_cruzada.run_motor(
            {
                "quantities": [
                    {
                        "quantity_id": f"Q_prec_{nome}",
                        "observations": [
                            {"source_type": "texto", "location": "p.1", "value": 10.0},
                            {"source_type": bad_st, "location": "", "value": 12.0},
                        ],
                    }
                ]
            }
        )
        validate_contract(out, "schema_motor.json")
        assert out["status"] == "ERRO_VALIDACAO"
        err = out["resultados"]["quantities"][0]["error"]
        assert trecho_esperado in err
        assert "location" not in err
