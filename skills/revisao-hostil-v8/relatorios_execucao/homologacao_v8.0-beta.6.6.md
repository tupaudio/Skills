# Relatório Técnico de Execução e Pré-Homologação — Revisão Hostil `v8.0-beta.6.6`

RUN_ID=BETA6.6-20261124T022833Z-85ef1fff

> **Fonte única de verdade (`run_id`):** `BETA6.6-20261124T022833Z-85ef1fff`  
> **Gerado programaticamente** a partir da mesma execução que produziu `pytest_verbose.txt`, `coverage_report.txt`, `smoke_tests.txt` e `run_manifest.json` (todos marcados com cabeçalho estrito `RUN_ID=BETA6.6-20261124T022833Z-85ef1fff` e verificados por `validate_artifact_run_id()` + `build_expected_checksum_inventory()` + `validate_run_consistency()`).

## 1. Objetivo da manutenção
Correção do achado `ACH-B6.5-001 (P2)` sobre `v8.0-beta.6.5`: endurecimento de `validate_artifact_run_id()` em `scripts/common/provenance.py` para exigir cabeçalho estritamente conforme (`RUN_ID=` ou `# run_id=`), rejeitando presença apenas no corpo, cabeçalhos vazios/malformados e cabeçalhos duplicados pela política padrão (documentada), preservando integralmente `ACH-B6.3-001`, `ACH-B6.3-002` e todas as tags históricas.

## 2. Commit-base e identificação Git
- **Tag-base preservada:** `v8.0-beta.6.5` (`fa09c3e07ea763e2bf2c76546c1c076391b17145`)
- **Branch de execução:** `maintenance/v8.0-beta.6.6`
- **Commit de código auditado (`audited_code_commit`):** `4215bfb7ebf219163d3b4872e7a7d4488eb1f1ad`
- **Início (UTC):** `2026-11-24T02:28:33+00:00`
- **Fim dos testes/relatórios (UTC):** `2026-11-24T02:29:07+00:00`

## 3. Achado tratado, 4. Causa-raiz e 5. Correção implementada

### ACH-B6.5-001 (P2) — Validação estrita de cabeçalho em `validate_artifact_run_id()`
- **Causa-raiz:** Na Beta 6.5, quando nenhum cabeçalho era encontrado (`distinct_headers == []`), a verificação `expected_run_id in content` ainda podia aprovar um artefato que apenas mencionasse o `run_id` no corpo textual.
- **Correção:** `validate_artifact_run_id()` em `scripts/common/provenance.py` passou a exigir explicitamente pelo menos um cabeçalho estritamente conforme (`_RUN_ID_STRICT_HEADER_RE`), rejeitando menção apenas no corpo, cabeçalhos vazios/malformados (`_RUN_ID_CANDIDATE_LINE_RE`), cabeçalhos divergentes, cabeçalhos conflitantes e múltiplas ocorrências idênticas por padrão (`allow_duplicate_identical_headers=False`, documentado).

## 6. Arquivos alterados na manutenção
- `skills/revisao-hostil-v8/scripts/common/provenance.py`
- `skills/revisao-hostil-v8/scripts/tools/generate_audit_reports.py`
- `skills/revisao-hostil-v8/tests/test_beta6_5_run_id_header_strict.py` (novo)
- `skills/revisao-hostil-v8/tests/test_beta6_3_requirements_provenance.py`
- `skills/revisao-hostil-v8/relatorios_execucao/{pytest_verbose.txt,coverage_report.txt,smoke_tests.txt,run_manifest.json,homologacao_v8.0-beta.6.6.md}`
- `skills/revisao-hostil-v8/SHA256SUMS` e `README.md`

## 7. Testes criados, 8. Executados e 9. Resultado integral do pytest
- **Suíte nova:** `tests/test_beta6_3_requirements_provenance.py` (unitários, integração, negativos e adversariais para `ACH-B6.2-002`, `ACH-B6.2-001` e regressão de `ACH-B6.1-001` a `005`).
- **Coletados:** `178`
- **Aprovados:** `178 passed`
- **Reprovados:** `0`
- **Ignorados:** `0`
- **Erros de coleta:** `0`
- Warnings: `0`
- **Código de saída:** `0`
- **Duração da suíte (precisão completa):** `21.864614s` (`21.86s`)
- **Duração smoke tests:** `9.180139s`
- **Duração geração de relatórios:** `0.328945s`
- **Log bruto:** `relatorios_execucao/pytest_verbose.txt`

## 10. Cobertura por módulo (`pytest-cov`)
- **Cobertura global (`scripts/`):** **82.73%** (`4093` statements, `707` missed)

| Módulo | Stmts | Miss | Cover |
| :--- | ---: | ---: | ---: |
| `scripts/__init__.py` | 0 | 0 | 100.00% |
| `scripts/auditor.py` | 184 | 42 | 77.17% |
| `scripts/common/__init__.py` | 2 | 0 | 100.00% |
| `scripts/common/citation.py` | 20 | 0 | 100.00% |
| `scripts/common/dependencies.py` | 317 | 35 | 88.96% |
| `scripts/common/evidence.py` | 67 | 11 | 83.58% |
| `scripts/common/profile_loader.py` | 176 | 17 | 90.34% |
| `scripts/common/provenance.py` | 390 | 34 | 91.28% |
| `scripts/common/schema_validator.py` | 55 | 2 | 96.36% |
| `scripts/common/statistics.py` | 13 | 1 | 92.31% |
| `scripts/common/text_normalize.py` | 14 | 1 | 92.86% |
| `scripts/common/units.py` | 16 | 2 | 87.50% |
| `scripts/common/validation.py` | 54 | 8 | 85.19% |
| `scripts/engines/__init__.py` | 0 | 0 | 100.00% |
| `scripts/engines/motor_argumentacao.py` | 65 | 14 | 78.46% |
| `scripts/engines/motor_consistencia_cruzada.py` | 91 | 17 | 81.32% |
| `scripts/engines/motor_dados.py` | 170 | 30 | 82.35% |
| `scripts/engines/motor_dimensional.py` | 259 | 63 | 75.68% |
| `scripts/engines/motor_estatistico.py` | 270 | 41 | 84.81% |
| `scripts/engines/motor_estetico.py` | 54 | 12 | 77.78% |
| `scripts/engines/motor_etica.py` | 96 | 16 | 83.33% |
| `scripts/engines/motor_evidencia.py` | 55 | 13 | 76.36% |
| `scripts/engines/motor_figuras.py` | 106 | 18 | 83.02% |
| `scripts/engines/motor_geometrico.py` | 207 | 40 | 80.68% |
| `scripts/engines/motor_imagem_forense.py` | 105 | 28 | 73.33% |
| `scripts/engines/motor_incerteza.py` | 157 | 40 | 74.52% |
| `scripts/engines/motor_linguagem.py` | 85 | 16 | 81.18% |
| `scripts/engines/motor_matematico.py` | 454 | 87 | 80.84% |
| `scripts/engines/motor_metadados.py` | 57 | 16 | 71.93% |
| `scripts/engines/motor_nomenclatura.py` | 57 | 12 | 78.95% |
| `scripts/engines/motor_normas.py` | 92 | 18 | 80.43% |
| `scripts/engines/motor_qualitativo.py` | 94 | 21 | 77.66% |
| `scripts/engines/motor_reprodutibilidade.py` | 55 | 14 | 74.55% |
| `scripts/engines/motor_risco.py` | 87 | 18 | 79.31% |
| `scripts/engines/motor_temporal.py` | 169 | 20 | 88.17% |

## 11. Ambiente efetivo (capturado diretamente do processo)
- **Python:** `3.14.6` (`CPython`)
- **Sistema Operacional:** `Windows 11`
- **Build do SO:** `10.0.26300`
- **Plataforma completa:** `Windows-11-10.0.26300-SP0`
- **Arquitetura:** `AMD64`
- **Ambiente virtual:** `C:\Users\dafnh\.gemini\antigravity\brain\d4ef86c0-a49f-4a11-9b77-a243d5779eda\scratch\venv_b66`
- **Ferramentas de teste:** `pytest==9.2.0`, `pytest-cov==7.1.0`, `coverage==7.17.5`, `packaging==26.4`

## 12. Versões das dependências instaladas no ambiente
- `Pillow==13.0.0`
- `PyYAML==6.0.4`
- `coverage==7.17.5`
- `jsonschema==4.26.0`
- `numpy==2.5.5`
- `packaging==26.4`
- `pypdf==7.1.1`
- `pytest==9.2.0`
- `pytest-cov==7.1.0`
- `python-docx==1.2.0`
- `referencing==0.37.0`
- `scipy==1.18.1`
- `sympy==1.14.0`

## 13. Resultado dos smoke tests reais
- **Motores implementados submetidos a smoke tests:** `21/21` (de 23 catalogados; 2 planejados para a Fase 8 não executáveis) + `auditor.py`.
- **Todos validados contra `schema_motor.json` fechado:** `True`
- **Log:** `relatorios_execucao/smoke_tests.txt`

## 14. Resultado dos sete perfis-piloto
- `artes` (`v1.0.0`, status=`active`, execution_eligible=`True`)
- `direito` (`v1.0.0`, status=`active`, execution_eligible=`True`)
- `engenharia_geral` (`v1.0.0`, status=`active`, execution_eligible=`True`)
- `musica_acustica` (`v1.0.0`, status=`active`, execution_eligible=`True`)
- `pesquisa_qualitativa` (`v1.0.0`, status=`active`, execution_eligible=`True`)
- `seguranca_trabalho` (`v1.0.0`, status=`active`, execution_eligible=`True`)
- `sistemas_espaciais` (`v1.0.0`, status=`active`, execution_eligible=`True`)

## 15. Resultado dos oito schemas JSON
- Schemas validados e fechados (`additionalProperties: false` na raiz): `8` (`schema_achado.json`, `schema_agente.json`, `schema_evidencia.json`, `schema_input.json`, `schema_iteracao.json`, `schema_motor.json`, `schema_profile.json`, `schema_relatorio_final.json`).

## 16. Validação de consistência e 17. Checksums SHA-256
- Executados imediatamente após a gravação deste relatório e do `run_manifest.json` pela mesma execução (`run_id=BETA6.6-20261124T022833Z-85ef1fff`), com recálculo real de bytes para todas as entradas de `SHA256SUMS` (exigindo 0 divergências).

## 18. Commit auditado e 19. Commit de publicação dos artefatos
- **Commit auditado:** `4215bfb7ebf219163d3b4872e7a7d4488eb1f1ad`
- **Commit de publicação dos artefatos:** criado imediatamente após esta geração como descendente direto de `4215bfb7ebf219163d3b4872e7a7d4488eb1f1ad`, com tag anotada `v8.0-beta.6.6`.

## 20. Limitações conhecidas
- `motor_integracao`, `motor_meta`, `orchestrator.py` e `SKILL.md` da v8.0 permanecem planejados para a Fase 8.
- Banca multiagente (`Challenger`, `Adversarial`, `Adjudicador`) permanece bloqueada na Fase 7 até reauditoria independente.
- Resultados aqui registrados correspondem à execução local em ambiente virtual limpo (`venv_b66`), não substituindo a reauditoria externa independente.

## 21. Decisão técnica local
**`APROVADA PARA REAUDITORIA EXTERNA`** — `ACH-B6.5-001` corrigido e regressão integral de `ACH-B6.1-001` a `ACH-B6.3-002` validada em ambiente limpo com fonte única de verdade (`run_id=BETA6.6-20261124T022833Z-85ef1fff`).
