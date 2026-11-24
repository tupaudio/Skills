# RELATÓRIO DE AUDITORIA INTERNA HOSTIL — REVISÃO 18

- **Verificação de `assert` em `tools/validate_rev18.py`:** `0` ocorrências (todas as verificações usam `require()` / `ValidationError`, mantendo validade integral sob `python -O`).
- **Verificação de fallbacks artesanais:** `0` ocorrências de código artesanal de JCS (`repr(float)`) ou Ed25519 (`_xrecover`, `_ed_add`, etc.).
- **Verificação de exceções mascaradas:** nenhuma validação captura `ValidationError` indevidamente fora dos loops explícitos de mutação negativa.
- **Verificação de independência:** `rfc8785==0.1.4` e `jcs==0.3.0` são bibliotecas independentes; `cryptography==50.0.2` valida Ed25519 e SPKI DER contra RFC 8032 TV1.
- **Resultado da auditoria interna:** `0` achados P1 abertos; `0` achados P2 abertos; `1` limitação ambiental declarada (`T-R18-184` Linux).
