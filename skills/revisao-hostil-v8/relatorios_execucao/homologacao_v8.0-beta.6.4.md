# Relatório Técnico de Execução e Pré-Homologação — Revisão Hostil `v8.0-beta.6.4`

> **Fonte única de verdade (`run_id`):** `BETA6.4-20261124T013225Z-46b678ba`  
> **Gerado programaticamente** a partir da mesma execução que produziu `pytest_verbose.txt`, `coverage_report.txt`, `smoke_tests.txt` e `run_manifest.json` (todos marcados internamente com `run_id` e verificados por `validate_run_consistency()`).

## 1. Objetivo da manutenção
Manutenção corretiva direcionada sobre `v8.0-beta.6.3` para encerrar `ACH-B6.3-001` (propagação e verificação efetiva do `run_id` dentro do conteúdo de todos os artefatos obrigatórios) e `ACH-B6.3-002` (verificação integral de completude, duplicatas, entradas inesperadas e integridade em `SHA256SUMS`), preservando intacta a tag `v8.0-beta.6.3` e sem iniciar a Fase 7.

## 2. Commit-base e identificação Git
- **Tag-base preservada:** `v8.0-beta.6.3` (`67efd041c359301dcaf4eedfad891daf731ecf8d`)
- **Branch de execução:** `maintenance/v8.0-beta.6.4`
- **Commit de código auditado (`audited_code_commit`):** `57ed91e808a39454715139b3fafd8d0e08f6d703`
- **Início (UTC):** `2026-11-24T01:32:25+00:00`
- **Fim dos testes/relatórios (UTC):** `2026-11-24T01:32:53+00:00`

## 3. Achados tratados, 4. Causa-raiz e 5. Correção implementada

### ACH-B6.3-001 (P2) — Propagação e verificação efetiva do `run_id` em todos os artefatos
- **Causa-raiz:** `pytest_verbose.txt` e `coverage_report.txt` não continham o `run_id` no conteúdo do arquivo, e `validate_run_consistency()` verificava apenas o metadado `art["run_id"]` no manifesto.
- **Correção:** Inserido cabeçalho `# run_id=BETA6.4-20261124T013225Z-46b678ba` em `pytest_verbose.txt`, `coverage_report.txt` e `smoke_tests.txt` (além da presença em `homologacao_v8.0-beta.6.4.md`), e endurecido `validate_run_consistency()` em `scripts/common/provenance.py` para inspecionar o conteúdo real de cada artefato em disco e rejeitar ausência ou divergência de `run_id`.

### ACH-B6.3-002 (P2) — Completude e integridade estrita de `SHA256SUMS`
- **Causa-raiz:** `validate_run_consistency()` recalculava apenas as linhas presentes em `SHA256SUMS`, sem verificar se algum arquivo esperado do inventário havia sido omitido ou se havia entradas duplicadas/inesperadas/malformadas.
- **Correção:** `validate_run_consistency()` agora constrói o conjunto esperado a partir de `inspected_files + self_excluded_files + artifacts` (excluindo `SHA256SUMS`), rejeitando arquivos omitidos, entradas duplicadas, arquivos inesperados, caminhos inválidos, hashes malformados e auto-inclusão.

## 6. Arquivos alterados na manutenção
- `skills/revisao-hostil-v8/scripts/common/provenance.py`
- `skills/revisao-hostil-v8/scripts/common/dependencies.py`
- `skills/revisao-hostil-v8/scripts/tools/generate_audit_reports.py`
- `skills/revisao-hostil-v8/tests/test_beta6_3_requirements_provenance.py`
- `skills/revisao-hostil-v8/relatorios_execucao/{pytest_verbose.txt,coverage_report.txt,smoke_tests.txt,run_manifest.json,homologacao_v8.0-beta.6.4.md}`
- `skills/revisao-hostil-v8/SHA256SUMS` e `README.md`

## 7. Testes criados, 8. Executados e 9. Resultado integral do pytest
- **Suíte nova:** `tests/test_beta6_3_requirements_provenance.py` (unitários, integração, negativos e adversariais para `ACH-B6.2-002`, `ACH-B6.2-001` e regressão de `ACH-B6.1-001` a `005`).
- **Coletados:** `136`
- **Aprovados:** `136 passed`
- **Reprovados:** `0`
- **Ignorados:** `0`
- **Erros de coleta:** `0`
- Warnings: `0`
- **Código de saída:** `0`
- **Duração da suíte (precisão completa):** `16.111179s` (`16.11s`)
- **Duração smoke tests:** `8.906304s`
- **Duração geração de relatórios:** `0.382970s`
- **Log bruto:** `relatorios_execucao/pytest_verbose.txt`

## 10. Cobertura por módulo (`pytest-cov`)
- **Cobertura global (`scripts/`):** **82.29%** (`3998` statements, `708` missed)

| Módulo | Stmts | Miss | Cover |
| :--- | ---: | ---: | ---: |
| `scripts/__init__.py` | 0 | 0 | 100.00% |
| `scripts/auditor.py` | 184 | 42 | 77.17% |
| `scripts/common/__init__.py` | 2 | 0 | 100.00% |
| `scripts/common/citation.py` | 20 | 0 | 100.00% |
| `scripts/common/dependencies.py` | 317 | 35 | 88.96% |
| `scripts/common/evidence.py` | 67 | 11 | 83.58% |
| `scripts/common/profile_loader.py` | 176 | 17 | 90.34% |
| `scripts/common/provenance.py` | 295 | 35 | 88.14% |
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
- **Ambiente virtual:** `<USER_HOME>\.gemini\antigravity\brain\d4ef86c0-a49f-4a11-9b77-a243d5779eda\scratch\venv_b64`
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
- Executados imediatamente após a gravação deste relatório e do `run_manifest.json` pela mesma execução (`run_id=BETA6.4-20261124T013225Z-46b678ba`), com recálculo real de bytes para todas as entradas de `SHA256SUMS` (exigindo 0 divergências).

## 18. Commit auditado e 19. Commit de publicação dos artefatos
- **Commit auditado:** `57ed91e808a39454715139b3fafd8d0e08f6d703`
- **Commit de publicação dos artefatos:** criado imediatamente após esta geração como descendente direto de `57ed91e808a39454715139b3fafd8d0e08f6d703`, com tag anotada `v8.0-beta.6.4`.

## 20. Limitações conhecidas
- `motor_integracao`, `motor_meta`, `orchestrator.py` e `SKILL.md` da v8.0 permanecem planejados para a Fase 8.
- Banca multiagente (`Challenger`, `Adversarial`, `Adjudicador`) permanece bloqueada na Fase 7 até reauditoria independente.
- Resultados aqui registrados correspondem à execução local em ambiente virtual limpo (`venv_b64`), não substituindo a reauditoria externa independente.

## 21. Decisão técnica local
**`APROVADA PARA REAUDITORIA EXTERNA`** — todos os critérios de `ACH-B6.3-001`, `ACH-B6.3-002` e regressão de `ACH-B6.1-001` a `ACH-B6.2-002` validados em ambiente limpo com fonte única de verdade (`run_id=BETA6.4-20261124T013225Z-46b678ba`).
