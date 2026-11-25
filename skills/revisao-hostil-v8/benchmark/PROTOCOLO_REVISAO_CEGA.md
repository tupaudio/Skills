# Protocolo da revisão cega (Etapa 2)

Status: rascunho. Versão do protocolo: 0.1.

## 1. Objetivo

Medir o que a Skill Revisão Hostil V8 encontra quando segue o seu próprio
SKILL.md num documento que o revisor nunca viu com gabarito, pareceres ou
resultados anteriores. O resultado alimenta o adapter `achados_arquivo`.

Este protocolo mede a Skill executada por um modelo. Não mede o
`auditor_estrutural` sozinho, que já tem o adapter `estrutural_json`.

## 2. O que "cega" significa aqui

A sessão do revisor NÃO pode ter acesso a:

1. `cases.json`, `PREREGISTRO.md`, `thresholds.json`, `lock.json`;
2. os pareceres dos Artigos 03 e 04 (nenhum dos dois relatórios);
3. qualquer `results/*.json` produzido antes (auditor_estrutural, revisões
   anteriores);
4. o histórico Git do repositório;
5. conversas anteriores sobre o A04 (memória, contexto, anexos).

A sessão PODE:

1. ler `artigo04.md`;
2. ler o `SKILL.md` e executar os motores da Skill sobre o artigo. Isso é parte
   da Skill e deve ser registrado (seção 7). Resultados de execuções feitas
   DENTRO da sessão são permitidos; resultados de execuções ANTERIORES não.

A cegueira é atestada pelo próprio revisor. O protocolo registra o
procedimento, mas não o prova (seção 9).

## 3. Preparação (feita pelo responsável, antes de abrir a sessão)

Crie um diretório limpo FORA do clone do repositório, por exemplo
`C:\revisao_cega_A04\` (Windows) ou `~/revisao_cega_A04/` (Linux).

Copie apenas:

1. `artigo04.md` (a mesma cópia cujo hash está no `manifest.json`);
2. `SKILL.md` da Skill;
3. a pasta `scripts/` (auditor e motores), sem `__pycache__`;
4. as dependências necessárias, se não estiverem instaladas globalmente.

NÃO copie `benchmark/`, `tests/`, `docs/`, `.git/`, `results/`.

Confira o hash do documento e anote:

```bash
# Linux/macOS
sha256sum artigo04.md
# Windows (PowerShell)
Get-FileHash artigo04.md -Algorithm SHA256
```

O hash deve ser igual ao do `manifest.json`. Se for diferente, pare: o
benchmark e a revisão estariam em versões diferentes do documento.

Verifique que o diretório não contém nada da lista da seção 2 (item 1 a 4):

```bash
find . -iname "cases*" -o -iname "prereg*" -o -iname "*parecer*" -o -iname "bench_*"
```

(no PowerShell: `Get-ChildItem -Recurse | Where-Object Name -match "cases|prereg|parecer|bench_"`).
O resultado deve ser vazio.

## 4. A sessão

1. Abra uma sessão NOVA, sem memória de conversas anteriores, com o diretório
   limpo como único espaço de trabalho.
2. Se a plataforma tiver memória de longo prazo, desative-a para esta sessão.
3. Registre ANTES de começar: modelo e versão, data e hora, identificador da
   sessão (qualquer identificador estável, como o ID da conversa).
4. Faça UMA execução. Não reabra a sessão para "corrigir" ou "completar" o
   resultado depois de ver o score. Se precisar repetir, é uma nova rodada,
   com novo registro e sem aproveitar a anterior (seção 8).

## 5. Prompt para o revisor

Cole o texto abaixo sem acrescentar dicas sobre defeitos ou categorias.

```text
Você vai fazer uma revisão hostil do manuscrito artigo04.md usando a Skill
Revisão Hostil V8 (SKILL.md deste diretório). Siga o SKILL.md. Você pode
executar os motores e o auditor da Skill sobre o manuscrito.

Regras:
1. Numere as linhas com o mesmo critério do benchmark: linha N é a N-ésima
   linha de Path("artigo04.md").read_text(encoding="utf-8").splitlines(),
   contando de 1. Confira cada line_start executando esse código.
2. Para cada achado registre: line_start, line_end, category (texto livre,
   snake_case), status e um excerpt curto do trecho.
3. status deve ser um destes:
   - CONFIRMADO: você refez o cálculo ou a verificação e mostrou que está
     errado; descreva a conta em "evidence";
   - TRIAGEM: suspeita que ainda precisa de verificação;
   - NAO_VERIFICADO: você não conseguiu verificar.
4. Não classifique como CONFIRMADO sem demonstração. Se não conseguir
   verificar, use NAO_VERIFICADO.
5. Não use a internet para procurar parecer, revisão ou erratas deste artigo.
6. Calcule o SHA-256 de artigo04.md e grave em document_sha256.
7. Grave a saída em blind_A04.json no formato abaixo e nada além disso na
   resposta final, exceto um parágrafo com as limitações da sua revisão.
8. No bloco "reviewer", preencha reviewer_model e session_id com o que você
   souber. Em saw_gabarito, saw_pareceres e saw_auditor_results use false
   SOMENTE se for verdade. Se você viu qualquer um desses itens, use true e
   explique em "notes". Não omita.

Formato de blind_A04.json:
{
  "document": "A04",
  "document_sha256": "<sha256 do artigo04.md>",
  "reviewer": {
    "reviewer_model": "<modelo>",
    "session_id": "<id da sessao>",
    "saw_gabarito": false,
    "saw_pareceres": false,
    "saw_auditor_results": false,
    "notes": ""
  },
  "findings": [
    {"line_start": 0, "line_end": 0, "category": "...",
     "status": "TRIAGEM", "excerpt": "...", "evidence": "..."}
  ]
}
```

Nota: o adapter ignora o campo `evidence` nas métricas, mas ele fica no arquivo
para auditoria humana. O adapter também ignora `notes`; a leitura delas é do
responsável (seção 7).

## 6. Depois da sessão

1. Copie `blind_A04.json` para `benchmark/results/blind_A04.json` (esse caminho
   já é ignorado pelo Git; não faça commit do arquivo).
2. Confirme as flags de cegueira no arquivo. Se alguma estiver `true` ou
   ausente, o adapter recusa a rodada. Isso é correto: a rodada vale como não
   cega e não deve ser reportada como cega.
3. Leia `reviewer.notes`. Se a sessão declarar que viu algo da lista da
   seção 2, a rodada é inválida para este protocolo.
4. Só então rode o benchmark com o adapter `achados_arquivo:achados_arquivo`:

```bash
python benchmark/bench.py run --split validacao \
  --adapter achados_arquivo:achados_arquivo \
  --out benchmark/results/blind_A04_resultado.json
```

   O `run` exige `lock.json` para o split `validacao`. Os limiares e o gabarito
   adjudicado devem estar congelados ANTES de a sessão cega começar. Se o
   `lock` ainda não existir, a revisão pode ser gravada, mas não deve ser
   medida até o lock (a revisão não pode ser usada para escolher casos ou
   limiares).

## 7. O que registrar no PREREGISTRO.md (campos)

- modelo e versão do revisor;
- data e hora de início e fim;
- identificador da sessão;
- plataforma e configurações relevantes (memória de longo prazo desligada ou
  não, ferramentas disponíveis);
- hash SHA-256 do `artigo04.md` usado na sessão;
- hash do SKILL.md e do `auditor.py` usados;
- se o revisor executou motores ou o auditor, e quais;
- quantidade de achados por status;
- valor das três flags de cegueira, como declaradas;
- número da rodada (1, 2, ...) e o motivo de cada rodada nova.

## 8. Rodadas

1. A primeira rodada é a registrada no relatório principal.
2. Se for necessário alterar a Skill, os motores ou o prompt depois de ver o
   resultado, a próxima execução é uma RODADA NOVA. Ela deve ser rotulada como
   tal, e o resultado da primeira continua sendo reportado.
3. É proibido escolher qual rodada reportar com base no melhor número.
4. A alteração de qualquer arquivo congelado no `frozen_files` do manifest
   invalida o lock e exige novo lock antes da validação.

## 9. Limites conhecidos (reportar junto com qualquer número)

1. A cegueira é atestada pelo próprio revisor.
2. O gabarito foi construído olhando o texto do A04 (viés de seleção). O
   resultado não é validação independente.
3. Um modelo de linguagem pode ter visto o artigo no treino ou em contexto
   anterior que o protocolo não controla.
4. Há um único documento com gabarito e poucos casos. Os intervalos de
   confiança serão largos e o gate tende a `NOT_VERIFIED`.
5. Uma só execução não mede a variabilidade do revisor. Repetir a mesma
   configuração em sessões novas, registrando cada uma, mede a estabilidade.
6. Se o revisor rodou o `auditor_estrutural`, parte do resultado reflete o
   triador e não o julgamento do modelo.

## 10. O que este protocolo NÃO permite

1. Mostrar o gabarito, os pareceres ou o `cases.json` ao revisor, nem em parte.
2. Corrigir o JSON do revisor à mão (inclusive linhas e hash).
3. Rodar a revisão duas vezes e reportar só a melhor.
4. Alterar o `cases.json`, o `thresholds.json` ou os arquivos congelados depois
   de olhar o resultado da revisão.
5. Chamar o resultado de "validação independente".
