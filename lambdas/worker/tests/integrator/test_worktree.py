"""Tests for per-PR worktree setup + cleanup."""

from unittest.mock import MagicMock, patch

import pytest

from worker.integrator.worktree import (
    WorktreeError,
    add_pr_worktree,
    remove_worktree,
)


def test_add_pr_worktree_calls_git_fetch_then_worktree_add() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
        path = add_pr_worktree(
            repo_path="/mnt/repos/T/t/r",
            pr_number=42,
        )
        assert path == "/mnt/repos/T/t/r/.pr-42"
        assert "fetch" in mock_run.call_args_list[0].args[0]
        assert "worktree" in mock_run.call_args_list[1].args[0]


def test_add_pr_worktree_raises_on_fetch_failure() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1, stdout=b"", stderr=b"auth error"
        )
        with pytest.raises(WorktreeError, match="fetch failed"):
            add_pr_worktree(repo_path="/mnt/repos/T/t/r", pr_number=42)


def test_remove_worktree_calls_git_worktree_remove() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
        remove_worktree(
            repo_path="/mnt/repos/T/t/r",
            worktree_path="/mnt/repos/T/t/r/.pr-42",
        )
        assert "remove" in mock_run.call_args.args[0]
        assert "--force" in mock_run.call_args.args[0]


def test_remove_worktree_is_idempotent_on_missing() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1, stdout=b"", stderr=b"not a working tree"
        )
        remove_worktree(
            repo_path="/mnt/repos/T/t/r",
            worktree_path="/mnt/repos/T/t/r/.gone",
        )
