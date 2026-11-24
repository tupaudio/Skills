# ESPECIFICAÇÃO TÉCNICA — FASE 7 (`v8.0-beta.7`), REVISÃO 19

**Status:** Documentação normativa autossuficiente (**runtime Python da Fase 7 NÃO iniciado**; `OS_STATUS = BLOCKED` até aprovação externa)  
**Branch de origem:** `specification/v8.0-beta.7-rev18` (`8d10ef1f98fa3888e2fdf08b80c2e82a5963b6e0`)  
**Base imutável:** `v8.0-beta.6.6` (`11e91b6f3d517707326357868cc34ff97ab8327d`)  
**Escopo:** Correção integral dos achados `ACH-B7-R18-001` a `ACH-B7-R18-006`.

1. **`ACH-B7-R18-001` (P1):** `validate_trust_key()` valida `key_id == SHA256(SPKI_DER)` e ASN.1 DER SPKI Ed25519 para autoridade do dossiê, autoridade de revogação, store e testemunhas; `validate_dossier()` compara o digest calculado contra dossiê, `verification.json` e `trust_bundle["expected_dossier_sha256"]`.
2. **`ACH-B7-R18-002` (P1):** `validate_administrative_independence()` impõe distinção semântica dos 3 domínios (`legal_entity_id`, `administrative_domain`, `kms_hsm_id`, `key_custodian_id`, `operator_key_id`, `no_shared_admin_credentials=True`, evidência e procedimento); `schema_revocation_list.json` (20º contrato canônico) + `validate_revocation_list()` + `parse_utc()` validam assinatura, autoridade, janela temporal UTC e revogações.
3. **`ACH-B7-R18-003` (P2):** Manifesto estruturado `tools/test_manifest_rev19.json`, runner independente `tools/run_independent_tests.py`, suíte `tests/test_rev19_all.py` executada sob `pytest` normal e `python -O`, resultados validados por `tools/test_results_schema.json` e 194 IDs históricos preservados.
4. **`ACH-B7-R18-004` (P2):** `validate_monotonic_context_structure()` separado de `tools/platform_clock.py` (`read_linux_monotonic_raw_ns()`, `read_windows_qpc_ns()`, `read_platform_monotonic_ns()`, `RuntimeClockContext`).
5. **`ACH-B7-R18-005` (P2):** `validate_compatibility_policy(..., registry)` reconcilia `compatibility_policy_jcs_sha256` contra a política E o `SCHEMA_REGISTRY_FASE7_REV19.json`.
6. **`ACH-B7-R18-006` (P2):** `tools/requirements-validation.in`, `tools/requirements-validation.lock` gerado com `pip-compile --generate-hashes`, instalação comprovada com `--require-hashes` e `tools/verify_environment.py` → `tools/ENVIRONMENT_FINGERPRINT.json`.
