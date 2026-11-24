# CONTRATOS CRIPTOGRÁFICOS E DE INTEGRIDADE — FASE 7 (`v8.0-beta.7`), REVISÃO 11

**Status:** Documentação normativa (sem implementação Python)  
**Base imutável:** `v8.0-beta.6.6` (`11e91b6f3d517707326357868cc34ff97ab8327d`)  
**Achados endereçados:** `ACH-B7-R10-001`, `ACH-B7-R10-004`, `ACH-B7-R10-005`, `ACH-B7-R10-006`

---

## 1. Formato Canônico e Identificadores Monotônicos (`ACH-B7-R10-005`)

1. **Canonicalização JSON:** RFC 8785 (JCS — JSON Canonicalization Scheme). Todos os hashes `*_jcs_sha256` são calculados sobre os bytes UTF-8 da serialização JCS do objeto **excluindo** o próprio campo de hash e campos de assinatura externos ao payload assinado.
2. **Regex estritamente ASCII para `policy_seq` e `checkpoint_revision`:**
   - **Python (`re.fullmatch`):** `\A(0|[1-9][0-9]{0,31})\Z`
   - **JSON Schema:** `^(0|[1-9][0-9]{0,31})(?![\r\n])$`
   - **Proibição normativa:** é proibido o uso de `\d` em Python (pois casa dígitos Unicode como `1٣`, `٢`, `０`).
   - **Comprimento máximo:** 32 dígitos ASCII (`0` a `99999999999999999999999999999999`), suficiente para monotonia prática e protegido contra DoS por inteiros arbitrários.

---

## 2. Modelo de Autoridade, Delegação e Rotação de Signatários da Política (`ACH-B7-R10-004`)

### 2.1. Raiz de Confiança Fixada (`pinned_trust_root`)
O verificador carrega fora da árvore mutável da campanha o objeto `pinned_trust_root`:
- `trust_root_key_id` (string)
- `algorithm` (`"Ed25519"` ou `"ECDSA-P256-SHA256"`)
- `public_key_pem` (string)

### 2.2. Regras de Autorização de uma Política Candidata `P_k`
Para aceitar uma política candidata `P_k` (com `policy_seq = k`) dada a última política aceita `P_{k-1}` (ou estado inicial `k = 0` sem política anterior):

1. **Proibição absoluta de autoautorização:** o verificador **NUNCA** lê `P_k.authorized_signers` para decidir se a assinatura de `P_k` é autorizada.
2. **Fontes exclusivas de autoridade para assinar `P_k`:**
   - **Caso A (Raiz):** `P_k.signature.key_id == pinned_trust_root.trust_root_key_id` e a assinatura verifica com `pinned_trust_root.public_key_pem`.
   - **Caso B (Delegação prévia, somente se `k > 0` e `P_{k-1}` já foi aceita):** existe entrada `S` em `P_{k-1}.authorized_signers` tal que:
     - `S.key_id == P_k.signature.key_id` (vinculação explícita `key_id` ↔ chave pública),
     - `"policy_sign" in S.scopes`,
     - `S.status == "active"`,
     - `S.not_before_utc <= tsa_gen_time_utc <= S.not_after_utc` (validado contra o `genTime` do carimbo RFC 3161 verificado, **nunca** contra o relógio local),
     - a assinatura sobre `P_k_payload_jcs` verifica com `S.public_key_pem`.
3. **Rotação e Revogação:**
   - Para revogar uma chave delegada `K_old`, publica-se `P_k` assinada pela raiz ou por outra chave delegada ativa em `P_{k-1}`, removendo `K_old` (ou marcando-a `revoked`) em `P_k.authorized_signers`.
   - A partir da aceitação de `P_k` (e avanço monotônico do checkpoint), `K_old` não pode mais assinar `P_{k+1}`.
4. **Bytes exatos assinados (`P_k_payload_jcs`):**
   - JCS do objeto `P_k` **excluindo** `policy_jcs_sha256` e `signature`.
   - `policy_jcs_sha256` deve igualar `SHA256(P_k_payload_jcs)`.
   - `P_k` inclui obrigatoriamente `compatibility_policy_jcs_sha256` vinculando o artefato `compatibility_policy_v1.json`.

---

## 3. Contrato Fechado do `MonotonicCheckpointStore` e Prova de Atualidade (`ACH-B7-R10-001`)

Para impedir rollback de política (reutilização de `P_{k-1}` validamente assinada) e restauração de snapshot do armazenamento remoto:

### 3.1. Schema Fechado de `signed_store_receipt` (`additionalProperties: false`)
```json
{
  "type": "object",
  "additionalProperties": false,
  "required": [
    "store_id",
    "namespace",
    "previous_revision",
    "new_revision",
    "previous_checkpoint_sha256",
    "new_checkpoint_sha256",
    "policy_seq",
    "policy_jcs_sha256",
    "receipt_timestamp_utc",
    "signature_algorithm",
    "store_key_id",
    "signature_b64"
  ],
  "properties": {
    "store_id": { "type": "string", "minLength": 1 },
    "namespace": { "type": "string", "minLength": 1 },
    "previous_revision": { "type": "string", "pattern": "^(0|[1-9][0-9]{0,31})(?![\\r\\n])$" },
    "new_revision": { "type": "string", "pattern": "^(0|[1-9][0-9]{0,31})(?![\\r\\n])$" },
    "previous_checkpoint_sha256": { "type": "string", "pattern": "^[0-9a-f]{64}(?![\\r\\n])$" },
    "new_checkpoint_sha256": { "type": "string", "pattern": "^[0-9a-f]{64}(?![\\r\\n])$" },
    "policy_seq": { "type": "string", "pattern": "^(0|[1-9][0-9]{0,31})(?![\\r\\n])$" },
    "policy_jcs_sha256": { "type": "string", "pattern": "^[0-9a-f]{64}(?![\\r\\n])$" },
    "receipt_timestamp_utc": { "type": "string", "format": "date-time" },
    "signature_algorithm": { "type": "string", "enum": ["Ed25519", "ECDSA-P256-SHA256"] },
    "store_key_id": { "type": "string", "minLength": 1 },
    "signature_b64": { "type": "string", "minLength": 1 }
  }
}
```
- **Invariante de monotonia:** `int(new_revision) == int(previous_revision) + 1`.
- **Verificação da assinatura do recibo:** `store_key_id` deve estar autorizado na política confiável com escopo `"checkpoint_sign"`, e `signature_b64` deve verificar sobre o JCS de `signed_store_receipt` excluindo `signature_b64`.

### 3.2. Prova Verificável de Atualidade / Freshness (`freshness_proof`)
Um `signed_store_receipt` isolado **não** impede replay de um recibo antigo ou restauração de snapshot do store remoto. Portanto, para classificar uma campanha como `ancoragem_externa_independente`, é obrigatório anexar e verificar `freshness_proof` usando **pelo menos um** dos três mecanismos fechados abaixo:

1. **`independent_witness_cosig` (Testemunha Externa Independente):**
   - Co-assinatura emitida por serviço de testemunha independente cuja chave pública (`witness_key_id`) é fixada na raiz de confiança ou política confiável com escopo `"witness_sign"` (distinta da chave do store).
   - Payload co-assinado: `JCS({store_id, namespace, new_revision, new_checkpoint_sha256, witness_timestamp_utc})`.
   - O verificador confirma que a testemunha não aceita regressão de `new_revision` e que `witness_timestamp_utc` está dentro da janela de atualidade configurada.
2. **`transparency_log_consistency` (Log de Transparência Append-Only):**
   - Prova de inclusão (`inclusion_proof`) da folha `new_checkpoint_sha256` em um log append-only (ex.: RFC 6962 / Rekor / Trillian) **E** prova de consistência Merkle (`consistency_proof`) ligando o `tree_head` do `previous_revision` ao `tree_head` do `new_revision`, ambos assinados pela chave pública do log fixada na política confiável.
3. **`hardware_monotonic_counter` (Contador Monotônico Atestado em Hardware):**
   - Cotação criptográfica (TPM 2.0 `TPM2_Quote` sobre índice NV monotônico, HSM ou TEE) assinada por chave de atestação (AK/EK) fixada na raiz de confiança, comprovando que `counter_value == int(new_revision)` e vinculando o nonce `new_checkpoint_sha256`.

### 3.3. Regra de Degradação / Fail-Closed
- Se `freshness_proof` estiver ausente, inválida, com recibo antigo replayed, ou se a testemunha externa estiver inacessível:
  - A classificação `ancoragem_externa_independente` é **negada**.
  - Se a política da campanha exigir ancoragem externa obrigatória: erro fatal `AnchorVerificationError` (fail-closed).
  - Caso contrário: degrada explicitamente para `integridade_local_com_ancora_co_localizada` com registro do motivo no manifesto.

---

## 4. Digest Composto do Parecer (`parecer_sha256`) (`ACH-B7-R10-006`)

```json
{
  "schema_version": "7.0.0",
  "parecer_core_jcs_sha256": "<64-hex>",
  "score_semantic_sha256": "<64-hex>",
  "score_provenance_sha256": "<64-hex>"
}
```
`parecer_sha256 = SHA256(JCS(objeto_acima))`.
Qualquer modificação em `score_provenance_sha256` (mesmo preservando `score_semantic_sha256`) altera deterministicamente `parecer_sha256` e invalida qualquer selo ou referência ao parecer original.
