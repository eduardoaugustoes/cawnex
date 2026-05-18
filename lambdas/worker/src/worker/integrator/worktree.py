"""git worktree setup/cleanup per PR."""

from __future__ import annotations

import logging
import os
import subprocess

logger = logging.getLogger("integrator.worktree")


def _git_env() -> dict[str, str]:
    """Env vars that make git operate on EFS-owned repos.

    The worker's repos live under /mnt/repos owned by uid 1000 (the EFS
    access point's posixUser). Without safe.directory=*, git refuses with
    'fatal: detected dubious ownership' when the integrator's process
    happens to run as a different UID than ensure_repo's clone.
    """
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_CONFIG_COUNT"] = "1"
    env["GIT_CONFIG_KEY_0"] = "safe.directory"
    env["GIT_CONFIG_VALUE_0"] = "*"
    return env


class WorktreeError(Exception):
    """Raised when a worktree operation fails in a way the caller must handle."""


def add_pr_worktree(repo_path: str, pr_number: int) -> str:
    """Fetch PR head and add a worktree at .pr-{pr_number}.

    Returns the absolute worktree path. Raises WorktreeError on failure.
    """
    pr_ref = f"refs/pull/{pr_number}/head"
    fetch = subprocess.run(
        ["git", "-C", repo_path, "fetch", "origin", pr_ref],
        capture_output=True,
        env=_git_env(),
    )
    if fetch.returncode != 0:
        raise WorktreeError(
            f"fetch failed for PR #{pr_number}: {fetch.stderr.decode()[:500]}"
        )

    worktree_path = f"{repo_path}/.pr-{pr_number}"
    add = subprocess.run(
        ["git", "-C", repo_path, "worktree", "add", worktree_path, "FETCH_HEAD"],
        capture_output=True,
        env=_git_env(),
    )
    if add.returncode != 0:
        raise WorktreeError(
            f"worktree add failed for PR #{pr_number}: {add.stderr.decode()[:500]}"
        )

    return worktree_path


def remove_worktree(repo_path: str, worktree_path: str) -> None:
    """Best-effort removal. Does NOT raise on failure (cleanup is non-critical)."""
    result = subprocess.run(
        ["git", "-C", repo_path, "worktree", "remove", "--force", worktree_path],
        capture_output=True,
        env=_git_env(),
    )
    if result.returncode != 0:
        logger.error(
            "worktree_remove_failed",
            extra={
                "worktree_path": worktree_path,
                "stderr": result.stderr.decode()[:500],
            },
        )
