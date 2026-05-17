"""Tests for lint check runner."""

import subprocess as sp
from unittest.mock import MagicMock, patch

from worker.integrator.checks.lint import run_lint


def test_run_lint_ok_when_black_and_flake8_clean() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
        result = run_lint(integration_path="/mnt/repos/T/t/r/.integration")
        assert result.status == "ok"
        assert result.failures == []


def test_run_lint_fail_when_black_reports_problems() -> None:
    calls = [
        MagicMock(
            returncode=1,
            stdout=b"would reformat foo.py\nwould reformat bar.py\n",
            stderr=b"",
        ),
        MagicMock(returncode=0, stdout=b"", stderr=b""),
    ]
    with patch("subprocess.run", side_effect=calls):
        result = run_lint(integration_path="/mnt/repos/T/t/r/.integration")
        assert result.status == "fail"
        assert "foo.py" in result.failures[0]


def test_run_lint_skipped_when_tools_missing() -> None:
    with patch("subprocess.run", side_effect=FileNotFoundError):
        result = run_lint(integration_path="/mnt/repos/T/t/r/.integration")
        assert result.status == "skipped"


def test_run_lint_timeout_treated_as_failure() -> None:
    with patch(
        "subprocess.run", side_effect=sp.TimeoutExpired(cmd="black", timeout=60)
    ):
        result = run_lint(integration_path="/mnt/repos/T/t/r/.integration")
        assert result.status == "timeout"
