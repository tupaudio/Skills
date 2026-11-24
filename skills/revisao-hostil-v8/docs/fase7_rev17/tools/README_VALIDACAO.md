# Validação Documental Independente — Revisão 17

## Dependências
- Python 3.10+
- `jsonschema` (`pip install jsonschema`)
- Opcional recomendado para verificação Ed25519 via OpenSSL: `cryptography` (`pip install cryptography`); na ausência, utiliza fallback RFC 8032 com validação estrita do cabeçalho ASN.1 DER SPKI Ed25519 (`302a300506032b6570032100`, 44 bytes).

## Execução
```bash
python skills/revisao-hostil-v8/docs/fase7_rev17/tools/validate_rev17.py
```

## Escopo Verificado (Código de saída `0` = aprovado; `!= 0` = divergência)
1. Parsing JSON estrito + zero placeholders (`34` arquivos JSON).
2. Conformidade RFC 8785 JCS (`test_vectors/rfc8785-conformance.json`, ordenação UTF-16 code units).
3. Validação Draft 2020-12 de **todos os 19 schemas**, unicidade de `$id`, ausência de `$ref` externos e ciclos, reconciliação com `SCHEMA_REGISTRY_FASE7_REV17.json` e `compatibility_policy_v1.json`.
4. Digest RFC 8785 JCS da política.
5. Verificação integral de todos os 6 campos de `dossier-tv-001.verification.json` + ASN.1 DER SPKI + Ed25519.
6. Validador semântico de `schema_monotonic_checkpoint_receipt.json` (1 positivo + 4 mutações negativas).
7. Limites matemáticos exatos (`D_bound`, `N_bound`) e `164` IDs únicos de cenários (`0/164` executados).
