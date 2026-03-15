"""EVT record builders for the Worker bounded context."""

from __future__ import annotations

from worker.enums import CrowType
from worker.models import Cost, EventRecord


class EventType:
    CROW_COMPLETED = "crow_completed"
    CROW_FAILED = "crow_failed"


class EventColor:
    GREEN = "green"
    RED = "red"


def build_crow_completed_event(
    tenant: str,
    project: str,
    wave_id: str,
    crow_type: CrowType,
    task_name: str,
    cost: Cost,
) -> EventRecord:
    return EventRecord(
        tenant=tenant,
        project=project,
        wave_id=wave_id,
        event_type=EventType.CROW_COMPLETED,
        message=f"{crow_type.value.capitalize()} completed — {task_name}",
        color=EventColor.GREEN,
        extra={
            "crow_type": crow_type.value,
            "task_name": task_name,
            "cost": cost.to_dict(),
        },
    )


def build_crow_failed_event(
    tenant: str,
    project: str,
    wave_id: str,
    crow_type: CrowType,
    task_name: str,
    error: str,
) -> EventRecord:
    return EventRecord(
        tenant=tenant,
        project=project,
        wave_id=wave_id,
        event_type=EventType.CROW_FAILED,
        message=f"{crow_type.value.capitalize()} failed — {task_name}: {error}",
        color=EventColor.RED,
        extra={"crow_type": crow_type.value, "task_name": task_name, "error": error},
    )
