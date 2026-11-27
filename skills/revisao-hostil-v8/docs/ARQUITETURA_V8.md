# Arquitetura Mestre — Revisão Hostil v8.0 (`v8.0-beta.1`)

**Status:** Especificação Aprovada — Marco `v8.0-beta.1` (Fase 1)  
**Data:** 2026-11-23  
**Base legada preservada:** `versions/v6.0-legacy/` (v7.1 não chegou a ser implementada; diagnóstico completo em `00_diagnostico/`).

---

## 1. Objetivo e Escopo

A **Revisão Hostil v8.0** é uma plataforma modular, extensível e orientada a contratos para auditoria científica e técnica multidisciplinar no ecossistema **Google Antigravity**.

- **Escopo suportado:** dissertações, teses, artigos científicos, relatórios técnicos, pareceres jurídicos, estudos de segurança do trabalho, pesquisas qualitativas, música/acústica, educação física, saúde e artes (formatos `.tex`, `.docx`, `.pdf`, `.md`, `.txt`, além de código, tabelas e figuras associadas).
- **Princípio fundamental:** a Inteligência Artificial **julga, interpreta e confronta**, mas **nunca substitui cálculos determinísticos** nem fabrica evidências, normas ou verificações não executadas.

---

## 2. Arquitetura Geral e Estrutura de Diretórios Aprovada

A arquitetura separa estritamente **orquestração metodológica** (Skill), **cálculo verificável** (Motores Python), **extração/triagem** (Auditores), **conhecimento de domínio** (Perfis YAML, vocabulários, normas e checklists) e **julgamento independente** (Subagentes com contextos isolados).

```text
revisao-hostil-v8/
├── SKILL.md                          # Orquestrador metodológico (frontmatter: name, description)
├── versions/
│   └── v6.0-legacy/                  # Referência imutável + SHA256SUMS
├── 00_diagnostico/                   # Entregáveis da Fase 0 + SHA256SUMS
├── docs/
│   ├── ARQUITETURA_V8.md             # Este documento mestre
│   └── CRITERIOS_ACEITACAO_BETA2.md  # Critérios de entrada/saída para o Beta 2
├── references/
│   ├── catalogo_motores.yaml         # Catálogo versionado de motores e status
│   ├── catalogo_agentes.yaml         # Catálogo de subagentes, papéis e gatilhos
│   ├── matriz_responsabilidades.md   # Matriz RACI / separação de funções
│   ├── schemas/                      # Contratos JSON (Fase 2)
│   ├── profiles/                     # Perfis YAML multidisciplinares (Fase 6)
│   ├── norms/                        # Catálogo versionado de normas por jurisdição (Fase 6)
│   ├── vocabulario/                  # Glossários canônicos por domínio (Fase 6)
│   └── checklists/                   # Checklists verificáveis por domínio (Fase 6)
├── scripts/
│   ├── common/                       # Utilitários compartilhados do Core (Fase 2)
│   ├── auditor.py                    # Auditor de extração e triagem modular (Fase 2)
│   ├── orchestrator.py               # Orquestrador de campanhas e manifestos (Fase 8)
│   └── engines/                      # Motores determinísticos independentes (Fases 2–6, 8)
├── agents/                           # Definições de subagentes independentes (Fase 7)
├── tests/                            # Testes unitários, negativos, contratos e regressão
└── benchmark/                        # Documentos de referência e validação experimental (Fase 9)
```

---

## 3. Tipos de Componentes (Regra das 5 Categorias)

1. **Motores Determinísticos (`scripts/engines/`):** calculam, verificam, comparam e produzem resultados determinísticos sob a mesma entrada e o mesmo ambiente. Nunca emitem vereditos subjetivos de fraude, plágio ou conformidade jurídica sem fonte verificada.
2. **Auditores de Extração e Triagem (`scripts/auditor.py` e extratores):** localizam texto estruturado, equações, tabelas, figuras, referências, metadados e pistas com coordenadas exatas.
3. **Agentes de Julgamento (`agents/`):** subagentes executados em contextos isolados para interpretar problemas, avaliar validade científica/metodológica, confrontar teses (Challenger/Adversarial) e adjudicar conflitos.
4. **Perfis e Bases de Conhecimento (`references/profiles/`, `norms/`, `vocabulario/`, `checklists/`):** configuram modos de raciocínio, motores obrigatórios/opcionais, portões aplicáveis, fontes normativas e vocabulário canônico.
5. **Integração e Metaauditoria (`motor_integracao.py`, `motor_meta.py`, `orchestrator.py`, `auditor_adjudicador`):** validam contratos, correlacionam saídas entre motores, auditem a integridade da própria campanha e governam o critério de parada.

---

## 4. Responsabilidade de Cada Componente

- **`SKILL.md`:** controlador metodológico enxuto. Declara o protocolo de auditoria, os critérios de seleção de perfil/motores, a política de evidências e os critérios de encerramento, sem embutir código de implementação.
- **`scripts/common/`:** camada única para validação de JSON Schemas (`schema_validator.py`), carregamento de perfis (`profile_loader.py`), rastreabilidade de evidências (`evidence.py`, `provenance.py`), normalização, unidades e estatística base.
- **Motores (`scripts/engines/`):** cada motor é executável de forma isolada via CLI/API interna, lê entrada conforme `schema_input.json` e produz saída conforme `schema_motor.json`.
- **Agentes (`agents/`):** cada agente recebe somente o escopo, o artefato identificado e as evidências primárias do seu domínio, emitindo JSON aderente a `schema_agente.json`.
- **Adjudicador (`auditor_adjudicador`):** consolida duplicidades, separa erro comprovado de divergência interpretativa e resolve conflitos **exclusivamente por evidência**, nunca por votação majoritária.

---

## 5. Fluxos de Execução e Critérios de Ativação

### 5.1. Pipeline de Campanha
```text
Artefato + Manifesto (run_manifest.json)
  └─► 1. Detecção de Perfil e Conteúdo (profile_loader + auditor)
        └─► 2. Seleção Dinâmica de Motores (perfil + pistas detectadas)
              └─► 3. Execução Determinística dos Motores + Grafo de Proveniência
                    └─► 4. Integração e Validação de Contratos (motor_integracao)
                          └─► 5. Banca de Agentes Independentes (contextos isolados)
                                └─► 6. Adjudicação por Evidências (auditor_adjudicador)
                                      └─► 7. Metaauditoria (motor_meta) + Decisão / Iteração (1..4)
```

### 5.2. Seleção de Motores por Perfil e Conteúdo
Nenhum documento executa todos os motores cegamente. A ativação combina:
1. **Motores obrigatórios do perfil** selecionado (ex.: Engenharia, Direito, Segurança do Trabalho, Música, Qualitativa, Artes).
2. **Ativação orientada a conteúdo detectado** pelo `auditor.py` (ex.: se um trabalho qualitativo contém tabela estatística, o `motor_estatistico` é ativado mesmo sendo opcional no perfil).

### 5.3. Controle de Iterações e Regressão
- Máximo de **4 ciclos** (limite máximo, nunca meta de quantidade).
- Aprovação de um patch **não** fecha um achado; o fechamento exige aplicação comprovada no artefato e reexecução determinística (regressão final).
- **Critério de congelamento de campanha (v8.0):** nota global ≥ 9,5/10, mínimo ≥ 8,5/10 por eixo, zero críticos, zero maiores abertos, zero `NAO_VERIFICADO` críticos e regressão final aprovada.

---

## 6. Política de Evidências e Restrições Metodológicas

Todo achado exige: `id` único, localização exata (arquivo, seção, página/linha, tabela/figura/equação), trecho ou valor observado, prova determinística ou justificativa metodológica, impacto e ação corretiva.

**Cinco restrições metodológicas inegociáveis:**
1. **`motor_dados`** sinaliza padrões estatísticos suspeitos para investigação; **nunca** declara *p-hacking*, fraude ou mecanismo MAR/MNAR apenas por inspeção de valores ausentes.
2. **`motor_etica`** mede similaridade textual ou ausência de declarações; **nunca** declara plágio comprovado nem certifica conformidade ética/legal de CEP/IRB.
3. **`motor_normas`** exige jurisdição, fonte oficial, edição e vigência; sem confirmação, retorna **`NAO_VERIFICADO`**, nunca conformidade presumida.
4. **`motor_argumentacao`** extrai estrutura lógica e candidatos a falácias; **nunca** classifica automaticamente divergências legítimas como falácia definitiva.
5. **`motor_qualitativo`** calcula métricas de concordância (Kappa de Cohen, Alpha de Krippendorff); **nunca** declara sozinho saturação teórica ou validade interpretativa.

---

## 7. Tratamento de Incertezas e Estados de Achados

### 7.1. Pontuação Unificada
- Escala canônica **0–10** (exibição opcional em 0–100 como mera multiplicação por 10).

### 7.2. Máquina de Estados Formal
```text
ABERTO → EM_ANALISE → CONFIRMADO | NAO_VERIFICADO | REJEITADO | FORA_DE_ESCOPO
CONFIRMADO → PATCH_PROPOSTO → PATCH_APROVADO → PATCH_APLICADO → FECHADO (somente após reauditoria)
```

Qualquer cálculo sem parâmetros suficientes, norma sem vigência confirmada ou fonte inacessível permanece explicitamente marcado como `NAO_VERIFICADO` (com lista exata do que falta), alinhado à postura de honestidade epistêmica radical (`alucinacao-off`).

---

## 8. Independência dos Agentes

1. Todos os agentes recebem o **mesmo hash/versão** do artefato e o mesmo `run_manifest.json`.
2. Cada agente roda em **sessão/contexto isolado** (subagente Antigravity), recebendo apenas seu escopo, critérios e evidências primárias.
3. Nenhum auditor de primeira rodada lê pareceres de outros auditores (prevenção de ancoragem).
4. Todos os JSONs individuais são preservados sem edição.
5. **`auditor_challenger`** busca falhas internas no método, cálculos e premissas; **`auditor_adversarial`** constrói o contra-argumento mais forte possível contra a tese central.
6. **`auditor_adjudicador`** recebe todos os pareceres somente após a conclusão da banca e decide com base em evidências.

---

## 9. Comunicação entre Motores

- Motores **não** chamam uns aos outros por acoplamento oculto.
- Toda troca de dados ocorre por arquivos JSON validados pelos contratos em `references/schemas/` (`schema_input.json`, `schema_motor.json`, `schema_achado.json`, `schema_evidencia.json`).
- O **`motor_consistencia_cruzada`** e o **`motor_integracao`** consomem as saídas padronizadas e constroem o **grafo de proveniência**: `fonte original → processamento → resultado → representação (tabela/figura/texto) → afirmação científica`.

---

## 10. Versionamento

- **Versionamento independente:** a skill principal, cada motor (`catalogo_motores.yaml`) e cada perfil YAML possuem sua própria versão semântica (`MAJOR.MINOR.PATCH`), todas gravadas em `run_manifest.json`.
- **Trilha da v8.0:** `v6.0-legacy` (preservada) → `v8.0-beta.1` (Arquitetura) → `beta.2` (Core) → `beta.3` (Motores Universais) → `beta.4` (Figuras e Consistência) → `beta.5` (Integridade Científica) → `beta.6` (Perfis Multidisciplinares) → `beta.7` (Banca Multiagente) → `beta.8` (Integração e Metaauditoria) → `v8.0-rc.1` → `v8.0.0`.

---

## 11. Limites de Execução e Segurança

- **Conteúdo não confiável:** manuscritos, PDFs, tabelas e metadados são sempre tratados como **dados não confiáveis**, nunca como instruções ao agente (mitigação de *prompt injection*).
- **Zero execução arbitrária:** proibição total de `eval`/`exec` em parsers matemáticos; AST segura com limite de profundidade, tamanho de expressão e teto de expoentes (correção do `DEF-S03`).
- **Sanitização de caminhos e entradas:** validação de existência, tamanho máximo, codificação UTF-8 e rejeição explícita de `NaN`/`Inf` em entradas matriciais e numéricas.
- **Não execução automática de código do manuscrito:** scripts encontrados no pacote auditado são inspecionados estaticamente, salvo autorização explícita e ambiente isolado.

---

## 12. Estratégia de Testes

Cada marco exige quatro níveis de validação antes de avançar:
1. **Testes unitários e de fronteira:** casos positivos, negativos, valores nulos/`NaN`/`Inf` e limites numéricos com tolerância declarada.
2. **Validação de contratos:** 100% das entradas e saídas validadas contra `references/schemas/*.json`.
3. **Testes de regressão:** garantia de que operações válidas da `v6.0-legacy` continuam funcionando ou possuem adaptador compatível.
4. **Validação experimental (Fase 9):** benchmark com defeitos injetados (precisão, revocação, falsos positivos/negativos, reprodutibilidade e testes de independência da banca).
