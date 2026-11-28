# Relatório Forense de Defeitos — Base v6.0 (Fase 0)

**Data:** 2026-11-23  
**Base auditada:** `versions/v6.0-legacy/` (cópia imutável da v6.0 instalada em `<USER_HOME>\.gemini\config\skills\revisao-hostil`)  
**Compilação sintática (`python -m py_compile`):** APROVADA (`exit code 0` em ambos os scripts).

---

## 1. Defeitos Confirmados em `motor_matematico.py`

| ID | Gravidade | Localização | Defeito Comprovado | Ação Planejada (Fase 2) |
| :--- | :--- | :--- | :--- | :--- |
| **DEF-M01** | `ALTA` | `audit_matrix` (L355–360) e `solve_linear_system` (L322–331) | Executa `np.linalg.matrix_rank(A)` **antes** de verificar `np.isfinite(A).all()`. Entrada com `NaN`/`Inf` derruba a operação com `LinAlgError: SVD did not converge` em vez de validar e rejeitar a entrada de forma controlada. | Validar `np.isfinite(A).all()` e `np.isfinite(b).all()` antes de qualquer operação matricial/linear. |
| **DEF-M02** | `ALTA` | `plug_in_check` (L190–215) | Quando o cálculo produz número complexo (ex.: `log(-1)`), `calculated_value` vira lista `[re, im]`, falhando `isinstance(calculated_value, float)` e retornando `status: "calculated"` sem comparar nem acusar discrepância frente ao `reported_value` real. | Sinalizar explicitamente `complex_result_vs_real_reported` como discrepância ou resultado fora do domínio real. |
| **DEF-M03** | `ALTA` | `SafeExpressionParser` + `integrate` (L118–125, L299–301) | Limites infinitos (`"oo"`, `"-oo"`, `"inf"`) passados como string são convertidos em `sp.Symbol("oo")` pelo `auto_declare=True`, em vez de `sp.oo`. `integrate(exp(-x), x, 0, "oo")` não avalia para `1.0`. | Registrar `oo` e `inf` como `sp.oo` no parser ou tratar limites infinitos explicitamente em `integrate`. |
| **DEF-M04** | `MÉDIA` | `solve_ode_bvp` (L431–489) | O parâmetro `interval` é exigido na assinatura e no despachante `execute_single_operation`, mas **nunca é utilizado** nem validado contra `mesh[0]` e `mesh[-1]`. Além disso, `ode_bvp` não aceita `parameters`. | Validar `mesh` contra `interval` (ou gerar malha quando omitida) e suportar `parameters`. |
| **DEF-M05** | `MÉDIA` | `solve_ode_ivp` (L393–396) | Se um item em `parameters` não for numérico, é convertido silenciosamente em `sp.Symbol(k)` e explode depois dentro do `solve_ivp` (`Cannot convert expression to float`). | Validar tipos numéricos finitos em `parameters` antes de montar o sistema. |
| **DEF-M06** | `MÉDIA` | `SafeExpressionParser.parse` (L121) | `symbols.setdefault("e", sp.E)` captura silenciosamente a letra `e` (excentricidade, espessura, erro) caso o usuário esqueça de passá-la em `substitutions`, gerando cálculo incorreto em vez de `incomplete_parameters`. | Reservar `E` para constante de Euler e só mapear `e` quando não houver conflito explícito (ou documentar/restringir). |
| **DEF-M07** | `MÉDIA` | `audit_ahp_matrix` + `process_payload` (L580–600, L746–749) | Quando a matriz AHP é inválida (`valid: False`), `process_payload` ainda marca `"success": True`, criando contrato ambíguo. Além disso, tolerância fixa `1e-6` rejeita arredondamentos comuns de tabela (ex.: `0.33` para `1/3`). | Padronizar envelope de saída via `schema_motor.json`, distinguindo erro de execução de achado de validação. |
| **DEF-M08** | `BAIXA` | Geral | Ausência de suíte de testes unitários e negativos; operações estatísticas ainda não existem na v6.0 (serão criadas no `motor_estatistico.py` na Fase 3). | Criar suíte `pytest` cobrindo todas as 13 operações + casos limites na Fase 2. |

---

## 2. Defeitos Confirmados em `auditor.py`

| ID | Gravidade | Localização | Defeito Comprovado | Ação Planejada (Fase 2) |
| :--- | :--- | :--- | :--- | :--- |
| **DEF-A01** | `ALTA` | `ABSOLUTE_CLAIMS` (L37) | A regex `r"\b(100\s*%|...)\b"` **nunca casa `100%` seguido de espaço** porque `%` não é caractere de palavra (`\w`), invalidando o `\b` final. Comprovado em teste: `"100% de eficiência"` retornou `0` achados de `absolute_claim`. | Substituir `\b` final após `%` por lookahead de fronteira não alfanumérica e testar todas as regex individualmente. |
| **DEF-A02** | `MÉDIA` | `ABSOLUTE_CLAIMS`, `MATH_TERMS`, `POWER_ENERGY_CONFUSION` (L35–167) | Regras específicas de engenharia/aeroespacial (`zero eclipse`, `Stefan-Boltzmann`, `Lyapunov`, `MPC`, `AHP`, potência vs. energia) estão hardcoded no script genérico. | Separar extração/triagem genérica das regras de domínio (que migrarão para perfis YAML). |
| **DEF-A03** | `MÉDIA` | `audit_structured_lines` (L277–418) | Achados não possuem `id` único, schema validado, estado formal de ciclo de vida (`ABERTO`, `CONFIRMADO`, etc.) nem manifesto de execução. | Adotar `schema_achado.json`, `evidence.py` e `run_manifest.json` na Fase 2. |
| **DEF-A04** | `BAIXA` | `extract_content` (L237–274) | Não há proteção explícita contra caminhos maliciosos/arquivos muito grandes ou codificações anômalas além de `errors="replace"`; sem suporte nativo a extração estruturada de tabelas/equações separadas. | Modularizar extratores e adicionar validações de entrada na Fase 2. |

---

## 3. Defeitos de Portabilidade, Segurança e Ambiente

| ID | Gravidade | Localização | Defeito Comprovado | Ação Planejada |
| :--- | :--- | :--- | :--- | :--- |
| **DEF-S01** | `ALTA` | `SKILL.md` (L72, L97) | Caminhos absolutos Windows hardcoded (`<USER_HOME>\.gemini\config\skills\revisao-hostil\scripts\...`), quebrando instalação limpa e portabilidade. | Usar caminhos relativos à raiz da skill / resolução dinâmica no orquestrador. |
| **DEF-S02** | `MÉDIA` | Ambiente Python | `PyYAML` e `jsonschema` não estão instalados no ambiente atual (`Python 3.14.6`), sendo pré-requisitos para os contratos JSON e perfis YAML da Fase 2/6. | Registrar em `pyproject.toml`/`requirements.txt` na Fase 2 e validar em instalação limpa (Fase 10). |
| **DEF-S03** | `BAIXA` | Segurança | `SafeExpressionParser` já evita `eval`/`exec` (ponto positivo), mas não limita profundidade da AST nem expoentes gigantes (ex.: `9**9**9`), criando risco de DoS local com manuscritos maliciosos. | Adicionar limite de profundidade AST, tamanho máximo de expressão e teto de expoente em `SafeExpressionParser`. |
