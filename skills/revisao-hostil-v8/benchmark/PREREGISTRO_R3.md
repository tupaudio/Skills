# Pré-Registro — Rodada 3 (Benchmark Científico Revisão Hostil v8.0)

**Data:** 2026-11-25  
**Branch:** `homologation/etapa2-benchmark-limpo`  
**Versão do runner:** `bench.py` `0.2.0` (entrypoint unificado, `max_span_lines`, contagem simétrica, âncoras múltiplas, descarte de documento sem casos).

## 1. Hipóteses
- **H1 (confirmatória):** limite inferior de Wilson 95% do `recall` $\ge 0{,}50$ no braço com Skill e ferramentas.
- **H2 (confirmatória):** limite inferior de Wilson 95% da `especificidade` $\ge 0{,}70$.
- **H3 (exploratória):** diferença pareada por defeito entre braço com Skill (A) e sem Skill (C).
- **H4 (exploratória):** diferença entre braço com ferramentas (B) e sem ferramentas (A).

## 2. Splits e Gabarito
- **`calibracao`:** `A04` (9 casos herdados das Rodadas 1–2; `B04-NEG-002` removido conforme R3-0) e `A03`.
- **`validacao`:** `A01_INJ` (`docs/artigo01_inj.md`, SHA-256 `ce9f37dd...`) e `A02_INJ` (`docs/artigo02_inj.md`, SHA-256 `77a54e9b...`):
  - **20 `DEFECT` injetados controlados** (`10` em `A01_INJ` + `10` em `A02_INJ`, categorias `resultado_numerico`, `unidades`, `inconsistencia_interna`).
  - **20 `NEGATIVE_CONTROL`** (`10` em `A01_INJ` + `10` em `A02_INJ`, regra de 1 afirmação verificada por linha em Python).
  - Todos os 40 casos adjudicados pelo usuário (`validated_by: "Dafnhê Thor"`) antes de qualquer revisor ver os textos.
  - **Transparência metodológica:** os defeitos de `A01_INJ` e `A02_INJ` são **injetados controlados** (não defeitos naturais espontâneos) e um agente da família Gemini auxiliou na triagem/injeção inicial; modelos da família Gemini serão rotulados como mesma família no relatório.

## 3. Parâmetros e Limiares (`thresholds.json`)
- `min_defects = 10`, `min_negatives = 10` (com `n = 20` defeitos e `n = 20` controles em validação).
- `recall_lower_bound_min = 0.50`, `specificity_lower_bound_min = 0.70`, `precision_pessimistic_min = 0.10`.
- `max_span_lines = 10` (**derivado da calibração em `A04`**, onde manteve achados legítimos de 6 linhas e descartou spans de 56 e 270 linhas).
- **Tolerância numérica:** `1%`.
- **Gate:** usa `recall` por linha; `recall_categoria` apenas como reporte paralelo.

## 4. Higiene e Privacidade
- Nenhum texto de manuscrito, parecer ou `lock.json` entra no Git.
- Todas as âncoras de `cases.json` usam `line_start`/`line_end` + `line_sha256` (0 caracteres literais do manuscrito no Git).

## 5. Registro do Lock — Rodada 3 (2026-11-25)

- **Data UTC:** `2026-11-25T05:16:57.056471+00:00`
- **Commit HEAD no momento do lock:** `b131b8a887fb84152ae0b16ac4ed342380af857e`
- **SHA-256 de `benchmark/lock.json` (local, fora do Git):** `bc79c871a6cbffbfc6c444d310e3d7c782803daa0edd0205b9724791b6cf5670`
- **`validation_cases_sha256`:** `7dc49f2a707c36d4d92d0e75b61f0624d586765a67af2c2160e60587e100040a`
- **`thresholds_sha256`:** `4a53739bd25c9415326684f9c644b6856b5c2716e2b5f6c43b5073ec1604ca16`
- **`manifest_sha256`:** `a3351a2981bbed6022521f59a4b46dfa2ddab7d7cd10f56b1614c54c2c285100`
- **`frozen_files_sha256`:**
  - `../scripts/auditor.py`: `bcbf39be01a7188c6f10fac67a6d0406e68aaa60b3999764f2a15f0c9300974c`
  - `bench.py`: `d44566182092ec98fac204a251caa7ecd5aa8caede9c07eba3da6dab67d0d408`
  - `adapters/estrutural_json.py`: `2ae5952f47f64d53c171944dec07a0fd380aef69b35c6944cfa6a5b73fd190c5`
  - `adapters/achados_arquivo.py`: `6d13143d50c4c1dbd7e9ecf1f823154968024bec6ad1571fb329e4666605b9a5`

