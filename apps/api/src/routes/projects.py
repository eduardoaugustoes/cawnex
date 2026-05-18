"""Projects routes — create and list projects."""

import re
import time
from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from src.auth.dependencies import get_tenant
from src.auth.tenant import TenantContext
from src.db.client import TenantDB
from src.db.project_state import compute_current_state
from src.models import ProjectReadResponse

router = APIRouter(prefix="/projects", tags=["projects"])

VALID_MURDERS = {"dev", "editorial", "infra", "data", "social"}


class CreateProjectRequest(BaseModel):
    """Request body for creating a new project."""

    name: str
    one_liner: str = ""
    repo: str = ""
    murders: List[str] = Field(default=["dev"])


class CreateProjectResponse(BaseModel):
    """Response after creating a project."""

    project_id: str
    name: str
    status: str
    current_state: str
    murders: List[str]
    created_at: str


class ProjectSummary(BaseModel):
    """Summary of a project for list responses."""

    project_id: str
    name: str
    one_liner: str
    status: str
    current_state: str
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
        repo=body.repo,
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
        repo=body.repo or None,
        repo_status="ready" if body.repo else "pending",
        auto_mode="off",
        maturity_stage="mvp",
        created_at=now,
        updated_at=now,
        entityType="Snapshot",
    )

    return {
        "project_id": project_id,
        "name": body.name,
        "status": "draft",
        "current_state": "draft",
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
    result = []
    for item in items:
        project_id = item.get("project_id", "")
        try:
            current_state = compute_current_state(project_id, db)
        except Exception:
            # If state computation fails, default to draft
            current_state = "draft"
        result.append(
            {
                "project_id": project_id,
                "name": item.get("name", ""),
                "one_liner": item.get("one_liner", item.get("description", "")),
                "status": item.get("status", "draft"),
                "current_state": current_state,
                "murders": item.get("murders", ["dev"]),
                "created_at": item.get("created_at", ""),
            }
        )
    return result


@router.get("/{project_id}", response_model=ProjectReadResponse)
async def get_project(
    project_id: str,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> Dict[str, Any]:
    """Get a single project by ID with computed state."""
    db = TenantDB(tenant)
    item = db.get_item(sk=f"P#{project_id}")
    if not item:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        current_state = compute_current_state(project_id, db)
    except Exception:
        # If state computation fails, default to draft
        current_state = "draft"

    return {
        "project_id": project_id,
        "name": item.get("name", ""),
        "one_liner": item.get("one_liner", item.get("description", "")),
        "status": item.get("status", "draft"),
        "current_state": current_state,
        "murders": item.get("murders", ["dev"]),
        "created_at": item.get("created_at", ""),
    }


VALID_AUTO_MODES = {"off", "auto", "supervised"}


class UpdateProjectRequest(BaseModel):
    """Request body for updating project settings."""

    auto_mode: str | None = None

    @field_validator("auto_mode")
    @classmethod
    def validate_auto_mode(cls, v: str | None) -> str | None:
        """Ensure auto_mode is one of the allowed values."""
        if v is not None and v not in VALID_AUTO_MODES:
            raise ValueError("auto_mode must be 'off', 'auto', or 'supervised'")
        return v


@router.patch("/{project_id}")
async def update_project(
    project_id: str,
    body: UpdateProjectRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> Dict[str, Any]:
    """Update project settings (auto_mode)."""
    db = TenantDB(tenant)
    root = db.get_project_item(project_id, "S#")
    if not root:
        raise HTTPException(status_code=404, detail="Project not found")

    updates: Dict[str, Any] = {}
    if body.auto_mode is not None:
        updates["auto_mode"] = body.auto_mode

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    db.update_project_item(project_id, "S#", updates)
    return {
        "status": "updated",
        "auto_mode": body.auto_mode or root.get("auto_mode", "off"),
    }
