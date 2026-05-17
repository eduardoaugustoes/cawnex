"""Tests for pytest check runner."""

from unittest.mock import MagicMock, patch

from worker.integrator.checks.tests import run_tests


def test_run_tests_ok_when_pytest_passes() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=b"5 passed", stderr=b"")
        result = run_tests(integration_path="/mnt/repos/T/t/r/.integration")
        assert result.status == "ok"


def test_run_tests_fail_captures_first_5_failures() -> None:
    pytest_output = b"""FAILED tests/test_a.py::test_one - AssertionError
FAILED tests/test_a.py::test_two - ValueError
FAILED tests/test_b.py::test_three - KeyError
FAILED tests/test_c.py::test_four - TypeError
FAILED tests/test_d.py::test_five - RuntimeError
FAILED tests/test_e.py::test_six - LookupError
1 passed, 6 failed
"""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1, stdout=pytest_output, stderr=b""
        )
        result = run_tests(integration_path="/mnt/repos/T/t/r/.integration")
        assert result.status == "fail"
        assert len(result.failures) == 5


def test_run_tests_skipped_when_pytest_missing() -> None:
    with patch("subprocess.run", side_effect=FileNotFoundError):
        result = run_tests(integration_path="/mnt/repos/T/t/r/.integration")
        assert result.status == "skipped"
