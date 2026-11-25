# Pre-registro e Resultado Agregado — Rodada 5 (Etapa 2)

## 1. Escopo e configuracao
- **Prompt:** `benchmark/prompts/revisor_v0.3/` (contrato de saida endurecido: proibicao de emitir checagens "Sem erro", `recomputed_value` estrito, `CONFIRMADO` reservado a defeitos inequivocos).
- **Gabarito adjudicado (fora do Git):** `cases_r5_v1_adjudicated.json` (`sha256: ad8b89f7fe166c86a26b9c06e7520772e9e57a5d9e36bde3b5e64a5f27da6075`) — **15 `DEFECT`** (`min_defects = 15` atendido: 12 da R4 + 3 novos de 2026 em XML JATS limpo), **22 `NEGATIVE_CONTROL`** (17 nos 14 docs com defeito), **4 `INCONCLUSIVE`**.
- **Thresholds:** `thresholds_r4.json` (`recall_lower_bound_min = 0.50`, `specificity_lower_bound_min = 0.70`, `precision_pessimistic_min = 0.10`, `max_span_lines = 12`, `recompute_tolerance_rel = 0.01`).
- **Executor:** Subagentes cegos isolados de contexto (`14` docs × `2` bracos = `28` sessoes, `r1`).
  - **Braco A:** `revisor_v0.3` + `SKILL.md` + Python ativo.
  - **Braco C:** `revisor_v0.3` sem Skill.

## 2. Resultado agregado (2026-11-25)
- **Status:** `EXECUTADO` (`28/28` sessoes `JSON_OK`, `0` invalidos).
- **Veredito oficial R5:** **`FAIL`** (nao atingiu `recall_lower_bound_min >= 0.50` nem `precision_pessimistic_min >= 0.10`).

| Metrica (`CONFIRMADO`, `span <= 12`, `tol = 1%`) | Braco A (Skill v8 + Python) | Braco C (Controle) | Gate |
|---|---:|---:|---|
| Docs / Sessoes validas | 14/14 (`JSON_OK`) | 14/14 (`JSON_OK`) | — |
| TP (defeitos reais) | 5/15 (`R4-DEF-004`, `R4-DEF-017`, `R5-DEF-001`, `R5-DEF-002`, `R5-DEF-003`) | 6/15 (`+ R4-DEF-001`) | — |
| Recall (IC95% Wilson) | 33.3% `[0.152, 0.583]` | 40.0% `[0.198, 0.643]` | `LB >= 0.50` -> `FAIL` |
| Especificidade (IC95% Wilson) | 100.0% `[0.816, 1.000]` (0/17 FP) | 94.1% `[0.730, 0.990]` (1/17 FP) | `LB >= 0.70` -> **`PASS`** |
| Precisao pessimista | 4.1% (5/121) | 5.0% (6/120) | `>= 0.10` -> `FAIL` |

## 3. Achados e limitacoes
1. **XML JATS vs PDF:** nos 3 novos defeitos de 2026 em XML JATS limpo (`R5-DEF-001`, `R5-DEF-002`, `R5-DEF-003`), o acerto foi **3/3 (100%)** em ambos os bracos, confirmando que a extracao quebrada de PDF e um gargalo central de recall.
2. **Efeito do `revisor_v0.3`:** a precisao pessimista subiu ~3x em relacao a R4 (`1.4% -> 4.1%` no Braco A), mantendo **100.0% de especificidade (0/17 FP)** pelo segundo round consecutivo.
3. **Limitacao de independencia:** subagentes isolados de contexto pertencem a mesma familia de modelo do ambiente; validacoes futuras em modelo independente local devem usar `qwen3:4b` via Ollama.
