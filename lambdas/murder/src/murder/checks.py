"""Deterministic MVI checks — run after reviewer approves, before ready_to_ship."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class CheckSeverity(Enum):
    HARD = "hard"
    SOFT = "soft"


@dataclass
class CheckResult:
    name: str
    passed: bool
    severity: CheckSeverity
    detail: str

    @property
    def is_hard_block(self) -> bool:
        return not self.passed and self.severity == CheckSeverity.HARD

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "severity": self.severity.value,
            "detail": self.detail,
        }


def _check_tests_pass(outcome: dict[str, Any]) -> CheckResult:
    test_results = outcome.get("test_results")
    if not test_results:
        return CheckResult(
            "tests_pass", False, CheckSeverity.HARD, "No test results found"
        )
    exit_code = test_results.get("exit_code", 1)
    summary = test_results.get("summary", "")
    return CheckResult(
        "tests_pass",
        exit_code == 0,
        CheckSeverity.HARD,
        summary if exit_code == 0 else f"Tests failed: {summary}",
    )


def _check_lint_passes(outcome: dict[str, Any]) -> CheckResult:
    lint_results = outcome.get("lint_results")
    if not lint_results:
        return CheckResult(
            "lint_passes", True, CheckSeverity.SOFT, "No lint results (skipped)"
        )
    exit_code = lint_results.get("exit_code", 1)
    summary = lint_results.get("summary", "")
    return CheckResult(
        "lint_passes",
        exit_code == 0,
        CheckSeverity.SOFT,
        summary if exit_code == 0 else f"Lint issues: {summary}",
    )


def _check_coverage_no_drop(outcome: dict[str, Any]) -> CheckResult:
    coverage = outcome.get("coverage_delta")
    if not coverage:
        return CheckResult(
            "coverage_no_drop",
            True,
            CheckSeverity.SOFT,
            "No coverage data (skipped)",
        )
    before = coverage.get("before", 0.0)
    after = coverage.get("after", 0.0)
    dropped = after < before
    detail = f"{before:.1f}% -> {after:.1f}%"
    return CheckResult(
        "coverage_no_drop",
        not dropped,
        CheckSeverity.SOFT,
        f"Coverage dropped: {detail}" if dropped else f"Coverage stable: {detail}",
    )


def run_deterministic_checks(
    outcome: dict[str, Any],
    mvi_item: dict[str, Any],
) -> list[CheckResult]:
    """Run all deterministic checks against crow outcome and MVI data."""
    return [
        _check_tests_pass(outcome),
        _check_lint_passes(outcome),
        _check_coverage_no_drop(outcome),
    ]
