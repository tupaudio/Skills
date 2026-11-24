# MATRIZ DE RASTREABILIDADE — AUDITORIA REVISÃO 17 → REVISÃO 18

| Achado | Severidade | Ação de Encerramento | Artefatos | Testes | Status |
| :--- | :---: | :--- | :--- | :--- | :---: |
| `ACH-B7-R17-001` | **P1** | Removida canonicalização artesanal; adotadas `rfc8785==0.1.4` + `jcs==0.3.0` com verificação cruzada e 18 vetores individuais em `test_vectors/rfc8785/`. | `tools/validate_rev18.py`, `tools/requirements-validation.txt`, `test_vectors/rfc8785/*` | `T-R18-165`..`168`, `190`..`191` | **FECHADO** |
| `ACH-B7-R17-002` | **P1** | Removido fallback artesanal Ed25519; adotada `cryptography==50.0.2` com validação SPKI DER completa e vetor oficial RFC 8032 TV1. | `tools/validate_rev18.py`, `test_vectors/ed25519/rfc8032-tv1.json` | `T-R18-169`..`172`, `192` | **FECHADO** |
| `ACH-B7-R17-003` | **P1** | Implementada `validate_checkpoint_receipt_global()` validando todas as 14 relações + assinaturas Ed25519 de Store e Testemunhas + 18 mutações negativas. | `tools/validate_rev18.py`, `CONTRATOS_CRIPTOGRAFICOS_REV18.md`, `test_vectors/checkpoint/*` | `T-R18-173`..`179`, `193` | **FECHADO** |
| `ACH-B7-R17-004` | **P1** | `clock_context_id` alterado para `format: "uuid"`, implementada `validate_process_clock_context_id()` (UUIDv4 RFC 4122 minúsculo) + 8 mutações negativas + QPC Windows. | `schemas/7.0.0/schema_monotonic_checkpoint_receipt.json`, `tools/validate_rev18.py` | `T-R18-180`..`184` | **FECHADO** (Linux QPC/CLOCK marcado `BLOQUEADO_AMBIENTE_LINUX`) |
| `ACH-B7-R17-005` | **P2** | Publicados `reports/COBERTURA_RFC8785_REV18.md`, `validate_rev18.py` sem `assert` (aprovado em `python -O`) e preservação dos 164 IDs históricos. | `reports/COBERTURA_RFC8785_REV18.md`, `tools/validate_rev18.py` | `T-R18-185`..`189`, `194` | **FECHADO** |
