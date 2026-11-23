# Critérios de Aceitação — Transição Beta 1 → Beta 2 (`v8.0-beta.2`)

**Marco de origem:** `v8.0-beta.1` (Fase 0 + Fase 1 concluídas)  
**Marco alvo:** `v8.0-beta.2` (Fase 2 — Core estabilizado)

---

## 1. Pré-requisitos de Entrada no Beta 2 (Atendidos no Beta 1)
- [x] Base legada congelada em `versions/v6.0-legacy/` com `SHA256SUMS`.
- [x] Diagnóstico completo salvo em `00_diagnostico/` com todos os componentes classificados (`aproveitavel`, `corrigivel`, `substituivel`, `descartavel`) e `SHA256SUMS`.
- [x] Documento mestre `docs/ARQUITETURA_V8.md` criado cobrindo todos os 12 tópicos obrigatórios.
- [x] Catálogos `references/catalogo_motores.yaml`, `references/catalogo_agentes.yaml` e `references/matriz_responsabilidades.md` criados sem sobreposição de papéis.
- [x] Nenhum motor novo implementado antes da conclusão do Beta 1.

---

## 2. Entregáveis Obrigatórios do Beta 2 (`v8.0-beta.2`)

1. **Contratos JSON (`references/schemas/`):**
   - `schema_input.json`
   - `schema_motor.json`
   - `schema_achado.json`
   - `schema_agente.json`
   - `schema_evidencia.json`
   - `schema_iteracao.json`
   - `schema_relatorio_final.json`
2. **Utilitários compartilhados (`scripts/common/`):**
   - `schema_validator.py`, `profile_loader.py`, `evidence.py`, `validation.py`, `text_normalize.py`, `citation.py`, `provenance.py`, `units.py`, `statistics.py`.
3. **Estabilização de `motor_matematico.py`:**
   - Correção comprovada de todos os defeitos catalogados (`DEF-M01` a `DEF-M08` + `DEF-S03` de limite de AST/expoente).
   - Preservação de compatibilidade com todas as 13 operações válidas da `v6.0-legacy`.
   - Saída padronizada aderente a `schema_motor.json`.
4. **Refatoração modular de `auditor.py`:**
   - Correção do bug `DEF-A01` (regex `100%`).
   - Separação entre extração genérica (texto, equações, tabelas, referências, metadados) e regras de domínio (preparadas para perfis YAML).
   - Saída aderente a `schema_achado.json` / `schema_motor.json`.
5. **Pontuação unificada e máquina de estados:**
   - Escala canônica `0–10` (exibição opcional `0–100`) e todos os 10 estados formais (`ABERTO` até `FORA_DE_ESCOPO`), exigindo reauditoria para `FECHADO`.
6. **Manifesto de execução (`run_manifest.json`):**
   - Gerador determinístico contendo versões (skill, motores, perfis), hashes SHA-256 dos arquivos, ambiente Python, dependências, sementes, data/hora e limitações.
7. **Dependências de desenvolvimento:**
   - `PyYAML` e `jsonschema` instalados e documentados em `requirements.txt` / `pyproject.toml`.

---

## 3. Critérios de Saída (Gate do Beta 2)

O Beta 2 só poderá ser marcado como concluído quando:
- [ ] `pytest` passar 100% nos testes unitários, negativos, de fronteira (`NaN`, `Inf`, entradas malformadas) e de regressão da `v6.0-legacy`.
- [ ] 100% das saídas do `auditor.py` e `motor_matematico.py` passarem no `schema_validator.py`.
- [ ] O Core executar isoladamente sem depender de nenhum motor da Fase 3+.
- [ ] Nenhum defeito crítico ou maior de `00_diagnostico/relatorio_defeitos.md` permanecer aberto no Core.
