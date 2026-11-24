# RELATÓRIO DE CONVERGÊNCIA — REVISÃO 20 (`specification/v8.0-beta.7-rev20`)

- **Branch de origem:** `specification/v8.0-beta.7-rev19` (`d68ba00f460f93872b0555c74c8dc7461ee96436`)
- **Base imutável:** `v8.0-beta.6.6` (`11e91b6f3d517707326357868cc34ff97ab8327d`)
- **Ambiente real:** Windows 11 (`10.0.26300`), Python `3.14.6`, `venv_rev19` instalado exclusivamente via `--require-hashes -r tools/requirements-validation.lock` (`lock_sha256 = d7270cbb1feeb640ef75321b856adcad048477e6bfa4456e680f3bd8ce693585`)
- **Relógio operacional:** `system_utc_realtime` (`datetime.now(timezone.utc)`) — zero constante fixa
- **Execuções reais:**
  - `python tools/validate_rev20.py` → Exit code `0`
  - `python -O tools/validate_rev20.py` → Exit code `0`
  - `python -m pytest -q --junitxml=reports/pytest-results.xml tests/` → `5 passed, 1 skipped` (exit code `0`)
  - `python -O -m pytest -q tests/` → `5 passed, 1 skipped` (exit code `0`)
  - `python tools/run_independent_tests.py` → Exit code `0` (`5 PASS`, `1 BLOCKED_ENVIRONMENT` para `T-R20-204` Linux)
- **Status final:** `BLOCKED_ENVIRONMENT` (exclusivamente pela ausência de kernel Linux ≥ 5.6 neste host Windows 11 para executar `T-R20-204`; `0` P1/P2 documentais abertos; `OS_STATUS = BLOCKED` aguardando banca externa; runtime da Fase 7 não iniciado).
