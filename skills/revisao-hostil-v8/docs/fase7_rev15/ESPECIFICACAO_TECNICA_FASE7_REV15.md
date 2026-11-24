# ESPECIFICAÇÃO TÉCNICA — FASE 7 (`v8.0-beta.7`), REVISÃO 15

**Status:** Documentação normativa autossuficiente (**implementação Python NÃO iniciada**; Ordem de Serviço **BLOQUEADA até aprovação externa**)  
**Base obrigatória imutável:** tag `v8.0-beta.6.6`, commit `11e91b6f3d517707326357868cc34ff97ab8327d`  
**Branch documental:** `specification/v8.0-beta.7-rev15`  
**Escopo:** Correção integral dos 3 achados da auditoria externa da Revisão 14 (`ACH-B7-R14-001`, `ACH-B7-R14-002`, `ACH-B7-R14-003`), preservando integralmente todas as garantias consolidadas até a Revisão 14.

---

## 0. Declaração de Escopo e Preservação da Base

1. Este pacote documental é estritamente normativo. **Nenhum código Python da Fase 7 foi criado ou executado** (`0/146 executados`).
2. `main`, a tag `v8.0-beta.6.6` (`11e91b6f3d517707326357868cc34ff97ab8327d`), `requirements.txt`, `catalogo_agentes.yaml`, `SKILL.md`, os 8 schemas em `references/schemas/` e as branches históricas (`rev10`–`rev14`) permanecem integralmente inalterados.

---

## 1. Inventário de Contratos e Migração da Beta 6.6

- **8 schemas históricos** da Beta 6.6 preservados byte a byte em `schemas/legacy-v8.0-beta.6.6/` (versões históricas não comprovadas permanecem `NAO_VERIFICADO` e bloqueadas).
- **19 contratos canônicos em `schemas/7.0.0/`**, todos com `$id` único `https://revisao-hostil.v8/schemas/7.0.0/<nome>`, `$ref` exclusivamente local e versionado, e `additionalProperties: false`.

---

## 2. Protocolo `MonotonicCheckpointStore`, Dossiê Assinado, Composição Exata dos 3 Papéis e `NonceConsumptionStore` (`ACH-B7-R14-001`, `ACH-B7-R14-002`, `ACH-B7-R14-003`)

Especificação criptográfica completa em `CONTRATOS_CRIPTOGRAFICOS_REV15.md`:

1. **Interface completa de consumo persistente de nonce (`ACH-B7-R14-001`):**
   - `NonceConsumptionStore.consume_once(nonce_sha256, protocol_scope, campaign_id, witness_id, bound_witness_key_id, expires_at_monotonic_context) -> NonceConsumptionResult` (dataclass imutável com `consumed`, `persisted_tx_id`, `nonce_sha256`, `protocol_scope`, `campaign_id`, `witness_id`, `bound_witness_key_id`, `store_epoch`).
   - Persistência atômica de todos os campos; `persisted_tx_id` identifica transação confirmada (nunca tentativa); unicidade `UNIQUE (protocol_scope, nonce_sha256)`; reconciliação campo a campo com `nonce_consumption_receipts` em `schema_monotonic_checkpoint_receipt.json`; transação abortada nunca gera recibo aceito; falha de persistência impede aceitação do checkpoint.
2. **Garantia estrutural e semântica dos 3 papéis no dossiê (`ACH-B7-R14-002`):**
   - `schema_administrative_independence_dossier.json` impõe `minItems: 3`, `maxItems: 3`, `uniqueItems: true` **E** `allOf` com `contains` + `const` + `minContains: 1` + `maxContains: 1` para cada papel (`checkpoint_store`, `witness_a`, `witness_b`).
   - Validação semântica independente compara o conjunto de papéis com exatamente `{"checkpoint_store", "witness_a", "witness_b"}`, rejeitando papéis repetidos, ausentes ou desconhecidos.
3. **Pré-imagem única e inequívoca de `dossier_jcs_sha256` (`ACH-B7-R14-003`):**
   - `dossier_payload = JCS(dossier sem authority_signature e dossier_jcs_sha256)`
   - `dossier_jcs_sha256 = SHA256(UTF8(dossier_payload))`
   - A assinatura `authority_signature` é calculada sobre exatamente os mesmos bytes; o digest é comparado com a política confiável e registrado identicamente no recibo; nenhuma implementação pode usar outra pré-imagem.

---

## 3. Confinamento Estrito de Arquivos, Domínio Racional e Política de Compatibilidade

- **Confinamento:** preservado integralmente (Windows NTFS `NtCreateFile` + `FILE_ID_INFO` + `NumberOfLinks == 1` + bloqueio UNC/ADS/reparse; Linux ≥ 5.6 `openat2` + `RESOLVE_NO_XDEV` + `st_nlink == 1`; macOS/outros → `UnsafePlatformPathError`; buffer único imutável).
- **Domínio racional:** preservado integralmente ($m \le 15$, $n_i \le 15$, notas $[0, 10]$, pesos $(0, 1000]$ em `Fraction`, $D_{\text{bound}} = 5.4054 \times 10^{21}$ [73 bits], $N_{\text{bound}} = 5.4054 \times 10^{22}$ [76 bits], teto operacional 128 bits).
- **Política de compatibilidade:** `compatibility_policy.schema.json` (`minItems: 19`, `maxItems: 19`, `uniqueItems: true`) + validador semântico obrigatório (unicidade de `schema_name`, `ref_schema_name` e `instance_schema_version`, correspondência 1-para-1 com `SCHEMA_REGISTRY_FASE7_REV15.json`, reconciliação da árvore transitiva `$ref` em disco, hashes físicos, digest JCS e rejeição de `normative_specification_template` em produção).
- **SemVer estável estrito:** `MAJOR.MINOR.PATCH` com comparador numérico `compare_semver_stable()`.
