"""Type check runner: mypy."""

from __future__ import annotations

import subprocess
import time

from worker.integrator.findings import CheckResult

TYPECHECK_TIMEOUT_SECONDS = 120


def run_typecheck(integration_path: str) -> CheckResult:
    """Run mypy on the integration worktree."""
    start = time.time()
    try:
        result = subprocess.run(
            ["mypy", "."],
            cwd=integration_path,
            capture_output=True,
            timeout=TYPECHECK_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        return CheckResult(
            status="skipped",
            failures=[],
            duration_ms=int((time.time() - start) * 1000),
            command="mypy .",
        )
    except subprocess.TimeoutExpired:
        return CheckResult(
            status="timeout",
            failures=["mypy timed out"],
            duration_ms=TYPECHECK_TIMEOUT_SECONDS * 1000,
            command="mypy .",
        )

    duration_ms = int((time.time() - start) * 1000)
    if result.returncode == 0:
        return CheckResult(
            status="ok", failures=[], duration_ms=duration_ms, command="mypy ."
        )

    failures = [
        line.strip()
        for line in result.stdout.decode().splitlines()[:5]
        if line.strip() and "error:" in line
    ]
    return CheckResult(
        status="fail",
        failures=failures,
        duration_ms=duration_ms,
        command="mypy .",
    )
