"""Goals routes — MVI planning within goals."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.auth.dependencies import get_tenant
from src.auth.tenant import TenantContext
from src.db.client import TenantDB

router = APIRouter(
    prefix="/projects/{project_id}/goals",
    tags=["goals"],
)

MAX_MVI_HOURS = 8


class MVIInput(BaseModel):
    """A single MVI within a goal."""

    id: str
    name: str
    description: str
    acceptance_criteria: str = ""
    estimated_hours: float = Field(le=MAX_MVI_HOURS, gt=0)
    status: str = "planned"


class SaveMVIsRequest(BaseModel):
    """Request body for saving MVIs."""

    mvis: List[MVIInput]


class MVIResponse(BaseModel):
    """Response after saving MVIs."""

    count: int
    status: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _find_goal_in_milestones(
    milestones: List[Dict[str, Any]], goal_id: str
) -> tuple[Dict[str, Any] | None, Dict[str, Any] | None]:
    """Find a goal by ID within the nested milestones structure.

    Returns (milestone, goal) or (None, None) if not found.
    """
    for milestone in milestones:
        for goal in milestone.get("goals", []):
            if goal.get("id") == goal_id:
                return milestone, goal
    return None, None


@router.get("/{goal_id}/context")
async def get_goal_context(
    project_id: str,
    goal_id: str,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> Dict[str, Any]:
    """Get full context for MVI planning within a goal.

    Returns the goal, its parent milestone, sibling goals,
    and all 4 project documents for the AI to read.
    """
    db = TenantDB(tenant)

    # Load milestones
    backlog = db.get_project_item(project_id=project_id, sk="BACKLOG#milestones")
    if not backlog:
        raise HTTPException(status_code=404, detail="No milestones found")

    milestones = backlog.get("milestones", [])
    milestone, goal = _find_goal_in_milestones(milestones, goal_id)

    if not milestone or not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    # Sibling goals (other goals in same milestone)
    sibling_goals = [g for g in milestone.get("goals", []) if g.get("id") != goal_id]

    # Load documents
    docs: Dict[str, Any] = {}
    for doc_type in ("vision", "architecture", "glossary", "design"):
        item = db.get_project_item(project_id=project_id, sk=f"DOC#{doc_type}")
        if item and item.get("status") == "complete":
            sections = item.get("sections", [])
            docs[doc_type] = "\n\n".join(
                f"## {s.get('title', '')}\n{s.get('content', '')}" for s in sections
            )
        else:
            docs[doc_type] = ""

    # Load existing MVIs for this goal — these are *plan* records (id, name,
    # description, estimated_hours) written at goal-planning time. They go
    # stale relative to execution. So we enrich each with the live state
    # from the execution snapshot at S#{wave_id}#m{mvi_id} when one exists.
    existing_mvis_item = db.get_project_item(
        project_id=project_id, sk=f"BACKLOG#goal#{goal_id}#mvis"
    )
    enriched_mvis = _enrich_with_execution_state(
        db, project_id, existing_mvis_item.get("mvis", []) if existing_mvis_item else []
    )

    return {
        "goal": goal,
        "milestone": {
            "id": milestone.get("id", ""),
            "name": milestone.get("name", ""),
            "description": milestone.get("description", ""),
        },
        "sibling_goals": sibling_goals,
        "documents": docs,
        "existing_mvis": enriched_mvis,
    }


def _enrich_with_execution_state(
    db: TenantDB, project_id: str, plan_mvis: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Overlay live status/tasks_done/tasks_total from the execution snapshot.

    The plan record at BACKLOG#goal#{gid}#mvis is frozen at planning time.
    The execution snapshot at S#{wave_id}#m{mvi_id} carries the live truth
    (status, tasks_done, tasks_total). When a plan record has wave_id set,
    we look up the snapshot and overlay those fields; if no wave has run
    yet (wave_id missing/empty), the plan record passes through unchanged.
    """
    out: list[dict[str, Any]] = []
    for plan in plan_mvis:
        merged = dict(plan)
        wave_id = plan.get("wave_id") or ""
        mvi_id = plan.get("id") or ""
        if wave_id and mvi_id:
            snapshot = db.get_project_item(
                project_id=project_id,
                sk=f"S#{wave_id}#m{mvi_id}",
            )
            if snapshot:
                # Snapshot wins for execution-state fields.
                for key in ("status", "tasks_done", "tasks_total", "can_ship"):
                    if key in snapshot:
                        merged[key] = snapshot[key]
        out.append(merged)
    return out


@router.post("/{goal_id}/mvis", response_model=MVIResponse, status_code=201)
async def save_mvis(
    project_id: str,
    goal_id: str,
    body: SaveMVIsRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> Dict[str, Any]:
    """Save MVIs for a goal. Replaces existing MVIs for this goal."""
    db = TenantDB(tenant)
    now = _now_iso()

    # Enforce ≤8h per MVI
    for mvi in body.mvis:
        if mvi.estimated_hours > MAX_MVI_HOURS:
            raise HTTPException(
                status_code=400,
                detail=f"MVI '{mvi.name}' exceeds {MAX_MVI_HOURS}h limit "
                f"({mvi.estimated_hours}h). Split into smaller MVIs.",
            )

    mvis_data = [
        {
            "id": m.id,
            "name": m.name,
            "description": m.description,
            "acceptance_criteria": m.acceptance_criteria,
            "estimated_hours": Decimal(str(m.estimated_hours)),
            "status": m.status,
        }
        for m in body.mvis
    ]

    total_hours = sum(m.estimated_hours for m in body.mvis)

    db.put_project_item(
        project_id=project_id,
        sk=f"BACKLOG#goal#{goal_id}#mvis",
        entityType="GoalMVIs",
        goal_id=goal_id,
        mvis=mvis_data,
        count=len(mvis_data),
        total_estimated_hours=Decimal(str(total_hours)),
        created_at=now,
        updated_at=now,
    )

    return {"count": len(mvis_data), "status": "saved"}


@router.get("/{goal_id}/mvis")
async def get_mvis(
    project_id: str,
    goal_id: str,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> Any:
    """Get MVIs for a goal. Returns null if none saved."""
    db = TenantDB(tenant)
    item = db.get_project_item(project_id=project_id, sk=f"BACKLOG#goal#{goal_id}#mvis")

    if item is None:
        return None

    return {
        "mvis": item.get("mvis", []),
        "count": item.get("count", 0),
        "total_estimated_hours": item.get("total_estimated_hours", 0),
        "created_at": item.get("created_at", ""),
        "updated_at": item.get("updated_at", ""),
    }
