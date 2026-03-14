"""Health check endpoint — no auth required."""

import os

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "stage": os.environ.get("STAGE", "unknown"),
    }
