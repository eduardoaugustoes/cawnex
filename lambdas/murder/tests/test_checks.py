"""Tests for deterministic MVI checks."""

from murder.checks import (
    CheckResult,
    CheckSeverity,
    run_deterministic_checks,
)


class TestCheckResult:
    def test_passed_check(self) -> None:
        result = CheckResult(
            name="tests_pass",
            passed=True,
            severity=CheckSeverity.HARD,
            detail="All 42 tests passed",
        )
        assert result.passed is True
        assert result.severity == CheckSeverity.HARD

    def test_failed_hard_check(self) -> None:
        result = CheckResult(
            name="no_secrets",
            passed=False,
            severity=CheckSeverity.HARD,
            detail="AWS key found in config.py",
        )
        assert result.passed is False
        assert result.is_hard_block is True

    def test_failed_soft_check(self) -> None:
        result = CheckResult(
            name="lint_passes",
            passed=False,
            severity=CheckSeverity.SOFT,
            detail="3 lint warnings",
        )
        assert result.passed is False
        assert result.is_hard_block is False


class TestRunDeterministicChecks:
    def test_all_checks_pass(self) -> None:
        outcome = {
            "test_results": {"exit_code": 0, "summary": "42 passed"},
            "lint_results": {"exit_code": 0, "summary": "no issues"},
            "coverage_delta": {"before": 80.0, "after": 82.0},
        }
        mvi_item = {
            "acceptance_criteria": "Users can log in with email and password",
        }

        results = run_deterministic_checks(outcome, mvi_item)

        passed = [r for r in results if r.passed]
        failed = [r for r in results if not r.passed]
        assert len(failed) == 0
        assert len(passed) >= 3

    def test_tests_fail_is_hard_block(self) -> None:
        outcome = {
            "test_results": {"exit_code": 1, "summary": "2 failed"},
            "lint_results": {"exit_code": 0, "summary": "no issues"},
            "coverage_delta": {"before": 80.0, "after": 82.0},
        }
        mvi_item = {"acceptance_criteria": ""}

        results = run_deterministic_checks(outcome, mvi_item)

        tests_check = next(r for r in results if r.name == "tests_pass")
        assert tests_check.passed is False
        assert tests_check.is_hard_block is True

    def test_coverage_drop_is_soft_signal(self) -> None:
        outcome = {
            "test_results": {"exit_code": 0, "summary": "42 passed"},
            "lint_results": {"exit_code": 0, "summary": "no issues"},
            "coverage_delta": {"before": 80.0, "after": 75.0},
        }
        mvi_item = {"acceptance_criteria": ""}

        results = run_deterministic_checks(outcome, mvi_item)

        coverage_check = next(r for r in results if r.name == "coverage_no_drop")
        assert coverage_check.passed is False
        assert coverage_check.is_hard_block is False

    def test_missing_outcome_fields_gracefully_handled(self) -> None:
        outcome: dict = {}
        mvi_item = {"acceptance_criteria": ""}

        results = run_deterministic_checks(outcome, mvi_item)

        tests_check = next(r for r in results if r.name == "tests_pass")
        assert tests_check.passed is False
        assert tests_check.is_hard_block is True

    def test_to_dict_serialization(self) -> None:
        result = CheckResult(
            name="tests_pass",
            passed=True,
            severity=CheckSeverity.HARD,
            detail="All passed",
        )
        d = result.to_dict()
        assert d == {
            "name": "tests_pass",
            "passed": True,
            "severity": "hard",
            "detail": "All passed",
        }
