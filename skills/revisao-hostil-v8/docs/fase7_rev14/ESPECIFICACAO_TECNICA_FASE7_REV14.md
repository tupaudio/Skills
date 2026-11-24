# ESPECIFICAÇÃO TÉCNICA — FASE 7 (`v8.0-beta.7`), REVISÃO 14

**Status:** Documentação normativa autossuficiente (**implementação Python NÃO iniciada**; Ordem de Serviço **BLOQUEADA até aprovação externa**)  
**Base obrigatória imutável:** tag `v8.0-beta.6.6`, commit `11e91b6f3d517707326357868cc34ff97ab8327d`  
**Branch documental:** `specification/v8.0-beta.7-rev14`  
**Escopo:** Correção integral dos 4 achados da auditoria externa da Revisão 13 (`ACH-B7-R13-001`, `ACH-B7-R13-002`, `ACH-B7-R13-003`, `ACH-B7-R13-004`), preservando integralmente todas as garantias consolidadas até a Revisão 13.

---

## 0. Declaração de Escopo e Preservação da Base

1. Este pacote documental é estritamente normativo. **Nenhum código Python da Fase 7 foi criado ou executado** (`0/137 executados`).
2. `main`, a tag `v8.0-beta.6.6` (`11e91b6f3d517707326357868cc34ff97ab8327d`), `requirements.txt`, `catalogo_agentes.yaml`, `SKILL.md`, os 8 schemas em `references/schemas/` e as branches históricas (`rev10`–`rev13`) permanecem integralmente inalterados.

---

## 1. Inventário de Contratos e Migração da Beta 6.6

- **8 schemas históricos** da Beta 6.6 preservados byte a byte em `schemas/legacy-v8.0-beta.6.6/` (versões históricas não comprovadas permanecem `NAO_VERIFICADO` e bloqueadas).
- **19 contratos canônicos em `schemas/7.0.0/`** (os 18 contratos da Rev 13 + o novo contrato fechado `schema_administrative_independence_dossier.json` exigido por `ACH-B7-R13-001`), todos com `$id` único `https://revisao-hostil.v8/schemas/7.0.0/<nome>`, `$ref` exclusivamente local e versionado, e `additionalProperties: false`.

---

## 2. Protocolo Definitivo do `MonotonicCheckpointStore`, Dossiê Assinado, Quórum `2-of-2` e Vinculação 1-para-1 de Nonces (`ACH-B7-R13-001`, `ACH-B7-R13-002`, `ACH-B7-R13-003`)

Especificação criptográfica completa em `CONTRATOS_CRIPTOGRAFICOS_REV14.md`:

1. **Dossiê Verificável de Independência Administrativa (`ACH-B7-R13-001`):** regido pelo schema fechado `schemas/7.0.0/schema_administrative_independence_dossier.json`, com envelope assinado por autoridade confiável previamente estabelecida, validade temporal `[valid_from_utc, valid_until_utc]` verificada no `genTime` TSA, referência de revogação (`revocation_list_ref`), evidências individualizadas para os 3 domínios (`checkpoint_store`, `witness_a`, `witness_b`), e hash `dossier_jcs_sha256` vinculado tanto à política confiável quanto ao `schema_monotonic_checkpoint_receipt.json`.
2. **Garantia Estrutural e Semântica do Quórum `2-of-2` (`ACH-B7-R13-002`):** `witness_assertions` exige `minItems: 2`, `maxItems: 2`, `uniqueItems: true` **MAIS** validação semântica obrigatória de `witness_id` distintos, `witness_key_id` distintos, correspondência exata com as testemunhas A e B fixadas na política confiável e concordância de `(store_id, namespace, policy_seq, checkpoint_revision, checkpoint_sha256)`. Duas declarações da mesma testemunha ou chave são rejeitadas mesmo com assinaturas ou nonces diferentes.
3. **Vinculação Obrigatória 1-para-1 entre Nonces Consumidos e Declarações Assinadas (`ACH-B7-R13-003`):** decodificar cada `witness_assertions[].challenge_nonce_b64` em bytes, calcular `SHA256(bytes)` e exigir correspondência exata 1-para-1 com um único registro em `nonce_consumption_receipts[]` (`nonce_sha256`, `witness_id`, `bound_witness_key_id`, `campaign_id`, `protocol_scope`), concluindo a verificação persistente em `NonceConsumptionStore.consume_once(...)` **antes** de aceitar o recibo.

---

## 3. Confinamento Estrito de Arquivos e Domínio Racional

- **Confinamento:** preservado integralmente (Windows NTFS `NtCreateFile` + `FILE_ID_INFO` + `NumberOfLinks == 1` + bloqueio UNC/ADS/reparse; Linux ≥ 5.6 `openat2` + `RESOLVE_NO_XDEV` + `st_nlink == 1`; macOS/outros → `UnsafePlatformPathError`; buffer único imutável).
- **Domínio racional:** preservado integralmente ($m \le 15$, $n_i \le 15$, notas $[0, 10]$, pesos $(0, 1000]$ em `Fraction`, $D_{\text{bound}} = 5.4054 \times 10^{21}$ [73 bits], $N_{\text{bound}} = 5.4054 \times 10^{22}$ [76 bits], teto operacional 128 bits).

---

## 4. Política Executável de Compatibilidade, Unicidade Semântica e SemVer Estável (`ACH-B7-R13-004`)

- `compatibility_policy.schema.json` (Draft 2020-12): `entries` com `minItems: 19`, `maxItems: 19`, `uniqueItems: true`; `ref_hashes` e `allowed_instance_versions` com `uniqueItems: true`.
- **Validador semântico obrigatório (além do JSON Schema):**
  1. Unicidade de `schema_name` (19 nomes distintos) e correspondência exata 1-para-1 com `SCHEMA_REGISTRY_FASE7_REV14.json`;
  2. Unicidade de `ref_schema_name` em cada `ref_hashes` e reconciliação exata com a árvore transitiva `$ref` em disco (19 referências transitivas);
  3. **Unicidade semântica de `instance_schema_version` em `allowed_instance_versions` (`ACH-B7-R13-004`):** cada `instance_schema_version` só pode aparecer **uma única vez** por contrato; versões repetidas com `evidence_status` ou `backward_validation` divergentes são rejeitadas com `PolicySemanticError`;
  4. Hashes físicos SHA-256 verificados, zero placeholders, digest JCS e assinatura pela raiz confiável antes de aceitar `policy_status == "frozen_executable"`.
- SemVer estável estrito `MAJOR.MINOR.PATCH` com comparador numérico `compare_semver_stable()`.
