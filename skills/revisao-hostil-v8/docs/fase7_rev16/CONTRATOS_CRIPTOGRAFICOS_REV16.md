# CONTRATOS CRIPTOGRÁFICOS E DE INTEGRIDADE — FASE 7 (`v8.0-beta.7`), REVISÃO 16

**Status:** Documentação normativa (sem implementação Python de runtime)  
**Base imutável:** `v8.0-beta.6.6` (`11e91b6f3d517707326357868cc34ff97ab8327d`)  
**Achados endereçados:** `ACH-B7-R15-001` (P1), `ACH-B7-R15-002` (P2), `ACH-B7-R15-003` (P2)

---

## 1. Formato Normativo Único de Chaves Públicas e Identificadores

- Todas as chaves públicas usam exclusivamente `public_key_spki_der_b64` (Base64 RFC 4648 estrito de SPKI DER) e `key_id = lowercase_hex(SHA256(SPKI_DER_BYTES))`.
- `policy_seq` e `checkpoint_revision`: dígitos ASCII puros `\A(0|[1-9][0-9]{0,31})\Z`.

---

## 2. Dossiê de Independência Administrativa e Vetor Reproduzível (`ACH-B7-R15-003`)

- Regido por `schemas/7.0.0/schema_administrative_independence_dossier.json` (`allOf` com 3× `contains`/`const`/`minContains: 1`/`maxContains: 1` para `checkpoint_store`, `witness_a`, `witness_b` + validação semântica independente).
- Pré-imagem única:
  ```text
  dossier_payload = JCS(dossier sem authority_signature e dossier_jcs_sha256)
  dossier_jcs_sha256 = SHA256(UTF8(dossier_payload))
  ```
- **Vetor de teste completo e reproduzível publicado na branch:**
  - Objeto completo: `test_vectors/dossier-tv-001.json`
  - Pré-imagem JCS exata (`1788` bytes UTF-8): `test_vectors/dossier-tv-001.jcs.txt`
  - Metadados de verificação (SHA-256, SPKI DER, `authority_key_id`, assinatura Ed25519): `test_vectors/dossier-tv-001.verification.json`
  - `dossier_jcs_sha256 = e322b6ae5d9b60084f115ee078c5eac6c48a0d3871e7739980556b2841a9ca8f`
  - `authority_key_id = d2e6845244863abf2042aeadcb920305981642ec81db48f7c31502c40d2f4e52`

---

## 3. Máquina de Estados de `NonceConsumptionStore` e Contexto Monotônico Tipado (`ACH-B7-R15-001`, `ACH-B7-R15-002`)

### 3.1. Contexto Temporal Monotônico Tipado (`ACH-B7-R15-002`)
```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional

@dataclass(frozen=True)
class MonotonicDeadlineContext:
    clock_source: str      # Literal["os_monotonic_raw"] (Linux CLOCK_MONOTONIC_RAW / Windows QPC)
    unit: str              # Literal["nanoseconds"]
    clock_context_id: str  # UUID único gerado na inicialização do processo/boot
    store_epoch: str       # Época monotônica persistida do NonceConsumptionStore
    deadline_ns: int       # Prazo em nanossegundos na origem de clock_context_id (nunca UTC)
```
**Regras de validade e invalidação:**
1. O prazo de 30 segundos (`30_000_000_000 ns`) é medido exclusivamente em `os_monotonic_raw` (`nanoseconds`) a partir da origem local identificada por `clock_context_id`.
2. **Proibição:** valores de `deadline_ns` **nunca** são tratados como timestamp UTC nem comparados entre dois `clock_context_id` distintos.
3. **Invalidação obrigatória:** qualquer reinicialização (novo `clock_context_id`), mudança ou regressão de `store_epoch`, `clock_source != "os_monotonic_raw"`, ou `current_monotonic_ns > deadline_ns` invalida imediatamente o contexto (`MonotonicContextInvalidError` / `NonceExpiredError`).

### 3.2. Máquina de Estados e Interface de `NonceConsumptionStore` (`ACH-B7-R15-001`)
```python
class NonceConsumptionStatus(str, Enum):
    CONSUMED = "CONSUMED"
    ALREADY_CONSUMED = "ALREADY_CONSUMED"
    PERSISTENCE_FAILURE = "PERSISTENCE_FAILURE"

@dataclass(frozen=True)
class NonceConsumptionResult:
    status: NonceConsumptionStatus
    persisted_tx_id: Optional[str]  # Preenchido APENAS quando status == CONSUMED; None nos demais estados
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
        expires_at_monotonic_context: MonotonicDeadlineContext,
    ) -> NonceConsumptionResult: ...
```

**Semântica normativa por estado e cenário:**
1. **`CONSUMED`:** primeira inserção atômica bem-sucedida sob `UNIQUE (protocol_scope, nonce_sha256)` com `COMMIT` + `fsync` confirmados. `persisted_tx_id` é uma string não vazia identificando a transação confirmada.
2. **`ALREADY_CONSUMED`:** a chave `(protocol_scope, nonce_sha256)` já existe no armazenamento. `persisted_tx_id` é obrigatoriamente `None` (nunca reutiliza nem fabrica ID). O registro original permanece imutável. O verificador **aborta com `NonceReplayError`** sem avançar o checkpoint.
3. **`PERSISTENCE_FAILURE`:** erro de I/O, falha de commit, lock timeout ou regressão de `store_epoch`. `persisted_tx_id` é `None`. O verificador **aborta com `NoncePersistenceError` / `NonceStoreRollbackError`** sem avançar o checkpoint.
4. **Concorrência simultânea:** diante de $k \ge 2$ chamadas concorrentes com o mesmo `(protocol_scope, nonce_sha256)`, a restrição `UNIQUE` ACID garante **exatamente 1** retorno `CONSUMED` e $k - 1$ retornos `ALREADY_CONSUMED`.
5. **Repetição após timeout do cliente ou commit-sem-resposta:** não existe reuso idempotente silencioso de nonce já consumido. Se a transação foi confirmada antes da queda de comunicação, a repetição recebe `ALREADY_CONSUMED` (`NonceReplayError`); o cliente deve gerar um **novo nonce de 32 bytes** e re-executar o desafio-resposta com ambas as testemunhas.
6. **Reutilização em outra campanha:** rejeitada com `ALREADY_CONSUMED` (`NonceReplayError`), pois a unicidade é global ao `protocol_scope`.
7. **Reconciliação com o recibo:** somente `status == CONSUMED` (com `persisted_tx_id` não nulo) pode popular `nonce_consumption_receipts[]` em `schema_monotonic_checkpoint_receipt.json`, reconciliado campo a campo.
