"""Tests for typecheck runner."""

from unittest.mock import MagicMock, patch

from worker.integrator.checks.typecheck import run_typecheck


def test_run_typecheck_ok_when_mypy_clean() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout=b"Success: no issues found", stderr=b""
        )
        result = run_typecheck(integration_path="/mnt/repos/T/t/r/.integration")
        assert result.status == "ok"


def test_run_typecheck_fail_captures_first_5_errors() -> None:
    mypy_output = b"""src/foo.py:10: error: incompatible types
src/bar.py:20: error: missing return type
src/baz.py:5: error: unused import
src/qux.py:100: error: invalid syntax
src/zap.py:1: error: name not found
src/extra.py:99: error: this should not appear
"""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1, stdout=mypy_output, stderr=b""
        )
        result = run_typecheck(integration_path="/mnt/repos/T/t/r/.integration")
        assert result.status == "fail"
        assert len(result.failures) == 5
        assert "extra.py" not in result.failures[-1]


def test_run_typecheck_skipped_when_mypy_missing() -> None:
    with patch("subprocess.run", side_effect=FileNotFoundError):
        result = run_typecheck(integration_path="/mnt/repos/T/t/r/.integration")
        assert result.status == "skipped"
