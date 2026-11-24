# ESPECIFICAÇÃO TÉCNICA — FASE 7 (`v8.0-beta.7`), REVISÃO 17

**Status:** Documentação normativa autossuficiente (**implementação Python de runtime da Fase 7 NÃO iniciada**; Ordem de Serviço **BLOQUEADA até aprovação externa**)  
**Base obrigatória imutável:** tag `v8.0-beta.6.6`, commit `11e91b6f3d517707326357868cc34ff97ab8327d`  
**Branch documental:** `specification/v8.0-beta.7-rev17`  
**Escopo:** Correção integral dos 5 achados da auditoria externa da Revisão 16 (`ACH-B7-R16-001` a `ACH-B7-R16-005`), preservando integralmente todas as garantias consolidadas até a Revisão 16.

---

## 0. Declaração de Escopo e Preservação da Base

1. Este pacote documental é estritamente normativo (`0/164` cenários de runtime executados).
2. `tools/validate_rev17.py` é uma ferramenta exclusivamente de auditoria documental (não é runtime da Fase 7), agora implementando **integralmente** todas as verificações anunciadas (`ACH-B7-R16-002`..`005`).
3. `main`, a tag `v8.0-beta.6.6` (`11e91b6f3d517707326357868cc34ff97ab8327d`), `requirements.txt`, `catalogo_agentes.yaml`, `SKILL.md`, os 8 schemas em `references/schemas/` e as branches históricas (`rev10`–`rev16`) permanecem integralmente inalterados.

---

## 1. Correções Normativas da Revisão 17

1. **Identificadores de relógio multiplataforma e ciclo de vida de `clock_context_id` (`ACH-B7-R16-001`):**
   - `clock_source` aceita exclusivamente `linux_clock_monotonic_raw` ou `windows_query_performance_counter` (eliminado `"os_monotonic_raw"`).
   - Conversão exata para `nanoseconds` sem `float`: Linux `tv_sec * 1_000_000_000 + tv_nsec`; Windows `(ticks * 1_000_000_000) // frequency`.
   - `clock_context_id`: **UUIDv4 gerado uma única vez na inicialização do processo** (muda obrigatoriamente a cada reinicialização de processo e a cada boot), vinculado ao `store_epoch`.
2. **Conformidade RFC 8785 JCS (`ACH-B7-R16-002`):**
   - `jcs_canonical()` implementa ordenação por **UTF-16 code units** (`key.encode("utf-16-be")`) e regras numéricas RFC 8785 (rejeitando `NaN`/`Infinity`, normalizando `-0.0` → `0`), validada contra `test_vectors/rfc8785-conformance.json` (incluindo ordenação de par substituto `U+1F600` vs BMP `U+FB33`, onde `json.dumps(sort_keys=True)` falha!).
3. **Verificação integral dos metadados do vetor e DER SPKI (`ACH-B7-R16-003`):**
   - `validate_rev17.py` compara **todos** os campos de `dossier-tv-001.verification.json` contra `dossier-tv-001.json` e `dossier-tv-001.jcs.txt`, e valida integralmente a estrutura ASN.1 DER SPKI Ed25519 (44 bytes, cabeçalho exato `302a300506032b6570032100` com OID `1.3.101.112` e 32 bytes de chave pública) + assinatura de 64 bytes.
4. **Validador semântico de `schema_monotonic_checkpoint_receipt.json` (`ACH-B7-R16-004`):**
   - Implementado em `validate_rev17.py` com verificação positiva sobre `test_vectors/checkpoint-receipt-tv-001.json` e verificações negativas automatizadas para cada invariante (testemunha duplicada, chave divergente, nonce divergente, `store_epoch` divergente).
5. **Validação integral dos 19 schemas Draft 2020-12 e do Registry (`ACH-B7-R16-005`):**
   - `validate_rev17.py` executa `Draft202012Validator.check_schema()` em **todos os 19 schemas** de `schemas/7.0.0/`, valida unicidade de `$id`, recalcula os 19 hashes físicos e toda a árvore `$ref` (rejeitando referências externas, caminhos não permitidos e ciclos), e compara integralmente `direct_refs`, `transitive_refs` e `physical_sha256` contra `SCHEMA_REGISTRY_FASE7_REV17.json` e `compatibility_policy_v1.json`.

---

## 2. Garantias Preservadas

Mantidas integralmente: 8 schemas legados preservados byte a byte, 19 contratos canônicos `7.0.0`, quórum `2-of-2` com dossiê assinado, máquina de estados `NonceConsumptionStatus` (`CONSUMED`, `ALREADY_CONSUMED`, `PERSISTENCE_FAILURE`), confinamento estrito Windows NTFS / Linux ≥ 5.6, domínio de pesos `(0, 1000]` com `D_bound = 5.4054 × 10²¹` (73 bits) e `N_bound = 5.4054 × 10²²` (76 bits), e SemVer estável estrito.
