# Changelog — Revisão Hostil v8

Consolidação das correções, limites defensivos e fortalecimento dos 21 motores determinísticos da Skill Revisão Hostil v8.

---

## v8.1.0-beta.3 (2026-11-28)

- **`motor_consistencia_cruzada` (`0.3.0-beta.1` -> `0.4.0-beta.1`)**: `location` (string não vazia após `strip`) passou a ser obrigatório em cada observação quando há 2 ou mais observações (**quebra de contrato**: payloads sem `location` ou com `location` `None`/vazio/não-string passam a gerar erro da grandeza com `status: error`, isolado em lote); achados deixam de sair com `"None"` ou `"desconhecido"`. Ordem de validação: `len < 2`, `obs` `dict`, `source_type`, `location`.
- **`SKILL.md`**: documentada a obrigatoriedade de `location` e acrescentadas as definições de `ERRO_VALIDACAO`, `ERRO_EXECUCAO` (verificação não ocorreu; não indicam erro no manuscrito) e `PARCIAL` em lote (pelo menos um item falhou ou ficou inconclusivo; demais resultados válidos) na seção "Como interpretar os estados".
- **Limitações conhecidas:** `benchmark/cases.json` contém o gabarito do benchmark dentro do repositório; continuam no HEAD com o nome do autor e/ou caminhos locais: `benchmark/cases.json` (travado por `validation_cases_sha256` da R3 e lido em `bench.py`), `benchmark/PREREGISTRO_R3.md` (mantido coerente com `cases.json`), `skills/revisao-hostil/SKILL.md` (skill v6.0 mantida intacta), `versions/v6.0-legacy/SKILL.md` (cópia imutável com `SHA256SUMS` próprio), `benchmark/posthoc_r3.py`, `benchmark/prepare_blind_dir.py` e `benchmark/PREREGISTRO.md`; e-mail do autor e caminhos locais permanecem em commits e tags já publicados (histórico do Git); 53 arquivos da skill não constam no `SHA256SUMS` raiz (`CHANGELOG.md`, `benchmark/*`, parte de `tests/*`, `00_diagnostico/SHA256SUMS` e `versions/v6.0-legacy/SHA256SUMS`), decisão registrada para revisão em uma versão futura.

---

## v8.1.0-beta.2 (2026-11-28)

- `SKILL.md` (regra 7): separação entre modo dissertação (padrão, priorização por gravidade sem teto fixo e aviso de omissões) e modo benchmark R6 (teto de 5 `CONFIRMADO`), mantendo a proibição de emitir checagens bem-sucedidas como achado.
- `SKILL.md` (segurança): corrigido o escopo de `hash_artefato` para registrar que apenas `auditor.py` e `motor_estetico` emitem SHA-256 do artefato e os demais motores retornam `null`.
- `SKILL.md`: adicionada seção "Como interpretar os estados" (`PARCIAL`, `NAO_VERIFICADO`, `sample_too_small`, `inconclusive`, `numerically_equal_at_samples` e `solver_failed` significam "não verificado", nunca aprovação nem erro confirmado).
- `SKILL.md` (`motor_consistencia_cruzada`): documentada a recomendação de informar `location` em cada observação (com 2+ observações), pois sem `location` o achado sai com localização `"None"` (assimétrico) ou `"desconhecido"` (empate).
- `SKILL.md`: registrado que o CI roda em Ubuntu e Windows, Python 3.12 e 3.14 (GitHub Actions).
- `README.md`: esclarecido que o `SKILL.md` atual é um protocolo executado manualmente e que o orquestrador automatizado (`orchestrator.py`) é da Fase 8.
- `relatorios_execucao/LEIA-ME.md`: criado aviso de que os relatórios da pasta são históricos da `v8.0-beta.6.6` (178 testes, 82,73% de cobertura) e não refletem esta versão.
- Saneamento de caminhos locais (`<USER_HOME>`, `<REPO_ROOT>` e `<WORKSPACE>`) em `00_diagnostico/{arvore_atual.txt,componentes_existentes.json,inventario.json,relatorio_defeitos.md}`, `relatorios_execucao/{homologacao_v8.0-beta.6.3.md,homologacao_v8.0-beta.6.4.md,homologacao_v8.0-beta.6.5.md,homologacao_v8.0-beta.6.6.md,pytest_verbose.txt,run_manifest.json}`, `docs/RELATORIO_HOMOLOGACAO_ETAPAS_0_1.md` e `docs/fase7_rev20/reports/pytest-results.xml`, preservando JSON/XML válidos.
- Os hashes em `run_manifest.json` e nos `homologacao_*.md` são os dos arquivos originais e não conferem com os atuais; os `SHA256SUMS` da raiz e de `00_diagnostico` foram regenerados ao final desta versão.
- Workflow do GitHub Actions (Ubuntu e Windows, Python 3.12 e 3.14) e ajuste do teste `os_name_mismatch` (`47f9f0a`).
- Rótulos atualizados para `v8.1.0-beta.2` em `SKILL.md`, `references/catalogo_motores.yaml` e `README.md` (sem alterar `MOTOR_VERSION` nem a tabela de versões dos motores).
- **Nota sobre `v8.1.0-beta.1`:** a tag `v8.1.0-beta.1` aponta para `5899a09`, anterior ao ajuste de teste do CI (`47f9f0a`); nesse commit o job Ubuntu falhava em `test_b63_consistency_detects_all_divergences[os_name_mismatch]`.
- **Limitações conhecidas:** `location` ausente em `motor_consistencia_cruzada` gera achado com localização `"None"` (assimétrico) ou `"desconhecido"` (empate); `benchmark/cases.json` contém o gabarito do benchmark dentro do repositório; continuam no HEAD com o nome do autor e/ou caminhos locais: `benchmark/cases.json` (travado por `validation_cases_sha256` da R3 e lido em `bench.py`), `benchmark/PREREGISTRO_R3.md` (mantido coerente com `cases.json`), `skills/revisao-hostil/SKILL.md` (skill v6.0 mantida intacta), `versions/v6.0-legacy/SKILL.md` (cópia imutável com `SHA256SUMS` próprio), `benchmark/posthoc_r3.py`, `benchmark/prepare_blind_dir.py` e `benchmark/PREREGISTRO.md`; e-mail do autor e caminhos locais permanecem em commits e tags já publicados (histórico do Git); 53 arquivos da skill não constam no `SHA256SUMS` raiz (`CHANGELOG.md`, `benchmark/*`, parte de `tests/*`, `00_diagnostico/SHA256SUMS` e `versions/v6.0-legacy/SHA256SUMS`), decisão registrada para revisão em uma versão futura.

---

## v8.1.0-beta.1 (2026-11-27)

### 1. motor_matematico (`8.0.0-beta.2` -> `8.1.0-beta.1`)
- **Divergência Simbólica Comprovada e Precedência** (`91d93db`, `26e82ff`, `7c8f698`):
  - Em `check_formula`, tratamento de `symbolic_equivalence = "proven_different"` quando a diferença algébrica simplificada ou polinomial for comprovadamente não-nula, definindo `symbolically_equal = False` e `status = "discrepancy_detected"` com prioridade sobre coincidência numérica pontual;
  - Criação de achado em `_extract_findings_from_results` com estado `CONFIRMADO` (portão `G03`), sem sobrescrever com `OK` se houver amostras numéricas coincidentes;
  - Formalização do contrato com `symbolic_equivalence` ("proven_equal", "proven_different", "inconclusive") e `symbolically_equal` como booleano anulável (`None` quando inconclusivo).
- **Convergência de Solvers ODE e Status do Envelope** (`d87a5b5`):
  - *O que já existia*: A emissão de status `solver_failed` quando `solve_ivp` ou `solve_bvp` não convergem (`success = False`) já existia na implementação anterior.
  - *O que mudou nesta branch* (`d87a5b5`): Definição do status do envelope do motor como `PARCIAL` quando houver `solver_failed`, fórmula com equivalência simbólica inconclusiva (`not_symbolically_equal`) ou `numerically_equal_at_samples`.
- **Novas Métricas Operacionais** (`d87a5b5`):
  - Inclusão dos campos `solvers_nao_convergidos` e `verificacoes_formula_nao_conclusivas` no bloco `metricas`.
- **Validação de Parâmetros e Símbolos Reservados em EDOs** (`a48647e`):
  - *O que já existia*: A validação de finitude numérica dos valores de `parameters` (`require_finite_number`) em `ode_ivp` estava presente desde a importação inicial (`53d1619`, DEF-M05); em `ode_bvp` a verificação de parâmetros finitos também já existia.
  - *O que mudou nesta branch* (`a48647e`):
    - Validação de que as chaves de `parameters` são identificadores Python válidos (`isidentifier()`);
    - Rejeição estrita de colisão de nomes com símbolos reservados do sistema:
      - `ode_ivp`: `{"t"} | {str(state) for state in states}` (ex.: `t`, `y0`, `y1`...);
      - `ode_bvp`: `{"x"} | {str(state) for state in states} | {"ya0".."yaN"} | {"yb0".."ybN"}`.
- **Robustez e Validação de Lote em `run_motor`** (`9e7c927`):
  - *O que já existia*: O laço com `try/except` por operação em lote já existia na versão anterior.
  - *O que mudou nesta branch* (`9e7c927`):
    - Rejeição de lote vazio (lista vazia ou `operations: []`) retornando envelope com status `ERRO_VALIDACAO`;
    - Validação de que `operations` em payload com `operation: "batch"` é obrigatoriamente uma lista (`isinstance(raw_ops, list)`), retornando `ERRO_VALIDACAO` em caso contrário;
    - Validação estrita de tipo de item (`if not isinstance(item, dict)`), gerando erro tipado `TypeError` no item sem interromper a execução das demais operações do lote.
- **Limites de Recursos e Proteção contra DoS** (`031ac2c`):
  - Aplicação dos limites centralizados em `scripts/common/validation.py`: `MAX_AST_NODES` (em `SafeExpressionParser.parse`), `MAX_AST_DEPTH`, `MAX_MATRIX_DIMENSION` (em `solve_linear_system` e `audit_matrix`), `MAX_ODE_SYSTEM_ORDER` e `MAX_ODE_MESH_POINTS` (em `solve_ode_ivp` e `solve_ode_bvp`) e `MAX_BATCH_OPERATIONS` (em `run_motor`).
- **Leitura Delimitada e CLI** (`bbdf08a`):
  - Em `main()`, adoção de `read_bounded_json` impondo o teto de bytes `MAX_JSON_PAYLOAD_BYTES` antes do parse JSON para stdin e arquivos (`--input`).

---

### 2. motor_consistencia_cruzada (`0.1.0-beta.4` -> `0.3.0-beta.1`)
*(Merge `3708234` trouxe `0.2.0-beta.1`; commit `c9152a1` trouxe `0.3.0-beta.1`)*
- **Obrigatoriedade de `source_type` Reconhecido e Validação de Observações** (`c9152a1`):
  - Com 2 ou mais observações em uma grandeza, `source_type` reconhecido passou a ser estritamente obrigatório em cada uma delas (`c9152a1`).
  - Tipo ausente, `None`, não-string ou desconhecido gera erro da grandeza com mensagem indicando o índice da observação, o valor recebido e os 10 tipos aceitos (as 10 chaves reais de `SOURCE_AUTHORITY_ORDER`: `codigo`, `simulacao`, `planilha`, `dataset`, `tabela`, `figura`, `grafico`, `texto`, `resumo`, `conclusao`).
  - Cada observação deve ser obrigatoriamente um dicionário (`isinstance(obs, dict)`); item que não seja `dict` gera erro da grandeza com índice e tipo recebido.
  - Uma única observação continua falhando com `ValueError` devido à exigência de `len < 2` (comportamento preservado).
- **Lógica Simétrica em Empate de Autoridade** (`05693de`):
  - Em `check_quantity_consistency`, quando há empate no menor rank de autoridade (`count_min > 1`) entre tipos válidos, o motor opera de forma simétrica: não elege âncora (`anchor: null`), gera arestas vazias no grafo e emite achado com estado `NAO_VERIFICADO` (portão `G05`);
  - Quando há uma única âncora estritamente dominante (ex.: `codigo` frente a `texto`), a divergência é assimétrica e gera achado com estado `CONFIRMADO` (portão `G05`).
- **Isolamento de Itens em Lista** (`4efbde9`):
  - Em `run_motor`, validação estrita de tipo para cada grandeza na lista `quantities` (`if not isinstance(q, dict)`), anexando resultado de erro para o índice inválido e prosseguindo o laço sem interromper a execução das demais grandezas.
- **Invariância de Ordem e Comportamento dos Grafos e Achados** (`c9152a1`):
  - *Casos simétricos (empate no rank mínimo)*:
    - *Caso A (`codigo=10, codigo=12, texto=10`)*: Ambas as ordens de entrada produzem `nodes` e `edges` rigorosamente idênticos (`edges: []`), e achado único paritário `NAO_VERIFICADO` perfeitamente idêntico. O `texto=10` entra no agrupamento com `codigo=10`.
    - *Caso C (`codigo=10, codigo=12, texto=15`)*: Ambas as ordens produzem `nodes` e `edges` idênticos (`edges: []`), e achado único `NAO_VERIFICADO` idêntico, com `texto=15` figurando como terceiro grupo distinto na justificativa.
  - *Casos assimétricos (âncora dominante única)*:
    - *Caso B (`codigo=10, texto=10, texto=12`)*: A âncora é `codigo=10`. A fonte com valor 10 fica em conformidade e a com valor 12 gera achado `CONFIRMADO`. Em `graph.nodes` e `graph.edges`, a ordem dos nós filhos e das arestas reflete a ordem de entrada das observações não-âncora (`n1: 10, n2: 12` vs `n1: 12, n2: 10`), mas o achado gerado é exatamente o mesmo em ambas as ordens.
    - *Caso D (`codigo=10, tabela=12, texto=15`)*: A âncora é estritamente `codigo=10`, gerando dois achados `CONFIRMADO` (um contra a tabela e outro contra o texto). Em `graph.nodes` e `graph.edges`, a ordem dos nós e arestas segue a sequência das observações na entrada; a lista `achados` reflete a ordem de detecção das divergências (ordem 1 emite tabela depois texto; ordem 2 emite texto depois tabela), sendo o conjunto de achados equivalente como multiconjunto.
  - *Identificadores*: os ids dos achados (`ACH-XCS-00N`) e das evidências (`EV-XCS-00N`) seguem a ordem de detecção. No Caso D eles trocam de dono conforme a ordem de entrada (ordem 1: `ACH-XCS-001` = tabela; ordem 2: `ACH-XCS-001` = texto). O conjunto de achados é equivalente ignorando `id`, `evidencia_id` e `timestamp`.
- **Limitações conhecidas**:
  - Sem `location` nas observações, os achados assimétricos saem com `localizacao: "None"` e `acao_recomendada: "Alinhar 'None' com a fonte primária 'None' ou documentar a transformação."`; nos casos simétricos, a localização sai como `"desconhecido"`. Os casos A–D acima foram rodados sem `location`; uma nova execução com `location` preenchida reproduziu as mesmas conclusões de invariância e produziu localização e ação recomendada com os nomes das fontes. Informe `location` em cada observação.
- **Leitura Delimitada e CLI** (`df8a7ca`):
  - Em `main()`, adoção de `read_bounded_json` com teto `MAX_JSON_PAYLOAD_BYTES` e tratamento de saída padronizada.

---

### 3. Outros Motores com Lote (10 motores)
Motores que suportam execução em lote (`operation == "batch"` ou lista direta de operações), com isolamento de falhas por item e leitura delimitada via `read_bounded_json`:

- **`motor_dados` (`0.1.0-beta.3` -> `0.2.0-beta.1`)** (`13e5837`, `c98e348`, `4efbde9`, `df8a7ca`):
  - Parâmetro `min_n` configurável em `pvalue_distribution_screen`;
  - Validação estrita de tipo para `min_n` (`isinstance(min_n, int) and not isinstance(min_n, bool) and min_n >= 1`), rejeitando `bool` e `float`;
  - Emissão de status `sample_too_small` em envelope `PARCIAL` quando $N < \text{min\_n}$, sem ocultar achados de outros itens do lote;
  - Isolamento de itens malformados no lote e `read_bounded_json`.
- **`motor_estatistico` (`0.2.0-beta.5.3` -> `0.3.0-beta.1`)** (`e944853`, `8c89240`, `7964c39`, `286a023`, `970cadb`, `4efbde9`, `df8a7ca`, `33ed2f0`):
  - Cálculo de poder estatístico bicaudal para duas amostras independentes via distribuição t não central (`scipy.stats.nct`), substituindo a aproximação normal assintótica;
  - Avaliação da cauda inferior por simetria $P(T < -t_{\text{crit}} \mid nc) = \text{sf}(t_{\text{crit}}, df, -nc)$, contornando `NaN` numérico do SciPy `nct.cdf`;
  - Documentação da cota da cauda inferior ($\le \alpha/2$ para $nc \ge 0$) e registro do campo `nan_fallback_applied`;
  - Tratamento de variância amostral nula com `reported_p`: emissão de achado `NAO_VERIFICADO` (portão `G04`) diferenciando analiticamente média idêntica ($0/0$) de médias distintas ($|t| \to \infty$);
  - *(Nota: o uso de `abs(effect_size_d)` já existia na implementação do motor; nesta branch foi adicionada a cobertura de teste de invariância sob inversão de sinal no commit `868c16b`)*;
  - Isolamento de itens malformados no lote e `read_bounded_json`.
- **`motor_incerteza` (`0.1.0-beta.3` -> `0.2.0-beta.1`)** (`90420bc`, `4efbde9`, `df8a7ca`):
  - Validação de obrigatoriedade de incerteza finita não-negativa para cada variável em `propagate_gum`;
  - Tratamento de chaves ausentes em `monte_carlo` aceitando incerteza nula ($u=0$);
  - Isolamento de itens malformados no lote e `read_bounded_json`.
- **`motor_dimensional` (`0.1.0-beta.3` -> `0.1.0-beta.3.1`)** (`4efbde9`, `df8a7ca`): Isolamento de falhas por item no lote e `read_bounded_json`.
- **`motor_etica` (`0.1.0-beta.5` -> `0.1.0-beta.5.1`)** (`4efbde9`, `df8a7ca`): Isolamento de falhas por item no lote e `read_bounded_json`.
- **`motor_figuras` (`0.1.0-beta.4` -> `0.1.0-beta.4.1`)** (`4efbde9`, `df8a7ca`): Isolamento de falhas por item no lote e `read_bounded_json`.
- **`motor_geometrico` (`0.1.0-beta.3` -> `0.1.0-beta.3.1`)** (`4efbde9`, `df8a7ca`): Isolamento de falhas por item no lote e `read_bounded_json`.
- **`motor_imagem_forense` (`0.1.0-beta.4` -> `0.1.0-beta.4.1`)** (`4efbde9`, `df8a7ca`): Isolamento de falhas por item no lote e `read_bounded_json`.
- **`motor_qualitativo` (`0.1.0-beta.5` -> `0.1.0-beta.5.1`)** (`4efbde9`, `df8a7ca`): Isolamento de falhas por item no lote e `read_bounded_json`.
- **`motor_risco` (`0.1.0-beta.6` -> `0.1.0-beta.6.1`)** (`4efbde9`, `df8a7ca`): Isolamento de falhas por item no lote e `read_bounded_json`.

---

### 4. Motores sem Lote com Tratamento Estruturado no CLI (4 motores)
Motores com modelo de entrada de entidade única que receberam validação de schema de entrada e tratamento defensivo no CLI (`61648af`, `df8a7ca`):
- **Contrato de saída no CLI (`main`)**:
  - Se a entrada for inválida (ex.: ausência de campos obrigatórios, formato inválido), `run_motor` retorna envelope estruturado com `status = "ERRO_VALIDACAO"` e o CLI encerra com código 1;
  - Se ocorrer falha inesperada durante a execução ou violação de limite de tamanho em `read_bounded_json`, o bloco `except` de `main()` captura o erro, imprime envelope JSON estruturado com `status = "ERRO_EXECUCAO"` e encerra com código 1.
- Motores atualizados:
  - **`motor_argumentacao` (`0.1.0-beta.5` -> `0.1.0-beta.5.1`)**;
  - **`motor_estetico` (`0.1.0-beta.6` -> `0.1.0-beta.6.1`)**;
  - **`motor_linguagem` (`0.1.0-beta.4` -> `0.1.0-beta.4.1`)**;
  - **`motor_temporal` (`0.2.0-beta.5.2` -> `0.2.0-beta.5.3`)**.

---

### 5. Motores Restantes com Leitura Delimitada (5 motores)
Motores que receberam a padronização de leitura delimitada via `read_bounded_json` (`MAX_JSON_PAYLOAD_BYTES`) e tratamento de exceção estruturado no CLI (`df8a7ca`):
- **`motor_evidencia` (`0.1.0-beta.5` -> `0.1.0-beta.5.1`)**;
- **`motor_metadados` (`0.1.0-beta.5` -> `0.1.0-beta.5.1`)**;
- **`motor_nomenclatura` (`0.1.0-beta.5` -> `0.1.0-beta.5.1`)**;
- **`motor_normas` (`0.1.0-beta.6` -> `0.1.0-beta.6.1`)**;
- **`motor_reprodutibilidade` (`0.1.0-beta.5` -> `0.1.0-beta.5.1`)**.

---

### 6. Auditor e Extratores (`ca929ec`)
- **`scripts/auditor.py`**:
  - Extração de texto em cabeçalhos e rodapés de seções de arquivos `.docx`;
  - Deduplicação de referências de células mescladas na extração de tabelas em `.docx`;
  - Documentação em `SKILL.md` das limitações intrínsecas de extração de layout/tabelas em arquivos `.pdf` via texto plano (`pypdf`).

---

### 7. Governança Metodológica e Testes
- **Avisos Metodológicos e Documentação** (`4e0c22d`, `2446d4f`, `907b458`, `011fc5b`):
  - Inclusão de avisos metodológicos explícitos em `benchmark/PREREGISTRO_R4.md` e `benchmark/PREREGISTRO_R6.md` esclarecendo que se tratam de pilotos exploratórios descritivos restritos às amostras avaliadas;
  - Ajuste em `docs/ARQUITETURA_V8.md` delimitando reproduzibilidade para determinismo sob o mesmo ambiente e mesma entrada;
  - Atualização de `SKILL.md` registrando escopo exploratório e limites operacionais dos motores.
- **Novas Baterias de Testes**:
  - `test_all_engines_bounded_json_cli.py` (`c857c1c`): Testes de integração de CLI para os 21 motores (stdin, `--input`, rejeição de excesso de bytes e payloads válidos);
  - `test_batch_robustness_engines.py` (`4efbde9`): Validação de isolamento de falhas por item em lotes;
  - `test_reference_values_engines.py` (`d7ccade`): Verificação de concordância contra valores de referência analíticos e SciPy;
  - `test_motor_estatistico_regressao.py` (`a343ef4`, `868c16b`, `0484b88`): Parametrização da grade de poder (60 pontos) comparando `stats.nct.sf` e `stats.nct.cdf`, teste de invariância de $d$ negativo, cobertura do ramo de fallback com monkeypatch e documentação da âncora do G*Power;
  - `test_motor_incerteza_regressao.py` (`16416ce`): Casos de borda e validação de schema;
  - `test_single_entity_engines_error_handling.py` (`61648af`): Validação de envelopes de erro estruturado (`ERRO_VALIDACAO` e `ERRO_EXECUCAO`) nos motores sem lote;
  - `test_motor_consistencia_cruzada_regressao.py` (`c9152a1`): Testes de regressão exigindo `source_type` reconhecido para 2+ observações nas duas ordens de entrada, validação de `isinstance(obs, dict)`, rejeição de tipos desconhecidos/inválidos e preservação de erro para observação única (`len < 2`).

---

### 8. Ressalvas
- A mensagem associada ao objeto de tag anotada `v8.0` (`73c33ff`, apontando para o commit `7677de3`) afirma *"Release oficial v8.0 da Skill Revisao Hostil - homologada com Recall 100% e Precisao 70% no Round 6"*.
- O piloto do Round 6 avaliou 15 artigos (corpus descrito no `benchmark/PREREGISTRO_R6.md`); o valor de 70% (7/10) refere-se à precisão reportada sobre 10 predições avaliadas, a qual não foi reconciliada com o total de 50 achados `CONFIRMADO` gerados na ocasião. Tais métricas não se aplicam automaticamente nem garantem taxa de acerto generalizável para a presente versão dos motores.
