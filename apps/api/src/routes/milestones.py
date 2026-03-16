"""Milestones routes — save and retrieve AI-generated milestones."""

from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.auth.dependencies import get_tenant
from src.auth.tenant import TenantContext
from src.db.client import TenantDB

router = APIRouter(
    prefix="/projects/{project_id}/milestones",
    tags=["milestones"],
)


class GoalInput(BaseModel):
    """A goal within a milestone."""

    id: str
    name: str
    description: str
    status: str = "planned"


class MilestoneInput(BaseModel):
    """A milestone with its goals."""

    id: str
    name: str
    description: str
    status: str = "planned"
    goals: List[GoalInput] = []


class SaveMilestonesRequest(BaseModel):
    """Request body for saving milestones."""

    milestones: List[MilestoneInput]


class MilestoneResponse(BaseModel):
    """Response after saving milestones."""

    count: int
    status: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.put("", response_model=MilestoneResponse)
async def save_milestones(
    project_id: str,
    body: SaveMilestonesRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> Dict[str, Any]:
    """Save milestones for a project. Replaces all existing milestones."""
    db = TenantDB(tenant)
    now = _now_iso()

    milestones_data = [
        {
            "id": m.id,
            "name": m.name,
            "description": m.description,
            "status": m.status,
            "goals": [
                {
                    "id": g.id,
                    "name": g.name,
                    "description": g.description,
                    "status": g.status,
                }
                for g in m.goals
            ],
        }
        for m in body.milestones
    ]

    db.put_project_item(
        project_id=project_id,
        sk="BACKLOG#milestones",
        entityType="Backlog",
        milestones=milestones_data,
        count=len(milestones_data),
        created_at=now,
        updated_at=now,
    )

    return {"count": len(milestones_data), "status": "saved"}


@router.get("")
async def get_milestones(
    project_id: str,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> Any:
    """Get milestones for a project. Returns null if none saved."""
    db = TenantDB(tenant)
    item = db.get_project_item(project_id=project_id, sk="BACKLOG#milestones")

    if item is None:
        return None

    return {
        "milestones": item.get("milestones", []),
        "count": item.get("count", 0),
        "created_at": item.get("created_at", ""),
        "updated_at": item.get("updated_at", ""),
    }


@router.get("/context")
async def get_planning_context(
    project_id: str,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> Dict[str, Any]:
    """Get all 4 documents as context for milestone planning.

    The iOS app sends this as context in the AI chat system prompt
    so the AI can propose milestones based on the actual documents.
    """
    db = TenantDB(tenant)

    docs: Dict[str, Any] = {}
    for doc_type in ("vision", "architecture", "glossary", "design"):
        item = db.get_project_item(project_id=project_id, sk=f"DOC#{doc_type}")
        if item and item.get("status") == "complete":
            sections = item.get("sections", [])
            docs[doc_type] = {
                "status": "complete",
                "content": "\n\n".join(
                    f"## {s.get('title', '')}\n{s.get('content', '')}"
                    for s in sections
                ),
            }
        else:
            docs[doc_type] = {"status": "not_started", "content": ""}

    return {"documents": docs}
