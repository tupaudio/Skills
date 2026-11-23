# Skills do Antigravity — Tupã Audio & Academic Framework

[![Status](https://img.shields.io/badge/Antigravity-Skills%20Repository-blue)](https://github.com/tupaudio/Skills)
[![Revisão Hostil](https://img.shields.io/badge/Revis%C3%A3o%20Hostil-v6.0%20%7C%20v8.0--beta.6.1-orange)](./skills/revisao-hostil-v8)
[![Alucinação-OFF](https://img.shields.io/badge/Alucina%C3%A7%C3%A3o--OFF-v2.1.0-green)](./skills/alucinacao-off)
[![Tests](https://img.shields.io/badge/pytest-61%20passed-brightgreen)](./skills/revisao-hostil-v8/relatorios_execucao/pytest_verbose.txt)

Repositório oficial de **Skills autorais para o Google Antigravity**, focadas em **rigor epistêmico radical**, **auditoria científica e técnica determinística** e **verificação orientada a evidências**.

---

## Catálogo de Skills

| Skill | Versão | Pasta | Descrição |
| :--- | :---: | :--- | :--- |
| **`alucinacao-off`** | `v2.1.0` | [`skills/alucinacao-off/`](./skills/alucinacao-off) | Honestidade epistêmica e rigor técnico (taxonomia de 8 categorias, protocolo de lacunas críticas, 9 módulos disciplinares, modo criativo explícito e homologação comportamental 18/18 em [`homologacao_v2.1.md`](./skills/alucinacao-off/homologacao_v2.1.md)). |
| **`revisao-hostil`** | `v6.0` | [`skills/revisao-hostil/`](./skills/revisao-hostil) | Versão estável de produção para revisão científica crítica e forense (`.tex`, `.docx`, `.pdf`, `.md`, `.txt`) com `auditor.py`, `motor_matematico.py` (*Zero-Trust Numerical Plug-In*) e 10 Portões de Qualidade. |
| **`revisao-hostil-v8`** | `v8.0-beta.6.1` | [`skills/revisao-hostil-v8/`](./skills/revisao-hostil-v8) | Plataforma modular multidisciplinar em desenvolvimento incremental (Beta → RC → 8.0), orientada a contratos JSON (8 schemas), com **21 motores implementados** (de 23 catalogados; 2 planejados para a Fase 8), **7 perfis-piloto YAML**, máquina formal de 10 estados e **61 testes `pytest` aprovados**. |

---

## Estrutura do Repositório

```text
Skills/
├── README.md
├── .gitignore
└── skills/
    ├── alucinacao-off/
    │   └── SKILL.md
    ├── revisao-hostil/                   # v6.0 (Estável)
    │   ├── SKILL.md
    │   └── scripts/
    │       ├── auditor.py
    │       └── motor_matematico.py
    └── revisao-hostil-v8/                # v8.0-beta.6.1 (Perfis Multidisciplinares Homologados)
        ├── 00_diagnostico/               # Inventário, defeitos da v6.0 e SHA256SUMS
        ├── docs/                         # ARQUITETURA_V8.md e critérios de aceitação
        ├── references/                   # 8 JSON Schemas (incl. schema_profile.json), 7 perfis-piloto YAML, normas, vocabulários e checklists
        ├── relatorios_execucao/          # Saída do pytest -v + pytest-cov, smoke tests dos 21 motores e run_manifest.json
        ├── scripts/
        │   ├── auditor.py                # Extrator e triador modular (v8.0-beta.2)
        │   ├── common/                   # Validador de schemas, carregador de perfis SemVer 2.0.0, estados e manifesto
        │   ├── engines/                  # 21 motores determinísticos implementados (23 catalogados; 2 da Fase 8 planejados)
        │   └── tools/                    # Gerador reproduzível de relatórios, cobertura e SHA256SUMS
        ├── tests/                        # Suíte pytest (61 testes: unitários, negativos, adversariais, contratos e perfis)
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
| **Fase 6 (`v8.0-beta.6` → `v8.0-beta.6.1`)** | 7 perfis-piloto YAML, contrato executável `schema_profile.json`, SemVer 2.0.0, bloqueio `draft`/`deprecated`, verificação de dependências no ambiente, `motor_normas`, `motor_risco`, `motor_estetico` (21/23) | Concluída |
| **Fase 7 (`v8.0-beta.7`)** | Banca multiagente independente, Challenger, Adversarial e Adjudicador | Planejada |
| **Fase 8 (`v8.0-beta.8`)** | `motor_integracao`, `motor_meta`, `orchestrator.py` e `SKILL.md` v8.0 | Planejada |
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

> **Nota sobre a `revisao-hostil-v8`:** até o marco `v8.0-beta.6.1`, os 21 motores implementados (de 23 catalogados; 2 planejados para a Fase 8), os 7 perfis-piloto YAML, os 8 contratos JSON (incluindo `schema_profile.json`) e o `auditor.py` já podem ser executados diretamente via Python/CLI; o `SKILL.md` orquestrador da v8.0 será integrado na **Fase 8**. Para uso imediato como skill completa em agentes hoje, utilize `skills/revisao-hostil/` (v6.0 estável) e `skills/alucinacao-off/` (v2.1.0 homologada).

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
