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
            "diff": "def login(email, password):\n    return authenticate(email, password)",
        }
        mvi_item = {
            "acceptance_criteria": "Users can log in with email and password",
        }

        results = run_deterministic_checks(outcome, mvi_item)

        passed = [r for r in results if r.passed]
        failed = [r for r in results if not r.passed]
        assert len(failed) == 0
        assert len(passed) == 6

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

    def test_returns_six_checks(self) -> None:
        results = run_deterministic_checks({}, {"acceptance_criteria": ""})
        assert len(results) == 6
        names = {r.name for r in results}
        assert names == {
            "tests_pass",
            "no_secrets",
            "integration",
            "lint_passes",
            "coverage_no_drop",
            "acceptance_criteria",
        }


class TestNoSecretsCheck:
    def test_detects_aws_access_key(self) -> None:
        outcome = {"diff": "aws_key = 'AKIAIOSFODNN7EXAMPLE'"}
        results = run_deterministic_checks(outcome, {})
        check = next(r for r in results if r.name == "no_secrets")
        assert check.passed is False
        assert check.is_hard_block is True

    def test_detects_private_key(self) -> None:
        outcome = {"diff": "-----BEGIN RSA PRIVATE KEY-----\nMIIEo..."}
        results = run_deterministic_checks(outcome, {})
        check = next(r for r in results if r.name == "no_secrets")
        assert check.passed is False

    def test_detects_github_token(self) -> None:
        outcome = {"diff": "token = 'ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij'"}
        results = run_deterministic_checks(outcome, {})
        check = next(r for r in results if r.name == "no_secrets")
        assert check.passed is False

    def test_clean_diff_passes(self) -> None:
        outcome = {"diff": "def hello():\n    return 'world'"}
        results = run_deterministic_checks(outcome, {})
        check = next(r for r in results if r.name == "no_secrets")
        assert check.passed is True

    def test_no_diff_skips(self) -> None:
        results = run_deterministic_checks({}, {})
        check = next(r for r in results if r.name == "no_secrets")
        assert check.passed is True  # skipped = pass


class TestAcceptanceCriteriaCheck:
    def test_criteria_addressed(self) -> None:
        outcome = {
            "diff": "def authenticate(email, password):\n    token = jwt.encode(...)",
            "test_results": {"exit_code": 0, "summary": "test_login_email passed"},
        }
        mvi_item = {
            "acceptance_criteria": "- Users can authenticate with email and password\n- JWT token returned",
        }
        results = run_deterministic_checks(outcome, mvi_item)
        check = next(r for r in results if r.name == "acceptance_criteria")
        assert check.passed is True

    def test_criteria_not_addressed(self) -> None:
        outcome = {
            "diff": "def list_users():\n    return db.query()",
        }
        mvi_item = {
            "acceptance_criteria": "- Webhook integration with Stripe\n- Payment confirmation email sent",
        }
        results = run_deterministic_checks(outcome, mvi_item)
        check = next(r for r in results if r.name == "acceptance_criteria")
        assert check.passed is False
        assert check.is_hard_block is False  # soft signal

    def test_empty_criteria_skips(self) -> None:
        results = run_deterministic_checks({}, {"acceptance_criteria": ""})
        check = next(r for r in results if r.name == "acceptance_criteria")
        assert check.passed is True

    def test_no_criteria_key_skips(self) -> None:
        results = run_deterministic_checks({}, {})
        check = next(r for r in results if r.name == "acceptance_criteria")
        assert check.passed is True


class TestIntegrationCheck:
    def test_merge_conflict_is_hard_block(self) -> None:
        outcome = {
            "integration_check": {
                "merge_ok": False,
                "build_ok": False,
                "detail": "Conflict in src/auth.py",
            }
        }
        results = run_deterministic_checks(outcome, {})
        check = next(r for r in results if r.name == "integration")
        assert check.passed is False
        assert check.is_hard_block is True
        assert "Conflict" in check.detail

    def test_build_failure_is_hard_block(self) -> None:
        outcome = {
            "integration_check": {
                "merge_ok": True,
                "build_ok": False,
                "detail": "TypeError: missing argument",
            }
        }
        results = run_deterministic_checks(outcome, {})
        check = next(r for r in results if r.name == "integration")
        assert check.passed is False
        assert check.is_hard_block is True

    def test_clean_integration_passes(self) -> None:
        outcome = {
            "integration_check": {
                "merge_ok": True,
                "build_ok": True,
                "detail": "Clean merge, build passed",
            }
        }
        results = run_deterministic_checks(outcome, {})
        check = next(r for r in results if r.name == "integration")
        assert check.passed is True

    def test_no_integration_data_skips(self) -> None:
        results = run_deterministic_checks({}, {})
        check = next(r for r in results if r.name == "integration")
        assert check.passed is True
