# MATRIZ DE RASTREABILIDADE — REVISÃO 19 → REVISÃO 20

| Achado | Ação de Encerramento | Artefato | Teste Independente | Status |
| :--- | :--- | :--- | :--- | :---: |
| `ACH-B7-R19-001` | `get_trusted_utc_now()` + `resolve_execution_now_utc()` proibindo relógio fixo em modo operacional. | `tools/validate_rev20.py` | `T-R20-201` (`PASS`) | **FECHADO** |
| `ACH-B7-R19-002` | `validate_dossier_trust_binding()` vinculando operadores às chaves do trust bundle + 3 provedores distintos. | `tools/validate_rev20.py` | `T-R20-202` (`PASS`) | **FECHADO** |
| `ACH-B7-R19-003` | `historical_test_manifest_rev20.json`, `historical_results_rev20.json`, `test_historical_preservation.py`, `artifact_sha256` e matriz gerada de JSON real. | `tools/build_rev20_matrix_and_manifests.py`, `tests/test_historical_preservation.py` | `T-R20-200` (`PASS`) | **FECHADO** |
| `ACH-B7-R19-004` | `run_independent_tests.py` com `--junitxml`, classificação explícita `passed`/`failed`/`skipped`/`error`, bloqueio de `skipped` indevido. | `tools/run_independent_tests.py`, `reports/pytest-results.xml` | `T-R20-200`..`205` | **FECHADO** |
| `ACH-B7-R19-005` | `RuntimeClockContext.boot_id` + validação de UUID, PID, `boot_id`, `store_epoch` e kernel Linux ≥ 5.6. | `tools/platform_clock.py` | `T-R20-203` (`PASS`), `T-R20-204` (`BLOCKED_ENVIRONMENT`) | **FECHADO NO WINDOWS / BLOQUEADO EM LINUX** |
| `ACH-B7-R19-006` | `validate_revocation_list()` validando `revoked_at <= now_utc`, unicidade (`seen`) e `reason` não vazia. | `tools/validate_rev20.py` | `T-R20-205` (`PASS`) | **FECHADO** |
