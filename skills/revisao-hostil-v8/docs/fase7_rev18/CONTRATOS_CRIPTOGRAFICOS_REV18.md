# CONTRATOS CRIPTOGRÁFICOS E DE INTEGRIDADE — FASE 7 (`v8.0-beta.7`), REVISÃO 18

**Status:** Documentação normativa (runtime Fase 7 não iniciado)  
**Base imutável:** `v8.0-beta.6.6` (`11e91b6f3d517707326357868cc34ff97ab8327d`)

---

## 1. RFC 8785 JCS e Ed25519 (`ACH-B7-R17-001`, `ACH-B7-R17-002`)

- **JCS:** exclusivamente `rfc8785==0.1.4` com verificação cruzada independente por `jcs==0.3.0`; rejeição explícita de `NaN`, `Infinity`, `-Infinity`, chaves duplicadas e tipos Python fora do modelo JSON (`Decimal`, `Fraction`, `bytes`, `tuple`).
- **Ed25519:** exclusivamente `cryptography==50.0.2` (zero fallback artesanal); `load_ed25519_public_key()` valida 44 bytes SPKI DER, OID `1.3.101.112` e re-encoding canônico; `authority_key_id = lowercase_hex(SHA256(SPKI_DER))`; assinatura estritamente 64 bytes.

---

## 2. Pré-imagem Assinada de `signed_store_receipt` (`ACH-B7-R17-003`)

- **Campos incluídos:** todos os campos normativos de `signed_store_receipt` (`protocol`, `store_id`, `namespace`, `previous_revision`, `new_revision`, `previous_checkpoint_sha256`, `new_checkpoint_sha256`, `policy_seq`, `policy_jcs_sha256`, `receipt_timestamp_utc`, `store_key_id`, `signature_algorithm`).
- **Campos excluídos:** exclusivamente `signature_b64`.
- **Canonicalização e digest:** `ssr_jcs = jcs_canonical(payload)`, `receipt_sha256 = SHA256(ssr_jcs)`.
- **Verificação:** assinatura Ed25519 verificada sobre `ssr_jcs` com a chave `store_key_id` autorizada na política de confiança.

---

## 3. Matriz Normativa de Correspondência Global do Checkpoint (`ACH-B7-R17-003`)

| Campo | Origem | Destino | Regra |
| :--- | :--- | :--- | :--- |
| `store_id` | `signed_store_receipt` | `witness_assertions[]` | Igualdade exata |
| `namespace` | `signed_store_receipt` | `witness_assertions[]` | Igualdade exata |
| `policy_seq` | `signed_store_receipt` | `witness_assertions[]` | Igualdade exata |
| `new_revision` | `signed_store_receipt` | `witness_assertions[].checkpoint_revision` | Igualdade exata |
| `new_checkpoint_sha256` | `signed_store_receipt` | `witness_assertions[].checkpoint_sha256` | Igualdade exata |
| `receipt_sha256` | `SHA256(JCS(signed_store_receipt sem signature_b64))` | `witness_assertions[].receipt_sha256` | Igualdade exata |
| `witness_id` | `witness_assertions[]` | `nonce_consumption_receipts[]` | Bijeção 1:1 por identidade |
| `witness_key_id` | `witness_assertions[]` | `nonce_consumption_receipts[].bound_witness_key_id` | Igualdade exata + chave autorizada |
| `challenge_nonce_b64` | `witness_assertions[]` | `nonce_consumption_receipts[].nonce_sha256` | `SHA256(strict_b64decode(32B))` |
| `store_epoch` | `nonce_consumption_receipts[].expires_at_monotonic_context` | `nonce_consumption_receipts[].store_epoch` | Igualdade exata |
| `clock_context_id` | `expires_at_monotonic_context` | `validate_process_clock_context_id()` | UUIDv4 RFC 4122 minúsculo canônico |
| `protocol_scope` | Política / protocolo | `nonce_consumption_receipts[].protocol_scope` | Igualdade exata (`checkpoint_freshness_assertion_v1`) |
| `campaign_id` | Campanha | `nonce_consumption_receipts[].campaign_id` | Igualdade exata |
| `administrative_independence_dossier_sha256` | `checkpoint_receipt` | `dossier.dossier_jcs_sha256` | Igualdade exata + assinatura Ed25519 do dossiê |

---

## 4. Identidade Monotônica UUIDv4 (`ACH-B7-R17-004`)

- **Linux:** `linux_clock_monotonic_raw` (`CLOCK_MONOTONIC_RAW`), conversão inteira exata `tv_sec * 1_000_000_000 + tv_nsec`.
- **Windows:** `windows_query_performance_counter` (`QueryPerformanceCounter` / `QueryPerformanceFrequency`), conversão inteira exata `(ticks * 1_000_000_000) // freq`.
- **`clock_context_id`:** UUIDv4 RFC 4122 em minúsculas canônicas (`36` chars), gerado uma única vez por inicialização de processo; qualquer mudança de `clock_context_id`, `clock_source`, `store_epoch`, restart ou falha de frequência invalida imediatamente prazos pendentes.
