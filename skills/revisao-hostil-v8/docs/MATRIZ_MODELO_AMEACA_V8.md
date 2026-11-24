# MATRIZ DO MODELO DE AMEAÇA — REVISÃO HOSTIL V8.0 (ETAPA 0)

**Base:** `docs/MODELO_DE_AMEACA_V8.md` + auditoria das pastas `docs/fase7_rev17` a `rev20`  
**Cenário de implantação:** 1 pessoa, 1 máquina (Windows 11, Python 3.14), 1 domínio de confiança (sem serviço multiusuário nem terceiros externos exigindo atestação assinada).

---

## 1. Matriz Completa dos 18 Requisitos (Seção 6 de `MODELO_DE_AMEACA_V8.md`)

| ID | Ativo Protegido | Adversário / Evento | Cenário de Ataque / Falha | Impacto | Probabilidade | Decisão | Justificativa Técnica | Funcionalidades Dependentes | Critério de Reintrodução |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :--- | :--- | :--- |
| `REQ-01` | A1, A2 | T2, T3 | Hash instável de JSON por formatação diferente | Médio | Média | `SIMPLIFY` | Sem assinaturas externas, JSON canônico próprio (chaves ordenadas, UTF-8, sem `NaN`/`Inf`) substitui dupla biblioteca RFC 8785 + 18 vetores. | `RI-1`, `RI-3`, `RI-4` | Reabrir T6 (interoperabilidade com verificador externo). |
| `REQ-02` | A1, A4 | T6 | Forja de parecer por operador externo | Alto | Nula (local) | `DEFER` | Em implantação de 1 pessoa/1 máquina, quem assina é quem verifica; não há terceiro verificador. | `REQ-03`, `REQ-05` | Entrega de relatórios a terceiros exigindo assinatura ou operação multiusuário (T6). |
| `REQ-03` | A4 | T6 | Uso de chave revogada ou autoridade não autorizada | Alto | Nula (local) | `DEFER` | Depende integralmente de `REQ-02` (PKI/assinaturas). | `REQ-02` | Reabertura de T6. |
| `REQ-04` | A5 | T6 | Colusão de operadores em nuvem compartilhada | Médio | Nula (local) | `REMOVE` | Exige 3 provedores jurídicos/KMS distintos; não mitiga nenhum ator de T1–T4. | Nenhuma no runtime atual | Implantação distribuída multipartes (T6). |
| `REQ-05` | A1 | T6 | Replay de recibo de checkpoint / rollback remoto | Alto | Nula (local) | `DEFER` | Exige 2 testemunhas independentes e store remoto inexistentes na implantação local. | `REQ-02`, `REQ-06` | Implantação como serviço com terceiros (T6). |
| `REQ-06` | A1 | T6 | Expiração de nonce sob relógio manipulado | Médio | Nula (local) | `REMOVE` | Serve exclusivamente a `REQ-05`; `boot_id` Windows por estimativa temporal introduzia fragilidade (`ACH-B7-R20-001`). Logs usam UTC simples. | Nenhuma no runtime atual | Reabertura de `REQ-05` com fonte de boot nativa/attestation. |
| `REQ-07` | A1 | T2, T3 | Truncamento ou edição acidental de estado | Médio | Média | `SIMPLIFY` | Substituído por `RI-4` (JSONL encadeado por `prev_hash`); rollback malicioso no disco local é T5 (fora de escopo). | `RI-4` | Operação com store remoto compartilhado (T6). |
| `REQ-08` | A4 | T2 | Quebra silenciosa de contrato JSON Schema | Médio | Média | `SIMPLIFY` | Um único conjunto canônico de schemas + `schema_version` + deny-by-default; cópias integrais por revisão ficam apenas no histórico Git. | Validação de saída dos motores | Múltiplas versões de clientes simultâneas em serviço. |
| `REQ-09` | A3, A4 | T4 | Pacote adulterado na cadeia de suprimentos | Alto | Baixa | `KEEP` | `--require-hashes` com lock é barato e efetivo; estender do `tools/` para o `requirements.txt` de runtime (`RI-5`). | `RI-5` | N/A (mantido). |
| `REQ-10` | A1, A4 | T2, T3 | Bypass de validação sob `python -O` | Médio | Baixa | `KEEP` | Proibir `assert` em validações de integridade/segurança (`RI-6`). | `RI-6` | N/A (mantido). |
| `REQ-11` | A1, A2 | T3 | Relatório adulterado ou teste ignorado contado como `PASS` | Alto | Média | `KEEP` | `run_id` estrito, `run_manifest.json`, JUnit como fonte única, `skipped` ≠ `PASS` (`RI-1`, `RI-2`). Congelar sem complexidade adicional. | `RI-1`, `RI-2` | N/A (mantido e congelado). |
| `REQ-12` | A1 | T3 | Rastreabilidade manual desconectada da execução | Médio | Alta | `REMOVE` | Matriz de 205 cenários onde 199 não eram executáveis não substitui testes reais + benchmark (Etapa 2). | Nenhuma no runtime atual | Não reintroduzir; substituir por suíte executável + benchmark. |
| `REQ-13` | A4 | T3 | Perda de IDs históricos de cenários | Baixo | Baixa | `REMOVE` | O histórico Git já preserva todas as revisões imutavelmente. | Nenhuma | Não aplicável. |
| `REQ-14` | A4 | Ambiente | Bloqueio permanente por teste Linux específico de `REQ-06` | Médio | Alta (host Win11) | `REMOVE` | Desaparece com a remoção de `REQ-06`; Linux entra no CI quando houver runner Linux. | `REQ-06` | Criação de pipeline CI Linux. |
| `REQ-15` | A1 | T3 | Data fixa em validação operacional de certificados | Médio | Nula (local) | `DEFER` | Parte do validador PKI/T6 (`REQ-02`/`REQ-03`). | `REQ-02`, `REQ-03` | Reabertura de T6. |
| `REQ-16` | A5 | T2 | Agente ancorado em parecer de outro agente | Alto | Alta (Fase 7) | `SIMPLIFY` | Substituir atestação assinada por manifesto com SHA-256 do pacote de entrada de cada agente (`RI-3`). | `RI-3`, Fase 7 | Reabertura de T6. |
| `REQ-17` | A1, A2, A5 | T1, T2 | Adjudicação sem evidência qualificada ou rastreabilidade | Alto | Alta (Fase 7) | `KEEP` | Núcleo de qualidade da banca adversarial na Fase 7 (`schema_ledger_adjudicacao`, `schema_adjudication_record`, `schema_evidence_qualification`, `schema_adversarial_contestation`). | Fase 7 | N/A (mantido). |
| `REQ-18` | A1, A4 | T3 | Gate de liberação baseado em burocracia documental | Alto | Alta | `SIMPLIFY` | Gate objetivo passa a ser `RI-1`..`RI-6` + `RS-1`/`RS-2` + benchmark científico (Etapa 2) com recall e precisão acima do limiar pré-definido. | Etapa 2 e Fase 7 | N/A (simplificado). |

---

## 2. Classificação dos Quatro Achados `ACH-B7-R20-*`

Nenhum achado é classificado como "corrigido" por simples retirada de escopo. Verificou-se que **nenhum caminho ativo do runtime (`scripts/` da Beta 6.6)** depende de `platform_clock.py`, `test_historical_preservation.py` ou `schema_revocation_list.json`.

| Achado | Classificação Formal | Justificativa Verificada |
| :--- | :---: | :--- |
| `ACH-B7-R20-001` (`boot_id` Windows por estimativa temporal) | `OBSOLETE_BY_SCOPE` | Nenhum módulo em `scripts/` importa ou depende de `platform_clock.py` (`REQ-06` retirado do gate). |
| `ACH-B7-R20-002` (igualdade histórica exata de IDs) | `OBSOLETE_BY_SCOPE` | Nenhum módulo em `scripts/` depende de `test_historical_preservation.py` (`REQ-13` retirado; Git preserva o histórico). |
| `ACH-B7-R20-003` (validação semântica de chaves revogadas) | `DEFERRED_WITH_T6` | Adiado junto com `REQ-02`/`REQ-03` (PKI/revogação não existe na implantação local). |
| `ACH-B7-R20-004` (integridade subprocesso ↔ JUnit ↔ relatório) | `KEEP_OPEN_FOR_SIMPLIFICATION` | Continua válido (`REQ-11` / `RI-2`); a ser simplificado gerando o relatório diretamente do XML do JUnit como fonte única. |
