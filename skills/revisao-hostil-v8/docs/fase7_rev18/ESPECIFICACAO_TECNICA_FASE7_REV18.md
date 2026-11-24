# ESPECIFICAÇÃO TÉCNICA — FASE 7 (`v8.0-beta.7`), REVISÃO 18

**Status:** Documentação normativa autossuficiente (**runtime Python da Fase 7 PROIBIDO/NÃO iniciado**; `OS_STATUS = BLOCKED` até aprovação formal externa)  
**Branch de origem:** `specification/v8.0-beta.7-rev17` (`20068023920cee12e44cf6b1e8f5d77c48516f00`)  
**Base imutável:** `v8.0-beta.6.6` (`11e91b6f3d517707326357868cc34ff97ab8327d`)  
**Branch documental:** `specification/v8.0-beta.7-rev18`  
**Escopo:** Correção integral dos achados `ACH-B7-R17-001` a `ACH-B7-R17-005` e autoverificação do validador documental `tools/validate_rev18.py`.

---

## 1. Correções Normativas da Revisão 18

1. **`ACH-B7-R17-001` (P1 — RFC 8785 JCS):** removida integralmente a implementação artesanal (`repr(float)`, `str(int(float))`). `jcs_canonical()` utiliza exclusivamente bibliotecas consolidadas fixadas em `tools/requirements-validation.txt` (`rfc8785==0.1.4` e `jcs==0.3.0`) com verificação cruzada obrigatória entre as duas implementações, rejeição de tipos fora do modelo JSON e valores não finitos, e 18 vetores individuais em `test_vectors/rfc8785/`.
2. **`ACH-B7-R17-002` (P1 — Ed25519 sem fallback artesanal):** removidas integralmente todas as funções artesanais de curva elíptica. `load_ed25519_public_key()` e `verify_ed25519_signature()` utilizam exclusivamente `cryptography==50.0.2`, validando estrutura ASN.1 DER SPKI completa (44B, OID `1.3.101.112`, re-encoding canônico), `authority_key_id = SHA256(SPKI_DER)`, autorização na política e vetor oficial RFC 8032 Section 7.1 TEST 1.
3. **`ACH-B7-R17-003` (P1 — Reconciliação semântica global do checkpoint):** implementada `validate_checkpoint_receipt_global()` validando todas as 14 relações cruzadas entre `signed_store_receipt` (incluindo sua assinatura Ed25519), `witness_assertions` (com assinaturas Ed25519), `nonce_consumption_receipts`, dossiê, política e contexto monotônico, com 1 teste positivo e 18 mutações negativas independentes.
4. **`ACH-B7-R17-004` (P1 — Identidade monotônica UUIDv4):** `schema_monotonic_checkpoint_receipt.json` atualizado para `clock_context_id: {"type": "string", "format": "uuid"}`; implementada `validate_process_clock_context_id()` exigindo UUIDv4 RFC 4122 em minúsculas canônicas; vetores atualizados com UUIDv4 reais (`f47ac10b-58cc-4372-a567-0e02b2c3d479`, `9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d`) e 8 mutações negativas.
5. **`ACH-B7-R17-005` (P2 — Cobertura RFC 8785 e validador autoverificável):** publicado `reports/COBERTURA_RFC8785_REV18.md`, `tools/validate_rev18.py` com **zero `assert`** (aprovado em `python` e `python -O`), e preservação integral dos 164 IDs históricos + 30 novos (`194` cenários).
