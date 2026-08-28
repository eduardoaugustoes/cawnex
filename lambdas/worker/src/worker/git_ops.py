"""Git operations extracted from POC6 — pure functions, no state."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from typing import Any

from worker.config import EFS_MOUNT, GITHUB_TOKEN
from worker.paths import resolve_within


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


_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_BRANCH_RE = re.compile(r"^[A-Za-z0-9_./-]+$")


def _normalize_repo(repo: str) -> str:
    """Normalize repo to owner/repo format, stripping full URLs.

    Raises ValueError on anything that is not a plain owner/repo slug — this
    value reaches subprocess argv, so shell metacharacters are rejected
    outright rather than escaped.
    """
    repo = repo.removeprefix("https://github.com/").removesuffix(".git")
    if not _REPO_RE.match(repo):
        raise ValueError(f"invalid repo slug: {repo!r}")
    return repo


def _validate_branch(branch: str) -> str:
    """Validate a git branch name. Raises ValueError if unsafe."""
    if not branch or not _BRANCH_RE.match(branch):
        raise ValueError(f"invalid branch name: {branch!r}")
    if ".." in branch or branch.startswith("-") or branch.endswith("/"):
        raise ValueError(f"invalid branch name: {branch!r}")
    return branch


def ensure_repo(
    repo: str,
    efs_mount: str = EFS_MOUNT,
    github_token: str = GITHUB_TOKEN,
) -> str:
    """Clone repo to EFS if not present, otherwise fetch. Returns repo dir."""
    repo = _normalize_repo(repo)
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

    # If branch is main/master, use a crow-scoped branch to avoid collision
    worktree_branch = branch if branch not in ("main", "master") else f"cawnex/{crow_id}"

    run_git(f"git branch -D {worktree_branch}", cwd=repo_dir, check=False)

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
        f"git worktree add {worktree_dir} -b {worktree_branch} {start_ref}",
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
    """Create/modify/delete files in worktree. Returns changed paths.

    Every path is model-authored, so each is validated against worktree_dir
    before any write happens. A single escaping path rejects the whole
    changeset — a partial apply would leave a tree neither the model nor the
    reviewer reasoned about, and `git add -A` would commit the surviving half.
    """
    resolved: list[tuple[str, str, dict[str, Any]]] = []
    for change in changes:
        rel = change.get("path")
        if not isinstance(rel, str):
            raise ValueError("change is missing a string 'path'")
        full = resolve_within(worktree_dir, rel)
        if full is None:
            raise ValueError(f"path escapes worktree: {rel}")
        rel_to_root = os.path.relpath(full, os.path.realpath(worktree_dir))
        if ".git" in rel_to_root.lower().split(os.sep):
            raise ValueError(f"path writes git internals: {rel}")
        resolved.append((rel, full, change))

    paths: list[str] = []
    for rel, full, change in resolved:
        if change.get("action") == "delete":
            if os.path.exists(full):
                os.remove(full)
        else:
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w") as f:
                f.write(change.get("content", ""))
        paths.append(rel)
    return paths


def commit_and_push(
    worktree_dir: str,
    message: str,
    repo: str,
    branch: str,
    github_token: str = GITHUB_TOKEN,
) -> str:
    """Git add, commit, push. Returns commit SHA or empty if nothing to commit."""
    repo = _normalize_repo(repo)
    run_git("git add -A", cwd=worktree_dir)
    diff = run_git("git diff --cached --name-only", cwd=worktree_dir, check=False)
    if not diff:
        return ""
    # Pass commit message via stdin (-F -) so multi-line messages, embedded
    # quotes, and shell metacharacters can't break the command. The previous
    # f-string interpolation broke on every implementer that returned a
    # multi-line commit message with embedded newlines or quotes.
    _git_commit_with_stdin_message(worktree_dir, message)
    push_url = f"https://x-access-token:{github_token}@github.com/{repo}.git"
    run_git(f"git push --force {push_url} {branch}", cwd=worktree_dir)
    sha = run_git("git rev-parse HEAD", cwd=worktree_dir)
    return sha


def _git_commit_with_stdin_message(worktree_dir: str, message: str) -> None:
    """Commit with the message read from stdin — no shell quoting needed."""
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_CONFIG_COUNT"] = "1"
    env["GIT_CONFIG_KEY_0"] = "safe.directory"
    env["GIT_CONFIG_VALUE_0"] = "*"
    result = subprocess.run(
        ["git", "commit", "-F", "-"],
        input=message,
        capture_output=True,
        text=True,
        cwd=worktree_dir,
        env=env,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git commit failed (rc={result.returncode}): {result.stderr.strip()}"
        )
