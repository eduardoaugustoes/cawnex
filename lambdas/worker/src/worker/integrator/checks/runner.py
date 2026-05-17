"""Orchestrates all deterministic checks and aggregates overall verdict."""

from __future__ import annotations

from typing import Literal

from worker.integrator.checks.lint import run_lint
from worker.integrator.checks.tests import run_tests
from worker.integrator.checks.typecheck import run_typecheck
from worker.integrator.findings import CheckResult


def run_all_checks(
    integration_path: str,
) -> tuple[CheckResult, CheckResult, CheckResult]:
    """Run lint, typecheck, tests in sequence. Returns (lint, typecheck, tests)."""
    return (
        run_lint(integration_path),
        run_typecheck(integration_path),
        run_tests(integration_path),
    )


def overall_from_checks(
    lint: CheckResult,
    typecheck: CheckResult,
    tests: CheckResult,
) -> tuple[Literal["ready_for_council", "needs_rework"], list[str]]:
    """Aggregate the three check results into an overall verdict + reasons."""
    failed_checks: list[tuple[str, CheckResult]] = []
    for name, result in [("lint", lint), ("typecheck", typecheck), ("tests", tests)]:
        if result.status in ("fail", "timeout", "error"):
            failed_checks.append((name, result))

    if not failed_checks:
        return "ready_for_council", []

    reasons: list[str] = []
    for name, result in failed_checks:
        if result.status == "timeout":
            reasons.append(f"{name} timed out after {result.duration_ms // 1000}s")
        elif result.status == "error":
            err = result.failures[0] if result.failures else "unknown"
            reasons.append(f"{name} errored: {err}")
        else:
            top_failures = "; ".join(result.failures[:3])
            reasons.append(f"{name} failed: {top_failures}")

    return "needs_rework", reasons
