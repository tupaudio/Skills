# CONTRATOS CRIPTOGRÁFICOS E DE INTEGRIDADE — FASE 7 (`v8.0-beta.7`), REVISÃO 19

- **Vinculação de chaves de confiança (`ACH-B7-R18-001`):** toda chave em `checkpoint-trust-bundle-tv-001.json` (autoridade do dossiê, autoridade de revogação, store, Testemunha A, Testemunha B) passa por `validate_trust_key()` comprovando `key_id == lowercase_hex(SHA256(SPKI_DER))` e SPKI DER Ed25519 canônico via `cryptography==50.0.2`.
- **Dossiê e Lista de Revogação (`ACH-B7-R18-002`):** `schema_revocation_list.json` (20º contrato canônico) assinado por autoridade de revogação fixada no trust bundle; `parse_utc()` exige timezone explícito; `valid_from_utc <= issued_at_utc <= valid_until_utc` e `issued <= now_utc <= expires`; qualquer chave revogada (autoridade, store, testemunha A ou B) é rejeitada.
- **RFC 8785 JCS:** `rfc8785==0.1.4` + `jcs==0.3.0` (100% concordantes).
- **Digest da política (`ACH-B7-R18-005`):** `5721b8e982e85f843283d571bbcb0d1e66dcac8b1f6ab43df566929cd498c028` reconciliado simultaneamente na política e no `SCHEMA_REGISTRY_FASE7_REV19.json`.
