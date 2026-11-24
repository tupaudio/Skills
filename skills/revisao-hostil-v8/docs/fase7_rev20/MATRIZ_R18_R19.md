# MATRIZ DE RASTREABILIDADE — AUDITORIA REVISÃO 18 → REVISÃO 19

| Achado | Severidade | Ação de Encerramento | Artefatos | Teste Independente | Status |
| :--- | :---: | :--- | :--- | :--- | :---: |
| `ACH-B7-R18-001` | **P1** | `validate_trust_key()` + 3-way digest check do dossiê + verificação de chaves do store e testemunhas. | `tools/validate_rev19.py` | `T-R19-195` (`PASS`) | **FECHADO** |
| `ACH-B7-R18-002` | **P1** | `validate_administrative_independence()` + `schema_revocation_list.json` + `revocation-list-tv-001.json` + `validate_revocation_list()` + `parse_utc()`. | `tools/validate_rev19.py`, `schemas/7.0.0/schema_revocation_list.json`, `test_vectors/trust/revocation-list-tv-001.json` | `T-R19-196` (`PASS`) | **FECHADO** |
| `ACH-B7-R18-003` | **P2** | `tools/test_manifest_rev19.json`, `tools/test_results_schema.json`, `tools/run_independent_tests.py`, `tests/test_rev19_all.py`, 194 IDs históricos preservados. | `tools/run_independent_tests.py`, `reports/test_results_rev19.json` | `T-R19-195`..`199` | **FECHADO** |
| `ACH-B7-R18-004` | **P2** | `validate_monotonic_context_structure()` separado de `tools/platform_clock.py` (Windows QPC real + Linux `CLOCK_MONOTONIC_RAW`). | `tools/platform_clock.py`, `tests/test_rev19_all.py` | `T-R19-197` (`PASS`), `T-R19-198` (`BLOCKED_ENVIRONMENT`) | **FECHADO NO WINDOWS / BLOQUEADO EM LINUX** |
| `ACH-B7-R18-005` | **P2** | `validate_compatibility_policy(..., registry)` reconcilia digest contra política e Registry. | `tools/validate_rev19.py` | `T-R19-199` (`PASS`) | **FECHADO** |
| `ACH-B7-R18-006` | **P2** | `requirements-validation.in` + `requirements-validation.lock` (`pip-compile --generate-hashes`) + instalação `--require-hashes` comprovada + `verify_environment.py` → `ENVIRONMENT_FINGERPRINT.json`. | `tools/requirements-validation.lock`, `tools/ENVIRONMENT_FINGERPRINT.json` | Instalação limpa `venv_rev19` (`exit 0`) | **FECHADO** |
