"""Milestones routes — save and retrieve AI-generated milestones."""

from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List

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


@router.post("", response_model=MilestoneResponse, status_code=201)
async def add_milestone(
    project_id: str,
    body: MilestoneInput,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> Dict[str, Any]:
    """Add a single milestone to the project backlog."""
    db = TenantDB(tenant)
    now = _now_iso()

    # Load existing milestones
    existing = db.get_project_item(project_id=project_id, sk="BACKLOG#milestones")
    milestones_data: List[Dict[str, Any]] = (
        existing.get("milestones", []) if existing else []
    )

    # Append new milestone
    new_milestone = {
        "id": body.id,
        "name": body.name,
        "description": body.description,
        "status": body.status,
        "goals": [
            {
                "id": g.id,
                "name": g.name,
                "description": g.description,
                "status": g.status,
            }
            for g in body.goals
        ],
    }
    milestones_data.append(new_milestone)

    db.put_project_item(
        project_id=project_id,
        sk="BACKLOG#milestones",
        entityType="Backlog",
        milestones=milestones_data,
        count=len(milestones_data),
        created_at=existing.get("created_at", now) if existing else now,
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

    milestones = item.get("milestones", [])
    for milestone in milestones:
        for goal in milestone.get("goals", []):
            mvi_item = db.get_project_item(
                project_id=project_id,
                sk=f"BACKLOG#goal#{goal['id']}#mvis",
            )
            mvis = mvi_item.get("mvis", []) if mvi_item else []
            goal["mvi_count"] = len(mvis)
            goal["mvis_complete"] = sum(1 for m in mvis if m.get("status") == "shipped")

    return {
        "milestones": milestones,
        "count": item.get("count", 0),
        "created_at": item.get("created_at", ""),
        "updated_at": item.get("updated_at", ""),
    }


# ---- MilestoneDetail (Phase 2.1) -------------------------------------------
#
# iOS MilestoneDetail expects a mix of real and placeholder fields:
#   * milestone (id, name, description, status, task counts, ROI) — real
#   * breadcrumb — derived
#   * sections (Business Achievement / Success Criteria / etc.) — placeholder
#     (we don't track per-milestone section completion yet)
#   * messages (AI chat history) — placeholder, no message store
#   * goals[] with mvi_count + task_count — derived from goal MVIs


class MilestoneMVICounts(BaseModel):
    """Per-milestone MVI status tally — buckets MVIs by their lifecycle stage.

    This is NOT a task count. Tasks live inside MVIs (and we sum them
    elsewhere for Project Hub totals). Milestones aggregate at the MVI
    grain because that's the natural unit of milestone progress.
    """

    done: int
    active: int
    refined: int
    draft: int


class MilestoneGoalSummary(BaseModel):
    """Lightweight goal summary nested in milestone detail."""

    id: str
    name: str
    status: str
    description: str
    mvi_count: int
    task_count: int


class MilestoneDefinitionSection(BaseModel):
    """Placeholder until per-milestone section tracking is added."""

    id: str
    title: str
    status: str  # "pending" | "complete"


class MilestoneDetailResponse(BaseModel):
    """Aggregated milestone view matching iOS MilestoneDetail."""

    id: str
    name: str
    description: str
    status: str
    breadcrumb: str
    mvi_counts: MilestoneMVICounts
    credits_spent: int
    human_equiv_saved: int
    roi: int
    goals: list[MilestoneGoalSummary]
    sections: list[MilestoneDefinitionSection]
    messages: list[dict[str, Any]]


# Fixed section list iOS expects — order matters for the progress bar UI.
_MILESTONE_SECTION_TITLES: list[str] = [
    "Business Achievement",
    "Success Criteria",
    "Target Impact",
    "Timeline",
    "Dependencies",
    "Risk Assessment",
]


def _aggregate_goal_mvis(
    db: TenantDB, project_id: str, goals: list[dict[str, Any]]
) -> tuple[list[MilestoneGoalSummary], MilestoneMVICounts]:
    """For each goal: count MVIs by status, plus per-goal task totals.

    The returned MilestoneMVICounts buckets MVIs by lifecycle stage —
    not tasks (per the rename done with the iOS rename to mvi_counts).
    """
    summaries: list[MilestoneGoalSummary] = []
    counts = {"done": 0, "active": 0, "refined": 0, "draft": 0}

    for goal in goals:
        goal_id = goal.get("id", "")
        mvi_record = db.get_project_item(
            project_id=project_id, sk=f"BACKLOG#goal#{goal_id}#mvis"
        )
        mvis: list[dict[str, Any]] = mvi_record.get("mvis", []) if mvi_record else []

        task_count = 0
        for m in mvis:
            status = (m.get("status") or "draft").lower()
            # MVI statuses we know about: draft, refined, planning, queued,
            # executing, ready_to_ship, shipped, failed, cancelled
            if status in ("shipped", "ready_to_ship"):
                counts["done"] += 1
            elif status in ("planning", "queued", "executing", "running"):
                counts["active"] += 1
            elif status == "refined":
                counts["refined"] += 1
            else:
                counts["draft"] += 1
            task_count += int(m.get("tasks_total", 0) or 0)

        summaries.append(
            MilestoneGoalSummary(
                id=goal_id,
                name=goal.get("name", ""),
                status=goal.get("status", "planned"),
                description=goal.get("description", ""),
                mvi_count=len(mvis),
                task_count=task_count,
            )
        )

    return summaries, MilestoneMVICounts(**counts)


@router.get("/{milestone_id}", response_model=MilestoneDetailResponse)
async def get_milestone_detail(
    project_id: str,
    milestone_id: str,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> MilestoneDetailResponse:
    """Aggregate one milestone's detail view for iOS MilestoneDetailScreen.

    Sources:
      * BACKLOG#milestones for the milestone record
      * BACKLOG#goal#{id}#mvis for each goal's MVIs + task tallies

    Placeholders (empty arrays / zeros):
      * sections — 6 fixed titles returned with status='pending'
      * messages — chat history not stored yet
      * credits_spent / human_equiv_saved / roi — set to 0 until we
        roll up wave costs per milestone (Phase 2.2 will own
        cross-project aggregation; milestone-level rollup is a
        separate enrichment we can layer on later)
    """
    db = TenantDB(tenant)
    container = db.get_project_item(project_id=project_id, sk="BACKLOG#milestones")
    if container is None:
        raise HTTPException(status_code=404, detail="No milestones for this project")
    milestones = container.get("milestones", []) or []

    target = next((m for m in milestones if m.get("id") == milestone_id), None)
    if target is None:
        raise HTTPException(
            status_code=404,
            detail=f"Milestone {milestone_id} not found in project",
        )

    goals = target.get("goals", []) or []
    goal_summaries, mvi_counts = _aggregate_goal_mvis(db, project_id, goals)

    sections = [
        MilestoneDefinitionSection(
            id=f"sec-{i}",
            title=title,
            status="pending",
        )
        for i, title in enumerate(_MILESTONE_SECTION_TITLES)
    ]

    return MilestoneDetailResponse(
        id=milestone_id,
        name=target.get("name", "Milestone"),
        description=target.get("description", ""),
        status=target.get("status", "planned"),
        breadcrumb=f"Backlog › {target.get('name', milestone_id)}",
        mvi_counts=mvi_counts,
        credits_spent=0,
        human_equiv_saved=0,
        roi=0,
        goals=goal_summaries,
        sections=sections,
        messages=[],
    )


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
                    f"## {s.get('title', '')}\n{s.get('content', '')}" for s in sections
                ),
            }
        else:
            docs[doc_type] = {"status": "not_started", "content": ""}

    return {"documents": docs}
