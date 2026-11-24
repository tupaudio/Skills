# Critérios Objetivos de Liberação da Ordem de Serviço — Fase 7 (`v8.0-beta.7`, Revisão 10)

> **Base de referência congelada:** `v8.0-beta.6.6` (`commit 11e91b6f3d517707326357868cc34ff97ab8327d`)  
> **Branch documental:** `specification/v8.0-beta.7-rev10`  
> **Estado atual:** implementação suspensa; documentação pronta para auditoria externa.

---

## 1. Resultado da Auditoria Interna de Consistência (Seção 9 do Plano)

Verificação cruzada executada sobre os 6 documentos da Revisão 10:

| Invariante verificado | Resultado | Referência documental |
| :--- | :---: | :--- |
| Nenhuma fórmula circular de hash (`policy`, `envelope`, `ledger`, `MandatoryAxesPlan`, `engine_run_manifest`) | **CONFORME** | `CONTRATOS_CRIPTOGRAFICOS_REV10.md` §1–2, `ESPECIFICACAO_TECNICA_FASE7_REV10.md` §1, §3 |
| Nenhum estado anti-rollback restaurável silenciosamente | **CONFORME** | `ESPECIFICACAO_TECNICA_FASE7_REV10.md` §1.2–1.3 (`MonotonicCheckpointStore`) |
| Nenhuma atualização concorrente não transacional do checkpoint | **CONFORME** | `compare_and_swap` atômico + `CheckpointConflictError` |
| Nenhuma seleção implícita de schema (sempre `contract_version` explícito) | **CONFORME** | `MATRIZ_COMPATIBILIDADE_CONTRATOS_REV10.md` §1–2 |
| Nenhum `$ref` sem versão na árvore de contratos | **CONFORME** | `MATRIZ_COMPATIBILIDADE_CONTRATOS_REV10.md` §2–3 |
| Nenhuma nota ou peso convertidos para `float` | **CONFORME** | `ESPECIFICACAO_TECNICA_FASE7_REV10.md` §4, §7 |
| Nenhuma classificação de reconstruibilidade sem artefatos verificáveis (incluindo interpretador Python) | **CONFORME** | `ESPECIFICACAO_TECNICA_FASE7_REV10.md` §5 |
| Nenhuma abertura de arquivo com fallback inseguro (`Path.resolve()` + prefixo textual proibido) | **CONFORME** | `ESPECIFICACAO_TECNICA_FASE7_REV10.md` §6 |
| Nenhum limite racional incompatível com limites de entrada ($D_{\max} = 5{,}4054 \times 10^{21}$, 73 bits ≤ 128 bits) | **CONFORME** | `ESPECIFICACAO_TECNICA_FASE7_REV10.md` §7.2 |
| Nenhum módulo/função futuro apresentado como implementado | **CONFORME** | Aviso explícito em todos os 6 documentos |
| Base `v8.0-beta.6.6` (`11e91b6`) preservada 100% intacta | **CONFORME** | Apenas novos arquivos `.md` criados em `docs/fase7_rev10/` |

---

## 2. Portão de Aprovação da Revisão 10 (Seção 10 do Plano)

| Critério | Condição obrigatória | Status na Revisão 10 |
| :--- | :--- | :---: |
| `ACH-B7-R9-001` (P1) | Anti-rollback resistente a restauração e concorrência | Especificado + 10 testes |
| `ACH-B7-R9-002` (P1) | Despacho explícito e compatibilidade sem contradição | Especificado + 8 testes |
| `ACH-B7-R9-003` (P2) | Assinatura da política com formato e prova temporal definidos | Especificado + 10 testes |
| `ACH-B7-R9-004` (P2) | Separação entre hash semântico e proveniência | Especificado + 6 testes |
| `ACH-B7-R9-005` (P2) | Artefato do interpretador e ambiente verificáveis | Especificado + 6 testes |
| `ACH-B7-R9-006` (P2) | Confinamento Windows baseado em handles | Especificado + 10 testes |
| `ACH-B7-R9-007` (P2) | Limites racionais formalmente derivados (73/76 bits ≤ 128 bits) | Especificado + 10 testes |
| Consistência global | Zero contradição entre seções, contratos e matrizes | Verificada |
| Escopo | Nenhuma implementação ou funcionalidade adicional da Fase 8 | Preservado |

---

## 3. Sequência Obrigatória para Liberação da Ordem de Serviço da Fase 7

1. **Concluído:** elaboração dos 6 documentos da Revisão 10 na branch `specification/v8.0-beta.7-rev10`.
2. **Concluído:** auditoria interna de consistência documental e verificação independente de $D_{\max}$.
3. **Próximo passo:** submissão desta documentação à **auditoria externa da banca**.
4. **Condição de liberação:** aprovação formal pela banca externa com **0 achados P1 abertos** e **0 achados P2 abertos**.
5. **Somente após o item 4:** emissão da Ordem de Serviço de implementação da `v8.0-beta.7` (em nova branch de desenvolvimento, mantendo `v8.0-beta.6.6` congelada como tag histórica imutável).
