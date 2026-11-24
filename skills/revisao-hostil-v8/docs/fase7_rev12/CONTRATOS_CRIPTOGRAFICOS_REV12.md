# CONTRATOS CRIPTOGRÁFICOS E DE INTEGRIDADE — FASE 7 (`v8.0-beta.7`), REVISÃO 12

**Status:** Documentação normativa (sem implementação Python)  
**Base imutável:** `v8.0-beta.6.6` (`11e91b6f3d517707326357868cc34ff97ab8327d`)  
**Achados endereçados:** `ACH-B7-R11-002`, `ACH-B7-R11-010` (e consolidação de `ACH-B7-R10-004`, `005`, `006`)

---

## 1. Formato Normativo Único de Chaves Públicas e Assinaturas (`ACH-B7-R11-010`)

1. **Representação canônica única:** todas as chaves públicas (raiz confiável, signatários delegados, Store, Testemunha A e Testemunha B) são representadas exclusivamente por:
   - `public_key_spki_der_b64`: Base64 RFC 4648 estrito dos bytes SubjectPublicKeyInfo (SPKI) em DER.
   - **Proibição:** `public_key_pem` não é permitido em contratos canônicos (PEM pode ser usado apenas em ferramentas administrativas externas, devendo ser convertido para SPKI DER antes do registro).
2. **Identificador determinístico de chave:**
   - `key_id = lowercase_hex(SHA256(SPKI_DER_BYTES))` (64 caracteres hexadecimais minúsculos).
   - Qualquer divergência entre `key_id` e `SHA256(base64_decode(public_key_spki_der_b64))` é rejeitada imediatamente (`T-R12-119`).
3. **Assinaturas:**
   - Base64 RFC 4648 estrito.
   - `Ed25519`: exatamente **64 bytes** decodificados.
   - `ECDSA-P256-SHA256` (quando habilitado para política): ASN.1 DER estrito.
   - Algoritmo e tipo de chave SPKI DER são validados conjuntamente (proibido declarar chave Ed25519 como ECDSA ou vice-versa).

---

## 2. Identificadores Monotônicos e Autoridade de Política

1. **`policy_seq` e `checkpoint_revision`:** dígitos ASCII puros `\A(0|[1-9][0-9]{0,31})\Z` (máx. 32 dígitos; proibido `\d`).
2. **Autoridade de política `P_k`:** somente assinada pela raiz fixada (`pinned_trust_root`) ou por chave delegada ativa em `P_{k-1}.authorized_signers` com escopo `policy_sign` e janela válida no `genTime` do TSA. Autoautorização via `P_k.authorized_signers` é estritamente proibida.
3. **Bytes assinados:** `UTF8(JCS(P_k excluindo policy_jcs_sha256 e signature))`. Inclui obrigatoriamente `compatibility_policy_jcs_sha256`.

---

## 3. Protocolo Definitivo do `MonotonicCheckpointStore` — Quórum `2-of-2` (`ACH-B7-R11-002`)

### 3.1. Três Domínios Administrativos Independentes
1. **Store de Checkpoint** (append-only com CAS atômico) — chave Ed25519 própria (`store_key_id`).
2. **Testemunha Externa A** — chave Ed25519 própria (`witness_a_key_id`).
3. **Testemunha Externa B** — chave Ed25519 própria (`witness_b_key_id`).

Invariante obrigatório: `store_key_id`, `witness_a_key_id` e `witness_b_key_id` são **mutuamente distintos** e todos fixados na política confiável em `public_key_spki_der_b64`.

### 3.2. Contrato `signed_store_receipt_v1` (`additionalProperties: false`)
Campos obrigatórios: `protocol` (`"signed_store_receipt_v1"`), `store_id`, `namespace`, `previous_revision`, `new_revision`, `previous_checkpoint_sha256`, `new_checkpoint_sha256`, `policy_seq`, `policy_jcs_sha256`, `receipt_timestamp_utc`, `store_key_id`, `signature_algorithm` (`"Ed25519"`), `signature_b64`.
- Assinatura sobre `UTF8(JCS(signed_store_receipt_v1 excluindo signature_b64))`.
- Regra de monotonia: `int(new_revision) == int(previous_revision) + 1`.
- Mesma revisão + mesmo hash: consulta idempotente permitida.
- Mesma revisão + hash diferente: `CheckpointEquivocationError`.

### 3.3. Contrato `checkpoint_freshness_assertion_v1` (`additionalProperties: false`)
Campos obrigatórios: `protocol` (`"checkpoint_freshness_assertion_v1"`), `witness_id`, `witness_key_id`, `store_id`, `namespace`, `policy_seq`, `checkpoint_revision`, `checkpoint_sha256`, `receipt_sha256`, `challenge_nonce_b64`, `issued_at_utc`, `signature_algorithm` (`"Ed25519"`), `signature_b64`.
- Assinatura sobre `UTF8(JCS(checkpoint_freshness_assertion_v1 excluindo signature_b64))`.

### 3.4. Protocolo Obrigatório de Desafio e Resposta (12 Passos)
1. Gerar nonce aleatório criptograficamente seguro (CSPRNG) de exatamente **32 bytes**.
2. Codificar em Base64 estrito (`challenge_nonce_b64`).
3. Consultar Testemunha A com `(store_id, namespace, challenge_nonce_b64)`.
4. Consultar Testemunha B com os mesmos dados.
5. Receber as duas asserções assinadas.
6. Verificar ambas as assinaturas Ed25519 com as chaves SPKI DER fixadas.
7. Confirmar reprodução exata do `challenge_nonce_b64` em ambas.
8. Confirmar concordância exata de `checkpoint_revision`, `checkpoint_sha256`, `policy_seq` e `receipt_sha256` entre A e B.
9. Confirmar que nenhuma testemunha retornou revisão inferior à maior revisão anteriormente aceita.
10. Confirmar ausência de equivocação (duas hashes para a mesma revisão → `CheckpointEquivocationError`).
11. Confirmar recebimento em até **30 segundos** medidos por relógio monotônico local (sem usar hora civil local como autoridade de validade).
12. Consumir o nonce uma única vez (reutilização rejeitada).

### 3.5. Regras de Falha e Recuperação
- **Quórum estrito `2-of-2`:** quórum `1-of-2` é proibido. Falha de A, de B, divergência ou replay bloqueiam `ancoragem_externa_independente` (`AnchorVerificationError` se obrigatória; ou degradação explícita para `integridade_local_com_ancora_co_localizada`).
- **Recuperação:** exige autorização assinada pela raiz fixada, justificativa, operador autorizado, estado anterior/novo, recibo do store, confirmação das duas testemunhas e evento append-only. Reset automático para zero é proibido.

---

## 4. Digest Composto do Parecer (`parecer_sha256`)

```text
parecer_sha256 = SHA256(JCS({
  "schema_version": parecer.schema_version,
  "parecer_core_jcs_sha256": parecer_core_jcs_sha256,
  "score_semantic_sha256": score_semantic_sha256,
  "score_provenance_sha256": score_provenance_sha256
}))
```
