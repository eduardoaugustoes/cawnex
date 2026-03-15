"""Deterministic state machine — completed crow to next action.

Pure function, no I/O. Murder decides what happens next based on
crow type, status, outcome, and retry count.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from murder.config import FIX_CYCLE_LIMIT
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


NextAction = AssignCrow | MarkMVIReady | FailMVI | NoAction


def determine_next(
    crow_type: CrowType,
    crow_status: CrowStatus,
    outcome: dict[str, Any] | None,
    retry_count: int,
) -> NextAction:
    """Given a completed/failed crow, return the next action Murder should take."""
    if crow_status == CrowStatus.COMPLETED:
        return _on_completed(crow_type, outcome, retry_count)
    if crow_status == CrowStatus.FAILED:
        return _on_failed(crow_type, retry_count)
    return NoAction(reason=f"unexpected status: {crow_status.value}")


def _on_completed(
    crow_type: CrowType,
    outcome: dict[str, Any] | None,
    retry_count: int,
) -> NextAction:
    if crow_type == CrowType.PLANNER:
        tasks = (outcome or {}).get("tasks", [])
        if not tasks:
            return FailMVI(reason="planner produced no tasks")
        return AssignCrow(CrowType.IMPLEMENTER, reason="planner completed with tasks")

    if crow_type == CrowType.IMPLEMENTER:
        return AssignCrow(CrowType.REVIEWER, reason="implementer completed")

    if crow_type == CrowType.REVIEWER:
        approved = (outcome or {}).get("approved", False)
        if approved:
            return MarkMVIReady()
        return AssignCrow(CrowType.FIXER, reason="reviewer found issues")

    if crow_type == CrowType.FIXER:
        if retry_count >= FIX_CYCLE_LIMIT:
            return FailMVI(reason=f"max fix cycles ({FIX_CYCLE_LIMIT}) exceeded")
        return AssignCrow(CrowType.REVIEWER, reason="fixer completed, re-review needed")

    return NoAction(reason=f"unexpected crow type: {crow_type.value}")


def _on_failed(crow_type: CrowType, retry_count: int) -> NextAction:
    if retry_count >= crow_type.max_retries:
        return FailMVI(
            reason=f"{crow_type.value} failed after {retry_count} retries"
        )
    return AssignCrow(crow_type, reason=f"{crow_type.value} failed, retry {retry_count + 1}")
