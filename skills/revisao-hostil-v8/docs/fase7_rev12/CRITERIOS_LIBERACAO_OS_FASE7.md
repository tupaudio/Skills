# CRITÉRIOS DE LIBERAÇÃO DA ORDEM DE SERVIÇO — FASE 7 (`v8.0-beta.7`), REVISÃO 12

**Base imutável:** `v8.0-beta.6.6` (`11e91b6f3d517707326357868cc34ff97ab8327d`)  
**Branch documental:** `specification/v8.0-beta.7-rev12`  
**Status atual da Ordem de Serviço:** `OS_STATUS = BLOCKED` (aguardando aprovação formal da banca externa sobre a Revisão 12)

---

## 1. As 14 Condições Obrigatórias para Liberação da OS (`ACH-B7-R11-009`)

A Ordem de Serviço da Fase 7 só poderá ser emitida quando **todas as 14 condições** abaixo forem simultaneamente verdadeiras:

1. Zero achados P1 abertos (`T-R12-117`).
2. Zero achados P2 abertos (`T-R12-118`).
3. Revisão documental aprovada formalmente pela banca externa.
4. Inventário dos 18 contratos canônicos completo (`SCHEMA_REGISTRY_FASE7_REV12.json`).
5. Compatibilidade da Beta 6.6 demonstrada sem versões inventadas (`MATRIZ_MIGRACAO_SCHEMAS_BETA66_REV12.md`).
6. Árvore transitiva `$ref` completa (19 referências transitivas com SHA-256 físico).
7. Política de compatibilidade validável (`compatibility_policy_v1.json` validado por `compatibility_policy.schema.json`).
8. Modelo de checkpoint e duas testemunhas externas (`2-of-2`) formalmente especificado (`CONTRATOS_CRIPTOGRAFICOS_REV12.md`).
9. Regras Windows NTFS e Linux ≥5.6 de confinamento completas (`ESPECIFICACAO_TECNICA_FASE7_REV12.md` §3).
10. Fórmula matemática corrigida (`(0, 1000]`, `D_bound = 5.4054 × 10²¹`, `N_bound = 5.4054 × 10²²`, 128 bits) e comprovada.
11. Matriz de testes com **119 cenários rastreáveis** (`60` Rev 10 + `15` Rev 11 + `44` Rev 12).
12. Nenhuma contradição entre os 10 documentos e 18 schemas.
13. Nenhuma funcionalidade da Fase 8 antecipada.
14. Base `v8.0-beta.6.6` (`11e91b6f3d517707326357868cc34ff97ab8327d`) preservada integralmente.

---

## 2. Separação entre Aprovação da OS e Execução Operacional

- A Revisão 12 é submetida à banca externa **sem executar os 119 testes** (`0/119 executados`), pois a implementação Python está suspensa até a OS.
- Nenhum componente operacional futuro poderá carregar `compatibility_policy_v1.json` enquanto `policy_status != "frozen_executable"` ou sem assinatura real da raiz confiável.

---

## 3. Regra de Bloqueio

Se qualquer uma das 14 condições não for atendida:

`OS_STATUS = BLOCKED`

É expressamente proibido transformar aprovação parcial em autorização de implementação.
