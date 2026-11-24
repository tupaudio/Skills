"""Gera MATRIZ_TESTES_ACEITACAO_REV19.md a partir dos 194 IDs da Rev18 e reports/test_results_rev19.json."""
import json
from pathlib import Path

REV19 = Path(__file__).resolve().parent.parent
rev18 = (REV19.parent / "fase7_rev18/MATRIZ_TESTES_ACEITACAO_REV18.md").read_text(encoding="utf-8")
res = json.loads((REV19 / "reports/test_results_rev19.json").read_text(encoding="utf-8"))["results"]
rows = "\n".join(
    f"| `{r['test_id']}` | `{r['test_module']}.{r['test_function']}` | `{r['expected_result']}` | `{r['actual_result']}` | `{r['exit_code']}` | `{r['status']}` |"
    for r in res
)
out = (
    rev18.replace("REVISÃO 18", "REVISÃO 19")
    + "\n\n---\n\n## 10. Novos Cenários Executáveis da Revisão 19 (`5` cenários — `T-R19-195` a `T-R19-199`, gerados de `reports/test_results_rev19.json`)\n\n"
    + "| ID | Função Executável | Esperado | Observado | Exit Code | Status |\n"
    + "| :--- | :--- | :---: | :---: | :---: | :---: |\n"
    + rows
    + "\n\n**Total consolidado:** `199` cenários (`194` históricos preservados + `5` novos Rev19).\n"
)
(REV19 / "MATRIZ_TESTES_ACEITACAO_REV19.md").write_text(out, encoding="utf-8")
print("Wrote MATRIZ_TESTES_ACEITACAO_REV19.md (199 scenarios)")
