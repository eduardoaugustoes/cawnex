"""EVT record builders — events written by Murder."""

from __future__ import annotations

from murder.enums import CrowType, EventColor, EventType
from murder.models import EventRecord


def build_crow_assigned_event(
    tenant: str,
    project: str,
    wave_id: str,
    crow_type: CrowType,
    task_name: str,
) -> EventRecord:
    return EventRecord(
        tenant=tenant,
        project=project,
        wave_id=wave_id,
        event_type=EventType.CROW_ASSIGNED.value,
        message=f"Murder assigned {crow_type.value} — {task_name}",
        color=EventColor.PURPLE.value,
        extra={"crow_type": crow_type.value, "task_name": task_name},
    )


def build_mvi_ready_event(
    tenant: str,
    project: str,
    wave_id: str,
    mvi_name: str,
) -> EventRecord:
    return EventRecord(
        tenant=tenant,
        project=project,
        wave_id=wave_id,
        event_type=EventType.MVI_READY.value,
        message=f"{mvi_name} ready to ship — all tasks completed, PR approved",
        color=EventColor.GREEN.value,
        extra={"mvi_name": mvi_name},
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
    credits_spent: float,
) -> EventRecord:
    return EventRecord(
        tenant=tenant,
        project=project,
        wave_id=wave_id,
        event_type=EventType.WAVE_DELIVERED.value,
        message=f"Wave delivered — ${credits_spent:.2f} spent",
        color=EventColor.GREEN.value,
        extra={"credits_spent": credits_spent},
    )


def build_budget_warning_event(
    tenant: str,
    project: str,
    wave_id: str,
    spent: float,
    limit: float,
) -> EventRecord:
    pct = int((spent / limit) * 100)
    return EventRecord(
        tenant=tenant,
        project=project,
        wave_id=wave_id,
        event_type=EventType.BUDGET_WARNING.value,
        message=f"Budget at {pct}% — ${spent:.2f} of ${limit:.2f}",
        color=EventColor.YELLOW.value,
        extra={"spent": spent, "limit": limit, "pct": pct},
    )


def build_budget_exceeded_event(
    tenant: str,
    project: str,
    wave_id: str,
    spent: float,
    limit: float,
) -> EventRecord:
    return EventRecord(
        tenant=tenant,
        project=project,
        wave_id=wave_id,
        event_type=EventType.BUDGET_EXCEEDED.value,
        message=f"Budget exceeded — ${spent:.2f} of ${limit:.2f}",
        color=EventColor.RED.value,
        extra={"spent": spent, "limit": limit},
    )
