# Validação Documental Independente — Revisão 18

## Dependências Fixadas (`requirements-validation.txt`)
```bash
pip install -r skills/revisao-hostil-v8/docs/fase7_rev18/tools/requirements-validation.txt
```
- `rfc8785==0.1.4`
- `jcs==0.3.0`
- `cryptography==50.0.2`
- `jsonschema==4.26.0`

## Execução (Normal e com `-O`)
```bash
python skills/revisao-hostil-v8/docs/fase7_rev18/tools/validate_rev18.py
python -O skills/revisao-hostil-v8/docs/fase7_rev18/tools/validate_rev18.py
```
Código de saída `0` = aprovado; `!= 0` = divergência ou dependência ausente/incorreta. Zero `assert` no código.
