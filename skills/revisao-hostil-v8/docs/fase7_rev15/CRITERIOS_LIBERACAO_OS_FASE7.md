# CRITÉRIOS DE LIBERAÇÃO DA ORDEM DE SERVIÇO — FASE 7 (`v8.0-beta.7`), REVISÃO 15

**Base imutável:** `v8.0-beta.6.6` (`11e91b6f3d517707326357868cc34ff97ab8327d`)  
**Branch documental:** `specification/v8.0-beta.7-rev15`  
**Status atual da Ordem de Serviço:** `OS_STATUS = BLOCKED` (aguardando aprovação formal da banca externa sobre a Revisão 15)

---

## 1. Condições Obrigatórias para Liberação da OS (14 Condições)

1. Zero achados P1 abertos (`T-R12-117`).
2. Zero achados P2 abertos (`T-R12-118`).
3. Revisão documental aprovada formalmente pela banca externa.
4. Inventário dos **19 contratos canônicos** completo (`SCHEMA_REGISTRY_FASE7_REV15.json`).
5. Compatibilidade da Beta 6.6 demonstrada sem versões inventadas (`MATRIZ_MIGRACAO_SCHEMAS_BETA66_REV15.md`).
6. Árvore transitiva `$ref` completa (19 referências transitivas) e validada semanticamente.
7. Política de compatibilidade validável estrutural e semanticamente (`minItems: 19`, `maxItems: 19`, unicidade de `schema_name`, `ref_schema_name` e `instance_schema_version`, correspondência 1-para-1 com o Registry).
8. Modelo de checkpoint `2-of-2` com dossiê assinado (composição exata dos 3 papéis via `allOf`/`contains` + pré-imagem única de `dossier_jcs_sha256` com vetor de teste), quórum `2-of-2` estrito e `NonceConsumptionStore.consume_once(...) -> NonceConsumptionResult` reconciliado campo a campo.
9. Regras Windows NTFS e Linux ≥ 5.6 de confinamento completas.
10. Fórmula matemática corrigida (`(0, 1000]`, `D_bound = 5.4054 × 10²¹`, `N_bound = 5.4054 × 10²²`, 128 bits) e comprovada.
11. Matriz de testes com **146 cenários rastreáveis** (`60` Rev 10 + `15` Rev 11 + `44` Rev 12 + `9` Rev 13 + `9` Rev 14 + `9` Rev 15; `0/146 executados`).
12. Nenhuma contradição entre os 10 documentos e 19 schemas.
13. Nenhuma funcionalidade da Fase 8 antecipada.
14. Base `v8.0-beta.6.6` (`11e91b6f3d517707326357868cc34ff97ab8327d`) preservada integralmente.

---

## 2. Regra de Bloqueio

Se qualquer uma das 14 condições não for atendida: `OS_STATUS = BLOCKED`. É proibido transformar aprovação parcial em autorização de implementação.
