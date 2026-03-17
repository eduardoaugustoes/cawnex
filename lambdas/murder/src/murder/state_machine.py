"""Deterministic state machine — completed crow to next action.

Pure function, no I/O. Murder decides what happens next based on
crow type, status, outcome, and retry count.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from murder.config import FIX_CYCLE_LIMIT, MAX_PLANNER_SPLITS, MAX_TASK_HOURS
from murder.enums import CrowStatus, CrowType


@dataclass
class AssignCrow:
    crow_type: CrowType
    reason: str


@dataclass
class MarkMVIReady:
    reason: str = "reviewer approved"


@dataclass
class FailMVI:
    reason: str


@dataclass
class NoAction:
    reason: str


@dataclass
class SplitRequired:
    """Planner produced tasks exceeding size limit — re-invoke with split instructions."""
    oversized_tasks: list[dict]
    reason: str


@dataclass
class CreateHumanTasks:
    """Planner produced tasks containing human tasks — create them and dispatch crow tasks."""
    human_tasks: list[dict]
    crow_tasks: list[dict]
    reason: str


NextAction = AssignCrow | MarkMVIReady | FailMVI | NoAction | SplitRequired | CreateHumanTasks


def determine_next(
    crow_type: CrowType,
    crow_status: CrowStatus,
    outcome: dict[str, Any] | None,
    retry_count: int,
    split_count: int = 0,
    fix_count: int = 0,
) -> NextAction:
    """Given a completed/failed crow, return the next action Murder should take."""
    if crow_status == CrowStatus.COMPLETED:
        return _on_completed(crow_type, outcome, retry_count, split_count, fix_count)
    if crow_status == CrowStatus.FAILED:
        return _on_failed(crow_type, retry_count)
    return NoAction(reason=f"unexpected status: {crow_status.value}")


def _on_completed(
    crow_type: CrowType,
    outcome: dict[str, Any] | None,
    retry_count: int,
    split_count: int = 0,
    fix_count: int = 0,
) -> NextAction:
    if crow_type == CrowType.PLANNER:
        tasks = (outcome or {}).get("tasks", [])
        if not tasks:
            return FailMVI(reason="planner produced no tasks")
        oversized = [t for t in tasks if t.get("estimated_hours", 0) > MAX_TASK_HOURS]
        if oversized:
            if split_count >= MAX_PLANNER_SPLITS:
                return FailMVI(
                    reason=f"planner cannot decompose within {MAX_TASK_HOURS}h task limit after {split_count} attempts"
                )
            return SplitRequired(oversized_tasks=oversized, reason="tasks exceed size limit")
        human_tasks = [t for t in tasks if t.get("task_type") == "human"]
        crow_tasks = [t for t in tasks if t.get("task_type") != "human"]
        if human_tasks:
            return CreateHumanTasks(
                human_tasks=human_tasks,
                crow_tasks=crow_tasks,
                reason="planner identified human tasks",
            )
        return AssignCrow(CrowType.IMPLEMENTER, reason="planner completed with tasks")

    if crow_type == CrowType.IMPLEMENTER:
        return AssignCrow(CrowType.REVIEWER, reason="implementer completed")

    if crow_type == CrowType.REVIEWER:
        o = outcome or {}
        if "blocking_issues" in o:
            approved = len(o["blocking_issues"]) == 0
        else:
            approved = o.get("approved", False)
        if approved:
            return MarkMVIReady()
        if fix_count >= FIX_CYCLE_LIMIT:
            return FailMVI(
                reason=(
                    f"max fix cycles ({FIX_CYCLE_LIMIT}) exceeded — reviewer still has "
                    f"blocking issues after {fix_count} fix attempts"
                )
            )
        return AssignCrow(CrowType.FIXER, reason="reviewer found issues")

    if crow_type == CrowType.FIXER:
        return AssignCrow(CrowType.REVIEWER, reason="fixer completed, re-review needed")

    return NoAction(reason=f"unexpected crow type: {crow_type.value}")


def _on_failed(crow_type: CrowType, retry_count: int) -> NextAction:
    if retry_count >= crow_type.max_retries:
        return FailMVI(
            reason=f"{crow_type.value} failed after {retry_count} retries"
        )
    return AssignCrow(crow_type, reason=f"{crow_type.value} failed, retry {retry_count + 1}")
