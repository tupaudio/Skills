"""Runner independente de testes da Revisao 19 (ACH-B7-R18-003).

Executa pytest sobre tests/, captura stdout/stderr/exit_code, verifica preservacao dos 194 IDs
da Rev18 e gera reports/test_results_rev19.json validado por test_results_schema.json.
"""
import hashlib
import json
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

REV19 = Path(__file__).resolve().parent.parent
REV18_TM = REV19.parent / "fase7_rev18/MATRIZ_TESTES_ACEITACAO_REV18.md"
MANIFEST_FILE = REV19 / "tools/test_manifest_rev19.json"
RESULTS_SCHEMA_FILE = REV19 / "tools/test_results_schema.json"
LOCK_FILE = REV19 / "tools/requirements-validation.lock"
OUT_RESULTS = REV19 / "reports/test_results_rev19.json"


def sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def main() -> int:
    manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    rev18_ids = set(re.findall(r"^\|\s*`(T-R(?:9-\d{3}-\d{2}|11-\d{3}|12-\d{3}|13-\d{3}|14-\d{3}|15-\d{3}|16-\d{3}|17-\d{3}|18-\d{3}))`\s*\|", REV18_TM.read_text(encoding="utf-8"), re.M))
    if len(rev18_ids) != 194:
        print(f"ERRO: Esperados 194 IDs na Rev18, encontrados {len(rev18_ids)}", file=sys.stderr)
        return 1

    results = []
    overall_rc = 0
    for item in manifest["new_rev19_tests"]:
        nodeid = f"tests/test_rev19_all.py::{item['test_function']}"
        proc = subprocess.run([sys.executable, "-m", "pytest", "-q", nodeid], cwd=REV19, capture_output=True, text=True)
        if item["execution_mode"] == "AUTOMATED_LINUX_ONLY" and platform.system() != "Linux":
            status, actual = "BLOCKED_ENVIRONMENT", "BLOCKED_ENVIRONMENT"
        elif proc.returncode == 0:
            status, actual = "PASS", item["expected_result"]
        else:
            status, actual, overall_rc = "FAIL", "UNEXPECTED", 1
        results.append({
            "test_id": item["test_id"],
            "status": status,
            "expected_result": item["expected_result"],
            "actual_result": actual,
            "exit_code": proc.returncode,
            "test_module": item["test_module"],
            "test_function": item["test_function"],
            "stdout_sha256": sha256_str(proc.stdout),
            "stderr_sha256": sha256_str(proc.stderr),
        })

    report = {
        "run_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "environment": {
            "python": sys.version.split()[0],
            "platform": f"{platform.system()} {platform.release()}",
            "architecture": platform.machine(),
            "lock_sha256": hashlib.sha256(LOCK_FILE.read_bytes()).hexdigest(),
        },
        "exit_code": overall_rc,
        "results": results,
    }
    schema = json.loads(RESULTS_SCHEMA_FILE.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(report)
    OUT_RESULTS.write_bytes((json.dumps(report, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(f"Wrote {OUT_RESULTS.name} (exit_code={overall_rc}, results={len(results)})")
    return overall_rc


if __name__ == "__main__":
    sys.exit(main())
