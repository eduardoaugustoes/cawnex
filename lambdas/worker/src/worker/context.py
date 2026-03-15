"""Scoped context gathering per crow type."""

from __future__ import annotations

import os

SKIP_DIRS = {".git", "node_modules", ".venv", "_archive", "__pycache__", ".mypy_cache"}
SKIP_EXTS = {
    ".pyc", ".png", ".jpg", ".jpeg", ".gif",
    ".zip", ".lock", ".map", ".woff", ".ttf",
}
MAX_FILE_SIZE = 50_000


def _read_file_safe(filepath: str, max_size: int = MAX_FILE_SIZE) -> str | None:
    """Read a file, returning None if too large or unreadable."""
    try:
        if os.path.getsize(filepath) > max_size:
            return None
        with open(filepath, "r", errors="ignore") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return None


def _walk_tree(worktree_dir: str) -> list[str]:
    """Walk directory tree, returning sorted relative paths."""
    all_files: list[str] = []
    for root, dirs, files in os.walk(worktree_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if os.path.splitext(f)[1] in SKIP_EXTS:
                continue
            rel = os.path.relpath(os.path.join(root, f), worktree_dir)
            all_files.append(rel)
    all_files.sort()
    return all_files


def gather_planner_context(worktree_dir: str, max_files: int = 30) -> str:
    """File tree + key files for planner analysis."""
    parts: list[str] = []
    all_files = _walk_tree(worktree_dir)

    tree = "\n".join(all_files[:200])
    parts.append(f"## File Tree ({len(all_files)} files)\n```\n{tree}\n```\n")

    files_read = 0
    for filepath in all_files:
        if files_read >= max_files:
            break
        content = _read_file_safe(os.path.join(worktree_dir, filepath))
        if content is not None:
            parts.append(f"## {filepath}\n```\n{content}\n```\n")
            files_read += 1

    return "\n".join(parts)


def gather_implementer_context(
    worktree_dir: str,
    files_to_read: list[str],
    files_to_modify: list[str],
) -> str:
    """Only the specific files the planner identified."""
    parts: list[str] = []

    # File tree for orientation
    all_files = _walk_tree(worktree_dir)
    tree = "\n".join(all_files[:200])
    parts.append(f"## File Tree ({len(all_files)} files)\n```\n{tree}\n```\n")

    # Read specified files
    seen: set[str] = set()
    for filepath in [*files_to_read, *files_to_modify]:
        if filepath in seen:
            continue
        seen.add(filepath)
        content = _read_file_safe(os.path.join(worktree_dir, filepath))
        if content is not None:
            label = "modify" if filepath in files_to_modify else "read"
            parts.append(f"## {filepath} [{label}]\n```\n{content}\n```\n")

    return "\n".join(parts)


def gather_reviewer_context(
    worktree_dir: str,
    git_diff: str,
    changed_files: list[str],
) -> str:
    """Reviewer sees the diff (from implementer artifact) + changed file contents."""
    parts: list[str] = []

    if git_diff:
        parts.append(f"## Git Diff\n```diff\n{git_diff}\n```\n")

    if changed_files:
        parts.append(f"## Modified Files ({len(changed_files)} files)")
        for filepath in changed_files[:10]:
            content = _read_file_safe(os.path.join(worktree_dir, filepath))
            if content is not None:
                parts.append(f"### {filepath}\n```\n{content}\n```\n")

    return "\n\n".join(parts)


def gather_fixer_context(
    worktree_dir: str,
    issues: list[str],
    suggestions: list[str],
    git_diff: str,
    changed_files: list[str],
) -> str:
    """Reviewer feedback + diff + modified files."""
    parts: list[str] = []

    parts.append("## Reviewer Feedback")
    if issues:
        parts.append("### Issues\n" + "\n".join(f"- {i}" for i in issues))
    if suggestions:
        parts.append("### Suggestions\n" + "\n".join(f"- {s}" for s in suggestions))

    reviewer_ctx = gather_reviewer_context(worktree_dir, git_diff, changed_files)
    if reviewer_ctx:
        parts.append(reviewer_ctx)

    return "\n\n".join(parts)
