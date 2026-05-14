"""Scoped context gathering per crow type.

Every gather_* function returns (context_string, audit_dict). The audit dict
records which files were successfully read into the prompt and which failed,
with reasons. This lets us prove post-hoc what was in the prompt rather than
guessing from token counts.
"""

from __future__ import annotations

import os
from typing import Any

SKIP_DIRS = {".git", "node_modules", ".venv", "_archive", "__pycache__", ".mypy_cache"}
SKIP_EXTS = {
    ".pyc", ".png", ".jpg", ".jpeg", ".gif",
    ".zip", ".lock", ".map", ".woff", ".ttf",
}
MAX_FILE_SIZE = 50_000

ReadOutcome = tuple[str | None, str]  # (content, reason). content is None iff failed.


def _read_file_safe(filepath: str, max_size: int = MAX_FILE_SIZE) -> str | None:
    """Read a file, returning None if too large or unreadable.

    Preserved for backward compatibility. Prefer _read_file_with_reason
    in new code so failures are auditable.
    """
    content, _ = _read_file_with_reason(filepath, max_size)
    return content


def _read_file_with_reason(filepath: str, max_size: int = MAX_FILE_SIZE) -> ReadOutcome:
    """Read a file. Returns (content, reason).

    reason is one of: "ok", "too_large", "missing", "permission", "encoding", "other".
    content is the file text on "ok", None otherwise.
    """
    try:
        size = os.path.getsize(filepath)
    except FileNotFoundError:
        return None, "missing"
    except PermissionError:
        return None, "permission"
    except OSError:
        return None, "other"

    if size > max_size:
        return None, "too_large"

    try:
        with open(filepath, "r", errors="ignore") as f:
            return f.read(), "ok"
    except FileNotFoundError:
        return None, "missing"
    except PermissionError:
        return None, "permission"
    except UnicodeDecodeError:
        return None, "encoding"
    except OSError:
        return None, "other"


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


def _empty_audit() -> dict[str, Any]:
    return {"files_read": [], "files_failed": [], "failure_reasons": {}}


def _record_read(audit: dict[str, Any], rel_path: str, reason: str) -> None:
    if reason == "ok":
        audit["files_read"].append(rel_path)
    else:
        audit["files_failed"].append(rel_path)
        audit["failure_reasons"][rel_path] = reason


def gather_planner_context(
    worktree_dir: str, max_files: int = 30
) -> tuple[str, dict[str, Any]]:
    """File tree + first N files (alphabetical) for planner orientation."""
    parts: list[str] = []
    audit = _empty_audit()
    all_files = _walk_tree(worktree_dir)

    tree = "\n".join(all_files[:200])
    parts.append(f"## File Tree ({len(all_files)} files)\n```\n{tree}\n```\n")

    files_read = 0
    for filepath in all_files:
        if files_read >= max_files:
            break
        content, reason = _read_file_with_reason(
            os.path.join(worktree_dir, filepath)
        )
        _record_read(audit, filepath, reason)
        if content is not None:
            parts.append(f"## {filepath}\n```\n{content}\n```\n")
            files_read += 1

    return "\n".join(parts), audit


def gather_implementer_context(
    worktree_dir: str,
    files_to_read: list[str],
    files_to_modify: list[str],
) -> tuple[str, dict[str, Any]]:
    """Only the specific files the planner identified."""
    parts: list[str] = []
    audit = _empty_audit()

    all_files = _walk_tree(worktree_dir)
    tree = "\n".join(all_files[:200])
    parts.append(f"## File Tree ({len(all_files)} files)\n```\n{tree}\n```\n")

    seen: set[str] = set()
    for filepath in [*files_to_read, *files_to_modify]:
        if filepath in seen:
            continue
        seen.add(filepath)
        content, reason = _read_file_with_reason(
            os.path.join(worktree_dir, filepath)
        )
        _record_read(audit, filepath, reason)
        if content is not None:
            label = "modify" if filepath in files_to_modify else "read"
            parts.append(f"## {filepath} [{label}]\n```\n{content}\n```\n")

    return "\n".join(parts), audit


def gather_reviewer_context(
    worktree_dir: str,
    git_diff: str,
    changed_files: list[str],
) -> tuple[str, dict[str, Any]]:
    """Reviewer sees the diff (from implementer artifact) + changed file contents."""
    parts: list[str] = []
    audit = _empty_audit()

    if git_diff:
        parts.append(f"## Git Diff\n```diff\n{git_diff}\n```\n")

    if changed_files:
        parts.append(f"## Modified Files ({len(changed_files)} files)")
        for filepath in changed_files[:10]:
            content, reason = _read_file_with_reason(
                os.path.join(worktree_dir, filepath)
            )
            _record_read(audit, filepath, reason)
            if content is not None:
                parts.append(f"### {filepath}\n```\n{content}\n```\n")

    return "\n\n".join(parts), audit


def gather_fixer_context(
    worktree_dir: str,
    issues: list[str],
    suggestions: list[str],
    git_diff: str,
    changed_files: list[str],
) -> tuple[str, dict[str, Any]]:
    """Reviewer feedback + diff + modified files."""
    parts: list[str] = []
    audit = _empty_audit()

    parts.append("## Reviewer Feedback")
    if issues:
        parts.append("### Issues\n" + "\n".join(f"- {i}" for i in issues))
    if suggestions:
        parts.append("### Suggestions\n" + "\n".join(f"- {s}" for s in suggestions))

    reviewer_ctx, reviewer_audit = gather_reviewer_context(
        worktree_dir, git_diff, changed_files
    )
    if reviewer_ctx:
        parts.append(reviewer_ctx)

    # Merge reviewer audit into fixer audit
    audit["files_read"].extend(reviewer_audit["files_read"])
    audit["files_failed"].extend(reviewer_audit["files_failed"])
    audit["failure_reasons"].update(reviewer_audit["failure_reasons"])

    return "\n\n".join(parts), audit
