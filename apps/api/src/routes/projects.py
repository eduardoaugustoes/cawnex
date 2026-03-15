"""Projects routes — create and list projects."""

import re
import time
from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.auth.dependencies import get_tenant
from src.auth.tenant import TenantContext
from src.db.client import TenantDB

router = APIRouter(prefix="/projects", tags=["projects"])

VALID_MURDERS = {"dev", "editorial", "infra", "data", "social"}


class CreateProjectRequest(BaseModel):
    """Request body for creating a new project."""

    name: str
    one_liner: str = ""
    murders: List[str] = Field(default=["dev"])


class CreateProjectResponse(BaseModel):
    """Response after creating a project."""

    project_id: str
    name: str
    status: str
    murders: List[str]
    created_at: str


class ProjectSummary(BaseModel):
    """Summary of a project for list responses."""

    project_id: str
    name: str
    one_liner: str
    status: str
    murders: List[str]
    created_at: str


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:40]


def _project_id(name: str) -> str:
    ts_suffix = hex(int(time.time() * 1000))[-4:]
    rand_suffix = hex(int.from_bytes(__import__("os").urandom(1), "big"))[-2:]
    return f"{_slug(name)}-{ts_suffix}{rand_suffix}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.post("", response_model=CreateProjectResponse, status_code=201)
async def create_project(
    body: CreateProjectRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> Dict[str, Any]:
    """Create a new project for the authenticated tenant.

    Writes two records:
    1. Project list entry (PK: T#{tenant}, SK: P#{id}) for listing
    2. Project root snapshot (PK: T#{tenant}#P#{id}, SK: S#) for Murder
    """
    db = TenantDB(tenant)
    project_id = _project_id(body.name)
    now = _now_iso()
    murders = [m for m in body.murders if m in VALID_MURDERS] or ["dev"]

    # Record 1: Project list entry — queryable via tenant PK
    db.put_item(
        sk=f"P#{project_id}",
        project_id=project_id,
        name=body.name,
        one_liner=body.one_liner,
        murders=murders,
        status="draft",
        created_at=now,
        updated_at=now,
        entityType="ProjectEntry",
    )

    # Record 2: Project root snapshot — Murder reads this
    db.put_project_item(
        project_id=project_id,
        sk="S#",
        level="root",
        name=body.name,
        one_liner=body.one_liner,
        murders=murders,
        status="draft",
        repo=None,
        repo_status="pending",
        created_at=now,
        updated_at=now,
        entityType="Snapshot",
    )

    return {
        "project_id": project_id,
        "name": body.name,
        "status": "draft",
        "murders": murders,
        "created_at": now,
    }


@router.get("", response_model=List[ProjectSummary])
async def list_projects(
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> List[Dict[str, Any]]:
    """List all projects for the authenticated tenant."""
    db = TenantDB(tenant)
    items = db.query(sk_prefix="P#")
    return [
        {
            "project_id": item.get("project_id", ""),
            "name": item.get("name", ""),
            "one_liner": item.get("one_liner", item.get("description", "")),
            "status": item.get("status", "draft"),
            "murders": item.get("murders", ["dev"]),
            "created_at": item.get("created_at", ""),
        }
        for item in items
    ]
