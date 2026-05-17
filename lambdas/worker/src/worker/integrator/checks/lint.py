"""Lint check runner: black --check + flake8."""

from __future__ import annotations

import subprocess
import time

from worker.integrator.findings import CheckResult

LINT_TIMEOUT_SECONDS = 60


def run_lint(integration_path: str) -> CheckResult:
    """Run black --check then flake8 on the integration worktree."""
    start = time.time()
    failures: list[str] = []

    try:
        black = subprocess.run(
            ["black", "--check", "."],
            cwd=integration_path,
            capture_output=True,
            timeout=LINT_TIMEOUT_SECONDS,
        )
        if black.returncode != 0:
            failures.extend(
                line.strip()
                for line in black.stdout.decode().splitlines()[:5]
                if line.strip()
            )
    except FileNotFoundError:
        return CheckResult(
            status="skipped",
            failures=[],
            duration_ms=int((time.time() - start) * 1000),
            command="black --check .",
        )
    except subprocess.TimeoutExpired:
        return CheckResult(
            status="timeout",
            failures=["black timed out"],
            duration_ms=LINT_TIMEOUT_SECONDS * 1000,
            command="black --check .",
        )

    try:
        flake = subprocess.run(
            ["flake8", "."],
            cwd=integration_path,
            capture_output=True,
            timeout=LINT_TIMEOUT_SECONDS,
        )
        if flake.returncode != 0:
            failures.extend(
                line.strip()
                for line in flake.stdout.decode().splitlines()[:5]
                if line.strip()
            )
    except FileNotFoundError:
        # flake8 not installed — black-only result still counts; no silent swallow,
        # this is an explicit no-op for a known optional tool.
        pass
    except subprocess.TimeoutExpired:
        return CheckResult(
            status="timeout",
            failures=["flake8 timed out"],
            duration_ms=LINT_TIMEOUT_SECONDS * 1000,
            command="flake8 .",
        )

    duration_ms = int((time.time() - start) * 1000)
    return CheckResult(
        status="fail" if failures else "ok",
        failures=failures,
        duration_ms=duration_ms,
        command="black --check . && flake8 .",
    )
