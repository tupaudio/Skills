# Pré-Registro — Benchmark Científico Revisão Hostil v8.0 (Etapa 2)

**Data:** 2026-11-24  
**Branch:** `homologation/etapa2-benchmark-limpo`  
**Status:** Declarado antes da primeira medição em `validacao` e antes da definição de `lock.json`.

## 1. Variante Principal vs. Ablação

- **Variante principal:** `estrutural_json:estrutural_sem_informativos`
  - **Justificativa:** remove pistas de triagem de gravidade `INFORMATIVO` (`equation_candidate`), que não representam defeitos reportados e distorceriam a precisão pessimista por caírem majoritariamente em regiões sem rótulo.
- **Variante de ablação (sempre reportada junto):** `estrutural_json:estrutural` (todos os achados emitidos pelo auditor, incluindo `INFORMATIVO`).
- **Adapter de revisão cega da Skill:** `achados_arquivo:achados_arquivo` (segue `benchmark/PROTOCOLO_REVISAO_CEGA.md`).
- **Linhas de base obrigatórias:** `builtin:nothing` (piso) e `builtin:every_line` (teto).

## 2. Separação de Splits e Limitações Metodológicas

- **Calibração:** não existe calibração nesta rodada (nenhum caso em `split=calibracao`); `A03` fica fora das métricas.
- **`validacao`:** `A04` (`docs/artigo04.md`, SHA-256 `1cb5b80eb8d0555a00a013afb7721876661b69ab555abc481ebccd06a1222cc2`).
  - **Viés de seleção registrado:** `A04` já foi inspecionado (texto, pareceres e saída do auditor) e os defeitos estão sendo selecionados a partir do próprio texto. Portanto, o resultado em `A04` **não constitui validação independente**; serve como referência interna de regressão até a inclusão de documentos inéditos.
  - **Escopo dos controles negativos (linhas 86 e 145):** validam **apenas a aritmética**, não a física/modelo subjacente (registrado também no `rationale` de `cases.json`).
- **Regressão de proveniência (`B03-001`, `B04-001` e `B04-005`):** mantidos fora do `cases.json` científico (`B03-001` e `B04-005` como testes do adapter; `B04-001` registrado como defeito de proveniência do Parecer 2).

## 3. Métricas de Recall e Gate

- Reportar simultaneamente **recall por linha** (`recall`) e **recall por linha com categoria compatível** (`recall_categoria`, via `detectable_by`).
- **Métrica do gate:** `recall` por linha (com `recall_categoria` reportado em paralelo para detectar inflação por categoria incompatível).

## 4. Protocolo da Revisão Cega e Limites

- **Protocolo (`benchmark/PROTOCOLO_REVISAO_CEGA.md`):** diretório limpo fora do clone contendo apenas `artigo04.md` + `SKILL.md` + `scripts/`; sessão nova sem memória; uma única execução registrada; modelo, data e identificador da sessão registrados.
- **Limites declarados:** cegueira atestada pelo próprio revisor; viés de seleção dos defeitos (gabarito escolhido olhando o texto); o modelo pode ter visto o artigo em treino ou contexto anterior.

## 5. Privacidade e Higiene de Repositório

- Material sensível (`docs/benchmark_etapa2/`, textos dos artigos e pareceres) foi retirado do Git; os insumos ficam fora do repositório, e `manifest.json` guarda apenas os hashes SHA-256.
- `cases.json` usa âncoras por `line_start`/`line_end` + `line_sha256` (Opção ii), sem trechos literais do manuscrito no Git.

## 6. Pendências de Decisão do Usuário Antes do Lock

- **Destino do histórico sensível (`homologation/etapas-0-1-rev20`) — EXECUTADO (Opção B + C, 2026-11-24):**
  - Branch `homologation/etapas-0-1-rev20` reescrita com `--force-with-lease` para `1483e398791303cdfc6ea1d08c87d91fe2ce80b1` (commits removidos da branch; identificadores guardados fora do Git; `main`, `v8.0-beta.6.6` e `homologation/etapa2-benchmark-limpo` intocados).
  - Pedido de purga de cache dos commits removidos da branch (identificadores guardados fora do Git) enviado ao Suporte do GitHub (Opção C).
  - **Exposição residual aceita (Opção A):** o caminho local `ZZ - Antigravity` permanece em 9 commits históricos que fazem parte de `main` e da baseline `v8.0-beta.6.6` (não contém texto do artigo).
- **Escopo da rodada:** escolher entre (a) piloto descritivo (aceitar `NOT_VERIFIED` com o gabarito atual) ou (b) ampliar o gabarito antes do lock.
- **Limiares (`thresholds.json`):** valores a definir pelo usuário (não pelo agente) antes do lock.
- **Métrica do gate:** `recall` por linha (já registrado) e `recall_categoria` apenas como reporte paralelo.
- **Registro do `lock.json`:** o hash SHA-256 do `lock.json` local deve ser anotado nesta seção depois do lock (`lock.json` não vai ao Git).
- **Revisor cego:** deve ser sessão nova e modelo diferente do que montou o gabarito.

## 7. Critérios de Adjudicação (a preencher pelo usuário ANTES de adjudicar)

- **Tolerância relativa para considerar divergência numérica um defeito:** [vazio]
- **Como tratar `B04-003` (divergência pequena):** [vazio]
- **Gate:** usa `recall` por linha; `recall_categoria` só como reporte (já decidido).
- **Escopo — (a) piloto descritivo ou (b) ampliar gabarito:** [vazio]
- **Privacidade do campo `evidence`:** o campo `evidence` de `cases.json` é versionado e **não pode conter trecho do artigo**.


