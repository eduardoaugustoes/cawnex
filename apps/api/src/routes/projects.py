"""Projects routes — create and list projects."""

import re
import time
from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.auth.dependencies import get_tenant
from src.auth.tenant import TenantContext
from src.db.client import TenantDB

router = APIRouter(prefix="/projects", tags=["projects"])


class CreateProjectRequest(BaseModel):
    """Request body for creating a new project."""

    name: str
    repo: str
    description: str = ""


class CreateProjectResponse(BaseModel):
    """Response after creating a project."""

    project_id: str
    name: str


class ProjectSummary(BaseModel):
    """Summary of a project for list responses."""

    project_id: str
    name: str
    repo: str
    description: str
    status: str
    created_at: str


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:40]


def _project_id(name: str) -> str:
    suffix = hex(int(time.time() * 1000))[-6:]
    return f"{_slug(name)}-{suffix}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.post("", response_model=CreateProjectResponse, status_code=201)
async def create_project(
    body: CreateProjectRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> Dict[str, Any]:
    """Create a new project for the authenticated tenant.

    Stores a project list entry under the tenant PK and a project root
    snapshot under the project PK so Murder can resolve the project.
    """
    db = TenantDB(tenant)
    project_id = _project_id(body.name)
    now = _now_iso()

    # Project list entry — queryable via tenant PK
    db.put_item(
        sk=f"P#{project_id}",
        project_id=project_id,
        name=body.name,
        description=body.description,
        repo=body.repo,
        murders=["dev"],
        status="active",
        phase="execution",
        created_at=now,
        entityType="Project",
    )

    # Project root snapshot — used by Murder for project context
    db.put_project_item(
        project_id=project_id,
        sk="S#",
        level="root",
        status="active",
        name=body.name,
        description=body.description,
        repo=body.repo,
        created_at=now,
        entityType="Snapshot",
    )

    return {"project_id": project_id, "name": body.name}


@router.get("", response_model=List[ProjectSummary])
async def list_projects(
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> List[Dict[str, Any]]:
    """List all projects for the authenticated tenant."""
    db = TenantDB(tenant)
    items = db.query(sk_prefix="P#")
    return [
        {
            "project_id": item["project_id"],
            "name": item["name"],
            "repo": item.get("repo", ""),
            "description": item.get("description", ""),
            "status": item.get("status", "active"),
            "created_at": item.get("created_at", ""),
        }
        for item in items
    ]
