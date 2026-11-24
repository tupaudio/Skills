"""Gera ENVIRONMENT_FINGERPRINT.json com metadados reais do ambiente e hash do lock (ACH-B7-R18-006)."""
import hashlib
import importlib.metadata
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
LOCK_FILE = TOOLS_DIR / "requirements-validation.lock"
OUT_FILE = TOOLS_DIR / "ENVIRONMENT_FINGERPRINT.json"


def main() -> None:
    lock_sha = hashlib.sha256(LOCK_FILE.read_bytes()).hexdigest()
    deps = {}
    for pkg in ("rfc8785", "jcs", "cryptography", "jsonschema", "pytest", "pip"):
        deps[pkg] = importlib.metadata.version(pkg)
    fp = {
        "collected_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "python_version": sys.version,
        "python_implementation": platform.python_implementation(),
        "os": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "lock_file": "tools/requirements-validation.lock",
        "lock_sha256": lock_sha,
        "installed_versions": deps,
    }
    OUT_FILE.write_bytes((json.dumps(fp, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(f"Wrote {OUT_FILE.name} (lock_sha256={lock_sha})")


if __name__ == "__main__":
    main()
