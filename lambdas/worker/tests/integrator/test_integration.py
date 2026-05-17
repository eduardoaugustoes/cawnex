"""Tests for integration merge."""

from unittest.mock import MagicMock, patch

from worker.integrator.integration import attempt_integration_merge


def test_attempt_integration_clean_merge_returns_ok() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
        result = attempt_integration_merge(
            repo_path="/mnt/repos/T/t/r",
            integration_branch="council-review-w1",
            pr_to_mvi={42: "m_1", 43: "m_2"},
        )
        assert result.status == "ok"
        assert result.conflicts == []


def test_attempt_integration_with_conflict_captures_files() -> None:
    calls = [
        MagicMock(returncode=0, stdout=b"", stderr=b""),  # worktree add
        MagicMock(returncode=0, stdout=b"", stderr=b""),  # merge PR 42
        MagicMock(
            returncode=1,
            stdout=b"CONFLICT (content): Merge conflict in foo.py\n",
            stderr=b"",
        ),  # merge PR 43
        MagicMock(returncode=0, stdout=b"foo.py", stderr=b""),  # git diff --name-only
        MagicMock(
            returncode=0,
            stdout=b"<<<<<<< HEAD\n line\n=======\n line\n>>>>>>>",
            stderr=b"",
        ),  # git diff hunk
        MagicMock(returncode=0, stdout=b"", stderr=b""),  # merge --abort
    ]
    with patch("subprocess.run", side_effect=calls):
        result = attempt_integration_merge(
            repo_path="/mnt/repos/T/t/r",
            integration_branch="council-review-w1",
            pr_to_mvi={42: "m_1", 43: "m_2"},
        )
        assert result.status == "conflict"
        assert len(result.conflicts) == 1
        assert result.conflicts[0].pr_a == 42
        assert result.conflicts[0].pr_b == 43
        assert result.conflicts[0].mvi_a == "m_1"
        assert result.conflicts[0].mvi_b == "m_2"
        assert "foo.py" in result.conflicts[0].files
