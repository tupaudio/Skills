# MATRIZ E POLÍTICA EXECUTÁVEL DE COMPATIBILIDADE DE CONTRATOS — FASE 7 (`v8.0-beta.7`), REVISÃO 17

**Status:** Documentação normativa (sem implementação Python de runtime)  
**Base imutável:** `v8.0-beta.6.6` (`11e91b6f3d517707326357868cc34ff97ab8327d`)

- **Schema fechado (Draft 2020-12):** `compatibility_policy.schema.json` (`minItems: 19`, `maxItems: 19`, `uniqueItems: true`, `additionalProperties: false` em todos os níveis).
- **Política de compatibilidade:** `compatibility_policy_v1.json` — 19 entradas 1-para-1 com `SCHEMA_REGISTRY_FASE7_REV17.json`, 19 referências transitivas `$ref`, zero placeholders.
- **Digest JCS da política (RFC 8785):** `ec21fff2dcb8a1c2387e374bd8f320890cf3f07865b6f631e3bd8832c839b41b`.
- **Verificação integral (`ACH-B7-R16-005`):** `tools/validate_rev17.py` valida Draft 2020-12 em **todos os 19 schemas**, unicidade de `$id`, ausência de `$ref` externos/ciclos, e reconcilia `direct_refs`, `transitive_refs` e `physical_sha256` contra o Registry e a política.
