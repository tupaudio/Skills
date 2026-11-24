# ESPECIFICAÇÃO TÉCNICA — FASE 7 (`v8.0-beta.7`), REVISÃO 16

**Status:** Documentação normativa autossuficiente (**implementação Python da Fase 7 NÃO iniciada**; Ordem de Serviço **BLOQUEADA até aprovação externa**)  
**Base obrigatória imutável:** tag `v8.0-beta.6.6`, commit `11e91b6f3d517707326357868cc34ff97ab8327d`  
**Branch documental:** `specification/v8.0-beta.7-rev16`  
**Escopo:** Correção integral dos 4 achados da auditoria externa da Revisão 15 (`ACH-B7-R15-001` a `ACH-B7-R15-004`), preservando integralmente todas as garantias consolidadas até a Revisão 15.

---

## 0. Declaração de Escopo e Preservação da Base

1. Este pacote documental é estritamente normativo. **Nenhum código Python de runtime da Fase 7 foi criado ou executado** (`0/154 executados`).
2. O diretório `tools/` contém exclusivamente o validador documental determinístico `validate_rev16.py` (exigido por `ACH-B7-R15-004`) para reprodução independente da integridade dos artefatos publicados; ele **não** é implementação operacional da Fase 7.
3. `main`, a tag `v8.0-beta.6.6` (`11e91b6f3d517707326357868cc34ff97ab8327d`), `requirements.txt`, `catalogo_agentes.yaml`, `SKILL.md`, os 8 schemas em `references/schemas/` e as branches históricas (`rev10`–`rev15`) permanecem integralmente inalterados.

---

## 1. Inventário de Contratos e Migração da Beta 6.6

- **8 schemas históricos** da Beta 6.6 preservados byte a byte em `schemas/legacy-v8.0-beta.6.6/` (versões históricas não comprovadas permanecem `NAO_VERIFICADO` e bloqueadas).
- **19 contratos canônicos em `schemas/7.0.0/`**, todos com `$id` único `https://revisao-hostil.v8/schemas/7.0.0/<nome>`, `$ref` exclusivamente local e versionado, e `additionalProperties: false`.

---

## 2. Protocolo `MonotonicCheckpointStore`, Máquina de Estados de Nonce, Contexto Monotônico Tipado e Vetor Reproduzível (`ACH-B7-R15-001`, `ACH-B7-R15-002`, `ACH-B7-R15-003`)

Especificação criptográfica completa em `CONTRATOS_CRIPTOGRAFICOS_REV16.md`:

1. **Máquina de estados do `NonceConsumptionStore` (`ACH-B7-R15-001`):**
   - Estados exclusivos `NonceConsumptionStatus`: `CONSUMED`, `ALREADY_CONSUMED`, `PERSISTENCE_FAILURE`.
   - `CONSUMED`: primeiro commit ACID confirmado; `persisted_tx_id` não vazio; único vencedor sob concorrência simultânea.
   - `ALREADY_CONSUMED`: chave `(protocol_scope, nonce_sha256)` já existe; `persisted_tx_id = None`; registro anterior imutável; aborta com `NonceReplayError` mesmo em repetição após timeout ou commit-sem-resposta (cliente deve gerar novo nonce de 32 bytes e re-desafiar ambas as testemunhas).
   - `PERSISTENCE_FAILURE`: erro de I/O, lock timeout ou regressão de `store_epoch`; `persisted_tx_id = None`; bloqueia aceitação do checkpoint (`NoncePersistenceError` / `NonceStoreRollbackError`).
2. **Contexto temporal monotônico tipado `MonotonicDeadlineContext` (`ACH-B7-R15-002`):**
   - Objeto fechado `{clock_source: "os_monotonic_raw", unit: "nanoseconds", clock_context_id, store_epoch, deadline_ns}` em `CONTRATOS_CRIPTOGRAFICOS_REV16.md` e `schema_monotonic_checkpoint_receipt.json`.
   - Reinicialização (novo `clock_context_id`), mudança de `store_epoch`, relógio incompatível ou `now_ns > deadline_ns` invalidam imediatamente qualquer prazo pendente; valores monotônicos nunca são comparados entre contextos distintos nem tratados como UTC.
3. **Vetor criptográfico integralmente reproduzível (`ACH-B7-R15-003`):**
   - Publicado em `test_vectors/dossier-tv-001.json`, `test_vectors/dossier-tv-001.jcs.txt` (`1788` bytes) e `test_vectors/dossier-tv-001.verification.json` (`dossier_jcs_sha256 = e322b6ae5d9b60084f115ee078c5eac6c48a0d3871e7739980556b2841a9ca8f`, chave Ed25519 SPKI DER de teste e assinatura verificável).

---

## 3. Confinamento de Arquivos, Domínio Racional, Política de Compatibilidade e Reprodutibilidade Documental (`ACH-B7-R15-004`)

- **Confinamento:** preservado integralmente (Windows NTFS `NtCreateFile` + `FILE_ID_INFO` + `NumberOfLinks == 1` + bloqueio UNC/ADS/reparse; Linux ≥ 5.6 `openat2` + `RESOLVE_NO_XDEV` + `st_nlink == 1`; macOS/outros → `UnsafePlatformPathError`; buffer único imutável).
- **Domínio racional:** preservado integralmente ($m \le 15$, $n_i \le 15$, notas $[0, 10]$, pesos $(0, 1000]$ em `Fraction`, $D_{\text{bound}} = 5.4054 \times 10^{21}$ [73 bits], $N_{\text{bound}} = 5.4054 \times 10^{22}$ [76 bits], teto operacional 128 bits).
- **Política de compatibilidade:** `compatibility_policy.schema.json` (`minItems: 19`, `maxItems: 19`, `uniqueItems: true`) + validador semântico obrigatório + SemVer estável estrito.
- **Reprodutibilidade documental (`ACH-B7-R15-004`):** `tools/validate_rev16.py` e `tools/README_VALIDACAO.md` publicados na própria branch, conferindo os 30 arquivos JSON, Draft 2020-12, 19 contratos, 19 `$ref` transitivos, vetor Ed25519 `dossier-tv-001` e 154 cenários, encerrando com código `!= 0` em qualquer divergência.
