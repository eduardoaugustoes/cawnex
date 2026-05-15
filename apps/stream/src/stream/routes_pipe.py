"""Pipe ingestion endpoint.

Accepts both flat records and DDB Streams shape via `pipe_record.normalize_record`.
Production traffic flows via SQS (see `sqs_poller.py`); this HTTP endpoint stays
for test injection.

Authenticated via a shared secret header (X-Pipe-Secret).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from stream.config import load_config
from stream.pipe_record import normalize_record, wave_id_from_pk
from stream.sse import encode_event
from stream.subscribers import SubscriberRegistry

router = APIRouter()


def record_to_frame(record: dict[str, Any]) -> tuple[str, str] | None:
    """Return (wave_id, sse_frame) or None if the record should be skipped.

    Accepts either flat or DDB-Streams-shaped input via normalize_record.
    Public so the SQS poller can reuse it.
    """
    normalized = normalize_record(record)
    if normalized is None:
        return None

    pk = normalized.get("PK", "")
    sk = normalized.get("SK", "")
    wave_id = wave_id_from_pk(pk)
    if wave_id is None:
        return None

    event_id = sk or None
    frame = encode_event(
        event_id=event_id,
        event_name="wave_event",
        data={
            "event_type": normalized.get("event_type", ""),
            "message": normalized.get("message", ""),
            "color": normalized.get("color", ""),
            "timestamp": normalized.get("timestamp", ""),
            "wave_id": wave_id,
            "mvi_id": normalized.get("mvi_id", ""),
        },
    )
    return wave_id, frame


async def publish_records(
    registry: SubscriberRegistry,
    records: list[dict[str, Any]],
) -> int:
    """Fan out a batch of records to subscribers. Returns count published."""
    published = 0
    for record in records:
        if not isinstance(record, dict):
            continue
        result = record_to_frame(record)
        if result is None:
            continue
        wave_id, frame = result
        await registry.publish(wave_id, frame)
        published += 1
    return published


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

    published = await publish_records(request.app.state.registry, payload)
    return {"published": published}
