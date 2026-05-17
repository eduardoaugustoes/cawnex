"""Tests check runner: pytest."""

from __future__ import annotations

import subprocess
import time

from worker.integrator.findings import CheckResult

TESTS_TIMEOUT_SECONDS = 300


def run_tests(integration_path: str) -> CheckResult:
    """Run pytest on the integration worktree."""
    start = time.time()
    try:
        result = subprocess.run(
            ["pytest", "--tb=short", "-q"],
            cwd=integration_path,
            capture_output=True,
            timeout=TESTS_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        return CheckResult(
            status="skipped",
            failures=[],
            duration_ms=int((time.time() - start) * 1000),
            command="pytest --tb=short -q",
        )
    except subprocess.TimeoutExpired:
        return CheckResult(
            status="timeout",
            failures=["pytest timed out — split into smaller suites or raise timeout"],
            duration_ms=TESTS_TIMEOUT_SECONDS * 1000,
            command="pytest --tb=short -q",
        )

    duration_ms = int((time.time() - start) * 1000)
    if result.returncode == 0:
        return CheckResult(
            status="ok",
            failures=[],
            duration_ms=duration_ms,
            command="pytest --tb=short -q",
        )

    failures = [
        line.strip()
        for line in result.stdout.decode().splitlines()[:50]
        if line.strip().startswith("FAILED")
    ][:5]
    return CheckResult(
        status="fail",
        failures=failures,
        duration_ms=duration_ms,
        command="pytest --tb=short -q",
    )
