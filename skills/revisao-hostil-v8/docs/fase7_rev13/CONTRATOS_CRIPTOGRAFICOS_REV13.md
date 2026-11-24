# CONTRATOS CRIPTOGRÁFICOS E DE INTEGRIDADE — FASE 7 (`v8.0-beta.7`), REVISÃO 13

**Status:** Documentação normativa (sem implementação Python)  
**Base imutável:** `v8.0-beta.6.6` (`11e91b6f3d517707326357868cc34ff97ab8327d`)  
**Achados endereçados:** `ACH-B7-R12-001` (P1), `ACH-B7-R12-002` (P1) (preservando integralmente `ACH-B7-R11-002` e `ACH-B7-R11-010`)

---

## 1. Formato Normativo Único de Chaves Públicas e Assinaturas

- Todas as chaves públicas (raiz confiável, signatários delegados, Store, Testemunha A e Testemunha B) são representadas exclusivamente por `public_key_spki_der_b64` (Base64 RFC 4648 estrito dos bytes SPKI DER).
- `key_id = lowercase_hex(SHA256(SPKI_DER_BYTES))`.
- `Ed25519`: assinatura de exatamente 64 bytes em Base64 estrito; `ECDSA-P256-SHA256` (quando habilitado): ASN.1 DER estrito. Validação conjunta algoritmo + tipo de chave SPKI DER.

---

## 2. Identificadores Monotônicos e Autoridade de Política

- `policy_seq` e `checkpoint_revision`: dígitos ASCII puros `\A(0|[1-9][0-9]{0,31})\Z` (máx. 32 dígitos; proibido `\d`).
- Política candidata `P_k` só pode ser assinada pela raiz fixada ou por chave delegada ativa em `P_{k-1}.authorized_signers` com escopo `policy_sign` e janela válida no `genTime` do TSA. Autoautorização via `P_k.authorized_signers` é estritamente proibida.

---

## 3. Protocolo Definitivo do `MonotonicCheckpointStore` — Quórum `2-of-2`

### 3.1. Três Domínios Administrativos Independentes
1. **Store de Checkpoint** (append-only com CAS atômico) — `store_key_id`.
2. **Testemunha Externa A** — `witness_a_key_id`.
3. **Testemunha Externa B** — `witness_b_key_id`.

As três chaves Ed25519 são mutuamente distintas e fixadas na política confiável.

#### 3.1.1. Prova de Independência Administrativa (`ACH-B7-R12-001` — Obrigatória)
A simples diferença entre `key_id` **NÃO** satisfaz o requisito de independência administrativa. Para que uma campanha possa receber a classificação `ancoragem_externa_independente`, a política confiável e o recibo de checkpoint (`administrative_independence_dossier_sha256`) devem vincular um **Dossiê Verificável de Independência Administrativa** contendo, obrigatoriamente, para cada um dos três operadores (Store, Testemunha A, Testemunha B):

1. **Identificador jurídico ou organizacional independente:** razão social / entidade legal distinta para cada um dos três operadores (proibido mesmo controlador ou mesma conta organizacional).
2. **Provedor de infraestrutura e domínio administrativo:** identificação explícita do provedor de nuvem/datacenter, conta/tenant/assinatura e domínio administrativo distintos entre Store, Testemunha A e Testemunha B.
3. **Declaração formal de ausência de credenciais administrativas compartilhadas:** nenhuma conta IAM, SSO, root, token de API ou bastion compartilhado entre quaisquer dois dos três domínios.
4. **Separação de KMS/HSM e custódia de chaves:** cada chave privada reside em KMS/HSM próprio e distinto, sob responsabilidade de custodiantes independentes.
5. **Procedimentos independentes de recuperação e rotação:** runbooks e aprovações de rotação/recuperação isolados por operador.
6. **Evidência documental verificável:** o dossiê assinado pelos responsáveis (com SHA-256 fixado em `administrative_independence_dossier_sha256`) deve ser verificado antes de conceder a classificação.
7. **Regra de rejeição fail-closed:** quando a independência administrativa não puder ser comprovada (dossiê ausente, hash divergente, provedor/conta/operador compartilhado ou KMS comum), a classificação `ancoragem_externa_independente` é **rejeitada obrigatoriamente** (`AdministrativeIndependenceError` se ancoragem independente for exigida, ou degradação explícita para `integridade_local_com_ancora_co_localizada`).

### 3.2. Contrato `signed_store_receipt_v1` e `checkpoint_freshness_assertion_v1`
Mantidos integralmente conforme `schemas/7.0.0/schema_monotonic_checkpoint_receipt.json` (`additionalProperties: false`, `new_revision == previous_revision + 1`, mesma revisão com hash diferente → `CheckpointEquivocationError`).

### 3.4. Protocolo de Desafio-Resposta (12 Passos) e Consumo Persistente de Nonces
Passos 1 a 11 mantidos integralmente (nonce CSPRNG de 32 bytes, consulta a A e B, validação Ed25519, concordância total, monotonia, prazo de 30 segundos por relógio monotônico local).

#### 3.4.1. Persistência Transacional e Anti-Replay de Nonces — `NonceConsumptionStore` (`ACH-B7-R12-002`)
Uma coleção em memória é **proibida** (pois permite replay após reinicialização do processo ou da máquina). O passo 12 é regido obrigatoriamente pela interface persistente abaixo:

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

**Contrato normativo obrigatório:**
1. **Persistência transacional:** cada consumo é gravado em armazenamento durável com confirmação transacional (`fsync` / commit ACID) antes de retornar `True`.
2. **Operação atômica de inserção condicional:** inserção atômica com restrição de unicidade (`UNIQUE (protocol_scope, nonce_sha256)`); nenhuma leitura-seguida-de-escrita (TOCTOU) é permitida.
3. **Unicidade de escopo:** a chave única vincula `(protocol_scope, nonce_sha256)`, impedindo colisão ou reutilização entre protocolos.
4. **Rejeição de qualquer consumo anterior:** se `(protocol_scope, nonce_sha256)` já existir, `consume_once()` retorna `False` e a validação aborta com `NonceReplayError`.
5. **Registro append-only do consumo:** entradas consumidas nunca são sobrescritas nem apagadas enquanto vigentes; cada consumo gera um `persisted_tx_id` registrado em `nonce_consumption_receipts`.
6. **Proteção contra restauração de backup:** o store de nonces vincula um identificador monotônico de geração/época (`store_epoch`) e checkpoint de integridade para detectar restauração de estado antigo; em caso de regressão detectada, falha fechado (`NonceStoreRollbackError`).
7. **Concorrência estrita:** diante de duas threads, processos ou campanhas concorrentes submetendo o mesmo nonce simultaneamente, **exatamente uma** operação obtém `True` e todas as demais recebem `False`.
8. **Falha de persistência bloqueia a validação:** qualquer erro de I/O, lock timeout ou falha de commit levanta `NoncePersistenceError` e bloqueia a validação (fail-closed).
9. **Política de retenção e expiração:**
   - Todo nonce consumido é retido por no mínimo `retention_window = max_campaign_ttl + witness_clock_skew_margin` (nunca inferior a 24 horas após o encerramento da campanha).
   - Nonces de campanhas ativas ou não expiradas nunca são purgados.
   - `expires_at_monotonic_context` vincula `(boot_epoch_id, monotonic_deadline_ns, campaign_id)` para que reinicializações do processo ou da máquina nunca estendam a validade de um nonce pendente nem permitam reuso de um nonce já consumido.

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
