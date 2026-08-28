"""Tests for git_ops — subprocess mocks for all git operations."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from worker.git_ops import (
    apply_changes,
    cleanup_worktree,
    commit_and_push,
    create_worktree,
    ensure_repo,
    run_git,
)


@patch("worker.git_ops.subprocess.run")
def test_run_git_returns_stdout(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(returncode=0, stdout="  output  ", stderr="")
    result = run_git("git status", cwd="/repo")
    assert result == "output"
    mock_run.assert_called_once()
    _, kwargs = mock_run.call_args
    assert kwargs["env"]["GIT_TERMINAL_PROMPT"] == "0"


@patch("worker.git_ops.subprocess.run")
def test_run_git_raises_on_failure(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error msg")
    with pytest.raises(RuntimeError, match="Command failed"):
        run_git("git bad", cwd="/repo")


@patch("worker.git_ops.subprocess.run")
def test_run_git_check_false_no_raise(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(returncode=1, stdout="warning", stderr="")
    result = run_git("git status", check=False)
    assert result == "warning"


@patch("worker.git_ops.subprocess.run")
def test_run_git_respects_timeout(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
    run_git("git status", timeout=30)
    _, kwargs = mock_run.call_args
    assert kwargs["timeout"] == 30


@patch("worker.git_ops.run_git")
@patch("os.path.exists")
def test_ensure_repo_clones_fresh(mock_exists: MagicMock, mock_git: MagicMock) -> None:
    mock_exists.return_value = False
    mock_git.return_value = ""
    result = ensure_repo("owner/repo", efs_mount="/efs", github_token="tok123")
    assert result == "/efs/owner_repo"
    calls = [c[0][0] for c in mock_git.call_args_list]
    assert any("git clone" in c for c in calls)
    assert any("git config user.email" in c for c in calls)


@patch("worker.git_ops.run_git")
@patch("os.path.exists")
def test_ensure_repo_fetches_existing(mock_exists: MagicMock, mock_git: MagicMock) -> None:
    # .git exists, health check OK, not shallow
    def exists_side_effect(path: str) -> bool:
        if path.endswith(".git"):
            return True
        if path.endswith("shallow"):
            return False
        return False

    mock_exists.side_effect = exists_side_effect
    mock_git.return_value = ""
    result = ensure_repo("owner/repo", efs_mount="/efs", github_token="tok")
    assert result == "/efs/owner_repo"
    calls = [c[0][0] for c in mock_git.call_args_list]
    assert any("git fetch origin" in c for c in calls)
    assert not any("git clone" in c for c in calls)


@patch("worker.git_ops.shutil.rmtree")
@patch("worker.git_ops.run_git")
@patch("os.path.exists")
def test_ensure_repo_reclones_shallow(
    mock_exists: MagicMock, mock_git: MagicMock, mock_rmtree: MagicMock
) -> None:
    def exists_side_effect(path: str) -> bool:
        if path.endswith(".git"):
            return True
        if path.endswith("shallow"):
            return True
        return False

    mock_exists.side_effect = exists_side_effect
    mock_git.return_value = ""
    ensure_repo("owner/repo", efs_mount="/efs", github_token="tok")
    mock_rmtree.assert_called_once()
    calls = [c[0][0] for c in mock_git.call_args_list]
    assert any("git clone" in c for c in calls)


@patch("worker.git_ops.run_git")
@patch("os.path.exists", return_value=False)
def test_create_worktree_from_main(mock_exists: MagicMock, mock_git: MagicMock) -> None:
    # Remote branch doesn't exist → start from origin/main
    def git_side_effect(cmd: str, **kwargs: object) -> str:
        if "rev-parse --verify" in cmd:
            return "fatal: not found"
        return ""

    mock_git.side_effect = git_side_effect
    result = create_worktree("/repo", "cr_impl_01", "feat/auth", efs_mount="/efs")
    assert result == "/efs/worktrees/cr_impl_01"
    calls = [c[0][0] for c in mock_git.call_args_list]
    wt_add = [c for c in calls if "worktree add" in c]
    assert len(wt_add) == 1
    assert "origin/main" in wt_add[0]


@patch("worker.git_ops.run_git")
@patch("os.path.exists", return_value=False)
def test_create_worktree_from_remote_branch(
    mock_exists: MagicMock, mock_git: MagicMock
) -> None:
    # Remote branch exists → start from it
    def git_side_effect(cmd: str, **kwargs: object) -> str:
        if "rev-parse --verify" in cmd:
            return "abc123"
        return ""

    mock_git.side_effect = git_side_effect
    result = create_worktree("/repo", "cr_fix_01", "feat/auth", efs_mount="/efs")
    calls = [c[0][0] for c in mock_git.call_args_list]
    wt_add = [c for c in calls if "worktree add" in c]
    assert "origin/feat/auth" in wt_add[0]


@patch("worker.git_ops.run_git")
@patch("worker.git_ops.shutil.rmtree")
@patch("os.path.exists")
def test_cleanup_worktree_swallows_errors(
    mock_exists: MagicMock, mock_rmtree: MagicMock, mock_git: MagicMock
) -> None:
    mock_exists.return_value = True
    mock_git.side_effect = RuntimeError("boom")
    # Should not raise
    cleanup_worktree("/repo", "/efs/worktrees/cr01")


def test_apply_changes_create_and_delete(tmp_path: object) -> None:
    work = str(tmp_path)
    changes = [
        {"path": "src/new.py", "action": "create", "content": "print('hello')"},
        {"path": "old.txt", "action": "create", "content": "data"},
    ]
    paths = apply_changes(work, changes)
    assert paths == ["src/new.py", "old.txt"]
    assert os.path.exists(os.path.join(work, "src", "new.py"))

    # Delete
    delete_changes = [{"path": "old.txt", "action": "delete"}]
    paths = apply_changes(work, delete_changes)
    assert not os.path.exists(os.path.join(work, "old.txt"))


@patch("worker.git_ops.run_git")
def test_commit_and_push_returns_sha(mock_git: MagicMock) -> None:
    call_count = 0

    def git_side_effect(cmd: str, **kwargs: object) -> str:
        if "diff --cached" in cmd:
            return "file.py"
        if "rev-parse HEAD" in cmd:
            return "abc123def456"
        return ""

    mock_git.side_effect = git_side_effect
    # Patch subprocess.run because commit itself now goes through it
    # directly (stdin-fed `git commit -F -`), bypassing run_git.
    with patch("worker.git_ops.subprocess.run") as mock_sub:
        mock_sub.return_value = MagicMock(returncode=0, stderr="")
        sha = commit_and_push("/wt", "feat: thing", "o/r", "branch", "tok")
    assert sha == "abc123def456"


@patch("worker.git_ops.run_git")
def test_commit_and_push_empty_diff(mock_git: MagicMock) -> None:
    def git_side_effect(cmd: str, **kwargs: object) -> str:
        if "diff --cached" in cmd:
            return ""
        return ""

    mock_git.side_effect = git_side_effect
    sha = commit_and_push("/wt", "feat: nothing", "o/r", "branch", "tok")
    assert sha == ""


@patch("worker.git_ops.subprocess.run")
@patch("worker.git_ops.run_git")
def test_commit_message_with_newlines_and_quotes_uses_stdin(
    mock_git: MagicMock, mock_subprocess: MagicMock
) -> None:
    """Multi-line commit messages with quotes broke the old f-string shell call.

    Verifies commit goes through ['git', 'commit', '-F', '-'] with the
    full multi-line message passed on stdin — no shell interpolation.
    """
    def git_side_effect(cmd: str, **kwargs: object) -> str:
        if "diff --cached" in cmd:
            return "file.py"
        if "rev-parse HEAD" in cmd:
            return "deadbeef"
        return ""

    mock_git.side_effect = git_side_effect
    mock_subprocess.return_value = MagicMock(returncode=0, stderr="")

    nasty_message = (
        'feat: tricky commit\n\n'
        'Line with "double quotes" and a $shell_var and\n'
        'a trailing newline.\n'
    )
    commit_and_push("/wt", nasty_message, "o/r", "branch", "tok")

    mock_subprocess.assert_called_once()
    call_args, call_kwargs = mock_subprocess.call_args
    assert call_args[0] == ["git", "commit", "-F", "-"]
    assert call_kwargs["input"] == nasty_message
    assert call_kwargs["cwd"] == "/wt"


def test_apply_changes_rejects_parent_traversal(tmp_path: Path) -> None:
    root = os.path.join(str(tmp_path), "wt")
    os.makedirs(root)
    with pytest.raises(ValueError, match="escapes worktree"):
        apply_changes(
            root, [{"path": "../pwned.txt", "action": "create", "content": "x"}]
        )
    assert not os.path.exists(os.path.join(str(tmp_path), "pwned.txt"))


def test_apply_changes_rejects_absolute_path(tmp_path: Path) -> None:
    root = os.path.join(str(tmp_path), "wt")
    os.makedirs(root)
    target = os.path.join(str(tmp_path), "abs.txt")
    with pytest.raises(ValueError, match="escapes worktree"):
        apply_changes(root, [{"path": target, "action": "create", "content": "x"}])
    assert not os.path.exists(target)


def test_apply_changes_rejects_git_hooks_write(tmp_path: Path) -> None:
    """Defense in depth: a hook inside the worktree still executes on commit."""
    root = os.path.join(str(tmp_path), "wt")
    os.makedirs(root)
    with pytest.raises(ValueError, match="git internals"):
        apply_changes(
            root,
            [
                {
                    "path": ".git/hooks/pre-commit",
                    "action": "create",
                    "content": "#!/bin/sh\nid\n",
                }
            ],
        )


def test_apply_changes_rejects_uppercase_git_write(tmp_path: Path) -> None:
    """macOS/APFS is case-insensitive by default — .GIT must be caught too."""
    root = os.path.join(str(tmp_path), "wt")
    os.makedirs(root)
    with pytest.raises(ValueError, match="git internals"):
        apply_changes(
            root,
            [
                {
                    "path": ".GIT/hooks/pre-commit",
                    "action": "create",
                    "content": "#!/bin/sh\nid\n",
                }
            ],
        )


def test_apply_changes_rejects_nested_git_write(tmp_path: Path) -> None:
    """A .git directory nested under a subdirectory is also git internals."""
    root = os.path.join(str(tmp_path), "wt")
    os.makedirs(root)
    with pytest.raises(ValueError, match="git internals"):
        apply_changes(
            root,
            [{"path": "sub/.git/hooks/pre-commit", "action": "create", "content": "x"}],
        )


def test_apply_changes_is_atomic_on_escape(tmp_path: Path) -> None:
    """A single bad path rejects the whole changeset — nothing is written."""
    root = os.path.join(str(tmp_path), "wt")
    os.makedirs(root)
    with pytest.raises(ValueError):
        apply_changes(
            root,
            [
                {"path": "good.py", "action": "create", "content": "ok"},
                {"path": "../bad.py", "action": "create", "content": "evil"},
            ],
        )
    assert not os.path.exists(os.path.join(root, "good.py"))


def test_apply_changes_writes_valid_paths(tmp_path: Path) -> None:
    root = os.path.join(str(tmp_path), "wt")
    os.makedirs(root)
    paths = apply_changes(
        root, [{"path": "pkg/mod.py", "action": "create", "content": "print(1)"}]
    )
    assert paths == ["pkg/mod.py"]
    with open(os.path.join(root, "pkg/mod.py")) as f:
        assert f.read() == "print(1)"


def test_apply_changes_delete_still_works(tmp_path: Path) -> None:
    root = os.path.join(str(tmp_path), "wt")
    os.makedirs(root)
    victim = os.path.join(root, "gone.py")
    with open(victim, "w") as f:
        f.write("x")
    apply_changes(root, [{"path": "gone.py", "action": "delete"}])
    assert not os.path.exists(victim)
