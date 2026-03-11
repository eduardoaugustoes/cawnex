"""Filesystem tools — sandboxed to the agent's workspace (nest)."""

from __future__ import annotations

import os
from pathlib import Path

from anthropic.lib.tools import beta_tool


def _resolve(workspace: Path, path: str) -> Path:
    """Resolve path within workspace, preventing directory traversal."""
    resolved = (workspace / path).resolve()
    if not str(resolved).startswith(str(workspace.resolve())):
        raise ValueError(f"Path '{path}' escapes workspace")
    return resolved


@beta_tool
def ReadFile(path: str, workspace: str = ".") -> str:
    """Read the contents of a file at the given path relative to the workspace.

    Args:
        path: File path relative to workspace root.
        workspace: Workspace root directory.
    """
    ws = Path(workspace)
    target = _resolve(ws, path)
    if not target.exists():
        return f"Error: File not found: {path}"
    if target.is_dir():
        return f"Error: '{path}' is a directory, not a file"
    try:
        content = target.read_text(encoding="utf-8")
        if len(content) > 100_000:
            return content[:100_000] + f"\n\n... [truncated, {len(content)} chars total]"
        return content
    except Exception as e:
        return f"Error reading file: {e}"


@beta_tool
def WriteFile(path: str, content: str, workspace: str = ".") -> str:
    """Write content to a file, creating parent directories if needed.

    Args:
        path: File path relative to workspace root.
        content: Content to write.
        workspace: Workspace root directory.
    """
    ws = Path(workspace)
    target = _resolve(ws, path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Written {len(content)} chars to {path}"
    except Exception as e:
        return f"Error writing file: {e}"


@beta_tool
def ListDirectory(path: str = ".", workspace: str = ".") -> str:
    """List files and directories at the given path.

    Args:
        path: Directory path relative to workspace root. Defaults to root.
        workspace: Workspace root directory.
    """
    ws = Path(workspace)
    target = _resolve(ws, path)
    if not target.exists():
        return f"Error: Directory not found: {path}"
    if not target.is_dir():
        return f"Error: '{path}' is a file, not a directory"

    entries = []
    for entry in sorted(target.iterdir()):
        rel = entry.relative_to(ws)
        prefix = "📁 " if entry.is_dir() else "📄 "
        size = f" ({entry.stat().st_size}B)" if entry.is_file() else ""
        entries.append(f"{prefix}{rel}{size}")

    if not entries:
        return "(empty directory)"
    return "\n".join(entries[:200])


@beta_tool
def SearchFiles(pattern: str, workspace: str = ".") -> str:
    """Search for files matching a glob pattern in the workspace.

    Args:
        pattern: Glob pattern (e.g. '**/*.py', 'src/**/*.ts').
        workspace: Workspace root directory.
    """
    ws = Path(workspace)
    matches = list(ws.glob(pattern))
    if not matches:
        return f"No files matching '{pattern}'"

    results = []
    for m in sorted(matches)[:100]:
        rel = m.relative_to(ws)
        results.append(str(rel))

    suffix = f"\n... and {len(matches) - 100} more" if len(matches) > 100 else ""
    return "\n".join(results) + suffix
