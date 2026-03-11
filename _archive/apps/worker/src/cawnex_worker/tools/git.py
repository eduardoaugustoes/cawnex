"""Git tools — branch, commit, push operations in agent workspace."""

from __future__ import annotations

import subprocess

from anthropic.lib.tools import beta_tool


def _git(args: list[str], cwd: str) -> str:
    """Run a git command and return output."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        output = result.stdout + result.stderr
        if result.returncode != 0:
            output += f"\n[exit code: {result.returncode}]"
        return output.strip() or "(no output)"
    except Exception as e:
        return f"Error: {e}"


@beta_tool
def GitStatus(workspace: str = ".") -> str:
    """Show the current git status (modified, staged, untracked files).

    Args:
        workspace: Git repository directory.
    """
    return _git(["status", "--short"], workspace)


@beta_tool
def GitDiff(staged: bool = False, workspace: str = ".") -> str:
    """Show git diff of current changes.

    Args:
        staged: If True, show staged changes. If False, show unstaged changes.
        workspace: Git repository directory.
    """
    args = ["diff"]
    if staged:
        args.append("--staged")
    return _git(args, workspace)


@beta_tool
def GitCommit(message: str, workspace: str = ".") -> str:
    """Stage all changes and create a git commit.

    Args:
        message: Commit message.
        workspace: Git repository directory.
    """
    # Stage all
    stage_result = _git(["add", "-A"], workspace)
    if "error" in stage_result.lower():
        return f"Error staging: {stage_result}"

    # Commit
    return _git(["commit", "-m", message], workspace)


@beta_tool
def GitPush(branch: str | None = None, workspace: str = ".") -> str:
    """Push current branch to origin.

    Args:
        branch: Branch name to push. If None, pushes current branch.
        workspace: Git repository directory.
    """
    args = ["push", "origin"]
    if branch:
        args.append(branch)
    else:
        args.append("HEAD")
    return _git(args, workspace)
