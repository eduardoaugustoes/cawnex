"""Waves routes — create and query waves."""

import re
import time
from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.auth.dependencies import get_tenant
from src.auth.tenant import TenantContext
from src.db.client import TenantDB

router = APIRouter(prefix="/projects/{project_id}/waves", tags=["waves"])

_DEFAULT_BUDGET_MICROS = 20_000_000  # $20


class CreateWaveRequest(BaseModel):
    """Request body for creating a wave with a human directive."""

    directive: str
    budget_micros: int = _DEFAULT_BUDGET_MICROS


class CreateWaveResponse(BaseModel):
    """Response after creating a wave and its initial MVI."""

    wave_id: str
    mvi_id: str
    status: str


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:30]


def _wave_id() -> str:
    return f"w{int(time.time() * 1000)}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.post("", response_model=CreateWaveResponse, status_code=201)
async def create_wave(
    project_id: str,
    body: CreateWaveRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> Dict[str, Any]:
    """Create a wave and an initial MVI for the given project.

    Writes wave and MVI snapshots using the Murder key pattern
    (PK: T#{tenant}#P#{project_id}). The DynamoDB Stream delivers
    the wave record to Murder which reacts to status=planning and
    assigns the first planner crow.
    """
    db = TenantDB(tenant)

    project = db.get_item(sk=f"P#{project_id}")
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    wave_id = _wave_id()
    mvi_id = _slug(body.directive) or wave_id
    now = _now_iso()
    repo = project.get("repo", "")
    branch = f"cawnex/{wave_id}-{mvi_id}"

    # Wave snapshot — status=planning triggers Murder
    db.put_project_item(
        project_id=project_id,
        sk=f"S#{wave_id}",
        level="wave",
        status="planning",
        human_directive=body.directive,
        progress={
            "mvis_total": 1,
            "mvis_shipped": 0,
            "tasks_done": 0,
            "tasks_total": 0,
        },
        budget={"spent": 0, "limit": body.budget_micros},
        created_at=now,
        entityType="Snapshot",
    )

    # MVI snapshot — Murder reacts to wave=planning, sees this queued MVI
    db.put_project_item(
        project_id=project_id,
        sk=f"S#{wave_id}#m{mvi_id}",
        level="murder",
        status="queued",
        name=body.directive,
        description="",
        acceptance_criteria="",
        tasks_done=0,
        tasks_total=0,
        can_ship=False,
        merge_checklist=[],
        cost={"tokens_in": 0, "tokens_out": 0, "credits": 0, "duration_ms": 0},
        repo=repo,
        branch=branch,
        created_at=now,
        entityType="Snapshot",
    )

    return {"wave_id": wave_id, "mvi_id": mvi_id, "status": "planning"}


@router.get("/{wave_id}")
async def get_wave(
    project_id: str,
    wave_id: str,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> Dict[str, Any]:
    """Return the wave snapshot and all child snapshots.

    Queries all items with PK T#{tenant}#P#{project_id} and SK beginning
    with S#{wave_id}, then partitions them into wave, mvi, and crow buckets.
    """
    db = TenantDB(tenant)
    items = db.query_project(project_id=project_id, sk_prefix=f"S#{wave_id}")

    if not items:
        raise HTTPException(status_code=404, detail="Wave not found")

    wave: Optional[Dict[str, Any]] = None
    mvis: List[Dict[str, Any]] = []
    crows: List[Dict[str, Any]] = []

    for item in items:
        level = item.get("level")
        if level == "wave":
            wave = item
        elif level == "murder":
            mvis.append(item)
        elif level == "crow":
            crows.append(item)

    return {
        "wave": wave,
        "mvis": mvis,
        "crows": crows,
    }
