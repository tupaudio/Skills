# Relatório de Homologação — Revisão Hostil `v8.0-beta.6.2`

## 1. Versão de origem e versão final
- **Versão de origem (referência congelada):** `v8.0-beta.6.1` (tag imutável preservada)
- **Versão final:** `v8.0-beta.6.2` (branch de manutenção `maintenance/v8.0-beta.6.2`, integrada à `main`)

## 2. Commit de origem
- `8f7baf9739d295f8584ea59c740d22d13049469d` (`v8.0-beta.6.1`)

## 3. Commits da manutenção
- `5430daa` — `fix(v8-beta.6.2): bloqueio efetivo de dependências, SemVer 2.0.0 fullmatch e compatibilidade packaging (ACH-B6.1-001 a 003)`
- `a7eb6ef` — `fix(v8-beta.6.2): fecha contratos JSON com additionalProperties=false e documenta extensibilidade (ACH-B6.1-004)`
- `03e62c8` — `fix(v8-beta.6.2): rastreabilidade perfil->motor->dependência->versão->estado no run_manifest.json (ACH-B6.1-005)`
- `92eb3c0921f4875f65aacaa418258708c6bb3495` — `test(v8-beta.6.2): suíte unitária, integração, negativa e adversarial para ACH-B6.1-001 a 005 (93 passed)` (`audited_code_commit`)
- Commit final de publicação dos artefatos de relatório, documentação, `SHA256SUMS` e tag `v8.0-beta.6.2` (filho direto de `92eb3c0921f4875f65aacaa418258708c6bb3495`).

## 4. Lista de arquivos alterados e adicionados
- `skills/revisao-hostil-v8/scripts/common/dependencies.py` (novo)
- `skills/revisao-hostil-v8/scripts/common/profile_loader.py`
- `skills/revisao-hostil-v8/scripts/common/provenance.py`
- `skills/revisao-hostil-v8/scripts/tools/generate_audit_reports.py`
- `skills/revisao-hostil-v8/requirements.txt`
- `skills/revisao-hostil-v8/references/schemas/schema_profile.json`
- `skills/revisao-hostil-v8/references/schemas/schema_achado.json`
- `skills/revisao-hostil-v8/references/schemas/schema_agente.json`
- `skills/revisao-hostil-v8/references/schemas/schema_input.json`
- `skills/revisao-hostil-v8/references/schemas/schema_iteracao.json`
- `skills/revisao-hostil-v8/references/schemas/schema_motor.json`
- `skills/revisao-hostil-v8/references/schemas/schema_relatorio_final.json`
- `skills/revisao-hostil-v8/tests/test_beta6_2_contratos_e_dependencias.py` (novo)
- `skills/revisao-hostil-v8/tests/test_beta6_perfis_e_normas.py`
- `skills/revisao-hostil-v8/relatorios_execucao/{pytest_verbose.txt,coverage_report.txt,smoke_tests.txt,run_manifest.json,homologacao_v8.0-beta.6.2.md}`
- `skills/revisao-hostil-v8/SHA256SUMS`
- `README.md`

## 5. Achados corrigidos e evidência técnica (6. Evidência por achado)

### ACH-B6.1-001
- **ID:** `ACH-B6.1-001`
- **Severidade:** `P1`
- **Problema:** Na Beta 6.1, dependências ausentes eram registradas em `_resolved["verified_dependencies"]`, mas `execution_eligible` permanecia `True` para perfis `active` e nenhum portão impedia a execução de motores.
- **Causa raiz:** `profile_loader.py` calculava `execution_eligible = (status == "active")` sem acoplar o resultado da verificação ambiental nem oferecer portão pré-execução.
- **Arquivo e função:** `scripts/common/dependencies.py` (`validate_environment_for_profile`, `assert_engine_execution_allowed`, `execute_engine_with_profile`) e `scripts/common/profile_loader.py` (`load_profile`).
- **Correção:** Criada validação centralizada por motor com os 5 estados (`available`, `missing`, `incompatible`, `unknown`, `not_applicable`), bloqueio com `ExecutionBlockedError` em `mode="execution"` (sem parâmetro de bypass), separação explícita de `mode="diagnostic"` (sempre `execution_eligible=False`), tolerância apenas para motor opcional não solicitado e portão pré-execução obrigatório.
- **Teste que comprova a correção:** `test_ach_b61_001_required_dep_installed_and_compatible_allows_execution`, `test_ach_b61_001_required_dep_missing_blocks_execution_and_no_engine_runs`, `test_ach_b61_001_required_dep_incompatible_blocks_execution`, `test_ach_b61_001_optional_dep_missing_tolerated_when_not_requested_and_blocked_when_requested`, `test_ach_b61_001_unknown_dep_never_treated_as_available_and_bypass_attempts_fail`.
- **Resultado:** `PASSED` (comprovação por spy de 0 chamadas de motor quando o ambiente é inelegível).
- **Estado final:** `RESOLVIDO E COMPROVADO`

### ACH-B6.1-002
- **ID:** `ACH-B6.1-002`
- **Severidade:** `P2`
- **Problema:** `is_valid_semver()` usava `SEMVER_2_0_0_RE.match()` com âncora `$`, aceitando quebra de linha final (`"1.0.0\n"`) tanto em Python quanto via `jsonschema`.
- **Causa raiz:** Em Python `re`, `$` casa antes de `\n` final e `match()` não impõe correspondência completa da string.
- **Arquivo e função:** `scripts/common/profile_loader.py` (`SEMVER_2_0_0_RE`, `validate_semver_strict`, `is_valid_semver`) e `references/schemas/schema_profile.json` (`profile_version.pattern`).
- **Correção:** Adotado `fullmatch()` com âncoras `\A...\Z`, rejeição explícita de espaços/quebras de linha/prefixos/não-strings sem normalização silenciosa, registro do motivo e endurecimento do `pattern` JSON Schema com `(?![\r\n])$`.
- **Teste que comprova a correção:** `test_ach_b61_002_semver_valid_cases` (10 casos parametrizados) e `test_ach_b61_002_semver_invalid_cases_rejected_without_normalization` (14 casos parametrizados, incluindo `"1.0.0\n"`, `"1.0.0 "`, `" 1.0.0"`, `"01.02.03"`, `"1.0.0-01"`, `"1.0.0-alpha..1"`, `"1.0.0+"`).
- **Resultado:** `PASSED` (24/24 casos parametrizados).
- **Estado final:** `RESOLVIDO E COMPROVADO`

### ACH-B6.1-003
- **ID:** `ACH-B6.1-003`
- **Severidade:** `P2`
- **Problema:** A existência do pacote em `importlib.metadata` era tratada como suficiente, sem comparar a versão instalada contra a restrição declarada em `requirements.txt`.
- **Causa raiz:** Ausência de parsing PEP 440 / `SpecifierSet` na verificação de dependências.
- **Arquivo e função:** `scripts/common/dependencies.py` (`parse_requirements_file`, `validate_single_dependency`) e `requirements.txt` (`packaging>=24.0`).
- **Correção:** Uso de `packaging.requirements.Requirement`, `packaging.specifiers.SpecifierSet` e `packaging.version.Version` comparando versões reais contra as restrições declaradas, separando `distribution_name` de `import_name` e classificando metadados vazios/corrompidos ou erros de parsing como `unknown`.
- **Teste que comprova a correção:** `test_ach_b61_003_version_compatibility_matrix`.
- **Resultado:** `PASSED`.
- **Estado final:** `RESOLVIDO E COMPROVADO`

### ACH-B6.1-004
- **ID:** `ACH-B6.1-004`
- **Severidade:** `P2`
- **Problema:** `schema_profile.json` e cinco outros schemas não definiam `additionalProperties: false`, permitindo propriedades desconhecidas que poderiam mascarar erros de configuração.
- **Causa raiz:** Contratos JSON originalmente omitiam `additionalProperties` na raiz e nos subobjetos fechados.
- **Arquivo e função:** Todos os 8 arquivos em `references/schemas/*.json`.
- **Correção:** Aplicado `additionalProperties: false` nas raízes e subobjetos fechados dos 8 schemas (`schema_profile.json`, `schema_achado.json`, `schema_evidencia.json`, `schema_agente.json`, `schema_iteracao.json`, `schema_relatorio_final.json`, `schema_motor.json`, `schema_input.json`), preservando os 7 perfis-piloto válidos e documentando explicitamente os objetos deliberadamente extensíveis (`metricas`, `resultados`, `tolerancias`, `payload`).
- **Teste que comprova a correção:** `test_ach_b61_004_all_eight_schemas_and_seven_profiles_valid_and_closed`.
- **Resultado:** `PASSED`.
- **Estado final:** `RESOLVIDO E COMPROVADO`

### ACH-B6.1-005
- **ID:** `ACH-B6.1-005`
- **Severidade:** `P2`
- **Problema:** O `run_manifest.json` agregava dependências de forma plana em `config`, impedindo reconstruir a associação `perfil -> motor -> dependência -> versão -> estado`.
- **Causa raiz:** `build_run_manifest()` não recebia nem validava registros estruturados por perfil/motor.
- **Arquivo e função:** `scripts/common/provenance.py` (`build_run_manifest`, `validate_run_manifest`, `save_run_manifest`) e `scripts/tools/generate_audit_reports.py`.
- **Correção:** Inclusão da hierarquia `profiles[] -> engines[] -> dependencies[]`, além de `manifest_generator_version`, `schema_validator_version`, `test_tools`, `global_eligibility`, `authorized_exceptions`, `report_references`, `integrity` e validação estrutural obrigatória antes de salvar o manifesto.
- **Teste que comprova a correção:** `test_ach_b61_005_manifest_full_profile_engine_dependency_provenance`.
- **Resultado:** `PASSED`.
- **Estado final:** `RESOLVIDO E COMPROVADO`

## 7. Testes criados e 8. Testes executados
- **Novo arquivo:** `tests/test_beta6_2_contratos_e_dependencias.py` (32 casos de teste cobrindo testes unitários, de integração, negativos e adversariais para `ACH-B6.1-001` a `ACH-B6.1-005`).
- **Regressão atualizada:** `tests/test_beta6_perfis_e_normas.py` (`test_ach_b6_008_environment_dependencies_verified` alinhado aos 5 estados normalizados).
- **Total executado:** 93 testes cobrindo ACH-001 a ACH-017, ACH-B6-001 a ACH-B6-008, ACH-B6.1-001 a ACH-B6.1-005, 7 perfis-piloto, 8 schemas e 21 motores implementados.

## 9. Resultado da suíte (ambiente virtual limpo)
- **Resultado:** `93 passed in 8.00s`
- **Falhas:** `0`
- **Warnings:** `0`
- **Log completo:** `relatorios_execucao/pytest_verbose.txt`

## 10. Cobertura global e dos componentes críticos
- **Cobertura global (`scripts/`):** **82%** (`3657` statements, `670` missed — superior ao piso de 81% da Beta 6.1).
- `scripts/common/schema_validator.py`: **96%**
- `scripts/common/dependencies.py`: **90%**
- `scripts/common/profile_loader.py`: **90%**
- `scripts/common/provenance.py`: **87%**
- **Tabela completa:** `relatorios_execucao/coverage_report.txt`

## 11. Smoke tests reais
- Todos os **21 motores implementados** (de 23 catalogados; 2 planejados para a Fase 8) + `auditor.py` foram importados e executados com validação contra `schema_motor.json` fechado (`relatorios_execucao/smoke_tests.txt`).

## 12. Ambiente utilizado e 13. Dependências instaladas no ambiente virtual limpo
- **SO:** Windows 11 (`Windows-11-10.0.26200-SP0`)
- **Python:** `3.14.6` (ambiente virtual isolado `venv_b62`, instalado exclusivamente a partir de `requirements.txt`)
- **Pacotes instalados verificados:** `numpy==2.5.5`, `scipy==1.18.1`, `sympy==1.14.0`, `python-docx==1.2.0`, `pypdf==7.1.1`, `Pillow==13.0.0`, `PyYAML==6.0.4`, `jsonschema==4.26.0`, `referencing==0.37.0`, `packaging==26.4`, `pytest==9.2.0`, `pytest-cov==7.1.0`, `coverage==7.17.5`.

## 14. Manifesto
- Gerado em `relatorios_execucao/run_manifest.json` a partir da execução real no ambiente limpo (`audited_code_commit = 92eb3c0921f4875f65aacaa418258708c6bb3495`, `git_dirty_code = False`, `global_eligibility.eligible_count = 7/7`).

## 15. Integridade SHA-256
- Gerado em `SHA256SUMS` com SHA-256 real dos bytes de cada arquivo (excluindo o próprio `SHA256SUMS`), seguido de recálculo e verificação integral pós-geração (`failed = 0`).

## 16. Limitações ainda existentes e 17. Itens deliberadamente adiados
- `motor_integracao`, `motor_meta`, `orchestrator.py` e `SKILL.md` da v8.0 permanecem deliberadamente adiados para a **Fase 8** (com base legada `v6.0` congelada em `versions/v6.0-legacy/`).
- Banca multiagente independente (`Challenger`, `Adversarial`, `Adjudicador`) permanece deliberadamente adiada para a **Fase 7** (não iniciada nesta manutenção).
- `Alucinação-OFF v2.1.0` e `Revisão Hostil v6.0` permaneceram inalteradas.

## 18. Decisão de homologação técnica local
- **APROVADA PARA PUBLICAÇÃO E REAUDITORIA EXTERNA (`v8.0-beta.6.2`)** — todos os 5 achados (`ACH-B6.1-001` P1 e `ACH-B6.1-002` a `ACH-B6.1-005` P2) foram corrigidos, testados em ambiente virtual limpo (`93/93`, `0 warnings`, `82%` cobertura) e rastreados no manifesto e checksums. O início da Fase 7 permanece condicionado à aprovação da reauditoria independente.
