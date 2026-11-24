# CONTRATOS CRIPTOGRÁFICOS E DE INTEGRIDADE — FASE 7 (`v8.0-beta.7`), REVISÃO 14

**Status:** Documentação normativa (sem implementação Python)  
**Base imutável:** `v8.0-beta.6.6` (`11e91b6f3d517707326357868cc34ff97ab8327d`)  
**Achados endereçados:** `ACH-B7-R13-001` (P1), `ACH-B7-R13-002` (P1), `ACH-B7-R13-003` (P1)

---

## 1. Formato Normativo Único de Chaves Públicas e Identificadores

- Todas as chaves públicas (raiz confiável, autoridade emissora do dossiê, signatários delegados, Store, Testemunha A e Testemunha B) usam exclusivamente `public_key_spki_der_b64` (Base64 RFC 4648 estrito de SPKI DER) e `key_id = lowercase_hex(SHA256(SPKI_DER_BYTES))`.
- `policy_seq` e `checkpoint_revision`: dígitos ASCII puros `\A(0|[1-9][0-9]{0,31})\Z`.

---

## 2. Protocolo `2-of-2` do `MonotonicCheckpointStore`

### 2.1. Contrato Criptográfico Verificável do Dossiê de Independência Administrativa (`ACH-B7-R13-001`)
O dossiê é regido pelo schema fechado `schemas/7.0.0/schema_administrative_independence_dossier.json` (`additionalProperties: false`):

1. **Estrutura dos 3 domínios (`domains`, `minItems: 3`, `maxItems: 3`, `uniqueItems: true`):** deve conter exatamente uma entrada para cada papel (`checkpoint_store`, `witness_a`, `witness_b`), com `legal_entity_id`, `infrastructure_provider`, `administrative_domain`, `kms_hsm_id`, `key_custodian_id` e `operator_key_id` **mutuamente distintos** entre os três domínios, `no_shared_admin_credentials: true`, `independent_rotation_recovery_ref` e `documentary_evidence_sha256` individualizado.
2. **Envelope assinado por autoridade confiável previamente estabelecida (`authority_signature`):**
   - `authority_key_id` deve pertencer à lista de autoridades de auditoria/independência fixada na raiz de confiança ou política confiável (escopo `"dossier_attest_sign"`) e coincidir com `SHA256(base64_decode(public_key_spki_der_b64))`.
   - Assinatura calculada sobre `UTF8(JCS(dossiê excluindo authority_signature e dossier_jcs_sha256))`.
   - `dossier_jcs_sha256` deve coincidir com o hash fixado na política confiável e em `schema_monotonic_checkpoint_receipt.json` (`administrative_independence_dossier_sha256`).
3. **Validade temporal, revogação e renovação:**
   - `valid_from_utc <= campaign_tsa_gen_time_utc <= valid_until_utc` (verificado contra `genTime` TSA, nunca relógio local).
   - O verificador consulta `revocation_list_ref` (lista assinada pela mesma raiz/autoridade) e rejeita dossiê revogado ou expirado (`DossierInvalidError` / `DossierRevokedError`).
   - Qualquer alteração de operador, provedor, KMS/HSM ou custodiante exige revogação do dossiê anterior e emissão de novo dossiê assinado.
4. **Regra fail-closed:** dossiê sem cadeia de confiança verificável, com assinatura inválida, autoridade não autorizada, expirado ou revogado **rejeita obrigatoriamente** `ancoragem_externa_independente`.

### 2.2. Garantia Estrutural e Semântica do Quórum `2-of-2` (`ACH-B7-R13-002`)
Em `schema_monotonic_checkpoint_receipt.json`, `witness_assertions` exige `minItems: 2`, `maxItems: 2`, `uniqueItems: true`. Além da validação estrutural, o verificador **DEVE** executar as seguintes verificações semânticas obrigatórias (falha fechada com `QuorumValidationError`):

1. `witness_assertions[0].witness_id != witness_assertions[1].witness_id` (unicidade semântica de `witness_id`).
2. `witness_assertions[0].witness_key_id != witness_assertions[1].witness_key_id` (unicidade semântica de `witness_key_id`).
3. O conjunto `{(a.witness_id, a.witness_key_id) for a in witness_assertions}` deve ser **exatamente igual** ao par `{(witness_a_id, witness_a_key_id), (witness_b_id, witness_b_key_id)}` fixado na política confiável.
4. Ambas as declarações devem possuir valores **idênticos** de `store_id`, `namespace`, `policy_seq`, `checkpoint_revision` e `checkpoint_sha256`, consistentes com `signed_store_receipt`.
5. **Rejeição explícita:** duas declarações produzidas pela mesma testemunha ou mesma chave são rejeitadas **mesmo que possuam assinaturas ou nonces diferentes**.

### 2.3. `NonceConsumptionStore` Persistente e Vinculação 1-para-1 com Declarações (`ACH-B7-R13-003`)
Interface persistente mantida:
```python
class NonceConsumptionStore:
    def consume_once(
        self,
        nonce_sha256: str,
        campaign_id: str,
        witness_id: str,
        expires_at_monotonic_context: str,
    ) -> bool: ...
```
(Persistência transacional ACID, inserção condicional atômica `UNIQUE (protocol_scope, nonce_sha256)`, log append-only, proteção contra restauração via `store_epoch`, exclusividade sob concorrência, falha fechada `NoncePersistenceError`, retenção mínima `max_campaign_ttl + witness_clock_skew_margin`.)

**Algoritmo obrigatório de vinculação 1-para-1 entre `witness_assertions[]` e `nonce_consumption_receipts[]`:**
1. Decodificar `a.challenge_nonce_b64` em bytes brutos (exatamente 32 bytes) para cada declaração `a` em `witness_assertions`.
2. Calcular `expected_nonce_sha256 = lowercase_hex(SHA256(raw_nonce_bytes))`.
3. Exigir correspondência bijetiva (1-para-1) entre cada declaração `a` e exatamente um registro `r` em `nonce_consumption_receipts` tal que:
   - `r.nonce_sha256 == expected_nonce_sha256`;
   - `r.witness_id == a.witness_id`;
   - `r.bound_witness_key_id == a.witness_key_id`;
   - `r.campaign_id == current_campaign_id`;
   - `r.protocol_scope == "checkpoint_freshness_assertion_v1"`.
4. Rejeitar imediatamente registros sem correspondência, registros extras, nonces duplicados entre declarações ou associação cruzada de testemunha (`NonceBindingError`).
5. A verificação e persistência via `NonceConsumptionStore.consume_once(...)` **DEVE** ser concluída com sucesso **antes** de aceitar o recibo, registrando `(witness_id, nonce_sha256, persisted_tx_id)`.

---

## 3. Digest Composto do Parecer (`parecer_sha256`)

Mantido integralmente: `parecer_sha256 = SHA256(JCS({schema_version, parecer_core_jcs_sha256, score_semantic_sha256, score_provenance_sha256}))`.
