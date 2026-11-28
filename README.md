# Skills do Antigravity — Tupã Audio & Academic Framework

[![Status](https://img.shields.io/badge/Antigravity-Skills%20Repository-blue)](https://github.com/tupaudio/Skills)
[![Revisão Hostil](https://img.shields.io/badge/Revis%C3%A3o%20Hostil-v8.1.0--beta.2-orange)](./skills/revisao-hostil-v8)
[![Alucinação-OFF](https://img.shields.io/badge/Alucina%C3%A7%C3%A3o--OFF-v2.1.0-green)](./skills/alucinacao-off)
[![Tests](https://img.shields.io/badge/pytest-524%20passed-brightgreen)](#como-rodar-os-testes-da-revisao-hostil-v8)

Repositório oficial de **Skills autorais para o Google Antigravity**, focadas em **rigor epistêmico radical**, **auditoria científica e técnica determinística** e **verificação orientada a evidências**.

---

## Catálogo de Skills

| Skill | Versão | Pasta | Descrição |
| :--- | :---: | :--- | :--- |
| **`alucinacao-off`** | `v2.1.0` | [`skills/alucinacao-off/`](./skills/alucinacao-off) | Honestidade epistêmica e rigor técnico (taxonomia de 8 categorias, protocolo de lacunas críticas, 9 módulos disciplinares, modo criativo explícito e homologação comportamental 18/18 em [`homologacao_v2.1.md`](./skills/alucinacao-off/homologacao_v2.1.md)). |
| **`revisao-hostil`** | `v6.0` | [`skills/revisao-hostil/`](./skills/revisao-hostil) | Versão estável legada de produção para revisão científica crítica e forense (`.tex`, `.docx`, `.pdf`, `.md`, `.txt`) com `auditor.py`, `motor_matematico.py` (*Zero-Trust Numerical Plug-In*) e 10 Portões de Qualidade. |
| **`revisao-hostil-v8`** | `v8.1.0-beta.2` | [`skills/revisao-hostil-v8/`](./skills/revisao-hostil-v8) | Plataforma modular multidisciplinar em desenvolvimento incremental, orientada a contratos JSON fechados (8 schemas), com **21 motores implementados** (de 23 catalogados; 2 planejados para a Fase 8), **7 perfis-piloto YAML**, parser fail-closed de `requirements.txt`, bloqueio efetivo de dependências/versões (`packaging`), validação estrita de cabeçalho `RUN_ID=` (`validate_artifact_run_id`) + inventário independente (`build_expected_checksum_inventory`), máquina formal de 10 estados e **524 testes `pytest` aprovados** em ambiente limpo. |

---

## Estado e Limitações (`revisao-hostil-v8`)

- **Classificação:** Beta para uso pessoal. Não é instrumento validado para avaliação de conformidade ou certificação.
- **Evidência empírica e benchmark:** Os resultados existentes constituem piloto exploratório e descritivo. Os resultados do piloto R6 foram obtidos no commit histórico `7677de3` e correspondem a uma precisão reportada de 70% (7/10) sobre 10 predições avaliadas em 15 artigos, valor não reconciliado com o total de 50 achados `CONFIRMADO` gerados na ocasião, não sendo generalizável nem aplicável a esta versão dos motores. A suíte automatizada (524 testes) atesta conformidade dos motores contra entradas controladas, não completude de detecção (recall) em manuscritos arbitrários.
- **Validação prática:** A validação prática em ambiente real ainda não foi realizada.
- **Operações simbólicas:** No `motor_matematico`, operações simbólicas não possuem timeout rígido em nível de processo ou thread; expressões de alta complexidade ou fortemente não-lineares podem elevar substancialmente a latência de execução. A operação `proven_different` assume símbolos genéricos em $\mathbb{C}$ sem hipóteses restritivas de domínio (como positividade ou intervalos reais restritos), podendo reportar inequivalência quando a igualdade dependeria de restrições tácitas do autor.
- **Segurança de caminhos:** Validação de caminho com tamanho máximo delimitado e saneamento numérico em `scripts/common/validation.py`, mas opera sem raiz autorizada restrita (*chroot/sandbox* nativo).
- **Extração de manuscritos (DOCX e PDF):**
  - Em DOCX, o auditor extrai parágrafos do corpo, linhas de tabelas (com deduplicação de células mescladas) e cabeçalhos/rodapés de seções, cobrindo casos inspecionados.
  - Em PDF, a extração via `pypdf` lê texto corrido plano por página; tabelas e layouts colunados não possuem segmentação semântica nativa no PDF. A extração de números e grandezas a partir de texto livre é inerentemente frágil.
- **Semântica de envelopes e achados:** `PARCIAL` e `NAO_VERIFICADO` significam estritamente **"não verificado"**, indicando ausência de verificação completa ou empate de autoridade/inconclusão, e **nunca** aprovação, atestado de correção ou erro do autor.

---

## Estrutura do Repositório

```text
Skills/
├── README.md
├── .gitignore
└── skills/
    ├── alucinacao-off/
    │   └── SKILL.md
    ├── revisao-hostil/                   # v6.0 (Estável legada)
    │   ├── SKILL.md
    │   └── scripts/
    │       ├── auditor.py
    │       └── motor_matematico.py
    └── revisao-hostil-v8/                # v8.1.0-beta.1
        ├── 00_diagnostico/               # Inventário, defeitos da v6.0 e SHA256SUMS
        ├── docs/                         # ARQUITETURA_V8.md e critérios de aceitação
        ├── references/                   # 8 JSON Schemas fechados, 7 perfis-piloto YAML, normas, vocabulários e checklists
        ├── relatorios_execucao/          # Relatórios de execução e documentação de testes
        ├── scripts/
        │   ├── auditor.py                # Extrator e triador modular
        │   ├── common/                   # Validador de schemas, SemVer 2.0.0, parser fail-closed + packaging, estados e evidência
        │   ├── engines/                  # 21 motores determinísticos implementados (23 catalogados; 2 da Fase 8 planejados)
        │   └── tools/                    # Ferramentas auxiliares de inventário e manifesto
        ├── tests/                        # Suíte pytest (524 testes: unitários, integração, negativos, adversariais, regressão e valores de referência)
        ├── versions/v6.0-legacy/         # Base legada congelada com SHA256SUMS
        ├── pytest.ini
        ├── requirements.txt
        └── SHA256SUMS
```

---

## Roadmap da Revisão Hostil v8.0

| Marco | Escopo | Status |
| :--- | :--- | :---: |
| **Fase 0 + Fase 1 (`v8.0-beta.1`)** | Congelamento v6.0, diagnóstico forense, arquitetura mestre, catálogos e matriz RACI | Concluída |
| **Fase 2 (`v8.0-beta.2`)** | 7 JSON Schemas, `scripts/common/`, correções do Core, 10 estados e `run_manifest.json` | Concluída |
| **Fase 3 (`v8.0-beta.3`)** | Motores universais: dimensional, estatístico, geométrico, incerteza e integridade de dados | Concluída |
| **Fase 4 (`v8.0-beta.4`)** | Linguagem, figuras + inventário visual, imagem forense e consistência cruzada | Concluída |
| **Fase 5 (`v8.0-beta.5`)** | Ética, argumentação, evidência, temporal, nomenclatura, metadados, reprodutibilidade e qualitativo (tag histórica) | Concluída |
| **Estabilização (`v8.0-beta.5.1` → `v8.0-beta.5.3`)** | Remediação completa da auditoria externa (`ACH-001` a `ACH-017`), 52 testes (0 warnings), cobertura `pytest-cov`, venv limpo validado e manifesto portável | Concluída |
| **Fase 6 (`v8.0-beta.6` → `v8.0-beta.6.6`)** | 7 perfis-piloto YAML, 8 schemas JSON fechados (`additionalProperties: false`), SemVer 2.0.0 `fullmatch()`, parser fail-closed de `requirements.txt` + detecção de conflitos (incl. `~=`), bloqueio efetivo de dependências (`packaging`), cabeçalho estrito `RUN_ID=` (`validate_artifact_run_id`) + inventário independente (`build_expected_checksum_inventory`) + segurança de caminhos, `motor_normas`, `motor_risco`, `motor_estetico` (21/23, 178 testes em venv limpo) | Concluída |
| **Consolidação dos Motores (`v8.1.0-beta.1`)** | Fortalecimento dos 21 motores determinísticos: precedência de equivalência simbólica comprovada em fórmulas, convergência e validação estrita de identificadores em EDOs, obrigatoriedade de `source_type` reconhecido e validação de `dict` em consistência cruzada, poder estatístico exato via `scipy.stats.nct.sf`, envelopes estruturados e isolamento de falhas por item em lotes, limites defensivos de recursos (AST, matrizes, EDOs), leitura delimitada (`read_bounded_json`) e 524 testes `pytest` aprovados | Concluída |
| **Fase 7 (`v8.0-beta.7`)** | Banca multiagente independente, Challenger, Adversarial e Adjudicador | Planejada |
| **Fase 8 (`v8.0-beta.8`)** | `motor_integracao`, `motor_meta` e orquestrador automatizado (`orchestrator.py`); o `SKILL.md` atual é um protocolo executado manualmente | Planejada |
| **Fase 9 + 10 (`v8.0-rc.1` → `v8.0.0`)** | Benchmark experimental, revisão adversarial externa, instalação limpa e congelamento | Planejada |

---

## Como Instalar e Usar (Antigravity e Outras IAs)

Como as skills deste repositório seguem o padrão aberto **`SKILL.md` (YAML + Markdown) + scripts Python independentes**, elas funcionam no **Google Antigravity** e também em **outras IAs e agentes de código**.

### 1. Clonar o repositório
```bash
git clone https://github.com/tupaudio/Skills.git
```

### 2. Google Antigravity
- **Global (todos os projetos):** copie a pasta desejada de `skills/` para:
  - **Windows:** `%USERPROFILE%\.gemini\config\skills\<nome-da-skill>\`
  - **Linux / macOS:** `~/.gemini/config/skills/<nome-da-skill>/`
- **Por projeto (workspace):** copie para `.agents/skills/<nome-da-skill>/` na raiz do seu repositório.

### 3. Claude Code / Claude Desktop (Anthropic)
- **Claude Code:** copie a pasta da skill para `~/.claude/skills/<nome-da-skill>/` (global) ou `.claude/skills/<nome-da-skill>/` (no projeto).
- **Claude Web / Desktop:** crie um *Project* e anexe o `SKILL.md` (e, quando quiser cálculos determinísticos, os scripts de `scripts/`) em *Project Knowledge*.

### 4. OpenAI Codex CLI / ChatGPT
- **Codex CLI:** copie para `.agents/skills/<nome-da-skill>/` no repositório ou referencie o `SKILL.md` no `AGENTS.md`.
- **ChatGPT (Plus/Pro/Team):** crie um *Project* ou *Custom GPT*, adicione o `SKILL.md` nas instruções/arquivos de conhecimento e habilite o **Code Interpreter** para executar os scripts Python de `scripts/`.

### 5. Cursor, Windsurf, Cline e GitHub Copilot
- **Cursor:** copie ou referencie o conteúdo do `SKILL.md` em `.cursor/rules/<nome-da-skill>.mdc` (ou `.agents/skills/`).
- **Windsurf / Cline:** coloque o `SKILL.md` em `.windsurf/rules/` ou `.clinerules/`.
- **GitHub Copilot:** referencie as instruções em `.github/copilot-instructions.md` (ou `.github/instructions/`).

### 6. Uso Independente via Terminal / CI (sem IA)
Os motores determinísticos da `revisao-hostil-v8` e o `auditor.py` funcionam de forma 100% autônoma via CLI Python + JSON, sem depender de nenhuma plataforma de IA:

```bash
cd skills/revisao-hostil-v8
pip install -r requirements.txt
python scripts/auditor.py caminho/para/manuscrito.tex --out relatorio_auditor.json
python scripts/engines/motor_matematico.py --input payload.json --out resultado_motor.json
```

> **Nota sobre a `revisao-hostil-v8`:** os 21 motores implementados (de 23 catalogados; 2 planejados para a Fase 8), os 7 perfis-piloto YAML, os 8 contratos JSON fechados e o `auditor.py` já podem ser executados diretamente via Python/CLI com parser fail-closed de `requirements.txt`, bloqueio efetivo de dependências e validação estrita de cabeçalho `RUN_ID=` + inventário independente `SHA256SUMS`. O `SKILL.md` atual é um protocolo executado manualmente; o orquestrador automatizado (`orchestrator.py`) é da **Fase 8**. Para uso em agentes hoje, utilize `skills/revisao-hostil-v8/` ou `skills/alucinacao-off/` (v2.1.0 homologada).

---

## Como Rodar os Testes da `revisao-hostil-v8`

```bash
cd skills/revisao-hostil-v8
pip install -r requirements.txt
python -m pytest -v
```

---

## Princípios de Integridade

- **IA julga, motores calculam:** nenhum resultado numérico, dimensional, estatístico ou de consistência cruzada é presumido sem verificação determinística.
- **Restrições metodológicas ativas:** similaridade textual não equivale a plágio comprovado; anomalias de dados ou valores-p não equivalem a fraude/*p-hacking*; ausência de metadados de imagem não prova manipulação; normas sem vigência confirmada retornam `NAO_VERIFICADO`.

---

**Autoria:** Thor Barros / Tupã Audio & Antigravity Academic Framework  
**Licença:** MIT
