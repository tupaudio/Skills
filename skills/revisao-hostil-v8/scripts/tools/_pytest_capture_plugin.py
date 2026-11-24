"""Plugin pytest programático para captura fiel de métricas e ambiente (ACH-B6.2-001).

Ativado quando a variável de ambiente `RH_PYTEST_CAPTURE_JSON` está definida.
Elimina dependência de regex sobre logs como fonte primária de resultados.
"""

from __future__ import annotations

import json
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any

import pytest


class _CaptureState:
    def __init__(self) -> None:
        self.t0 = time.perf_counter()
        self.collected = 0
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.collection_errors = 0
        self.warnings = 0


_STATE: _CaptureState | None = None


def pytest_sessionstart(session: pytest.Session) -> None:
    global _STATE
    _STATE = _CaptureState()


def pytest_collection_finish(session: pytest.Session) -> None:
    if _STATE is not None:
        _STATE.collected = len(session.items)


def pytest_collectreport(report: pytest.CollectReport) -> None:
    if _STATE is not None and report.failed:
        _STATE.collection_errors += 1


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    if _STATE is None:
        return
    if report.when == "call":
        if report.passed:
            _STATE.passed += 1
        elif report.failed:
            _STATE.failed += 1
        elif report.skipped:
            _STATE.skipped += 1
    elif report.when in ("setup", "teardown") and report.failed:
        _STATE.failed += 1
    elif report.when == "setup" and report.skipped:
        _STATE.skipped += 1


def pytest_warning_recorded(warning_message: Any, when: str, nodeid: str, location: Any) -> None:
    if _STATE is not None:
        _STATE.warnings += 1


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    out_path = os.environ.get("RH_PYTEST_CAPTURE_JSON")
    if not out_path or _STATE is None:
        return
    duration_s = time.perf_counter() - _STATE.t0
    payload = {
        "run_id": os.environ.get("RH_RUN_ID", ""),
        "pytest_version": pytest.__version__,
        "python_version": sys.version.split()[0],
        "python_implementation": platform.python_implementation(),
        "os_name": platform.system(),
        "os_release": platform.release(),
        "os_build": platform.version(),
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "virtual_env": os.environ.get("VIRTUAL_ENV") or sys.prefix,
        "collected": _STATE.collected,
        "passed": _STATE.passed,
        "failed": _STATE.failed,
        "skipped": _STATE.skipped,
        "collection_errors": _STATE.collection_errors,
        "warnings": _STATE.warnings,
        "duration_seconds": duration_s,
        "exit_code": int(exitstatus),
        "command": sys.executable,
        "args": list(sys.argv),
    }
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
