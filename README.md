# Skills do Antigravity — Tupã Audio & Academic Framework

[![Status](https://img.shields.io/badge/Antigravity-Skills%20Repository-blue)](https://github.com/tupaudio/Skills)
[![Revisão Hostil](https://img.shields.io/badge/Revis%C3%A3o%20Hostil-v6.0%20%7C%20v8.0--beta.5-orange)](./skills/revisao-hostil-v8)
[![Alucinação-OFF](https://img.shields.io/badge/Alucina%C3%A7%C3%A3o--OFF-v1.0-green)](./skills/alucinacao-off)
[![Tests](https://img.shields.io/badge/pytest-41%20passed-brightgreen)](./skills/revisao-hostil-v8/relatorios_execucao/pytest_verbose.txt)

Repositório oficial de **Skills autorais para o Google Antigravity**, focadas em **rigor epistêmico radical**, **auditoria científica e técnica determinística** e **verificação orientada a evidências**.

---

## Catálogo de Skills

| Skill | Versão | Pasta | Descrição |
| :--- | :---: | :--- | :--- |
| **`alucinacao-off`** | `v1.0` | [`skills/alucinacao-off/`](./skills/alucinacao-off) | Ativa postura de honestidade epistêmica radical e tolerância zero a chutes ou preenchimento arbitrário de parâmetros em engenharia, eletrônica, RF, física, matemática e pesquisa científica. |
| **`revisao-hostil`** | `v6.0` | [`skills/revisao-hostil/`](./skills/revisao-hostil) | Versão estável de produção para revisão científica crítica e forense (`.tex`, `.docx`, `.pdf`, `.md`, `.txt`) com `auditor.py`, `motor_matematico.py` (*Zero-Trust Numerical Plug-In*) e 10 Portões de Qualidade. |
| **`revisao-hostil-v8`** | `v8.0-beta.5` | [`skills/revisao-hostil-v8/`](./skills/revisao-hostil-v8) | Plataforma modular multidisciplinar em desenvolvimento incremental (Beta → RC → 8.0), orientada a contratos JSON, com **18 motores determinísticos**, rastreabilidade de evidências, máquina formal de 10 estados e **34 testes `pytest` aprovados**. |

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
    └── revisao-hostil-v8/                # v8.0-beta.5 (Desenvolvimento Incremental)
        ├── 00_diagnostico/               # Inventário, defeitos da v6.0 e SHA256SUMS
        ├── docs/                         # ARQUITETURA_V8.md e critérios de aceitação
        ├── references/                   # 7 JSON Schemas, catálogos de motores/agentes e matriz RACI
        ├── relatorios_execucao/          # Saída do pytest -v, smoke tests CLI e run_manifest.json
        ├── scripts/
        │   ├── auditor.py                # Extrator e triador modular (v8.0-beta.2)
        │   ├── common/                   # Validador de schemas, estados, pontuação, manifesto e utilitários
        │   └── engines/                  # 18 motores determinísticos (Fases 2 a 5)
        ├── tests/                        # Suíte pytest (unitários, negativos, contratos e regressão)
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
| **Fase 5 (`v8.0-beta.5`)** | Ética, argumentação, evidência, temporal, nomenclatura, metadados, reprodutibilidade e qualitativo | Concluída |
| **Fase 6 (`v8.0-beta.6`)** | Perfis YAML multidisciplinares, `motor_normas` e motores especializados | Planejada |
| **Fase 7 (`v8.0-beta.7`)** | Banca multiagente independente, Challenger, Adversarial e Adjudicador | Planejada |
| **Fase 8 (`v8.0-beta.8`)** | `motor_integracao`, `motor_meta`, `orchestrator.py` e `SKILL.md` v8.0 | Planejada |
| **Fase 9 + 10 (`v8.0-rc.1` → `v8.0.0`)** | Benchmark experimental, revisão adversarial externa, instalação limpa e congelamento | Planejada |

---

## Como Instalar no Antigravity

### Instalação Global (todos os projetos)
Copie a pasta da skill desejada dentro de `skills/` para o diretório global de skills do Antigravity:

- **Windows:** `%USERPROFILE%\.gemini\config\skills\<nome-da-skill>\`
- **Linux / macOS:** `~/.gemini/config/skills/<nome-da-skill>/`

### Instalação por Workspace (projeto específico)
Copie a pasta da skill desejada para `.agents/skills/<nome-da-skill>/` na raiz do seu repositório.

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
