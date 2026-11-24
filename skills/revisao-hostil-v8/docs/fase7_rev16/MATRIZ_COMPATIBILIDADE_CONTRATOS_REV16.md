# MATRIZ E POLÍTICA EXECUTÁVEL DE COMPATIBILIDADE DE CONTRATOS — FASE 7 (`v8.0-beta.7`), REVISÃO 16

**Status:** Documentação normativa (sem implementação Python de runtime)  
**Base imutável:** `v8.0-beta.6.6` (`11e91b6f3d517707326357868cc34ff97ab8327d`)

- **Schema fechado (Draft 2020-12):** `compatibility_policy.schema.json` (`minItems: 19`, `maxItems: 19`, `uniqueItems: true`, `additionalProperties: false` em todos os níveis).
- **Política de compatibilidade:** `compatibility_policy_v1.json` — 19 entradas 1-para-1 com `SCHEMA_REGISTRY_FASE7_REV16.json`, 19 referências transitivas `$ref`, zero placeholders.
- **Digest JCS da política:** `5fb6998923d74cc90576d0f4b83a90b38e8bbd595c3c5efd7e159d9e9bd9fe0e`.
- **Validador semântico obrigatório:** unicidade de `schema_name`, `ref_schema_name` e `instance_schema_version`; correspondência 1-para-1 com o Registry; reconciliação da árvore transitiva `$ref` em disco; hashes físicos SHA-256; digest JCS; assinatura pela raiz confiável; rejeição de `policy_status != "frozen_executable"`.
