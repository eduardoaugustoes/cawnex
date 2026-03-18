"""Event emission helpers for the Monarch Lambda."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any

from monarch.config import EVENT_TTL_DAYS


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def emit_event(
    events_table: Any,
    tenant_id: str,
    project_id: str,
    event_type: str,
    message: str,
    color: str,
) -> None:
    """Write a progress event to the events table."""
    now = _now_iso()
    uid = uuid.uuid4().hex[:8]
    pk = f"T#{tenant_id}#P#{project_id}#W#monarch"
    sk = f"EVT#{now}#{uid}"
    item: dict[str, Any] = {
        "PK": pk,
        "SK": sk,
        "GSI1PK": f"T#{tenant_id}#P#{project_id}",
        "GSI1SK": now,
        "event_type": event_type,
        "message": message,
        "color": color,
        "timestamp": now,
        "expires_at": int(time.time()) + (EVENT_TTL_DAYS * 86400),
        "entityType": "Event",
    }
    events_table.put_item(Item=item)
