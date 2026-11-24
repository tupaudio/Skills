# MATRIZ E POLÍTICA EXECUTÁVEL DE COMPATIBILIDADE DE CONTRATOS — FASE 7 (`v8.0-beta.7`), REVISÃO 14

**Status:** Documentação normativa (sem implementação Python)  
**Base imutável:** `v8.0-beta.6.6` (`11e91b6f3d517707326357868cc34ff97ab8327d`)  
**Achado endereçado:** `ACH-B7-R13-004` (P2) e atualização para 19 contratos canônicos (`ACH-B7-R13-001`)

---

## 1. Artefatos Estruturados da Política

1. **Schema fechado (Draft 2020-12):** `compatibility_policy.schema.json` — `additionalProperties: false` em todos os níveis; `entries` com **`minItems: 19`**, **`maxItems: 19`**, **`uniqueItems: true`**; `ref_hashes` e `allowed_instance_versions` com `uniqueItems: true`.
2. **Política de compatibilidade:** `compatibility_policy_v1.json` — exatamente **19 entradas** (correspondência 1-para-1 com `SCHEMA_REGISTRY_FASE7_REV14.json`), cobrindo **19 referências transitivas `$ref`** com SHA-256 físico real e **zero placeholders**.
3. **Digest JCS da política:** `17f30abc61fe8db7f8e051e693251f640aa639d86e91a8f52b6d48589b64c838`.

---

## 2. Validador Semântico Obrigatório (`ACH-B7-R13-004`)

A validação do JSON Schema, isoladamente, **NÃO** comprova a integridade semântica da política. Antes de aceitar `policy_status == "frozen_executable"`, `load_compatibility_policy()` deve executar:

1. **Cardinalidade e unicidade de `schema_name`:** exatamente 19 entradas e `len(set(e.schema_name)) == 19`.
2. **Correspondência exata com o Registry:** conjunto de `schema_name` igual ao de `SCHEMA_REGISTRY_FASE7_REV14.json`.
3. **Unicidade de `ref_schema_name` e reconciliação da árvore transitiva `$ref` em disco:** sem referências extras, ausentes, duplicadas ou divergentes.
4. **Unicidade semântica de `instance_schema_version` (`ACH-B7-R13-004`):** dentro de cada entrada `e`, `len(set(v.instance_schema_version for v in e.allowed_instance_versions)) == len(e.allowed_instance_versions)`. Qualquer versão de instância repetida — **mesmo com `evidence_status` ou `backward_validation` diferentes** — é rejeitada com `PolicySemanticError`. Cada versão de instância possui exatamente uma única origem de evidência por contrato.
5. **Hashes físicos SHA-256, digest JCS e assinatura pela raiz confiável.**
6. **Estado template (`normative_specification_template`) sempre rejeitado em carga operacional.**
