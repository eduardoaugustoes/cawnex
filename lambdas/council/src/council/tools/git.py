"""Git-based investigation tools."""

from __future__ import annotations

import os
import subprocess
from typing import Any


def git_log_for_file(
    repo_path: str, file_path: str, max_entries: int = 10
) -> dict[str, Any]:
    """Return recent commits touching file_path."""
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                repo_path,
                "log",
                f"-{max_entries}",
                "--pretty=format:%h %an %ad %s",
                "--date=short",
                "--",
                file_path,
            ],
            capture_output=True,
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        return {"error": "git_log_timeout"}
    if result.returncode != 0:
        return {"error": "git_log_failed", "stderr": result.stderr.decode()[:200]}

    commits: list[dict[str, Any]] = []
    for line in result.stdout.decode().splitlines():
        parts = line.split(" ", 3)
        if len(parts) == 4:
            commits.append(
                {
                    "sha": parts[0],
                    "author": parts[1],
                    "date": parts[2],
                    "subject": parts[3],
                }
            )
    return {"commits": commits}


def get_pr_diff(worktree_path: str) -> dict[str, Any]:
    """Return the diff of the PR's worktree against origin/main."""
    try:
        result = subprocess.run(
            ["git", "-C", worktree_path, "diff", "origin/main..."],
            capture_output=True,
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        return {"error": "git_diff_timeout"}
    if result.returncode != 0:
        return {"error": "git_diff_failed", "stderr": result.stderr.decode()[:200]}
    return {"diff": result.stdout.decode()[:100000]}


def read_integration_file(integration_path: str, path: str) -> dict[str, Any]:
    """Read a file from the integration worktree (post-merge state)."""
    full = os.path.join(integration_path, path)
    if not os.path.isfile(full):
        return {"error": "file_not_found", "path": full}
    try:
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(50000)
    except (OSError, PermissionError) as e:
        return {"error": "read_error", "message": str(e)[:200]}
    return {"content": content, "path": full}
