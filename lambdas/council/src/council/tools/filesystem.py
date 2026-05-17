"""Filesystem investigation tools: read_file, grep, list_directory."""

from __future__ import annotations

import os
import re
import subprocess
from typing import Any


def read_file(
    path: str,
    line_start: int | None = None,
    line_end: int | None = None,
) -> dict[str, Any]:
    """Return file contents or a structured error.

    line_start and line_end are 1-indexed and inclusive.
    """
    if not os.path.isfile(path):
        return {"error": "file_not_found", "path": path}
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except (OSError, PermissionError) as e:
        return {"error": "read_error", "message": str(e)[:200]}

    if line_start is not None or line_end is not None:
        start = (line_start or 1) - 1
        end = line_end if line_end is not None else len(lines)
        content = "".join(lines[start:end])
    else:
        content = "".join(lines)
    return {"content": content[:50000], "path": path, "line_count": len(lines)}


def grep(pattern: str, path: str = ".", max_results: int = 50) -> dict[str, Any]:
    """Search for pattern across files under path."""
    try:
        re.compile(pattern)
    except re.error as e:
        return {"error": "invalid_regex", "message": str(e)}

    try:
        result = subprocess.run(
            [
                "grep",
                "-rn",
                "--include=*.py",
                "--include=*.swift",
                "--include=*.ts",
                "--include=*.md",
                "-E",
                pattern,
                path,
            ],
            capture_output=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return {"error": "grep_timeout"}

    matches: list[dict[str, Any]] = []
    for line in result.stdout.decode(errors="replace").splitlines()[:max_results]:
        parts = line.split(":", 2)
        if len(parts) == 3:
            matches.append(
                {"file": parts[0], "line": int(parts[1]), "match": parts[2][:200]}
            )
    return {"matches": matches}


def list_directory(path: str) -> dict[str, Any]:
    """List the immediate entries of a directory."""
    if not os.path.isdir(path):
        return {"error": "not_a_directory", "path": path}
    try:
        entries = sorted(os.listdir(path))
    except (OSError, PermissionError) as e:
        return {"error": "list_error", "message": str(e)[:200]}
    return {"entries": entries[:200], "path": path}
