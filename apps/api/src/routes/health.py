"""Health check endpoint — no auth required."""

import os
from typing import Dict

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> Dict[str, str]:
    """Health check endpoint for load balancer and monitoring.

    Returns:
        Dictionary containing service status and deployment stage
    """
    return {
        "status": "ok",
        "stage": os.environ.get("STAGE", "unknown"),
    }
