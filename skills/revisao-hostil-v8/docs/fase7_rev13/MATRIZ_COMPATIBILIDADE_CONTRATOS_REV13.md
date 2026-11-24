# MATRIZ E POLÍTICA EXECUTÁVEL DE COMPATIBILIDADE DE CONTRATOS — FASE 7 (`v8.0-beta.7`), REVISÃO 13

**Status:** Documentação normativa (sem implementação Python)  
**Base imutável:** `v8.0-beta.6.6` (`11e91b6f3d517707326357868cc34ff97ab8327d`)  
**Achado endereçado:** `ACH-B7-R12-003` (P1)

---

## 1. Artefatos Estruturados da Política

1. **Schema fechado (Draft 2020-12):** `compatibility_policy.schema.json`
   - `additionalProperties: false` em todos os níveis;
   - `entries`: **`minItems: 18`**, **`maxItems: 18`**, **`uniqueItems: true`**;
   - `ref_hashes`: **`uniqueItems: true`**;
   - `allowed_instance_versions`: **`uniqueItems: true`**.
2. **Política de compatibilidade:** `compatibility_policy_v1.json` — exatamente **18 entradas** (correspondência 1-para-1 com `SCHEMA_REGISTRY_FASE7_REV13.json`), cobrindo **19 referências transitivas `$ref`** com SHA-256 físico real e **zero placeholders**.
3. **Digest JCS da política:**
   - `compatibility_policy_jcs_sha256 = 6f1be68d407bb9abb63220d15418a6fce853dcd49404c8ef5f1a37e0843930ad`

---

## 2. Validador Semântico Obrigatório (`ACH-B7-R12-003`)

**Regra explícita:** a validação pelo JSON Schema `compatibility_policy.schema.json`, isoladamente, **NÃO** comprova a integridade semântica da política. Antes de aceitar `policy_status == "frozen_executable"`, `load_compatibility_policy()` deve executar todas as verificações semânticas abaixo (falha fechada com `PolicySemanticError` / `ExecutionBlockedError`):

1. **Cardinalidade e unicidade de `schema_name`:** exatamente 18 entradas e `len(set(e.schema_name)) == 18`.
2. **Unicidade de `ref_schema_name`:** dentro de cada entrada, `len(set(r.ref_schema_name)) == len(e.ref_hashes)`.
3. **Correspondência exata com o Registry:** o conjunto de `schema_name` das 18 entradas deve ser **exatamente igual** ao conjunto de chaves em `SCHEMA_REGISTRY_FASE7_REV13.json` (rejeitar schemas desconhecidos, ausentes ou duplicados).
4. **Reconciliação da árvore transitiva `$ref` em disco:** recalcular a árvore transitiva real de `$ref` a partir dos arquivos físicos em `schemas/7.0.0/` e exigir igualdade exata de conjuntos `(ref_schema_name, ref_path, ref_sha256)` com `ref_hashes` (rejeitar referências extras, ausentes, duplicadas ou com caminhos divergentes).
5. **Integridade física:** cada `schema_sha256` e `ref_sha256` deve corresponder aos bytes físicos em disco (`^[0-9a-f]{64}$`, zero placeholders).
6. **Digest JCS e assinatura:** `compatibility_policy_jcs_sha256` recalculado e vinculado à política confiável assinada pela raiz.
7. **Estado template rejeitado em produção:** `policy_status != "frozen_executable"` é rejeitado imediatamente.

---

## 3. SemVer Estável Estrito

- `MAJOR.MINOR.PATCH` (`^(0|[1-9][0-9]{0,9})\.(0|[1-9][0-9]{0,9})\.(0|[1-9][0-9]{0,9})(?![\r\n])$`), comparador numérico `compare_semver_stable()` (`1.10.0 > 1.9.0`), sem `packaging.Version`.
