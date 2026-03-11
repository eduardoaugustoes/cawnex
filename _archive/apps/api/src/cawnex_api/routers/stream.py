"""SSE streaming endpoint — real-time execution events to dashboard."""

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from cawnex_core.models import Task, Tenant
from cawnex_api.deps import get_db, get_tenant, get_redis

router = APIRouter(prefix="/stream", tags=["streaming"])


@router.get("/tasks/{task_id}/events")
async def stream_task_events(
    task_id: int,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """SSE stream of execution events for a task. Used by dashboard for live updates."""
    # Verify task belongs to tenant
    task = (await db.execute(
        select(Task).where(Task.id == task_id, Task.tenant_id == tenant.id)
    )).scalar_one_or_none()
    if not task:
        raise HTTPException(404, "Task not found")

    stream_key = f"cawnex:events:{task_id}"

    async def event_generator():
        last_id = "0"
        while True:
            # Read new events from Redis Stream
            events = await redis.xread({stream_key: last_id}, count=10, block=5000)
            if events:
                for stream_name, messages in events:
                    for msg_id, data in messages:
                        last_id = msg_id
                        yield f"data: {json.dumps(data)}\n\n"

            # Send keepalive
            yield ": keepalive\n\n"

            # Check if task is terminal
            task_check = (await db.execute(
                select(Task.status).where(Task.id == task_id)
            )).scalar()
            if task_check in ("completed", "failed", "rejected"):
                yield f"data: {json.dumps({'type': 'done', 'status': task_check})}\n\n"
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
