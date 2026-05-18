"""EVT record builders — events written by Murder."""

from __future__ import annotations

from typing import Any

from murder.config import MICROS_PER_DOLLAR
from murder.enums import CrowType, EventColor, EventType, HumanTaskSubtype
from murder.models import EventRecord


def _to_dollars(micros: int) -> float:
    return micros / MICROS_PER_DOLLAR


def build_crow_assigned_event(
    tenant: str,
    project: str,
    wave_id: str,
    crow_type: CrowType,
    task_name: str,
    mvi_id: str = "",
) -> EventRecord:
    extra: dict[str, Any] = {"crow_type": crow_type.value, "task_name": task_name}
    if mvi_id:
        extra["mvi_id"] = mvi_id
    return EventRecord(
        tenant=tenant,
        project=project,
        wave_id=wave_id,
        event_type=EventType.CROW_ASSIGNED.value,
        message=f"Murder assigned {crow_type.value} — {task_name}",
        color=EventColor.PURPLE.value,
        extra=extra,
    )


def build_mvi_ready_event(
    tenant: str,
    project: str,
    wave_id: str,
    mvi_name: str,
    mvi_id: str = "",
) -> EventRecord:
    extra: dict[str, Any] = {"mvi_name": mvi_name}
    if mvi_id:
        extra["mvi_id"] = mvi_id
    return EventRecord(
        tenant=tenant,
        project=project,
        wave_id=wave_id,
        event_type=EventType.MVI_READY.value,
        message=f"{mvi_name} ready to ship — all tasks completed, PR approved",
        color=EventColor.GREEN.value,
        extra=extra,
    )


def build_wave_started_event(
    tenant: str,
    project: str,
    wave_id: str,
    directive: str,
) -> EventRecord:
    return EventRecord(
        tenant=tenant,
        project=project,
        wave_id=wave_id,
        event_type=EventType.WAVE_STARTED.value,
        message=f"Wave started — {directive}",
        color=EventColor.BLUE.value,
        extra={"directive": directive},
    )


def build_wave_delivered_event(
    tenant: str,
    project: str,
    wave_id: str,
    credits_spent: int,
) -> EventRecord:
    return EventRecord(
        tenant=tenant,
        project=project,
        wave_id=wave_id,
        event_type=EventType.WAVE_DELIVERED.value,
        message=f"Wave delivered — ${_to_dollars(credits_spent):.2f} spent",
        color=EventColor.GREEN.value,
        extra={"credits_spent": credits_spent},
    )


def build_budget_warning_event(
    tenant: str,
    project: str,
    wave_id: str,
    spent: int,
    limit: int,
) -> EventRecord:
    pct = spent * 100 // limit
    return EventRecord(
        tenant=tenant,
        project=project,
        wave_id=wave_id,
        event_type=EventType.BUDGET_WARNING.value,
        message=f"Budget at {pct}% — ${_to_dollars(spent):.2f} of ${_to_dollars(limit):.2f}",
        color=EventColor.YELLOW.value,
        extra={"spent": spent, "limit": limit, "pct": pct},
    )


def build_budget_exceeded_event(
    tenant: str,
    project: str,
    wave_id: str,
    spent: int,
    limit: int,
) -> EventRecord:
    return EventRecord(
        tenant=tenant,
        project=project,
        wave_id=wave_id,
        event_type=EventType.BUDGET_EXCEEDED.value,
        message=f"Budget exceeded — ${_to_dollars(spent):.2f} of ${_to_dollars(limit):.2f}",
        color=EventColor.RED.value,
        extra={"spent": spent, "limit": limit},
    )


def build_human_task_created_event(
    tenant: str,
    project: str,
    wave_id: str,
    human_task_id: str,
    subtype: HumanTaskSubtype,
    ask: str,
) -> EventRecord:
    return EventRecord(
        tenant=tenant,
        project=project,
        wave_id=wave_id,
        event_type=EventType.HUMAN_TASK_CREATED.value,
        message=f"Human task created ({subtype.value}) — {ask}",
        color=EventColor.ORANGE.value,
        extra={
            "human_task_id": human_task_id,
            "subtype": subtype.value,
            "ask": ask,
        },
    )


def build_human_task_completed_event(
    tenant: str,
    project: str,
    wave_id: str,
    human_task_id: str,
    ask: str,
) -> EventRecord:
    return EventRecord(
        tenant=tenant,
        project=project,
        wave_id=wave_id,
        event_type=EventType.HUMAN_TASK_COMPLETED.value,
        message=f"Human task completed — {ask}",
        color=EventColor.GREEN.value,
        extra={"human_task_id": human_task_id, "ask": ask},
    )


def build_task_blocked_event(
    tenant: str,
    project: str,
    wave_id: str,
    crow_id: str,
    blocker_ref: str,
    reason: str,
) -> EventRecord:
    return EventRecord(
        tenant=tenant,
        project=project,
        wave_id=wave_id,
        event_type=EventType.TASK_BLOCKED.value,
        message=f"Task {crow_id} blocked — {reason}",
        color=EventColor.YELLOW.value,
        extra={"crow_id": crow_id, "blocker_ref": blocker_ref, "reason": reason},
    )


def build_task_unblocked_event(
    tenant: str,
    project: str,
    wave_id: str,
    crow_id: str,
    unblocked_by: str,
) -> EventRecord:
    return EventRecord(
        tenant=tenant,
        project=project,
        wave_id=wave_id,
        event_type=EventType.TASK_UNBLOCKED.value,
        message=f"Task {crow_id} unblocked by {unblocked_by}",
        color=EventColor.GREEN.value,
        extra={"crow_id": crow_id, "unblocked_by": unblocked_by},
    )


def build_verification_failed_event(
    tenant: str,
    project: str,
    wave_id: str,
    human_task_id: str,
    reason: str,
) -> EventRecord:
    return EventRecord(
        tenant=tenant,
        project=project,
        wave_id=wave_id,
        event_type=EventType.VERIFICATION_FAILED.value,
        message=f"Verification failed for {human_task_id} — {reason}",
        color=EventColor.RED.value,
        extra={"human_task_id": human_task_id, "reason": reason},
    )
