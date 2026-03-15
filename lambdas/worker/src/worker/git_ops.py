"""Git operations extracted from POC6 — pure functions, no state."""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any

from worker.config import EFS_MOUNT, GITHUB_TOKEN


def run_git(
    cmd: str,
    cwd: str | None = None,
    check: bool = True,
    timeout: int = 120,
) -> str:
    """Run a shell command with git-safe env vars. Returns stdout."""
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_CONFIG_COUNT"] = "1"
    env["GIT_CONFIG_KEY_0"] = "safe.directory"
    env["GIT_CONFIG_VALUE_0"] = "*"
    if GITHUB_TOKEN:
        env["GH_TOKEN"] = GITHUB_TOKEN

    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
        timeout=timeout,
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed: {cmd}\nstderr: {result.stderr}")
    return result.stdout.strip()


def ensure_repo(
    repo: str,
    efs_mount: str = EFS_MOUNT,
    github_token: str = GITHUB_TOKEN,
) -> str:
    """Clone repo to EFS if not present, otherwise fetch. Returns repo dir."""
    repo_dir = os.path.join(efs_mount, repo.replace("/", "_"))
    clone_url = f"https://x-access-token:{github_token}@github.com/{repo}.git"

    if os.path.exists(os.path.join(repo_dir, ".git")):
        health = run_git("git status --porcelain", cwd=repo_dir, check=False)
        is_shallow = os.path.exists(os.path.join(repo_dir, ".git", "shallow"))

        if "fatal" in health or is_shallow:
            shutil.rmtree(repo_dir)
        else:
            run_git("git fetch origin", cwd=repo_dir)
            return repo_dir

    run_git(f"git clone {clone_url} {repo_dir}")
    run_git('git config user.email "cawnex-worker@cawnex.ai"', cwd=repo_dir)
    run_git('git config user.name "Cawnex Worker"', cwd=repo_dir)
    return repo_dir


def create_worktree(
    repo_dir: str,
    crow_id: str,
    branch: str,
    efs_mount: str = EFS_MOUNT,
) -> str:
    """Create an isolated worktree for a crow execution."""
    worktree_dir = os.path.join(efs_mount, "worktrees", crow_id)

    # Clean up leftover from a previous failed run
    if os.path.exists(worktree_dir):
        run_git(
            f"git worktree remove {worktree_dir} --force",
            cwd=repo_dir,
            check=False,
        )
        if os.path.exists(worktree_dir):
            shutil.rmtree(worktree_dir)

    run_git("git worktree prune", cwd=repo_dir)
    run_git("git fetch --prune origin", cwd=repo_dir)
    run_git(f"git branch -D {branch}", cwd=repo_dir, check=False)

    # Detect remote branch (sequential crow building on previous push)
    remote_ref = run_git(
        f"git rev-parse --verify origin/{branch}",
        cwd=repo_dir,
        check=False,
    )
    start_ref = (
        f"origin/{branch}"
        if remote_ref and "fatal" not in remote_ref
        else "origin/main"
    )

    run_git(
        f"git worktree add {worktree_dir} -b {branch} {start_ref}",
        cwd=repo_dir,
    )
    run_git('git config user.email "cawnex-worker@cawnex.ai"', cwd=worktree_dir)
    run_git('git config user.name "Cawnex Worker"', cwd=worktree_dir)
    return worktree_dir


def cleanup_worktree(repo_dir: str, worktree_dir: str) -> None:
    """Remove worktree after execution. Swallows errors."""
    try:
        run_git(
            f"git worktree remove {worktree_dir} --force",
            cwd=repo_dir,
            check=False,
        )
        if os.path.exists(worktree_dir):
            shutil.rmtree(worktree_dir)
        run_git("git worktree prune", cwd=repo_dir)
    except Exception:
        pass


def apply_changes(worktree_dir: str, changes: list[dict[str, Any]]) -> list[str]:
    """Create/modify/delete files in worktree. Returns changed paths."""
    paths: list[str] = []
    for change in changes:
        filepath = os.path.join(worktree_dir, change["path"])
        if change.get("action") == "delete":
            if os.path.exists(filepath):
                os.remove(filepath)
        else:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w") as f:
                f.write(change["content"])
        paths.append(change["path"])
    return paths


def commit_and_push(
    worktree_dir: str,
    message: str,
    repo: str,
    branch: str,
    github_token: str = GITHUB_TOKEN,
) -> str:
    """Git add, commit, push. Returns commit SHA or empty if nothing to commit."""
    run_git("git add -A", cwd=worktree_dir)
    diff = run_git("git diff --cached --name-only", cwd=worktree_dir, check=False)
    if not diff:
        return ""
    run_git(f"git commit -m \"{message}\"", cwd=worktree_dir)
    push_url = f"https://x-access-token:{github_token}@github.com/{repo}.git"
    run_git(f"git push --force {push_url} {branch}", cwd=worktree_dir)
    sha = run_git("git rev-parse HEAD", cwd=worktree_dir)
    return sha
