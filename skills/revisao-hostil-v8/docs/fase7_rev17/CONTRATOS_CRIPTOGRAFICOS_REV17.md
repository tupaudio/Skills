# CONTRATOS CRIPTOGRÁFICOS E DE INTEGRIDADE — FASE 7 (`v8.0-beta.7`), REVISÃO 17

**Status:** Documentação normativa (sem implementação Python de runtime)  
**Base imutável:** `v8.0-beta.6.6` (`11e91b6f3d517707326357868cc34ff97ab8327d`)  
**Achados endereçados:** `ACH-B7-R16-001` (P1), `ACH-B7-R16-002` (P1), `ACH-B7-R16-003` (P1), `ACH-B7-R16-004` (P1)

---

## 1. Formato Normativo Único de Chaves Públicas, SPKI DER e RFC 8785 JCS

1. **SPKI DER Ed25519 estrito (`ACH-B7-R16-003`):**
   - Toda chave pública Ed25519 em `public_key_spki_der_b64` deve decodificar (Base64 estrito) para exatamente **44 bytes** iniciando pelo cabeçalho ASN.1 DER RFC 8410 exato `302a300506032b6570032100` (SEQUENCE 42, AlgorithmIdentifier OID `1.3.101.112`, BIT STRING 33 com 0 bits não utilizados) seguido de **32 bytes** de chave pública.
   - `key_id = lowercase_hex(SHA256(SPKI_DER_BYTES))`.
   - Assinatura Ed25519: exatamente **64 bytes** decodificados.
2. **Canonicalização RFC 8785 JCS (`ACH-B7-R16-002`):**
   - Ordenação de chaves de objetos exclusivamente por **UTF-16 code units** (`UTF-16-BE`), não por code point Unicode/UTF-8.
   - Números estritos (rejeição de `NaN`/`Infinity`; `-0.0` → `0`).
   - Vetores de conformidade publicados em `test_vectors/rfc8785-conformance.json` e verificados por `tools/validate_rev17.py`.

---

## 2. Contexto Temporal Monotônico Multiplataforma (`ACH-B7-R16-001`)

```python
@dataclass(frozen=True)
class MonotonicDeadlineContext:
    clock_source: Literal["linux_clock_monotonic_raw", "windows_query_performance_counter"]
    unit: Literal["nanoseconds"]
    clock_context_id: str  # UUIDv4 gerado uma unica vez na inicializacao do processo
    store_epoch: str       # Epoca monotonica persistida do NonceConsumptionStore
    deadline_ns: int       # Prazo em nanossegundos inteiros na origem do processo
```

**Regras normativas de conversão e ciclo de vida:**
1. **Linux (`linux_clock_monotonic_raw`):** leitura de `CLOCK_MONOTONIC_RAW`, convertido exatamente por `tv_sec * 1_000_000_000 + tv_nsec` (aritmética inteira).
2. **Windows (`windows_query_performance_counter`):** leitura de `QueryPerformanceCounter` (`ticks`) e `QueryPerformanceFrequency` (`freq`), convertido exatamente por `(ticks * 1_000_000_000) // freq` (aritmética inteira; proibido `float`).
3. **Ciclo de vida de `clock_context_id`:** gerado como **UUIDv4 único na inicialização do processo** (muda obrigatoriamente a cada reinicialização de processo e a cada boot do sistema operacional). Nunca é persistido para reutilização em novo processo.
4. **Invalidação:** qualquer reinicialização de processo (novo `clock_context_id`), mudança ou regressão de `store_epoch`, `clock_source` incompatível com a plataforma em execução, ou `now_ns > deadline_ns` invalida imediatamente o contexto (`MonotonicContextInvalidError` / `NonceExpiredError`).

---

## 3. Máquina de Estados de `NonceConsumptionStore` e Validador Semântico do Recibo (`ACH-B7-R16-004`)

- Máquina de estados `NonceConsumptionStatus` (`CONSUMED`, `ALREADY_CONSUMED`, `PERSISTENCE_FAILURE`) com `persisted_tx_id: Optional[str]` (`None` fora de `CONSUMED`) mantida integralmente.
- **Invariantes semânticas obrigatórias de `schema_monotonic_checkpoint_receipt.json` (executadas em `tools/validate_rev17.py`):**
  1. `len(witness_assertions) == 2` e `len(nonce_consumption_receipts) == 2`;
  2. `witness_id`, `witness_key_id` e `nonce_sha256` mutuamente distintos entre os 2 registros;
  3. `set(receipt_witness_ids) == set(witness_ids)`;
  4. Para cada testemunha `w` e seu recibo `r = receipt_by_witness_id[w["witness_id"]]`:
     - `r["bound_witness_key_id"] == w["witness_key_id"]`;
     - `r["nonce_sha256"] == sha256(strict_base64_decode(w["challenge_nonce_b64"]))`;
     - `r["store_epoch"] == r["expires_at_monotonic_context"]["store_epoch"]`.
  5. Vetor de referência publicado em `test_vectors/checkpoint-receipt-tv-001.json`.
