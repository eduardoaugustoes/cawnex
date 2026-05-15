"""Public SSE endpoint: GET /projects/{pid}/waves/{wid}/stream.

Validates the Cognito JWT, registers a subscriber, then yields SSE frames
forever. A keepalive comment is emitted every 25 seconds so the ALB's 60s
idle timeout doesn't kill the connection. On client disconnect or
backpressure drop, the subscriber is unregistered.

Wave ownership (tenant has access to this wave) is enforced in Phase 2
when DDB lookups are wired. For Phase 1 the JWT proves authenticated user;
wave_id is otherwise unguessable per tenant.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from stream.auth import AuthError, validate_token
from stream.config import load_config
from stream.sse import KEEPALIVE_COMMENT
from stream.subscribers import BackpressureDrop, Subscriber, SubscriberRegistry

router = APIRouter()

KEEPALIVE_INTERVAL_SEC = 25.0


@router.get("/projects/{project_id}/waves/{wave_id}/stream")
async def stream_wave_events(
    project_id: str,
    wave_id: str,
    request: Request,
    authorization: str = Header(default=""),
) -> StreamingResponse:
    cfg = load_config()
    try:
        validate_token(
            authorization,
            user_pool_id=cfg.user_pool_id,
            region=cfg.region,
        )
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    registry: SubscriberRegistry = request.app.state.registry

    async def event_generator() -> AsyncIterator[str]:
        sub = Subscriber(wave_id=wave_id)
        registry.register(sub)
        try:
            while True:
                if await request.is_disconnected():
                    return
                try:
                    frame = await asyncio.wait_for(
                        sub.queue.get(),
                        timeout=KEEPALIVE_INTERVAL_SEC,
                    )
                    yield frame
                except asyncio.TimeoutError:
                    yield KEEPALIVE_COMMENT
                try:
                    sub.raise_if_dropped()
                except BackpressureDrop:
                    return
        finally:
            registry.unregister(sub)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
