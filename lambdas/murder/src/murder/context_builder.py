"""Build instructions for next crow from previous outcome.

Pure functions — no I/O. Replicates what the Worker smoke test
does manually when chaining planner -> implementer -> reviewer -> fixer.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from murder.enums import CrowType


def _json_default(obj: Any) -> Any:
    """Handle Decimal values from DynamoDB in JSON serialization."""
    if isinstance(obj, Decimal):
        return int(obj) if obj == int(obj) else float(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def build_planner_instructions(
    human_directive: str,
    mvi_description: str,
) -> str:
    """Build instructions for the first planner crow."""
    return (
        f"You are a planner. Break this work into implementable tasks.\n\n"
        f"Directive: {human_directive}\n\n"
        f"MVI description: {mvi_description}\n\n"
        f"Return a JSON object with a 'tasks' array. Each task must have:\n"
        f"- name: short task name\n"
        f"- description: what to implement\n"
        f"- files_to_modify: list of file paths to change\n"
        f"- context_files: list of file paths to read for context"
    )


def build_planner_split_instructions(
    oversized_tasks: list[dict[str, Any]],
    human_directive: str,
    mvi_description: str,
) -> str:
    """Build instructions for a planner re-invocation to split oversized tasks."""
    task_lines = "\n".join(
        f'- "{t.get("name", "unnamed")}" (estimated: {t.get("estimated_hours", "?")}h)'
        f" \u2014 split into 2-3 smaller tasks"
        for t in oversized_tasks
    )
    return (
        f"Your previous plan included tasks that exceed the 8-hour limit.\n"
        f"Split these oversized tasks into smaller subtasks (each \u2264 8 hours):\n\n"
        f"{task_lines}\n\n"
        f"Original directive: {human_directive}\n\n"
        f"MVI description: {mvi_description}\n\n"
        f"Produce a new plan where ALL tasks are \u2264 8 hours.\n\n"
        f"Return a JSON object with a 'tasks' array. Each task must have:\n"
        f"- name: short task name\n"
        f"- description: what to implement\n"
        f"- estimated_hours: estimated hours (must be \u2264 8)\n"
        f"- files_to_modify: list of file paths to change\n"
        f"- context_files: list of file paths to read for context"
    )


def build_instructions(
    next_type: CrowType,
    previous_outcome: dict[str, Any] | None,
    mvi_description: str,
    planner_outcome: dict[str, Any] | None = None,
    fix_history: list[dict[str, Any]] | None = None,
    iteration: int = 1,
) -> str:
    """Build instructions for a non-planner crow based on previous outcome."""
    outcome = previous_outcome or {}

    if next_type == CrowType.IMPLEMENTER:
        return _build_implementer_instructions(outcome, mvi_description)
    if next_type == CrowType.REVIEWER:
        return _build_reviewer_instructions(mvi_description, planner_outcome, iteration)
    if next_type == CrowType.FIXER:
        return _build_fixer_instructions(outcome, mvi_description, fix_history)

    return f"Execute task for MVI: {mvi_description}"


def _build_implementer_instructions(
    outcome: dict[str, Any],
    mvi_description: str,
) -> str:
    tasks = outcome.get("tasks", [])
    all_context_files: list[str] = []
    all_files_to_modify: list[str] = []
    for task in tasks:
        all_context_files.extend(task.get("context_files", []))
        all_files_to_modify.extend(task.get("files_to_modify", []))

    payload = {
        "tasks": tasks,
        "context_files": list(dict.fromkeys(all_context_files)),
        "files_to_modify": list(dict.fromkeys(all_files_to_modify)),
    }
    return (
        f"You are an implementer. Write code for all tasks below.\n\n"
        f"MVI: {mvi_description}\n\n"
        f"Task details:\n{json.dumps(payload, indent=2, default=_json_default)}"
    )


def _build_reviewer_instructions(
    mvi_description: str,
    planner_outcome: dict[str, Any] | None = None,
    iteration: int = 1,
) -> str:
    plan_section = ""
    if planner_outcome:
        tasks = planner_outcome.get("tasks", [])
        if tasks:
            plan_section = (
                f"## Planned tasks\n"
                f"The planner broke this MVI into these tasks:\n"
                f"{json.dumps(tasks, indent=2, default=_json_default)}\n\n"
                f"Verify each task was implemented correctly.\n\n"
            )

    iteration_note = ""
    if iteration > 1:
        iteration_note = (
            f"This is review iteration {iteration}. "
            f"Focus only on blocking issues — approve if no blocking issues remain.\n\n"
        )

    return (
        f"You are a reviewer. Review the changes made for this MVI.\n\n"
        f"MVI: {mvi_description}\n\n"
        f"{iteration_note}"
        f"{plan_section}"
        f"Check for:\n"
        f"- Correctness: does the code do what it should?\n"
        f"- Quality: clean code, proper error handling, no security issues\n"
        f"- Tests: are there adequate tests?\n\n"
        f"Return a JSON object with:\n"
        f"- approved: boolean (true when blocking_issues is empty)\n"
        f"- blocking_issues: list of blocking issues (security, correctness, data loss)\n"
        f"- non_blocking_issues: list of non-blocking issues (style, naming, minor improvements)\n"
        f"- issues: all issues combined (backward compat)\n"
        f"- suggestions: list of optional improvements"
    )


def _build_fixer_instructions(
    outcome: dict[str, Any],
    mvi_description: str,
    fix_history: list[dict[str, Any]] | None = None,
) -> str:
    issues = outcome.get("issues", [])
    suggestions = outcome.get("suggestions", [])
    payload = {
        "issues": issues,
        "suggestions": suggestions,
    }
    base = (
        f"You are a fixer. Address the reviewer's feedback.\n\n"
        f"MVI: {mvi_description}\n\n"
        f"Reviewer feedback:\n{json.dumps(payload, indent=2, default=_json_default)}"
    )

    if not fix_history:
        return base

    history_lines = ["", "", "## Previous Fix Attempts", "Do NOT repeat approaches that already failed."]
    for entry in fix_history:
        iteration = entry.get("iteration", "?")
        reviewer_issues = entry.get("reviewer_issues", [])
        fixer_summary = entry.get("fixer_summary", "")
        fixer_files_changed = entry.get("fixer_files_changed", [])

        history_lines.append(f"\n### Attempt {iteration}")
        history_lines.append(f"- Issues presented: {', '.join(reviewer_issues)}")
        history_lines.append(f"- Approach taken: {fixer_summary}")
        history_lines.append(f"- Files changed: {', '.join(fixer_files_changed)}")
        history_lines.append("- Result: Reviewer still found issues (see current issues above)")

    return base + "\n".join(history_lines)
