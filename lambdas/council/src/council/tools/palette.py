"""Per-advisor tool palette with path-scoping enforcement."""

from __future__ import annotations

from typing import Any

from council.enums import AdvisorType
from council.tools.filesystem import grep, list_directory, read_file
from council.tools.git import get_pr_diff, git_log_for_file, read_integration_file
from council.tools.github import get_pr_metadata


ALL_TOOL_SPECS: dict[str, dict[str, Any]] = {
    "read_file": {
        "name": "read_file",
        "description": (
            "Read a file from the codebase. Optionally specify line_start/line_end."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "line_start": {"type": "integer"},
                "line_end": {"type": "integer"},
            },
            "required": ["path"],
        },
    },
    "grep": {
        "name": "grep",
        "description": "Search for a regex pattern across files.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
                "path": {"type": "string"},
            },
            "required": ["pattern"],
        },
    },
    "list_directory": {
        "name": "list_directory",
        "description": "List the entries of a directory.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    "git_log_for_file": {
        "name": "git_log_for_file",
        "description": "Return recent commits touching a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "max_entries": {"type": "integer"},
            },
            "required": ["file_path"],
        },
    },
    "get_pr_diff": {
        "name": "get_pr_diff",
        "description": "Return the diff of a PR's worktree against origin/main.",
        "input_schema": {
            "type": "object",
            "properties": {"pr_number": {"type": "integer"}},
            "required": ["pr_number"],
        },
    },
    "read_integration_file": {
        "name": "read_integration_file",
        "description": (
            "Read a file from the merged integration worktree (post-merge state)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    "get_pr_metadata": {
        "name": "get_pr_metadata",
        "description": (
            "Fetch PR metadata from GitHub (title, author, head_sha, body)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"pr_number": {"type": "integer"}},
            "required": ["pr_number"],
        },
    },
}


_PALETTES: dict[AdvisorType, list[str]] = {
    AdvisorType.SECURITY: [
        "read_file",
        "grep",
        "list_directory",
        "git_log_for_file",
        "get_pr_diff",
        "read_integration_file",
        "get_pr_metadata",
    ],
    AdvisorType.ARCHITECTURE: [
        "read_file",
        "grep",
        "list_directory",
        "git_log_for_file",
        "get_pr_diff",
        "read_integration_file",
        "get_pr_metadata",
    ],
    AdvisorType.CLARITY: [
        "read_file",
        "grep",
        "get_pr_diff",
        "read_integration_file",
        "get_pr_metadata",
    ],
    AdvisorType.PERFORMANCE: [
        "read_file",
        "grep",
        "git_log_for_file",
        "get_pr_diff",
        "read_integration_file",
        "get_pr_metadata",
    ],
    AdvisorType.UX: [
        "read_file",
        "grep",
        "get_pr_diff",
        "read_integration_file",
        "get_pr_metadata",
    ],
    AdvisorType.COST: [
        "read_file",
        "grep",
        "list_directory",
        "get_pr_diff",
        "read_integration_file",
        "get_pr_metadata",
    ],
}


def get_palette(advisor: AdvisorType) -> list[dict[str, Any]]:
    """Return the tool definitions available to this advisor."""
    return [ALL_TOOL_SPECS[name] for name in _PALETTES[advisor]]


def is_in_scope(advisor: AdvisorType, tool_name: str, args: dict[str, Any]) -> bool:
    """Path-scoping enforcement. UX scoped to apps/ios/. Cost scoped to infra/."""
    path = args.get("path", "")
    if not path:
        return True

    if advisor == AdvisorType.UX:
        return (
            "/apps/ios/" in path
            or path.endswith(".strings")
            or path.endswith(".swift")
        )
    if advisor == AdvisorType.COST:
        return "/infra/" in path

    return True


def execute_tool(
    advisor: AdvisorType,
    tool_name: str,
    args: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    """Execute a tool call for an advisor, enforcing palette + scope."""
    if tool_name not in _PALETTES[advisor]:
        return {
            "tool_error": "not_in_palette",
            "advisor": advisor.value,
            "tool": tool_name,
        }

    if not is_in_scope(advisor, tool_name, args):
        return {
            "tool_error": "out_of_scope",
            "advisor": advisor.value,
            "tool": tool_name,
            "path": args.get("path"),
        }

    if tool_name == "read_file":
        return read_file(**args)
    if tool_name == "grep":
        path = args.get("path", context.get("repo_path", "."))
        return grep(pattern=args["pattern"], path=path)
    if tool_name == "list_directory":
        return list_directory(**args)
    if tool_name == "git_log_for_file":
        return git_log_for_file(
            repo_path=context["repo_path"],
            file_path=args["file_path"],
            max_entries=args.get("max_entries", 10),
        )
    if tool_name == "get_pr_diff":
        worktree = context["worktree_paths"].get(args["pr_number"])
        if not worktree:
            return {"tool_error": "pr_not_in_context", "pr_number": args["pr_number"]}
        return get_pr_diff(worktree_path=worktree)
    if tool_name == "read_integration_file":
        return read_integration_file(
            integration_path=context["integration_path"],
            path=args["path"],
        )
    if tool_name == "get_pr_metadata":
        return get_pr_metadata(
            repo=context["repo"],
            pr_number=args["pr_number"],
            github_token=context.get("github_token", ""),
        )

    return {"tool_error": "unknown_tool", "tool": tool_name}
