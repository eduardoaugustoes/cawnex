"""Notifications route — derived from events table.

Transforms recent wave/crow events into a NotificationsData payload for
iOS. The split between "needsAction" and "recent" follows the iOS enum:

  needsAction: task_approval, mvi_ready, task_failed
  updates:     mvi_shipped, credits_low, vision_ready

Approval gates (task_approval) aren't wired through events yet — we
return an empty needsAction list for that category. mvi_ready /
task_failed / mvi_shipped come straight from event_type values that
already flow through the events table.

Scope: tenant-wide, oldest items capped via the events table TTL.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Annotated, Any

from typing import cast

import boto3
from boto3.dynamodb.conditions import Key
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.auth.dependencies import get_tenant
from src.auth.tenant import TenantContext

router = APIRouter(prefix="/notifications", tags=["notifications"])
log = logging.getLogger(__name__)


# ---- response models -------------------------------------------------------


class CawnexNotification(BaseModel):
    """Matches iOS CawnexNotification."""

    id: str
    type: str  # NotificationType raw value
    title: str
    description: str
    timestamp: str
    is_read: bool


class NotificationsDataResponse(BaseModel):
    """Matches iOS NotificationsData."""

    needs_action: list[CawnexNotification]
    recent: list[CawnexNotification]


# ---- event mapping ---------------------------------------------------------

_EVENT_TYPE_TO_NOTIFICATION: dict[str, str] = {
    "mvi_ready": "mvi_ready",
    "mvi_failed": "task_failed",
    "mvi_shipped": "mvi_shipped",
    # wave_cancelled also surfaces as a failure to the operator
    "wave_cancelled": "task_failed",
}


def _humanize_relative(ts_iso: str, now: datetime | None = None) -> str:
    """Convert ISO timestamp to '2m ago' / '14m ago' / '2h ago' / '3d ago'."""
    if not ts_iso:
        return "—"
    try:
        ts = datetime.fromisoformat(ts_iso.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return "—"
    now = now or datetime.now(timezone.utc)
    delta = now - ts
    seconds = max(0, int(delta.total_seconds()))
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"


def _event_to_notification(event: dict[str, Any]) -> CawnexNotification | None:
    """Translate one event row to a CawnexNotification, or None if filtered."""
    ev_type = (event.get("event_type") or "").lower()
    notif_type = _EVENT_TYPE_TO_NOTIFICATION.get(ev_type)
    if notif_type is None:
        return None
    msg = str(event.get("message") or "")
    ts = str(event.get("timestamp") or "")
    pk = str(event.get("PK") or "")
    sk = str(event.get("SK") or "")
    # Synthesize a stable id from PK#SK so dedup works across polls
    return CawnexNotification(
        id=f"{pk}#{sk}"[-128:],
        type=notif_type,
        title=_title_for_type(notif_type),
        description=msg[:280] or "(no detail)",
        timestamp=_humanize_relative(ts),
        is_read=False,
    )


def _title_for_type(notif_type: str) -> str:
    return {
        "mvi_ready": "MVI ready to ship",
        "mvi_shipped": "MVI shipped",
        "task_failed": "Execution failed",
        "task_approval": "Task ready for review",
        "credits_low": "Credits running low",
        "vision_ready": "Vision document ready",
    }.get(notif_type, "Notification")


# ---- DDB read --------------------------------------------------------------


def _events_table_name() -> str:
    """Events live in a separate table — read it directly here."""
    return os.environ.get("EVENTS_TABLE_NAME", "")


def _recent_events_for_tenant(tenant_id: str, limit: int = 100) -> list[dict[str, Any]]:
    """Query events scoped to the tenant via the GSI1 (tenant#project key).

    The events table indexes by GSI1PK = "T#{tenant}#P#{project}" so we
    paginate per project — for v1 we use a Scan with a filter, which is
    cheaper than enumerating projects at this scale. If the tenant has
    no events yet, this returns [].
    """
    table_name = _events_table_name()
    if not table_name:
        log.warning("EVENTS_TABLE_NAME not set; returning no notifications")
        return []
    table = boto3.resource("dynamodb").Table(table_name)
    resp = table.scan(
        FilterExpression=Key("GSI1PK").begins_with(f"T#{tenant_id}"),
        Limit=limit * 4,  # filter scans waste reads; over-fetch
    )
    items = resp.get("Items", [])
    # Newest first
    items.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return cast("list[dict[str, Any]]", items[:limit])


# ---- route -----------------------------------------------------------------


@router.get("", response_model=NotificationsDataResponse)
async def get_notifications(
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> NotificationsDataResponse:
    """Read recent events, project them into iOS notification shapes.

    Newest first. needsAction vs recent buckets follow the iOS enum
    category mapping. Read state is always False in v1 (we don't
    persist read receipts yet).
    """
    events = _recent_events_for_tenant(tenant.tenant_id, limit=50)

    needs_action: list[CawnexNotification] = []
    recent: list[CawnexNotification] = []

    for ev in events:
        notif = _event_to_notification(ev)
        if notif is None:
            continue
        # category mapping mirrors iOS NotificationType.category
        if notif.type in ("task_approval", "mvi_ready", "task_failed"):
            needs_action.append(notif)
        else:
            recent.append(notif)

    return NotificationsDataResponse(
        needs_action=needs_action[:25],
        recent=recent[:25],
    )
