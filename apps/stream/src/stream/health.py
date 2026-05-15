"""Health check endpoint for the ALB target group."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/_health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
