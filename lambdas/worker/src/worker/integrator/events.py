"""Loud-failure event emission helper."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("integrator.events")


def emit_pipeline_error(
    blackboard: Any,
    project_id: str,
    wave_id: str,
    phase: str,
    error_class: str,
    error_message: str,
    traceback_head: str = "",
    session_id: str | None = None,
    retry_count: int = 0,
    final: bool = False,
) -> None:
    """Emit a council_pipeline_error event AND log at ERROR with structured JSON."""
    now = datetime.now(timezone.utc).isoformat()
    event_id = uuid.uuid4().hex[:12]
    event_item = {
        "PK": f"P#{project_id}",
        "SK": f"E#{now}#{event_id}",
        "event_type": "council_pipeline_error",
        "phase": phase,
        "error_class": error_class,
        "error_message": error_message[:1000],
        "traceback_head": traceback_head[:1000],
        "wave_id": wave_id,
        "session_id": session_id,
        "retry_count": retry_count,
        "final": final,
        "created_at": now,
        "expires_at": int(datetime.now(timezone.utc).timestamp()) + 86400,
    }
    blackboard.write_event(event_item=event_item)
    logger.error(
        json.dumps(
            {
                "event": "council_pipeline_error",
                "phase": phase,
                "wave_id": wave_id,
                "session_id": session_id,
                "error_class": error_class,
                "error_message": error_message[:200],
                "retry_count": retry_count,
                "final": final,
            }
        )
    )
