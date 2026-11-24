# RELATÓRIO DE COBERTURA RFC 8785 JCS — REVISÃO 18 (`ACH-B7-R17-005`)

**Implementação A:** `rfc8785==0.1.4`  
**Implementação B:** `jcs==0.3.0`  
**Total:** `18/18` vetores executados com `100%` de concordância byte a byte e SHA-256.

| Requisito Normativo | Vetor(es) | Implementação A (`rfc8785`) | Implementação B (`jcs`) | Resultado |
| :--- | :--- | :---: | :---: | :---: |
| Ordenação UTF-16 (Oficial, ASCII, BMP, Suplementares, `U+1F600` vs `U+FB33`) | `v01`..`v05` | PASS | PASS | **PASS** |
| Strings (aspas, barra invertida, controle) | `v06` | PASS | PASS | **PASS** |
| Unicode sem normalização implícita NFC/NFD | `v07` | PASS | PASS | **PASS** |
| Números (`0`, `-0.0`, `1e-6`, `1e-7`, `1e20`, `1e21`, limites, IEEE-754, faixa segura) | `v08`..`v15`, `v17` | PASS | PASS | **PASS** |
| Objetos aninhados e arrays mistos | `v18` | PASS | PASS | **PASS** |
| Valores inválidos (`NaN`, `Infinity`, `-Infinity`, tipos não-JSON) | `v16` + testes negativos | PASS (rejeitado) | PASS (rejeitado) | **PASS** |
