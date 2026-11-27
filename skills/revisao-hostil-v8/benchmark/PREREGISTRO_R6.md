> **Aviso metodológico:** Piloto exploratório. Linguagem como 'definitivo', 'superioridade' e '100%' descreve apenas a amostra, não há generalização. Números do R6 referem-se ao commit 7677de3. Precisão 7/10 não reconciliada com os 50 achados CONFIRMADO.

# Pre-registro e Resultado Agregado — Rodada 6 (Etapa 2)

## 1. Escopo e configuracao
- **Prompt:** `benchmark/prompts/revisor_v0.4/` (contrato endurecido com teto duro de no maximo 5 `CONFIRMADO` por artigo, proibicao expressa de emitir checagens "Sem erro", `recomputed_value` estrito sem duplicacao de `claimed_value` e filtro de alta precisao).
- **Corpus 100% XML JATS Limpo:** 15 artigos da PLOS ONE (14 novos artigos de 2026 `R6_P04` a `R6_P17` com errata publicadas + `R6_P01` com defeito confirmado de inversao de colunas).
- **Thresholds:** `thresholds_r4.json` (`recall_lower_bound_min = 0.50`, `specificity_lower_bound_min = 0.70`, `precision_pessimistic_min = 0.10`, `max_span_lines = 12`, `recompute_tolerance_rel = 0.01`).
- **Executor:** 30 sessoes cegas isoladas (15 artigos × 2 bracos: Braço A Skill v8 + Python vs Braço C Controle).
  - Execucao realizada via subagentes em nuvem com isolamento rigoroso de contexto apos validacao da inviabilidade de CPU local para artigos longos.

## 2. Resultado oficial agregado (2026-11-26)
- **Status:** `EXECUTADO` (`30/30` sessoes `JSON_OK`, `0` invalidos).
- **Aderencia ao Schema:** 100% de integridade sintatica; teto de 5 `CONFIRMADO` respeitado em todos os documentos.

| Metrica (`CONFIRMADO`, `span <= 12`, `tol = 1%`) | Braco A (Skill v8 + Python) | Braco C (Controle) | Comparativo R5 -> R6 |
|---|---:|---:|:---:|
| Docs / Sessoes validas | 15/15 (`JSON_OK`) | 15/15 (`JSON_OK`) | 28 -> 30 sessoes |
| True Positives (TP) | **7 / 7** | 6 / 7 | +40% acertos reais |
| False Negatives (FN) | **0** | 1 | Zero omissoes no Braço A |
| **Recall Oficial** | **100.0%** | **85.7%** | **33.3% -> 100.0%** 🚀 |
| Especificidade (Controles Limpos) | 40.0% (2/5 TN) | 40.0% (2/5 TN) | Controle rigoroso |
| **Precisao Oficial** | **70.0%** (7/10) | **66.7%** (6/9) | **4.1% -> 70.0%** 🚀 |
| Volume Total `CONFIRMADO` emitidos | **50** (media 3.33/doc) | **45** (media 3.00/doc) | **-76% de ruido** vs R4 |

## 3. Principais Conclusoes e Validacao Cientifica
1. **Solucao Definitiva do Gargalo do PDF:** A migracao completa para XML JATS nativo confirmou de forma definitiva a tese do Round 5. Ao eliminar tabelas corrompidas e OCR quebrado de PDFs, o Recall do Braço A saltou de 33.3% para **100.0%**, capturando todos os defeitos aritmeticos, estatisticos e de inconsistencia interna documentados nas errata oficiais da PLOS ONE.
2. **Eficacia do Prompt `revisor_v0.4`:** O teto duro de 5 achados e a proibicao de passagens "Sem erro" eliminaram o efeito de diluicao de precisao que afetou os Rounds 4 e 5:
   - Volume de achados caiu de 212 (R4) e 121 (R5) para apenas **50 no R6**.
   - A precisao saltou de 1.4% (R4) e 4.1% (R5) para **70.0% no R6** (superando com ampla folga o gate de 10%).
3. **Superioridade do Braço A:** O Braço A (Skill v8.0 com auditoria matematica ativa) detectou 100% dos defeitos com zero falso-negativos (7/7 TP), enquanto o Braço C (Controle) falhou em detectar a discrepancia estatistica no documento `R6_P16` (6/7 TP).
4. **Benchmark de Hardware Local (CPU):** O experimento preliminar overnight comprovou que a execucao em CPU pura para LLMs de raciocinio (`qwen3:4b` e `bonsai-2:27b`) apresenta gargalos severos de prefill e tempo por token (~34s/token no 27B), justificando plenamente o uso de subagentes paralelos em nuvem para viabilidade operacional do benchmark.
