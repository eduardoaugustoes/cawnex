"""EventBridge Pipe ingestion endpoint.

The Pipe POSTs an array of records (or, during Phase 1, we POST manually).
Each record should have at least PK and event_type. We extract wave_id
from PK (`T#{tenant}#P#{project}#W#{wave_id}`) and fan out to in-memory
subscribers.

Authenticated via a shared secret header (X-Pipe-Secret). The endpoint
lives behind an ALB listener rule scoped to this path; a stronger posture
(IAM SigV4 verification) is a Phase 2 follow-up.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from stream.config import load_config
from stream.sse import encode_event

router = APIRouter()


_PK_PATTERN = re.compile(r"^T#(?P<tenant>[^#]+)#P#(?P<project>[^#]+)#W#(?P<wave>[^#]+)$")


def _wave_id_from_pk(pk: str) -> str | None:
    match = _PK_PATTERN.match(pk)
    return match.group("wave") if match else None


def _record_to_frame(record: dict[str, Any]) -> tuple[str, str] | None:
    """Return (wave_id, sse_frame) or None if the record should be skipped."""
    pk = record.get("PK", "")
    sk = record.get("SK", "")
    wave_id = _wave_id_from_pk(pk)
    if wave_id is None:
        return None

    event_id = sk or None
    frame = encode_event(
        event_id=event_id,
        event_name="wave_event",
        data={
            "event_type": record.get("event_type", ""),
            "message": record.get("message", ""),
            "color": record.get("color", ""),
            "timestamp": record.get("timestamp", ""),
            "wave_id": wave_id,
            "mvi_id": record.get("mvi_id", ""),
        },
    )
    return wave_id, frame


@router.post("/_pipe")
async def receive_pipe_batch(
    request: Request,
    x_pipe_secret: str = Header(default=""),
) -> dict[str, int]:
    cfg = load_config()
    if x_pipe_secret != cfg.pipe_secret:
        raise HTTPException(status_code=401, detail="invalid pipe secret")

    payload = await request.json()
    if not isinstance(payload, list):
        raise HTTPException(status_code=400, detail="expected JSON array")

    registry = request.app.state.registry
    published = 0
    for record in payload:
        if not isinstance(record, dict):
            continue
        result = _record_to_frame(record)
        if result is None:
            continue
        wave_id, frame = result
        await registry.publish(wave_id, frame)
        published += 1

    return {"published": published}
