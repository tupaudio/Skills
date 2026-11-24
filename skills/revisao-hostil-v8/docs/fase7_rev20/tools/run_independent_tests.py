"""Runner independente de testes da Revisao 20 com JUnit XML (ACH-B7-R19-003 e ACH-B7-R19-004).

Nunca classifica 'skipped' como 'PASS'; falha se um teste obrigatorio for ignorado na plataforma alvo.
"""
import hashlib
import json
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

REV20 = Path(__file__).resolve().parent.parent
JUNIT_XML = REV20 / "reports/pytest-results.xml"
RESULTS_JSON = REV20 / "reports/test_results_rev20.json"
RESULTS_SCHEMA = REV20 / "tools/test_results_schema.json"
LOCK_FILE = REV20 / "tools/requirements-validation.lock"

TEST_MAP = [
    ("T-R20-200", "tests.test_historical_preservation", "test_historical_id_sets_preserved", "ACCEPT", "ALL"),
    ("T-R20-201", "tests.test_rev20_all", "test_trusted_utc_clock_and_operational_guard", "REJECT", "ALL"),
    ("T-R20-202", "tests.test_rev20_all", "test_dossier_trust_binding_and_providers", "REJECT", "ALL"),
    ("T-R20-203", "tests.test_rev20_all", "test_windows_qpc_lifecycle_with_boot_id", "ACCEPT", "Windows"),
    ("T-R20-204", "tests.test_rev20_all", "test_linux_monotonic_raw_lifecycle_with_boot_id", "ACCEPT", "Linux"),
    ("T-R20-205", "tests.test_rev20_all", "test_revocation_list_individual_entries", "REJECT", "ALL"),
]


def sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def main() -> int:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", f"--junitxml={JUNIT_XML}", "tests/"],
        cwd=REV20,
        capture_output=True,
        text=True,
    )
    tree = ET.parse(JUNIT_XML)
    cases = {}
    for tc in tree.findall(".//testcase"):
        name = tc.attrib["name"]
        if tc.find("failure") is not None:
            cases[name] = "failed"
        elif tc.find("error") is not None:
            cases[name] = "error"
        elif tc.find("skipped") is not None:
            cases[name] = "skipped"
        else:
            cases[name] = "passed"

    cur_os = platform.system()
    xml_sha = hashlib.sha256(JUNIT_XML.read_bytes()).hexdigest()
    results = []
    overall_rc = 0
    for tid, mod, fn, expected, target_os in TEST_MAP:
        outcome = cases.get(fn, "error")
        if outcome == "passed":
            status, actual = "PASS", expected
        elif outcome == "skipped":
            if target_os != "ALL" and target_os != cur_os:
                status, actual = "BLOCKED_ENVIRONMENT", "BLOCKED_ENVIRONMENT"
            else:
                status, actual, overall_rc = "FAIL", "UNJUSTIFIED_SKIP", 1
        else:
            status, actual, overall_rc = "FAIL", outcome.upper(), 1
        results.append({
            "test_id": tid,
            "status": status,
            "expected_result": expected,
            "actual_result": actual,
            "exit_code": 0 if status in {"PASS", "BLOCKED_ENVIRONMENT"} else 1,
            "test_module": mod,
            "test_function": fn,
            "stdout_sha256": sha256_str(proc.stdout),
            "stderr_sha256": sha256_str(proc.stderr),
            "artifact_sha256": xml_sha,
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
    schema = json.loads(RESULTS_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(report)
    RESULTS_JSON.write_bytes((json.dumps(report, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(f"Wrote {RESULTS_JSON.name} (exit_code={overall_rc}, passed={sum(r['status']=='PASS' for r in results)}, blocked={sum(r['status']=='BLOCKED_ENVIRONMENT' for r in results)})")
    return overall_rc


if __name__ == "__main__":
    sys.exit(main())
