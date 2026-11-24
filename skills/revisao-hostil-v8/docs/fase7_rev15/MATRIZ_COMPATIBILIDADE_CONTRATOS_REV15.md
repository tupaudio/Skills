# MATRIZ E POLÍTICA EXECUTÁVEL DE COMPATIBILIDADE DE CONTRATOS — FASE 7 (`v8.0-beta.7`), REVISÃO 15

**Status:** Documentação normativa (sem implementação Python)  
**Base imutável:** `v8.0-beta.6.6` (`11e91b6f3d517707326357868cc34ff97ab8327d`)

---

## 1. Artefatos Estruturados da Política

1. **Schema fechado (Draft 2020-12):** `compatibility_policy.schema.json` — `additionalProperties: false` em todos os níveis; `entries` com `minItems: 19`, `maxItems: 19`, `uniqueItems: true`; `ref_hashes` e `allowed_instance_versions` com `uniqueItems: true`.
2. **Política de compatibilidade:** `compatibility_policy_v1.json` — exatamente **19 entradas** (correspondência 1-para-1 com `SCHEMA_REGISTRY_FASE7_REV15.json`), cobrindo **19 referências transitivas `$ref`** com SHA-256 físico real e **zero placeholders**.
3. **Digest JCS da política:** `78241458cf405cea0cc33da58d8ae50273b5c7662f03fb451b3c265dbb99db5d`.

---

## 2. Validador Semântico Obrigatório

A validação pelo JSON Schema, isoladamente, **NÃO** comprova integridade semântica. Antes de aceitar `policy_status == "frozen_executable"`, `load_compatibility_policy()` deve validar:
1. Exatamente 19 entradas com `schema_name` únicos e correspondência 1-para-1 com `SCHEMA_REGISTRY_FASE7_REV15.json`;
2. Unicidade de `ref_schema_name` e reconciliação exata com a árvore transitiva `$ref` em disco;
3. Unicidade semântica de `instance_schema_version` em `allowed_instance_versions` por contrato;
4. Hashes físicos SHA-256, digest JCS e assinatura pela raiz confiável;
5. Rejeição obrigatória de `policy_status != "frozen_executable"`.
