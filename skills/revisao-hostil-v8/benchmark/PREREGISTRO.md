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

## 7. Critérios de Adjudicação (preenchidos pelo usuário ANTES do lock)

- **Tolerância relativa para considerar divergência numérica um defeito:** `1%`
- **Como tratar `B04-003` (divergência pequena ~2,0%):** mantido como defeito de severidade menor (acima da tolerância de `1%`).
- **Gate:** usa `recall` por linha; `recall_categoria` só como reporte (já decidido).
- **Escopo:** **(a) piloto descritivo** (aceitar `NOT_VERIFIED` por dados insuficientes; `thresholds.json` definido com `min_defects=10`, `min_negatives=10`, `recall_lower_bound_min=0.50`, `specificity_lower_bound_min=0.70`, `precision_pessimistic_min=0.10`).
- **Privacidade do campo `evidence`:** o campo `evidence` de `cases.json` é versionado e **não pode conter trecho do artigo**.

## 8. Registro do Lock (2026-11-25)

- **Data UTC:** `2026-11-25T03:05:21.314637+00:00`
- **Commit HEAD no momento do lock:** `f9ad81c00c9c6958247d75da27d4bbbf119d97f2` (`dirty: false`)
- **SHA-256 de `benchmark/lock.json` (local, fora do Git):** `0214d45d4dee456617c9f0c2a92ae0b6939925a32feb2c78cc4734fc1472898b`
- **`validation_cases_sha256`:** `ff25ceccf0b4d1ee80994a334599711e0f36ce0aaede43391f6abdbb681b4f78`
- **`thresholds_sha256`:** `665319784f030dcbd35e92f71d104498a12be010aafe305b1f4bf44ecc1b7a81`
- **`manifest_sha256`:** `a5e9b857d1b41d770a781e21358e1b65e6ea951793d9dcaa0e41739c9dc7b6fe`
- **`frozen_files_sha256`:**
  - `../scripts/auditor.py`: `bcbf39be01a7188c6f10fac67a6d0406e68aaa60b3999764f2a15f0c9300974c`
  - `bench.py`: `5c786331e987c9b7913b5dc894369bebd57cc2a2a451d53daf15c26d1aa7ea78`
  - `adapters/estrutural_json.py`: `2ae5952f47f64d53c171944dec07a0fd380aef69b35c6944cfa6a5b73fd190c5`
  - `adapters/achados_arquivo.py`: `6d13143d50c4c1dbd7e9ecf1f823154968024bec6ad1571fb329e4666605b9a5`

## 9. Registro da Rodada 1 — Revisão Cega (`Gemini 4 Neon (Low)`) e Desvios

- **Modelo e versão:** `Gemini 4 Neon (Low)` (mesma família Gemini do agente orquestrador; registrado como limite)
- **Session ID:** `0dc5f890-0209-4525-a8de-52c52e257849`
- **Ferramentas usadas na sessão:** `scripts/auditor.py --engineering-preset` e `scripts/engines/motor_matematico.py`
- **Flags de cegueira declaradas:** `saw_gabarito=false`, `saw_pareceres=false`, `saw_auditor_results=false` (cegueira autodeclarada, não verificável externamente)
- **SHA-256 de `blind_A04__gemini4_neon_low.json`:** `c3e6b76c7e411a20ae61afac912dd42adca30697856aa71b3627e6d19cd4dfdf`
- **Achados por status (`15` total):** `CONFIRMADO=11`, `TRIAGEM=1`, `NAO_VERIFICADO=3`
- **Desvios registrados da Rodada 1:**
  1. Primeira tentativa com `python benchmark/bench.py run` falhou com `exit 1` por duplo import de `bench.BenchError` ao bloquear `A03` (`results/blind_A03.json` ausente).
  2. Execução concluída via entrypoint por módulo (`import bench; bench.main(...)`), sem alterar nenhum arquivo congelado (`lock.json` mantido intacto).
  3. Todos os modelos da bateria piloto (`Gemini 4 Neon`, `Hermes 3` local, `ChatGPT`, `DeepSeek`) serão avaliados sob o **mesmo `lock.json`** (`0214d45d...`) para manter comparabilidade direta.




