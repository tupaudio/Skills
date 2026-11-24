# RELATÓRIO DE CONVERGÊNCIA — REVISÃO 18 (`specification/v8.0-beta.7-rev18`)

1. **Commit-base (Rev17):** `20068023920cee12e44cf6b1e8f5d77c48516f00` (derivado de `v8.0-beta.6.6` `11e91b6f3d517707326357868cc34ff97ab8327d`)
2. **Commit final:** registrado no commit de publicação da branch `specification/v8.0-beta.7-rev18`
3. **Arquivos adicionados:** diretório `skills/revisao-hostil-v8/docs/fase7_rev18/` (documentos, 8 schemas legados, 19 schemas `7.0.0`, 18 vetores RFC 8785, vetores Ed25519/Dossiê/Checkpoint, ferramentas e relatórios)
4. **Arquivos alterados fora de `docs/fase7_rev18/`:** `0`
5. **Arquivos preservados:** `main`, tag `v8.0-beta.6.6`, branches `rev10`–`rev17`, `references/schemas/`, `requirements.txt`, `catalogo_agentes.yaml`, `SKILL.md`
6. **Hashes principais:**
   - `compatibility_policy_jcs_sha256`: `cc8bcd14d8b98c2f95c8b1ec78827a17fd7e82e13f7642d8e1813169adae8415`
   - `dossier_jcs_sha256`: `9e6c0a4261151b55a65579b1062a3aa8e561f83e5e65eecb385dd625a73b737b`
7. **Dependências fixadas (`requirements-validation.txt`):** `rfc8785==0.1.4`, `jcs==0.3.0`, `cryptography==50.0.2`, `jsonschema==4.26.0`
8. **Ambiente Python:** Python `3.14.6` (venv isolado)
9. **Sistema operacional:** Windows 11 (`10.0.26300`)
10. **Comandos executados:** `build_rev18_all.py`, `build_test_matrix_rev18.py`, `validate_rev18.py`, `python -O validate_rev18.py`
11. **Código de saída de cada execução:** `0`, `0`, `0`, `0`
12. **Testes especificados:** `194` (`164` históricos preservados + `30` novos)
13. **Testes executados (documentais/validador):** `28`
14. **Testes aprovados:** `28`
15. **Testes reprovados:** `0`
16. **Testes bloqueados / não executados:** `165` de runtime Fase 7 (`NAO_EXECUTADO_RUNTIME`) + `1` bloqueado por ambiente Linux (`T-R18-184`: `BLOQUEADO_AMBIENTE_LINUX`)
17. **Comparação JCS:** `18/18` vetores `PASS` com 100% concordância entre `rfc8785==0.1.4` e `jcs==0.3.0`
18. **Ed25519:** RFC 8032 TV1 + mutações SPKI DER/assinatura `PASS` via `cryptography==50.0.2` (zero fallback)
19. **Reconciliação semântica global:** `1` positivo + `18` mutações negativas `PASS`
20. **Relógios Linux e Windows:** Windows QPC `PASS` (executado localmente); Linux `CLOCK_MONOTONIC_RAW` `BLOQUEADO_AMBIENTE_LINUX` (não executado neste host Windows)
21. **Auditoria interna:** `PASS` (`0` asserts, `0` fallbacks, `0` P1/P2 documentais)
22. **Achados encerrados:** `ACH-B7-R17-001`, `ACH-B7-R17-002`, `ACH-B7-R17-003`, `ACH-B7-R17-004` (Windows + UUIDv4), `ACH-B7-R17-005`
23. **Achados abertos:** `0` P1/P2 documentais
24. **Impedimento registrado:** execução real de `CLOCK_MONOTONIC_RAW` em Linux (`T-R18-184`) requer host/container Linux kernel ≥ 5.6; mantido como `BLOQUEADO_AMBIENTE_LINUX` sem falsa aprovação.
25. **Status final:** `BLOCKED_ENVIRONMENT` (para o teste Linux `T-R18-184`; todas as validações documentais e Windows 100% aprovadas; `OS_STATUS = BLOCKED` aguardando banca externa).
