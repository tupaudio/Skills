# RELATÓRIO DE EXECUÇÃO — REVISÃO 18

- **Ambiente:** Windows 11 (`10.0.26300`), Python `3.14.6` (venv isolado `venv_rev18`)
- **Dependências verificadas:** `rfc8785==0.1.4`, `jcs==0.3.0`, `cryptography==50.0.2`, `jsonschema==4.26.0`
- **Comandos executados:**
  1. `python tools/build_rev18_all.py` → Exit code `0`
  2. `python tools/build_test_matrix_rev18.py` → Exit code `0`
  3. `python tools/validate_rev18.py` → Exit code `0` (`53` JSON estritos, `18` vetores RFC 8785, RFC 8032 TV1, `19` schemas Draft 2020-12, `1` positivo + `18` negativos checkpoint global, `8` negativos UUIDv4, QPC Windows, `194` IDs únicos)
  4. `python -O tools/validate_rev18.py` → Exit code `0` (comprovando ausência de dependência de `assert`)
- **Limitação explícita de SO:** Teste de `CLOCK_MONOTONIC_RAW` em kernel Linux ≥ 5.6 (`T-R18-184`) registrado como `BLOQUEADO_AMBIENTE_LINUX` (host de execução é Windows 11).
