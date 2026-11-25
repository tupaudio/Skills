# Pre-registro da Rodada 4 (R4)

Status: PRONTO PARA LOCK (v1.0, preenchido pelo pesquisador em 2026-11-25).
Commitar ANTES do lock e de qualquer revisor ver os documentos. Depois do
lock, qualquer alteracao e registrada na secao 12 como desvio, com data.
Nao escrever aqui trecho de manuscrito, SHAs sensiveis nem numero de chamado.

## 1. Natureza
Rodada com defeitos REAIS, vindos de erratas publicas, em textos extraidos de
PDF e XML JATS. Uma unica adjudicadora. NAO e validacao independente.
Resultado exploratorio, pois o gabarito atual (n=12) fica abaixo de
min_defects=15 (secao 6).

## 2. Relacao com as rodadas anteriores
- R1 e R2: pilotos descritivos (n=3 defeitos). R3: piloto diagnostico com
  defeitos sinteticos; desvios registrados no PREREGISTRO_R3.
- bench.py desta rodada: v0.3.0 (hash congelado no lock).
- As tabelas da R4 nao sao comparaveis com as da R3.

## 3. Pergunta e hipoteses
Pergunta: o SKILL.md melhora a revisao de manuscritos com defeitos reais,
comparado ao mesmo modelo, na mesma interface, sem Skill?
- H1 (confirmatoria): limite inferior do IC de Wilson 95% do recall
  LOCALIZADO >= recall_lower_bound_min.
- H2 (confirmatoria): limite inferior da especificidade >=
  specificity_lower_bound_min.
- Ambas so na configuracao primaria (secao 7).
- Exploratorias: A contra C pareado por defeito; modelo primario contra o
  secundario; estrato 2026 contra 2025. Sem teste de significancia.

## 4. Documentos e gabarito
- Documentos (11 com defeito; fonte unica por documento registrada no
  manifest): R4_IEEE_01, R4_IEEE_06, R4_IEEE_07, R4_C02, R4_C04 (XML JATS),
  R4_C05, R4_C07, R4_C11, R4_C13, R4_N01 (XML JATS), R4_N07 (XML JATS).
- Arquivo registrado no manifest = arquivo numerado entregue ao revisor
  (prefixo "L0001: "). DOC_SHA256 do prompt = hash desse mesmo arquivo.
  line_sha256 calculado sobre o texto da linha SEM prefixo.
- Casos finais (cases_r4_v4, a adjudicar): 12 DEFECT, 22 NEGATIVE_CONTROL,
  4 INCONCLUSIVE (total = 38). Minimo desejado: 3 defeitos por categoria.
  Categoria abaixo de 3: unidade (n = 2; estatistico = 4, numerico = 3,
  inconsistencia interna = 3).
- Estratos: 2026 (n defeitos = 7) e 2025 (n defeitos = 5; risco de
  contaminacao por treino). Principal: todos os 12 defeitos. Sensibilidade:
  so 2026 (n = 7).
- Ancoras: distancia minima entre ancoras do mesmo documento >
  max_span_lines (12). Uma afirmacao por ancora.
- Adjudicacao: feita pelo pesquisador, caso a caso, a partir do dossie.
  Segunda pessoa conferindo ~20%: nao houve. O arquivo historico
  cases_r4_adjudicated.json (sha256 2e187a66...) NAO e o gabarito.
- evidence e validated_by nao contem trecho do artigo.
- Pre-triagem de controles: flash_lite (sessoes novas 64748f7b, b9e869db e
  225b0e3d com janela L-10..L+10; 1/23 sinalizado e descartado: R4-NEG-010;
  22/23 aprovados). Modelo possivelmente da mesma familia do agente que
  montou o gabarito; pre-triagem por outra familia BLOQUEADA neste ambiente.

## 5. Prompts (congelados)
- Blocos em benchmark/prompts/revisor_v0.2/:
  - bloco1_cabecalho: 6879ae46a0aabbb880659a2c0095866c69d8fcf47892a3347e3eb89c0c9f8399
  - bloco2_metodo_A:  d1387c9cce112a2d039f5710d3fb2359c65c542bc38c23e14190819ac70a67c5
  - bloco3_metodo_C:  580cca946008ab5e5ded6e1ba3a368d3ffaad0d76eed4cb1980b373b78826114
  - bloco4_saida:     9ff4d7154fe47ad0141500aeb5d9976f6c09901b97591be38bcc17b15e162d71
- Modelos montados (derivados por build):
  - revisor_A_v0.2.txt: f67bbe661c560949eca1eb4948fe0decac9fb25fc1ef7a8ba19a642825162a6b
  - revisor_C_v0.2.txt: 8a6fe4ccdcdda9718dba2d16b438fb58a04183acc0d45235f3aa23b39370f5cc
- montar_prompts.py: ec279c178fd28f6cc933ee4a174b85748494a8fef5584f262fce4daa0012d784
- MAX_LINHAS = 12 (escolha do autor, acima do 10 da regra "maior ancora de
  defeito + 2, piso 5"). MAX_ACHADOS = 45. Decididos em 2026-11-25, antes de
  qualquer execucao.
- Braco A: SKILL.md anexo + texto numerado. Braco C: so o texto numerado.
  Os dois diferem apenas no bloco de metodo.

## 6. Limiares (benchmark/thresholds_r4.json)
- min_defects: 15 (mantido sem reducao; com n=12 o gate e NOT_VERIFIED e a
  rodada e exploratoria).
- min_negatives: 20
- recall_lower_bound_min: 0.50
- specificity_lower_bound_min: 0.70
- precision_pessimistic_min: 0.10 (so piso informativo)
- max_span_lines: 12 (igual a MAX_LINHAS)
- recompute_tolerance_rel: 0.01
- Recall do gate = recall LOCALIZADO (sobreposicao de linha dentro do limite
  de span). O recall demonstrado so se aplica a defeitos com valor escalar.

## 7. Configuracao primaria
- Modelo, interface e modo: DeepSeek Web (DeepThink desligado, modo padrao).
- Braco primario do gate: A (com Skill). C e o comparador.
- Escolhida em 2026-11-25, antes da primeira execucao da R4.
- Criterio: disponibilidade de interface web sem bloqueio de anexos e
  reprodutibilidade operacional pelo pesquisador.
- Outros modelos: exploratorios, 1 execucao por braco.

## 8. Execucoes
- Primaria: 3 execucoes por braco e documento, mesmo modelo, mesma interface,
  mesmo dia, ordem aleatoria (ordem_seed = 20261125), sessao nova, memoria,
  busca e execucao de codigo desligadas.
- Via: web manual.
- Modo estrito, sem normalizar. Falha de schema: um unico pedido de reemissao
  com o texto padrao; arquivar as duas saidas; o conteudo nao pode mudar.
- JSON bruto arquivado com sha256 logo apos cada execucao. Planilha de
  registro por execucao: interface, modo, data, modelo selecionado, sha256 do
  prompt e do JSON, ultima linha lida, reemissao.
- Aprovacao (so configuracao primaria): H1 e H2 avaliadas por execucao;
  passa se pelo menos 2 das 3 execucoes cumprirem os dois limiares. Reportar
  todas as execucoes, mediana e faixa.

## 9. Metricas secundarias (pre-registradas)
- Recall com rubrica cega (o achado identifica o problema e mostra o
  raciocinio), sobre os JSONs brutos, com modelo e braco ocultos.
- Precisao adjudicada e descobertas fora do gabarito: adjudicacao agrupada,
  achados embaralhados, sem modelo e braco. Reportada a parte; nao altera o
  denominador do recall.
- Excesso de confianca em inconclusivos: so contagens.
- Pos-hoc: sensibilidade do span (5, 10, 12, 15), rotulada como pos-hoc.

## 10. Regra de parada
- Nenhuma regra, motor, prompt ou caso e ajustado olhando o resultado.
- Gate NOT_VERIFIED por falta de dados = rodada insuficiente, nao fracasso.
- Resultado nunca e chamado de "validacao independente".

## 11. Congelamento
frozen_files do manifest da R4 inclui: SKILL.md, scripts/,
benchmark/prompts/revisor_v0.2/, montar_prompts.py, cases da R4 adjudicado,
thresholds_r4.json e manifest.json. lock.json fica fora do Git; sha256 do
lock: [PREENCHER apos o lock]. Commit do HEAD no lock: [PREENCHER apos o lock].

## 12. Limitacoes e desvios
Limitacoes:
1. Texto extraido de PDF pode perder equacoes e tabelas; so entram defeitos
   legiveis no texto entregue (3 artigos PLOS ONE usam XML JATS).
2. Gabarito pequeno (n=12 < min_defects=15); ICs largos. Uma adjudicadora.
3. Erratas de 2025 (n=5) podem estar no treino dos modelos.
4. Cegueira e isolamento sao autodeclarados nos JSONs. Identidade do modelo
   declarada no JSON nao e prova.
5. Pre-triagem por modelo possivelmente da mesma familia do agente que
   montou o gabarito.
6. Recall localizado mede "tocou a linha", nao "viu o erro".
Desvios (registrar com data, antes de ver o resultado): [nenhum ate agora]
