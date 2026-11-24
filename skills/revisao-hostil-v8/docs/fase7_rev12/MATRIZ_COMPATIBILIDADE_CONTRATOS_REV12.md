# MATRIZ E POLÍTICA EXECUTÁVEL DE COMPATIBILIDADE DE CONTRATOS — FASE 7 (`v8.0-beta.7`), REVISÃO 12

**Status:** Documentação normativa (sem implementação Python)  
**Base imutável:** `v8.0-beta.6.6` (`11e91b6f3d517707326357868cc34ff97ab8327d`)  
**Achados endereçados:** `ACH-B7-R11-001`, `ACH-B7-R11-006`, `ACH-B7-R11-007`

---

## 1. Artefatos Estruturados da Política

1. **Schema fechado (Draft 2020-12):** `compatibility_policy.schema.json` — impõe `additionalProperties: false` no objeto raiz, em cada entrada de `entries`, em cada entrada de `ref_hashes` e em cada entrada de `allowed_instance_versions`.
2. **Política de compatibilidade:** `compatibility_policy_v1.json` — contém **18 regras de compatibilidade** (uma por contrato canônico `7.0.0`), cobrindo **19 referências transitivas `$ref`** com SHA-256 físico real de cada arquivo em `schemas/7.0.0/` e **zero placeholders**.
3. **Digest JCS da política:**
   - `compatibility_policy_jcs_sha256 = a8ba99bb92b83abbddc533daafe887ea7dc9c525f205fed8074a862235b84635`
   - Calculado sobre `UTF8(JCS(compatibility_policy_v1.json excluindo compatibility_policy_jcs_sha256))`.

---

## 2. Estados da Política e Regras de Carregamento

- **`normative_specification_template`:** estado atual deste pacote documental. A função futura `load_compatibility_policy()` **DEVE rejeitar imediatamente** qualquer política com `policy_status != "frozen_executable"` (`T-R12-105`).
- **`frozen_executable`:** estado operacional (somente após OS e assinatura com raiz confiável real). Exige:
  - `default_decision == "deny"`;
  - `schema_sha256` e todos os `ref_sha256` casando `^[0-9a-f]{64}$` e correspondendo aos bytes físicos;
  - zero placeholders (`PENDING_*` rejeitado em `T-R12-106`);
  - cobertura completa de toda a árvore transitiva `$ref`;
  - parser JSON estrito (UTF-8 válido, rejeição de chaves duplicadas, `NaN`, `Infinity`, `-Infinity`, dados trailing);
  - validação integral contra `compatibility_policy.schema.json`;
  - assinatura verificada pela raiz confiável vinculando `compatibility_policy_jcs_sha256`.

---

## 3. SemVer Estável Estrito (`ACH-B7-R11-007`)

- Formato único para `contract_version` e `schema_version`: `MAJOR.MINOR.PATCH` (`^(0|[1-9][0-9]{0,9})\.(0|[1-9][0-9]{0,9})\.(0|[1-9][0-9]{0,9})(?![\r\n])$`).
- Comparador `compare_semver_stable()` compara os três inteiros numericamente (`1.10.0 > 1.9.0`), sem `packaging.Version`.
- Versões de domínio (`profile_version`, `motor_version`) não se confundem com `contract_version` nem `schema_version`.
