"""Worktree-scoped tools exposed to Claude during the implementer's tool-use loop.

Each tool is implemented as a method on WorktreeTools. The execute() entry point
dispatches by tool name so the agentic loop can call tools by the schemas Claude
sees. Every tool enforces path containment within worktree_dir — paths that
resolve outside the worktree are rejected with an "escapes worktree" error.
"""

from __future__ import annotations

import fnmatch
import os
import re
from dataclasses import dataclass, field
from typing import Any

from worker.logging import StructuredLogger

SKIP_DIRS = {".git", "node_modules", ".venv", "_archive", "__pycache__", ".mypy_cache"}
MAX_FILE_BYTES_DEFAULT = 100_000
MAX_FILES_READ_DEFAULT = 50
MAX_GLOB_RESULTS_DEFAULT = 100
MAX_GREP_MATCHES_DEFAULT = 50


@dataclass
class WorktreeTools:
    """Stateful per-crow tool executor scoped to a single worktree directory."""

    worktree_dir: str
    logger: StructuredLogger
    files_read: set[str] = field(default_factory=set)
    max_files_read: int = MAX_FILES_READ_DEFAULT

    def _resolve_safe(self, rel_path: str) -> str | None:
        """Resolve rel_path against worktree_dir. Returns None if it escapes."""
        if rel_path.startswith("/"):
            candidate = rel_path
        else:
            candidate = os.path.join(self.worktree_dir, rel_path)
        full = os.path.realpath(candidate)
        wt_real = os.path.realpath(self.worktree_dir)
        if full == wt_real:
            return full
        if not full.startswith(wt_real + os.sep):
            return None
        return full

    def _skip_dir(self, parts: tuple[str, ...]) -> bool:
        return any(p in SKIP_DIRS for p in parts)

    def execute(self, name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        """Dispatch a tool call by name. Always returns a dict (no raises)."""
        try:
            if name == "read_file":
                path = tool_input.get("path")
                if not isinstance(path, str):
                    return {"error": "read_file requires 'path' (string)"}
                max_bytes = int(tool_input.get("max_bytes", MAX_FILE_BYTES_DEFAULT))
                return self.read_file(path, max_bytes=max_bytes)
            if name == "glob_files":
                pattern = tool_input.get("pattern")
                if not isinstance(pattern, str):
                    return {"error": "glob_files requires 'pattern' (string)"}
                max_results = int(
                    tool_input.get("max_results", MAX_GLOB_RESULTS_DEFAULT)
                )
                return self.glob_files(pattern, max_results=max_results)
            if name == "grep_files":
                pattern = tool_input.get("pattern")
                if not isinstance(pattern, str):
                    return {"error": "grep_files requires 'pattern' (string)"}
                path_glob = tool_input.get("path_glob", "**/*")
                max_matches = int(
                    tool_input.get("max_matches", MAX_GREP_MATCHES_DEFAULT)
                )
                return self.grep_files(
                    pattern, path_glob=path_glob, max_matches=max_matches
                )
            if name == "list_dir":
                path = tool_input.get("path", ".")
                if not isinstance(path, str):
                    return {"error": "list_dir 'path' must be a string"}
                return self.list_dir(path)
            return {"error": f"unknown tool: {name}"}
        except Exception as e:  # defensive — tools must never crash the loop
            self.logger.error("tool_call_crashed", tool=name, error=str(e))
            return {"error": f"tool crashed: {e}"}

    def read_file(
        self, path: str, max_bytes: int = MAX_FILE_BYTES_DEFAULT
    ) -> dict[str, Any]:
        """Read a file's contents. Returns {content, truncated, size_bytes} on success."""
        if len(self.files_read) >= self.max_files_read and path not in self.files_read:
            return {
                "error": (
                    f"file-read limit reached ({self.max_files_read} files). "
                    "Use what you have to finalize the work."
                )
            }
        full = self._resolve_safe(path)
        if full is None:
            self.logger.warning("tool_read_blocked", path=path, reason="escapes_worktree")
            return {"error": f"path escapes worktree: {path}"}
        try:
            size = os.path.getsize(full)
            with open(full, "r", errors="replace") as f:
                content = f.read(max_bytes)
        except FileNotFoundError:
            self.logger.event("tool_read_file", path=path, reason="missing")
            return {"error": f"file not found: {path}"}
        except (OSError, UnicodeDecodeError) as e:
            reason = type(e).__name__
            self.logger.event("tool_read_file", path=path, reason=reason)
            return {"error": f"{reason}: {e}"}

        self.files_read.add(path)
        truncated = size > max_bytes
        self.logger.event(
            "tool_read_file",
            path=path,
            reason="ok",
            bytes=len(content),
            truncated=truncated,
        )
        return {"content": content, "truncated": truncated, "size_bytes": size}

    def glob_files(
        self, pattern: str, max_results: int = MAX_GLOB_RESULTS_DEFAULT
    ) -> dict[str, Any]:
        """Glob for files relative to the worktree root. Skips SKIP_DIRS."""
        all_files = self._walk_relative()
        matches: list[str] = []
        for rel in all_files:
            if _glob_match(rel, pattern):
                matches.append(rel)
                if len(matches) >= max_results:
                    break
        truncated = len(matches) >= max_results and len(all_files) > max_results
        self.logger.event(
            "tool_glob_files",
            pattern=pattern,
            matches=len(matches),
            truncated=truncated,
        )
        return {"matches": matches, "truncated": truncated}

    def grep_files(
        self,
        pattern: str,
        path_glob: str = "**/*",
        max_matches: int = MAX_GREP_MATCHES_DEFAULT,
    ) -> dict[str, Any]:
        """Regex-search file contents. Returns up to max_matches hits."""
        try:
            regex = re.compile(pattern)
        except re.error as e:
            return {"error": f"invalid regex: {e}"}

        matches: list[dict[str, Any]] = []
        truncated = False
        for rel in self._walk_relative():
            if not _glob_match(rel, path_glob):
                continue
            full = os.path.join(self.worktree_dir, rel)
            try:
                with open(full, "r", errors="replace") as f:
                    for lineno, line in enumerate(f, start=1):
                        if regex.search(line):
                            matches.append(
                                {
                                    "path": rel,
                                    "line": lineno,
                                    "text": line.rstrip("\n")[:200],
                                }
                            )
                            if len(matches) >= max_matches:
                                truncated = True
                                break
            except (OSError, UnicodeDecodeError):
                continue
            if truncated:
                break

        self.logger.event(
            "tool_grep_files",
            pattern=pattern,
            path_glob=path_glob,
            matches=len(matches),
            truncated=truncated,
        )
        return {"matches": matches, "truncated": truncated}

    def list_dir(self, path: str = ".") -> dict[str, Any]:
        """List immediate children of a directory. Adds trailing slash to dirs."""
        full = self._resolve_safe(path)
        if full is None:
            return {"error": f"path escapes worktree: {path}"}
        if not os.path.isdir(full):
            return {"error": f"not a directory: {path}"}
        try:
            entries = sorted(os.listdir(full))
        except OSError as e:
            return {"error": f"{type(e).__name__}: {e}"}
        decorated = [
            f"{name}/" if os.path.isdir(os.path.join(full, name)) else name
            for name in entries
            if name not in SKIP_DIRS or not os.path.isdir(os.path.join(full, name))
        ]
        self.logger.event("tool_list_dir", path=path, count=len(decorated))
        return {"entries": decorated}

    def _walk_relative(self) -> list[str]:
        """Walk the worktree and return sorted relative file paths, skipping SKIP_DIRS."""
        all_files: list[str] = []
        for root, dirs, files in os.walk(self.worktree_dir):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for f in files:
                rel = os.path.relpath(os.path.join(root, f), self.worktree_dir)
                all_files.append(rel)
        all_files.sort()
        return all_files


def _glob_match(rel_path: str, pattern: str) -> bool:
    """Match a relative path against a glob pattern, supporting ** for recursion.

    Semantics:
      - `*` matches any characters except `/`
      - `?` matches a single character except `/`
      - `**/` matches zero or more directory segments (including none)
      - `**` at the end of a pattern matches anything (including nothing)
    """
    normalized = rel_path.replace(os.sep, "/")

    # Convert pattern to regex token by token, walking through the pattern.
    regex_parts: list[str] = []
    i = 0
    while i < len(pattern):
        # Detect '**/' — zero-or-more directory segments
        if pattern[i : i + 3] == "**/":
            regex_parts.append("(?:.*/)?")
            i += 3
            continue
        # Detect bare '**' (end of pattern, no trailing slash)
        if pattern[i : i + 2] == "**":
            regex_parts.append(".*")
            i += 2
            continue
        # Single '*' — match within a path segment
        if pattern[i] == "*":
            regex_parts.append("[^/]*")
            i += 1
            continue
        if pattern[i] == "?":
            regex_parts.append("[^/]")
            i += 1
            continue
        regex_parts.append(re.escape(pattern[i]))
        i += 1

    full_regex = "^" + "".join(regex_parts) + "$"
    return re.match(full_regex, normalized) is not None


WORKTREE_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "read_file",
        "description": (
            "Read the contents of a file in the repository. Use this whenever "
            "you need to see what a file contains before modifying it, and "
            "ALWAYS read every file mentioned in the directive (e.g. a "
            "`Spec: docs/foo.md` line) before writing any changes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path relative to the repo root, e.g. 'src/main.py'.",
                },
                "max_bytes": {
                    "type": "integer",
                    "description": (
                        "Optional cap on bytes returned. Defaults to "
                        f"{MAX_FILE_BYTES_DEFAULT}."
                    ),
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "glob_files",
        "description": (
            "List files matching a glob pattern (supports ** for recursive "
            "matches). Use this to find files when you only know a partial "
            "name or extension."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern, e.g. '**/*.py' or 'src/**/test_*.py'.",
                },
                "max_results": {"type": "integer"},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "grep_files",
        "description": (
            "Regex-search file contents and return matching lines. Use this to "
            "find functions, classes, or text references across the repo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Python regex pattern.",
                },
                "path_glob": {
                    "type": "string",
                    "description": "Optional glob to restrict the search scope.",
                },
                "max_matches": {"type": "integer"},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "list_dir",
        "description": (
            "List the immediate contents of a directory. Directories end in '/'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path relative to repo root. Defaults to '.'.",
                },
            },
            "required": [],
        },
    },
]
