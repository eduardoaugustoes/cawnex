"""Tests for check orchestration runner."""

from unittest.mock import patch

from worker.integrator.checks.runner import overall_from_checks, run_all_checks
from worker.integrator.findings import CheckResult


def test_run_all_checks_returns_three_results() -> None:
    ok = CheckResult(status="ok", failures=[], duration_ms=10, command="x")
    with patch(
        "worker.integrator.checks.runner.run_lint", return_value=ok
    ), patch(
        "worker.integrator.checks.runner.run_typecheck", return_value=ok
    ), patch(
        "worker.integrator.checks.runner.run_tests", return_value=ok
    ):
        lint, typecheck, tests = run_all_checks("/integration")
        assert lint.status == "ok"
        assert typecheck.status == "ok"
        assert tests.status == "ok"


def test_run_all_checks_aggregates_overall_ok_when_all_pass_or_skip() -> None:
    ok = CheckResult(status="ok", failures=[], duration_ms=10, command="x")
    skipped = CheckResult(status="skipped", failures=[], duration_ms=0, command="y")
    overall, reasons = overall_from_checks(ok, skipped, ok)
    assert overall == "ready_for_council"
    assert reasons == []


def test_run_all_checks_aggregates_overall_needs_rework_on_any_fail() -> None:
    ok = CheckResult(status="ok", failures=[], duration_ms=10, command="x")
    fail = CheckResult(
        status="fail",
        failures=["foo.py:1: error: bad"],
        duration_ms=5,
        command="mypy .",
    )
    overall, reasons = overall_from_checks(ok, fail, ok)
    assert overall == "needs_rework"
    assert any("typecheck" in r for r in reasons)
