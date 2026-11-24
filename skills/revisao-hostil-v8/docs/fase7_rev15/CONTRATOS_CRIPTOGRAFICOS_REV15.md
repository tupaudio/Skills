# CONTRATOS CRIPTOGRÁFICOS E DE INTEGRIDADE — FASE 7 (`v8.0-beta.7`), REVISÃO 15

**Status:** Documentação normativa (sem implementação Python)  
**Base imutável:** `v8.0-beta.6.6` (`11e91b6f3d517707326357868cc34ff97ab8327d`)  
**Achados endereçados:** `ACH-B7-R14-001` (P1), `ACH-B7-R14-002` (P1), `ACH-B7-R14-003` (P2)

---

## 1. Formato Normativo Único de Chaves Públicas e Identificadores

- Todas as chaves públicas (raiz confiável, autoridade emissora do dossiê, signatários delegados, Store, Testemunha A e Testemunha B) usam exclusivamente `public_key_spki_der_b64` (Base64 RFC 4648 estrito de SPKI DER) e `key_id = lowercase_hex(SHA256(SPKI_DER_BYTES))`.
- `policy_seq` e `checkpoint_revision`: dígitos ASCII puros `\A(0|[1-9][0-9]{0,31})\Z`.

---

## 2. Protocolo `2-of-2` do `MonotonicCheckpointStore`

### 2.1. Dossiê de Independência Administrativa — Composição dos 3 Papéis e Pré-imagem Única (`ACH-B7-R14-002`, `ACH-B7-R14-003`)

Regido por `schemas/7.0.0/schema_administrative_independence_dossier.json` (`additionalProperties: false`):

1. **Composição estrutural e semântica dos 3 domínios (`ACH-B7-R14-002`):**
   - **Estrutural (JSON Schema Draft 2020-12):** `domains` impõe `minItems: 3`, `maxItems: 3`, `uniqueItems: true` **E** `allOf` com `contains` + `const` + `minContains: 1` + `maxContains: 1` para cada um dos três papéis: `"checkpoint_store"`, `"witness_a"`, `"witness_b"`.
   - **Semântica independente (obrigatória):** o verificador extrai `roles = [d["role"] for d in dossier["domains"]]` e exige `len(roles) == 3` e `set(roles) == {"checkpoint_store", "witness_a", "witness_b"}`, rejeitando papéis repetidos, ausentes ou desconhecidos (`DossierRoleCompositionError`), além de exigir `legal_entity_id`, `infrastructure_provider`, `administrative_domain`, `kms_hsm_id`, `key_custodian_id` e `operator_key_id` mutuamente distintos entre os três domínios.
2. **Pré-imagem única e normativa de `dossier_jcs_sha256` (`ACH-B7-R14-003`):**
   ```text
   dossier_payload = JCS(dossier sem authority_signature e dossier_jcs_sha256)
   dossier_jcs_sha256 = SHA256(UTF8(dossier_payload))
   ```
   - A assinatura `authority_signature.signature_b64` é calculada sobre **exatamente os mesmos bytes** `UTF8(dossier_payload)`.
   - `dossier_jcs_sha256` é comparado byte a byte com o valor fixado na política confiável e com `administrative_independence_dossier_sha256` no recibo `schema_monotonic_checkpoint_receipt.json`.
   - **Proibição:** nenhuma implementação pode utilizar outra pré-imagem (ex.: incluir `authority_signature` no hash).
3. **Vetor de teste determinístico (`ACH-B7-R14-003`):**
   - Para o objeto canônico `dossier-tv-001` (`schema_version="7.0.0"`, `scope="administrative_independence_2of2_checkpoint"`, `issued_at_utc="2026-11-24T00:00:00Z"`, `valid_from_utc="2026-11-24T00:00:00Z"`, `valid_until_utc="2027-11-24T00:00:00Z"`, `revocation_list_ref="revocation-list-v1"`, e 3 domínios ordenados `checkpoint_store`/`witness_a`/`witness_b` com `legal_entity_id` `LEI-ORG-A/B/C`, `operator_key_id` `"1"*64`/`"2"*64`/`"3"*64`, `documentary_evidence_sha256` `"a"*64`/`"b"*64`/`"c"*64`):
   - Comprimento exato de `UTF8(dossier_payload)`: **`1788` bytes**.
   - `dossier_jcs_sha256` esperado: **`e322b6ae5d9b60084f115ee078c5eac6c48a0d3871e7739980556b2841a9ca8f`**.
   - Dois verificadores independentes devem produzir exatamente esse digest e verificar a assinatura sobre os mesmos 1788 bytes.
4. **Validade temporal e revogação:** `valid_from_utc <= campaign_tsa_gen_time_utc <= valid_until_utc` e verificação de `revocation_list_ref` (dossiê expirado, revogado ou sem cadeia confiável rejeita `ancoragem_externa_independente`).

### 2.2. Garantia Estrutural e Semântica do Quórum `2-of-2`
Mantida integralmente: `witness_assertions` (`minItems: 2, maxItems: 2, uniqueItems: true`), `witness_id` distintos, `witness_key_id` distintos, correspondência exata com `(witness_a, witness_b)` fixadas na política confiável e igualdade de `(store_id, namespace, policy_seq, checkpoint_revision, checkpoint_sha256)`.

### 2.3. Interface Completa de `NonceConsumptionStore` e Vinculação 1-para-1 (`ACH-B7-R14-001`)

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class NonceConsumptionResult:
    consumed: bool
    persisted_tx_id: str
    nonce_sha256: str
    protocol_scope: str
    campaign_id: str
    witness_id: str
    bound_witness_key_id: str
    store_epoch: str

class NonceConsumptionStore:
    def consume_once(
        self,
        nonce_sha256: str,
        protocol_scope: str,
        campaign_id: str,
        witness_id: str,
        bound_witness_key_id: str,
        expires_at_monotonic_context: str,
    ) -> NonceConsumptionResult: ...
```

**Requisitos contratuais obrigatórios:**
1. **Persistência atômica de todos os campos:** a transação ACID grava atomicamente `(nonce_sha256, protocol_scope, campaign_id, witness_id, bound_witness_key_id, expires_at_monotonic_context, persisted_tx_id, store_epoch)`.
2. **Transação confirmada:** `persisted_tx_id` identifica exclusivamente uma transação confirmada (`COMMIT` + `fsync`), nunca uma tentativa pendente ou abortada.
3. **Unicidade:** restrição `UNIQUE (protocol_scope, nonce_sha256)` no armazenamento persistente.
4. **Reconciliação campo a campo:** o `NonceConsumptionResult` retornado (com `consumed == True`) é reconciliado campo a campo com o registro correspondente em `nonce_consumption_receipts[]` de `schema_monotonic_checkpoint_receipt.json` (`nonce_sha256`, `protocol_scope`, `campaign_id`, `witness_id`, `bound_witness_key_id`, `persisted_tx_id`, `store_epoch`) e com `SHA256(base64_decode(witness_assertions[].challenge_nonce_b64))`.
5. **Ausência de efeitos colaterais em falha:** uma transação abortada nunca gera recibo aceito; falha de persistência (`NoncePersistenceError`) ou rollback de `store_epoch` (`NonceStoreRollbackError`) impede a aceitação do checkpoint e o avanço de revisão.

---

## 3. Digest Composto do Parecer (`parecer_sha256`)

Mantido integralmente: `parecer_sha256 = SHA256(JCS({schema_version, parecer_core_jcs_sha256, score_semantic_sha256, score_provenance_sha256}))`.
