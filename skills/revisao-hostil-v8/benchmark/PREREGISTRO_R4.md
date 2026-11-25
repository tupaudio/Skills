# Pre-registro da Rodada 4 (R4)

Status: RASCUNHO v0.1. Commitar ANTES do lock e de qualquer revisor ver os
documentos. Depois do lock, qualquer alteracao e registrada na secao 12 como
desvio, com data. Nao escrever aqui trecho de manuscrito, SHAs sensiveis nem
numero de chamado.

## 1. Natureza
Rodada com defeitos REAIS, vindos de erratas publicas, em textos extraidos de
PDF. Uma unica adjudicadora. NAO e validacao independente. Resultado
exploratorio se o gabarito ficar abaixo de min_defects (secao 6).

## 2. Relacao com as rodadas anteriores
- R1 e R2: pilotos descritivos (n=3 defeitos). R3: piloto diagnostico com
  defeitos sinteticos; desvios registrados no PREREGISTRO_R3.
- bench.py desta rodada: v0.3.0 [PREENCHER: confirmar versao e hash no lock].
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
- Documentos: [PREENCHER: ids finais apos os descartes]. Fonte unica por
  documento (texto de PDF ou XML), registrada no manifest.
- Arquivo registrado no manifest = arquivo numerado entregue ao revisor
  (prefixo "L0001: "). DOC_SHA256 do prompt = hash desse mesmo arquivo.
  line_sha256 calculado sobre [PREENCHER: com ou sem prefixo].
- Casos finais (cases_r4_v3 adjudicado): [PREENCHER] DEFECT, [PREENCHER]
  NEGATIVE_CONTROL, [PREENCHER] INCONCLUSIVE. Minimo desejado: 3 defeitos por
  categoria (numerico, unidade, estatistico, inconsistencia interna). Se nao
  for atingido: [PREENCHER: registrar categoria e numero].
- Estratos: 2026 (n defeitos = [PREENCHER]) e 2025 (n defeitos = [PREENCHER];
  risco de contaminacao por treino). Principal: todos os defeitos.
  Sensibilidade: so 2026.
- Ancoras: distancia minima entre ancoras do mesmo documento >
  max_span_lines. Uma afirmacao por ancora.
- Adjudicacao: feita pelo pesquisador, caso a caso, a partir do dossie. Uma
  segunda pessoa confere cerca de 20% sem ver a decisao: [PREENCHER: nome ou
  "nao houve"; concordancia]. O arquivo gerado pelo agente
  (cases_r4_adjudicated.json, sha256 historico 2e187a66...) NAO e o gabarito.
- evidence e validated_by nao contem trecho do artigo.
- Pre-triagem de controles: [PREENCHER: modelos, versoes, quantos sinalizados].
  O modelo usado ate agora (flash_lite) provavelmente e da mesma familia do
  agente que montou o gabarito.

## 5. Prompts (congelados)
- Blocos em benchmark/prompts/revisor_v0.2/:
  - bloco1_cabecalho: [PREENCHER: sha256 final; ultimo relatado 6879ae46...]
  - bloco2_metodo_A:  d1387c9c... (relatado)
  - bloco3_metodo_C:  580cca94... (relatado)
  - bloco4_saida:     9ff4d715... (relatado)
- Modelos montados (derivados por build): revisor_A [PREENCHER: sha256],
  revisor_C [PREENCHER: sha256].
- montar_prompts.py: [PREENCHER: sha256].
- MAX_LINHAS = 12 (escolha do autor, acima do 10 da regra "maior ancora de
  defeito + 2, piso 5"). MAX_ACHADOS = 45. Decididos em [PREENCHER: data],
  antes de qualquer execucao.
- Braco A: SKILL.md anexo + texto numerado. Braco C: so o texto numerado.
  Os dois diferem apenas no bloco de metodo.

## 6. Limiares (thresholds.json da R4)
- min_defects: [PREENCHER] (nao reduzir para encaixar o gabarito; se o
  numero de defeitos adjudicados ficar abaixo, o gate e NOT_VERIFIED e a
  rodada e exploratoria).
- min_negatives: [PREENCHER]
- recall_lower_bound_min: [PREENCHER] (proposta: 0.50)
- specificity_lower_bound_min: [PREENCHER] (proposta: 0.70)
- precision_pessimistic_min: [PREENCHER] (so piso informativo)
- max_span_lines: 12 (igual a MAX_LINHAS)
- recompute_tolerance_rel: [PREENCHER]
- Recall do gate = recall LOCALIZADO (sobreposicao de linha dentro do limite
  de span). O recall demonstrado so se aplica a defeitos com valor escalar
  (poucos nesta rodada).
- Conferir os minimos com bench.wilson depois que n for conhecido.

## 7. Configuracao primaria
- Modelo, interface/API, modo (ex.: DeepThink) e versao: [PREENCHER]
- Braco primario do gate: A (com Skill). C e o comparador.
- Escolhida em [PREENCHER: data], antes da primeira execucao e sem olhar
  resultados anteriores de modelo.
- Criterio: [PREENCHER: ex.: identidade verificavel, termos de uso].
- Outros modelos: exploratorios, 1 execucao por braco.

## 8. Execucoes
- Primaria: 3 execucoes por braco e documento, mesmo modelo, mesma
  interface/API, mesmo dia, ordem aleatoria (seed [PREENCHER]), sessao nova,
  memoria, busca e execucao de codigo desligadas.
- Via: [PREENCHER: web manual ou API com script].
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
thresholds.json e manifest.json. lock.json fica fora do Git; sha256 do lock:
[PREENCHER apos o lock]. Commit do HEAD no lock: [PREENCHER].

## 12. Limitacoes e desvios
Limitacoes:
1. Texto extraido de PDF pode perder equacoes e tabelas; so entram defeitos
   legiveis no texto entregue.
2. Gabarito pequeno; ICs largos. Uma adjudicadora.
3. Erratas de 2025 podem estar no treino dos modelos; datas de corte dos
   modelos: [PREENCHER].
4. Cegueira e isolamento sao autodeclarados nos JSONs. Identidade do modelo
   declarada no JSON nao e prova.
5. Pre-triagem por modelo possivelmente da mesma familia do agente que
   montou o gabarito.
6. Recall localizado mede "tocou a linha", nao "viu o erro".
Desvios (registrar com data, antes de ver o resultado): [nenhum ate agora]
