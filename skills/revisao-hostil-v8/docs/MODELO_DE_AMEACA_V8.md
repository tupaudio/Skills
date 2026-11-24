# Modelo de Ameaça e Decisões de Segurança — Revisão Hostil V8 (Etapa 0)

**Status:** proposta para aceite do mantenedor. Nada nas Rev17 a Rev20 foi apagado; "adiar" e "retirar do gate" significam que o requisito deixa de bloquear a Fase 7, e os arquivos permanecem como histórico.
**Base lida:** `v8.0-beta.6.6` + pasta `docs/fase7_rev17` a `rev20` do zip `revisao-hostil-v8-rev20`.

## 1. Princípio

O produto é **detectar erro científico em manuscritos** (SKILL.md, Etapa 2 do plano). A segurança existe para que o resultado da auditoria seja confiável e reproduzível, não para tornar a auditoria um sistema distribuído à prova de adversário. Todo mecanismo precisa responder: *contra quem protege, e o que essa pessoa ganharia atacando?*

## 2. Modelo de confiança

- **Implantação real:** uma pessoa, uma máquina (Windows 11, Python 3.14), um domínio de confiança. Não há serviço, múltiplos operadores nem terceiro que dependa de uma atestação assinada.
- **Confiável após teste:** motores determinísticos (`scripts/engines/`).
- **Não confiável quanto à correção:** o modelo de linguagem que julga. Serve para interpretar, nunca para calcular nem para atestar verificação.
- **Não confiável como entrada:** o manuscrito e tudo que vem dele (texto, DOCX, PDF, metadados, tabelas, código anexo).

## 3. Ativos

| ID | Ativo | Propriedade a proteger |
| --- | --- | --- |
| A1 | Parecer final e achados | Integridade contra erro acidental, edição manual não registrada e resultado de teste não executado apresentado como executado |
| A2 | Evidência de cada achado | Rastreabilidade até o trecho/cálculo; reprodutibilidade |
| A3 | Máquina do usuário | Não executar nem ser comprometida por conteúdo do manuscrito |
| A4 | Código e regras da skill | Dependências íntegras; versão auditada identificável |
| A5 | Independência da banca | Pareceres individuais não ancorados uns nos outros |

## 4. Atores

| Ator | Situação | Decisão |
| --- | --- | --- |
| T1 Manuscrito malicioso ou com instruções embutidas (prompt injection, arquivo patológico, expressão que causa DoS) | **Real e o risco principal**: é o único adversário que entrega conteúdo direto à skill | No escopo |
| T2 Erro acidental: agente lendo parecer de outro, artefato desatualizado, norma ou resultado inventado pelo modelo | **Real** | No escopo |
| T3 Mantenedor com pressa (relatório editado à mão, teste ignorado contado como aprovado) | **Real**; foi o foco das betas 6.2 a 6.6 | No escopo (já mitigado; congelar) |
| T4 Cadeia de suprimentos (pacote adulterado) | Plausível, mitigação barata | No escopo |
| T5 Atacante com escrita no disco do usuário | Controla também o código e as chaves; assinatura local não ajuda | Fora de escopo |
| T6 Operadores independentes forjando recibo de testemunha, rollback de checkpoint, replay de nonce entre infraestruturas | Exige implantação multipartes que não existe | **Adiado** |

**Condições para reabrir T6:** (a) relatórios passarem a ser entregues a terceiro (banca, órgão, revista) que exija atestação verificável; ou (b) a skill virar serviço multiusuário; ou (c) houver mais de um operador com chaves distintas. Sem uma dessas, o custo não tem contrapartida.

## 5. Requisitos de integridade adotados

- **RI-1** Todo relatório registra: SHA-256 do artefato auditado, versão da skill e dos motores, versões das dependências, `run_id`, data UTC. (Já existe em `run_manifest.json` e nas saídas dos motores.)
- **RI-2** Resultados de testes vêm de saída estruturada do próprio executor (JUnit), nunca digitados; `skipped` e `NOT_EXECUTED` nunca contam como aprovação. (Já existe; ver 6, item 11.)
- **RI-3** Pareceres individuais ficam em arquivos próprios, gravados uma vez; a adjudicação referencia o hash de cada um. Independência é registrada como "o que cada agente recebeu" (hash do pacote de entrada), sem assinatura.
- **RI-4** Ledger de achados e adjudicações em JSONL com encadeamento por hash (`prev_hash`), para detectar truncamento ou edição acidental.
- **RI-5** Dependências com versões fixas e hashes (`pip install --require-hashes`) para o conjunto de runtime, não só para as ferramentas de validação.
- **RI-6** Nenhuma validação de segurança ou integridade usa `assert`; o comportamento sob `python -O` é idêntico.
- **RS-1** Manuscrito é dado. Texto copiado dele para achados (campo `conteudo`) é entregue aos agentes como dado delimitado, e há testes com manuscritos que tentam dar ordens ao revisor. **Hoje isso está declarado em `docs/ARQUITETURA_V8.md` §11, mas não encontrei teste para isso.**
- **RS-2** Parser matemático sem `eval`/`exec`, com limite de profundidade, tamanho e expoente; caminho de arquivo validado; arquivo limitado a 50 MB. (Já existe em `scripts/common/validation.py` e `motor_matematico.py`.)

## 6. Inventário das Rev17 a Rev20 e decisão por requisito

Legenda: **MANTER**, **SIMPLIFICAR**, **ADIAR** (volta quando T6 for reaberto), **RETIRAR DO GATE** (sem proteção correspondente a ameaça real; arquivo fica como histórico).

| # | Mecanismo (onde aparece) | Ameaça que cobre | Decisão | Justificativa |
| --- | --- | --- | --- | --- |
| 1 | Canonicalização RFC 8785 com duas bibliotecas cruzadas (`rfc8785`, `jcs`) e 18 vetores | Hash estável de JSON assinado | **SIMPLIFICAR** | Sem assinaturas não há necessidade de interoperar com outras implementações. Usar JSON canônico próprio e documentado (chaves ordenadas, UTF-8, sem `NaN`/`Inf`, sem floats nos objetos hasheados). Vetores e dupla biblioteca saem do gate |
| 2 | Assinaturas Ed25519 (`cryptography`), SPKI DER, `key_id` = SHA-256 do SPKI | T6 | **ADIAR** | Quem assinaria, e para quem? |
| 3 | Trust bundle, autoridades autorizadas, lista de revogação (`schema_revocation_list`) | T6 | **ADIAR** | Dependem do item 2 |
| 4 | Dossiê de independência administrativa com 3 provedores de infraestrutura distintos | T6 | **RETIRAR DO GATE** | Exige 3 provedores reais; não protege contra nenhum ator de T1 a T4 |
| 5 | Testemunhas A/B, recibos de consumo de nonce, `signed_store_receipt` | T6 | **ADIAR** | Idem |
| 6 | Contexto monotônico (`platform_clock.py`): `clock_context_id`, `boot_id`, PID, `store_epoch`, relógio QPC/`CLOCK_MONOTONIC_RAW` | Expiração de nonce | **RETIRAR DO GATE** | Só serve ao item 5. O `boot_id` do Windows é uma estimativa (hash de `MachineGuid` com `time.time() − GetTickCount64()` dividido em minutos): como os dois termos são truncados em instantes diferentes, a estimativa pode divergir dentro do mesmo boot. Remover a dependência é mais barato que consertá-la. Logs usam timestamp UTC simples |
| 7 | Checkpoint com anti-rollback e CAS | Rollback de estado | **SIMPLIFICAR** | Substituído por RI-4 (JSONL encadeado por hash). Rollback malicioso é T5 |
| 8 | Política de compatibilidade, matrizes de migração, schemas `7.0.0` e `legacy-v8.0-beta.6.6` copiados em cada revisão | Quebra silenciosa de contrato | **SIMPLIFICAR** | Manter um único conjunto canônico de schemas + campo `schema_version` + regra deny-by-default para versão desconhecida. As cópias integrais por revisão (27 a 28 JSONs × 4 revisões) ficam só no histórico do Git |
| 9 | `--require-hashes` com lock | T4 | **MANTER e estender** | Barato e com ganho real; hoje cobre só `tools/` da Fase 7, não o `requirements.txt` do runtime (RI-5) |
| 10 | Execução igual sob `python -O`, sem `assert` de validação | Bypass por otimização | **MANTER** | Regra barata; falta lint que a imponha (RI-6) |
| 11 | `run_id` estrito, `run_manifest.json`, `artifact_sha256`, matriz gerada de resultados estruturados, `skipped` ≠ `PASS` | T3 | **MANTER e congelar** | Funciona; as betas 6.2 a 6.6 gastaram esforço aqui. Não evoluir mais sem novo incidente |
| 12 | Matriz de 205 cenários (199 IDs herdados) | Rastreabilidade | **RETIRAR DO GATE** | Só 6 testes da Rev20 são executáveis. Aceitação passa a ser: testes executáveis passando + benchmark (Etapa 2). Matriz manual não conta |
| 13 | `test_historical_preservation` (igualdade de conjuntos de IDs) | Perda de IDs históricos | **RETIRAR DO GATE** | O Git já preserva histórico; o teste protege numeração de testes que não existem |
| 14 | Teste Linux `T-R20-204` (`BLOCKED_ENVIRONMENT`) | Portabilidade do item 6 | **RETIRAR DO GATE** | Some junto com o item 6. Para o produto: Windows 11 + Python 3.14 homologados; Linux no CI quando existir |
| 15 | Relógio de teste proibido em modo operacional (`resolve_execution_now_utc`) | Data fixa em validação | **ADIAR** | Parte do validador T6 |
| 16 | Atestação de isolamento entre agentes (`schema_isolation_attestation`) | A5 | **SIMPLIFICAR** | Trocar atestação por manifesto: hash do pacote de entrada de cada agente (RI-3) |
| 17 | `schema_ledger_adjudicacao`, `schema_adjudication_record`, `schema_evidence_qualification`, `schema_adversarial_contestation` | A1, A2, A5 | **MANTER** | São o núcleo da qualidade da auditoria; passam a ter implementação na Fase 7 de fato |
| 18 | `OS_STATUS = BLOCKED` "aguardando banca externa" | Gate de liberação | **SIMPLIFICAR** | Gate passa a ser: RI-1 a RI-6 + RS-1/RS-2 + benchmark com recall e precisão acima de limiar definido antes de medir |

## 7. Efeito sobre os achados abertos da Rev20

Descrição dos quatro achados conforme o enunciado do mantenedor; **não reproduzi cada um no código**, a leitura abaixo é de decisão, não de verificação.

| Achado | Decisão |
| --- | --- |
| `ACH-B7-R20-001` identidade de boot no Windows por aproximação temporal | Fecha por **retirada do mecanismo** (item 6), não por correção. Registrar como "obsoleto por decisão de escopo", não como "corrigido" |
| `ACH-B7-R20-002` igualdade histórica exata | Obsoleto com o item 13; o histórico é o Git |
| `ACH-B7-R20-003` validação semântica de identificadores de chaves revogadas | Adiado com os itens 2 e 3 |
| `ACH-B7-R20-004` integridade entre subprocesso, JUnit e relatório | **Continua válido** (item 11). Simplificar: gerar o relatório estruturado a partir do XML do JUnit, única fonte de verdade, em vez de reconciliar três fontes |

## 8. O que esta análise não verificou

- Não executei os testes das Rev17 a Rev20: dependem de `cryptography`, `rfc8785`, `jcs`, `jsonschema` (sem rede aqui) e dois deles de Windows ou Linux específicos.
- Não auditei a lógica de cada validador (`validate_rev20.py` tem 455 linhas); a decisão por mecanismo parte do que ele e a documentação declaram proteger.
- Confirmei por comparação que `scripts/` e `tests/` da Rev20 são idênticos aos da Beta 6.6: **as Rev17 a Rev20 não acrescentaram nenhuma linha de runtime**; todo o trabalho está em `docs/`.
- Os requisitos RI-4, RI-5, RI-6 e RS-1 são propostas ainda sem implementação nem teste.

## 9. Próximos passos propostos

1. Mantenedor aceita ou ajusta as decisões da seção 6.
2. Etapa 2: benchmark científico (Artigos 03 e 04 + defeitos injetados), antes de qualquer implementação da Fase 7.
3. Implementar RS-1 (testes de prompt injection) e RI-5/RI-6, que são pequenos.
4. Só então a Fase 7 de agentes, usando os schemas do item 17.
