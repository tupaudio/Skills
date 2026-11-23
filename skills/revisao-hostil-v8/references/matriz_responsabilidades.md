# Matriz de Responsabilidades — Revisão Hostil v8.0 (`v8.0-beta.1`)

Esta matriz garante que **cada função crítica tenha um único proprietário**, evitando duplicidade entre motores determinísticos e agentes de julgamento.

---

## 1. Separação Cálculo vs. Julgamento

| Função Crítica | Proprietário Determinístico (Calcula / Extrai) | Proprietário de Julgamento (Interpreta / Decide) | Regra de Fronteira |
| :--- | :--- | :--- | :--- |
| Extração estrutural e pistas | `auditor.py` | — | Apenas localiza e gera pistas; nunca emite veredito final. |
| Matemática, matrizes e EDOs | `motor_matematico.py` | `auditor_dominio` / `auditor_engenharia` | O motor prova a conta; o agente avalia o significado físico/teórico. |
| Homogeneidade dimensional | `motor_dimensional.py` | `auditor_dominio` | Motor detecta incompatibilidade; agente avalia impacto na modelagem. |
| Cálculos estatísticos | `motor_estatistico.py` | `auditor_estatistico` | Motor executa testes/IC/poder; agente julga pressupostos e interpretação. |
| Integridade e anomalias de dados | `motor_dados.py` | `auditor_dados` | Motor aponta faltantes/outliers/vazamento; agente investiga coleta/viés. |
| Geometria e incerteza | `motor_geometrico.py`, `motor_incerteza.py` | `auditor_engenharia` / `auditor_empirico` | Motores quantificam; agentes julgam suficiência das margens. |
| Linguagem e nomenclatura | `motor_linguagem.py`, `motor_nomenclatura.py` | `auditor_clareza` | Motores sinalizam termos/siglas; agente julga clareza e precisão semântica. |
| Figuras, tabelas e imagem forense | `motor_figuras.py`, `motor_imagem_forense.py` | `auditor_visual` | Motores medem DPI/metadados; agente inspeciona correspondência visual-texto. |
| Consistência cruzada (Efeito Dominó) | `motor_consistencia_cruzada.py` | `auditor_reprodutibilidade` / `auditor_challenger` | Motor constrói grafo de proveniência; agentes avaliam gravidade sistêmica. |
| Ética e integridade | `motor_etica.py` | `auditor_etico` | Motor checa declarações/similaridade; agente faz juízo ético (sem acusar plágio automático). |
| Argumentação e evidência | `motor_argumentacao.py`, `motor_evidencia.py` | `auditor_metodologia` / `auditor_adversarial` | Motores estruturam alegações/hierarquia; agentes avaliam força inferencial. |
| Normas, leis e vigência | `motor_normas.py`, `motor_temporal.py` | `auditor_juridico` / `auditor_editorial` | Motor valida fonte e vigência (ou `NAO_VERIFICADO`); agente interpreta subsunção. |
| Codificação qualitativa | `motor_qualitativo.py` | `auditor_metodologia` / `auditor_dominio` | Motor calcula Kappa/Alpha; agente julga saturação e validade interpretativa. |
| Pacote e reprodutibilidade | `motor_metadados.py`, `motor_reprodutibilidade.py` | `auditor_reprodutibilidade` / `auditor_editorial` | Metadados = integridade do pacote; Reprodutibilidade = reconstrução dos resultados. |
| Integração e contratos | `motor_integracao.py`, `schema_validator.py` | `auditor_adjudicador` | Integrador valida schemas/conflitos numéricos; Adjudicador resolve conflitos por evidência. |
| Auditoria da auditoria | `motor_meta.py` | `auditor_meta` | Motor checa cobertura/estados/parada; agente avalia profundidade científica. |

---

## 2. Critérios de Ativação de Motores (Perfil + Conteúdo)

| Tipo de Documento / Perfil | Motores Prioritários | Agentes Extras Ativados |
| :--- | :--- | :--- |
| Dissertação / Artigo de Engenharia | `motor_matematico`, `motor_dimensional`, `motor_estatistico`, `motor_incerteza`, `motor_figuras`, `motor_consistencia_cruzada`, `motor_reprodutibilidade` | `auditor_engenharia`, `auditor_dados`, `auditor_estatistico` |
| Segurança do Trabalho | `motor_estatistico`, `motor_dados`, `motor_normas`, `motor_risco`, `motor_temporal`, `motor_etica` | `auditor_engenharia`, `auditor_etico`, `auditor_juridico` |
| Trabalho Jurídico | `motor_normas`, `motor_temporal`, `motor_argumentacao`, `motor_evidencia`, `motor_linguagem` | `auditor_juridico`, `auditor_adversarial` |
| Pesquisa Musical / Acústica | `motor_matematico`, `motor_estatistico`, `motor_figuras`, `motor_nomenclatura` (+ futuros `motor_musical`, `motor_acustico`) | `auditor_empirico`, `auditor_artistico` |
| Pesquisa Qualitativa | `motor_qualitativo`, `motor_etica`, `motor_argumentacao`, `motor_evidencia`, `motor_linguagem` | `auditor_etico`, `auditor_adversarial` |
| Trabalho de Artes | `motor_figuras`, `motor_imagem_forense`, `motor_estetico`, `motor_linguagem`, `motor_temporal` | `auditor_visual`, `auditor_artistico` |

---

## 3. Controle de Redundância entre Agentes (Matriz de Sobreposição)

| Comparação | Fronteira Obrigatória a Auditar |
| :--- | :--- |
| `auditor_dominio` × `auditor_engenharia` | Validade científica/teórica vs. viabilidade prática e termos omitidos. |
| `auditor_dominio` × `auditor_metodologia` | Erro conceitual da disciplina vs. falha de desenho de estudo ou comparadores. |
| `auditor_metodologia` × `auditor_estatistico` | Cobertura do desenho metodológico vs. pressupostos e inferência estatística especializada. |
| `auditor_clareza` × `motor_linguagem` | Julgamento editorial/semântico vs. sinalização determinística de siglas e jargões. |
| `auditor_challenger` × `auditor_adversarial` | Contradições e falhas internas no método entregue vs. contra-argumento máximo contra a tese central. |
| `auditor_editorial` × `auditor_juridico` | Normalização bibliográfica/template vs. hierarquia normativa, precedentes e vigência legal. |
