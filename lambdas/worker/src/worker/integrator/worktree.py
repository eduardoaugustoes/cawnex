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
    """Fetch PR head into a named local ref and add a worktree at .pr-{pr_number}.

    The refspec `refs/pull/N/head:refs/remotes/origin/pr-N` creates a
    persistent local remote-tracking ref so the integration merge step
    can `git merge origin/pr-N`. Without the colon + destination, the
    fetch only updates FETCH_HEAD and `origin/pr-N` doesn't exist —
    integration merges then fail with "merge: origin/pr-N - not something
    we can merge", which produced phantom conflicts with PR #0.

    Returns the absolute worktree path. Raises WorktreeError on failure.
    """
    pr_refspec = f"+refs/pull/{pr_number}/head:refs/remotes/origin/pr-{pr_number}"
    fetch = subprocess.run(
        ["git", "-C", repo_path, "fetch", "origin", pr_refspec],
        capture_output=True,
        env=_git_env(),
    )
    if fetch.returncode != 0:
        raise WorktreeError(
            f"fetch failed for PR #{pr_number}: {fetch.stderr.decode()[:500]}"
        )

    worktree_path = f"{repo_path}/.pr-{pr_number}"
    add = subprocess.run(
        [
            "git", "-C", repo_path, "worktree", "add",
            worktree_path, f"origin/pr-{pr_number}",
        ],
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
