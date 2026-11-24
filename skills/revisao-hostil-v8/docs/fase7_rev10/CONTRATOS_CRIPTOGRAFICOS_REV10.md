# Contratos Criptográficos e Temporais — Fase 7 (`v8.0-beta.7`, Revisão 10)

> **Base de referência congelada:** `v8.0-beta.6.6` (`commit 11e91b6f3d517707326357868cc34ff97ab8327d`)  
> **Aviso normativo:** especificação contratual documental (não representa implementação executada).

---

## 1. Projeção Não Circular da Política de Confiança (`trusted_anchors_policy_payload_v1`)

Campos **incluídos** na projeção canônica JCS (RFC 8785):
- `payload_schema`: `"trusted_anchors_policy_payload_v1"`
- `policy_version`: string SemVer 2.0.0
- `policy_seq`: string decimal canônica `\A(0|[1-9]\d*)\Z`
- `prev_policy_sha256`: SHA-256 hex-64 da política anterior (ou `null` exclusivamente na gênese `policy_seq == "0"`)
- `valid_from_utc`: ISO-8601 UTC
- `expires_at_utc`: ISO-8601 UTC (`expires_at_utc > valid_from_utc`)
- `allowed_remotes`: lista ordenada de repositórios remotos confiáveis
- `authorized_signers`: lista ordenada de signatários autorizados (`key_id`, `spki_der_sha256`, `scopes`, `not_before`, `not_after`)
- `trusted_tsa_roots`: lista ordenada de raízes TSA confiáveis (`root_der_sha256`, `allowed_tsa_policies`)

Campos **explicitamente excluídos** da projeção assinada (garantia formal anti-circularidade):
- `policy_jcs_sha256`
- `policy_signature`
- `timestamp_token_ref`

Fórmulas:
- `signed_bytes = UTF8(JCS(trusted_anchors_policy_payload_v1))`
- `policy_jcs_sha256 = signed_payload_sha256 = SHA256(signed_bytes)`

---

## 2. Contrato de `policy_signature` (`ACH-B7-R9-003`)

```json
{
  "algorithm": "Ed25519",
  "key_id": "<sha256_hex64_of_spki_der>",
  "signature_encoding": "base64_strict",
  "signature_b64": "<base64_of_64_raw_bytes>",
  "signed_payload_sha256": "<hex64>",
  "timestamp_token_ref": "<relative_ref_or_detached_rfc3161_token>"
}
```

### Algoritmos autorizados (lista fechada)
1. **`Ed25519` (normativo padrão):**
   - Chave pública: **SubjectPublicKeyInfo (SPKI) em ASN.1 DER**;
   - `key_id`: `SHA256(spki_der)` em hex minúsculo de 64 caracteres;
   - Assinatura: exatamente 64 bytes brutos codificados em Base64 estrito (`validate=True`, sem caracteres estranhos).
2. **`ECDSA-P256-SHA256` (opcional):**
   - Chave pública: SPKI DER explicitamente na curva NIST P-256 (`secp256r1`, OID `1.2.840.10045.3.1.7`);
   - Assinatura: exclusivamente **ASN.1 DER** (proibido IEEE P1363), codificada em Base64 estrito.

### Prova temporal vinculada (RFC 3161)
- O token RFC 3161 carimba obrigatoriamente **`SHA256(signature_bytes)`** (não apenas o payload).
- Passos obrigatórios do verificador:
  1. Decodificar `signature_b64` em Base64 estrito e validar tamanho/formato do algoritmo;
  2. Validar assinatura criptográfica sobre `signed_bytes` contra a chave-raiz fixada (`pinned_trust_root_spki_der_sha256`);
  3. Validar token RFC 3161: OID `messageImprint.hashAlgorithm == 2.16.840.1.101.3.4.2.1` (SHA-256), `hashedMessage == SHA256(signature_bytes)`, assinatura CMS `SignedData`, extensão crítica `id-kp-timeStamping` (`1.3.6.1.5.5.7.3.8`), `TSTInfo.policy ∈ allowed_tsa_policies`, cadeia X.509 até raiz confiável e revogação histórica (CRL/OCSP avaliada em `genTime`);
  4. Avaliar `valid_from_utc <= genTime <= expires_at_utc` e validade da chave-raiz exclusivamente usando `genTime` (nunca o relógio local).

---

## 3. Contrato de `MonotonicCheckpointStore` (`ACH-B7-R9-001`)

### Registro canônico do checkpoint
```json
{
  "last_accepted_policy_seq": "13",
  "last_accepted_policy_jcs_sha256": "<hex64>",
  "root_key_spki_der_sha256": "<hex64>",
  "checkpoint_revision": "14",
  "previous_checkpoint_sha256": "<hex64>",
  "updated_at_utc": "2026-11-24T00:00:00Z",
  "checkpoint_integrity_proof": {
    "store_type": "remote_append_only_cas",
    "proof_type": "signed_store_receipt",
    "proof_payload": "<opaque_verifiable_receipt>"
  }
}
```

### Operações e garantias
| Operação | Garantia obrigatória | Erro em falha |
| :--- | :--- | :--- |
| `read_checkpoint()` | Retorna estado atual, `checkpoint_revision`, hashes, sequência e prova de autenticidade do armazenamento | `CheckpointUnavailableError` / `CheckpointIntegrityError` |
| `compare_and_swap(expected_revision, new_state)` | Transação atômica e durável após confirmação; falha se revisão divergir | `CheckpointConflictError` (relê, revalida e reinicia) |
| `initialize_genesis(genesis_record)` | Executa somente se o store estiver vazio (`policy_seq == "0"`); proibido sobrescrever store existente | `CheckpointAlreadyInitializedError` |
| `verify_checkpoint_integrity()` | Valida encadeamento `previous_checkpoint_sha256` e `checkpoint_integrity_proof` | `CheckpointIntegrityError` |
| `recover_checkpoint(recovery_record)` | Exige autorização assinada fora de banda, registro de auditoria e nova âncora confiável | `UnauthorizedRecoveryError` |

### Classificação de garantia
- `ancoragem_externa_independente`: requer store transacional remoto append-only (ou contador monotônico em hardware verificado) acessível e íntegro + verificação completa da política e da prova temporal.
- `integridade_local_com_ancora_co_localizada`: obrigatório quando o checkpoint for apenas local/restaurável ou quando o store independente estiver inacessível (fail-closed).
