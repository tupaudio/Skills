# RELATÓRIO DE CONVERGÊNCIA — REVISÃO 19 (`specification/v8.0-beta.7-rev19`)

- **Branch de origem:** `specification/v8.0-beta.7-rev18` (`8d10ef1f98fa3888e2fdf08b80c2e82a5963b6e0`)
- **Base imutável:** `v8.0-beta.6.6` (`11e91b6f3d517707326357868cc34ff97ab8327d`)
- **Ambiente real:** Windows 11 (`10.0.26300`), Python `3.14.6`, `venv_rev19` instalado exclusivamente via `python -m pip install --require-hashes -r tools/requirements-validation.lock` (`exit 0`, `lock_sha256 = d7270cbb1feeb640ef75321b856adcad048477e6bfa4456e680f3bd8ce693585`)
- **Instante UTC usado na validação do dossiê e revogação:** `2026-11-24T12:00:00Z` (fixo e documentado)
- **Execuções reais observadas:**
  - `python tools/validate_rev19.py` → Exit code `0` (`59` JSON estritos, `20` schemas Draft 2020-12, Registry + política `5721b8e982e85f843283d571bbcb0d1e66dcac8b1f6ab43df566929cd498c028`, dossiê + revogação + checkpoint global)
  - `python -O tools/validate_rev19.py` → Exit code `0` (zero `assert`)
  - `python -m pytest -q tests/` → `4 passed, 1 skipped` (exit code `0`)
  - `python -O -m pytest -q tests/` → `4 passed, 1 skipped` (exit code `0`)
  - `python tools/run_independent_tests.py` → Exit code `0`, gerado `reports/test_results_rev19.json` (`4 PASS`, `1 BLOCKED_ENVIRONMENT` para `T-R19-198` Linux)
- **Achados encerrados:** `ACH-B7-R18-001`, `002`, `003`, `004` (Windows real aprovado; Linux `BLOCKED_ENVIRONMENT`), `005`, `006`.
- **Status final:** `BLOCKED_ENVIRONMENT` (exclusivamente por ausência de kernel Linux ≥ 5.6 neste host Windows 11 para executar `T-R19-198`; todos os critérios documentais e Windows 100% aprovados; `0` P1/P2 documentais abertos; `OS_STATUS = BLOCKED`).
