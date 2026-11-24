# Validação Documental Independente — Revisão 16 (`ACH-B7-R15-004`)

## Dependências
- Python 3.10+
- `jsonschema` (`pip install jsonschema`)
- Zero dependências externas de criptografia (verificação Ed25519 RFC 8032 incluída em Python puro para reprodutibilidade do vetor `dossier-tv-001`).

## Execução
A partir da raiz do repositório:
```bash
python skills/revisao-hostil-v8/docs/fase7_rev16/tools/validate_rev16.py
```

## Saída Determinística
- **Código de saída `0`:** todos os 32 arquivos JSON, schemas Draft 2020-12, 19 contratos, 19 `$ref` transitivos, digest JCS da política, vetor criptográfico Ed25519 `dossier-tv-001`, prova matemática e 154 IDs de cenários conferem.
- **Código de saída `!= 0`:** qualquer divergência estrutural, semântica, de hash ou de assinatura.

> **Nota:** `validate_rev16.py` é exclusivamente uma ferramenta de auditoria documental; não implementa código operacional da Fase 7.
