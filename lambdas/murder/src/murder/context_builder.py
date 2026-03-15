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


def build_instructions(
    next_type: CrowType,
    previous_outcome: dict[str, Any] | None,
    mvi_description: str,
    planner_outcome: dict[str, Any] | None = None,
) -> str:
    """Build instructions for a non-planner crow based on previous outcome."""
    outcome = previous_outcome or {}

    if next_type == CrowType.IMPLEMENTER:
        return _build_implementer_instructions(outcome, mvi_description)
    if next_type == CrowType.REVIEWER:
        return _build_reviewer_instructions(mvi_description, planner_outcome)
    if next_type == CrowType.FIXER:
        return _build_fixer_instructions(outcome, mvi_description)

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

    return (
        f"You are a reviewer. Review the changes made for this MVI.\n\n"
        f"MVI: {mvi_description}\n\n"
        f"{plan_section}"
        f"Check for:\n"
        f"- Correctness: does the code do what it should?\n"
        f"- Quality: clean code, proper error handling, no security issues\n"
        f"- Tests: are there adequate tests?\n\n"
        f"Return a JSON object with:\n"
        f"- approved: boolean\n"
        f"- issues: list of issues found (empty if approved)\n"
        f"- suggestions: list of optional improvements"
    )


def _build_fixer_instructions(
    outcome: dict[str, Any],
    mvi_description: str,
) -> str:
    issues = outcome.get("issues", [])
    suggestions = outcome.get("suggestions", [])
    payload = {
        "issues": issues,
        "suggestions": suggestions,
    }
    return (
        f"You are a fixer. Address the reviewer's feedback.\n\n"
        f"MVI: {mvi_description}\n\n"
        f"Reviewer feedback:\n{json.dumps(payload, indent=2, default=_json_default)}"
    )
