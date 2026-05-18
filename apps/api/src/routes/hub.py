"""Project Hub route — aggregated view for the Project Hub screen."""

from typing import Annotated, Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from src.auth.dependencies import get_tenant
from src.auth.tenant import TenantContext
from src.db.client import TenantDB
from src.db.project_state import compute_current_state

router = APIRouter(prefix="/projects/{project_id}", tags=["hub"])

DOC_TYPES = ["vision", "architecture", "glossary", "design"]


@router.get("/hub")
async def get_project_hub(  # noqa: C901
    project_id: str,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> Dict[str, Any]:
    """Return aggregated Project Hub data.

    Queries the project root snapshot and all DOC# records in one sweep.
    Returns project info, document statuses, and basic stats.
    """
    db = TenantDB(tenant)

    # Get project root
    project = db.get_project_item(project_id=project_id, sk="S#")
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # Compute current_state
    try:
        current_state = compute_current_state(project_id, db)
    except Exception:
        current_state = "draft"

    # Get all items under the project (includes DOC#, S#wave, etc.)
    all_items = db.query_project(project_id=project_id, sk_prefix="DOC#")

    # Build document status map
    doc_status_map: Dict[str, str] = {}
    for item in all_items:
        doc_type = item.get("doc_type", "")
        if doc_type in DOC_TYPES:
            doc_status_map[doc_type] = item.get("status", "not_started")

    # Build documents list with all 4 types
    documents: List[Dict[str, str]] = []
    for doc_type in DOC_TYPES:
        status = doc_status_map.get(doc_type, "not_started")
        documents.append({"type": doc_type, "status": status})

    # Basic stats from project root
    ai_cost = float(project.get("ai_cost_usd", 0) or 0)
    ai_calls = int(project.get("ai_call_count", 0) or 0)

    # Wave and execution stats
    wave_items = db.query_project(project_id=project_id, sk_prefix="S#")
    active_waves = 0
    pending_ship = 0
    pending_human_tasks = 0
    total_budget_spent = 0
    total_budget_limit = 0
    total_mvis = 0
    mvis_shipped = 0
    tasks_done = 0
    tasks_total = 0

    # Collect data in first pass, compute derived stats after
    completed_mvi_sks: set[str] = set()
    # Keep only the last planner per MVI (highest crow sequence number)
    planner_by_mvi: Dict[str, int] = {}

    for item in wave_items:
        level = item.get("level", "")
        if level == "wave":
            status = item.get("status", "")
            if status in ("executing", "paused"):
                active_waves += 1
            budget = item.get("budget", {})
            total_budget_spent += int(budget.get("spent", 0))
            total_budget_limit += int(budget.get("limit", 0))
            total_mvis += int(item.get("progress", {}).get("mvis_total", 0))
        elif level == "murder":
            mvi_status = item.get("status", "")
            if mvi_status == "ready_to_ship":
                pending_ship += 1
            if mvi_status in ("ready_to_ship", "shipped"):
                completed_mvi_sks.add(item.get("SK", ""))
                mvis_shipped += 1
        elif level == "crow":
            if item.get("task_type") == "human":
                ht_status = item.get("status", "")
                if ht_status in (
                    "pending",
                    "notified",
                    "in_progress",
                    "verification_failed",
                ):
                    pending_human_tasks += 1
            if item.get("crow_type") == "planner" and item.get("status") == "completed":
                outcome = item.get("outcome")
                if isinstance(outcome, dict):
                    plan_tasks = outcome.get("tasks", [])
                    if isinstance(plan_tasks, list) and plan_tasks:
                        sk = item.get("SK", "")
                        mvi_sk = "#".join(sk.split("#")[:3])
                        # Keep latest planner per MVI (last one wins)
                        planner_by_mvi[mvi_sk] = len(plan_tasks)

    # Derive task counts — one entry per MVI, not per planner
    for mvi_sk, count in planner_by_mvi.items():
        tasks_total += count
        if mvi_sk in completed_mvi_sks:
            tasks_done += count

    progress_pct = int(mvis_shipped * 100 / total_mvis) if total_mvis > 0 else 0

    return {
        "project": {
            "id": project_id,
            "name": project.get("name", ""),
            "one_liner": project.get("one_liner", ""),
            "status": project.get("status", "draft"),
            "current_state": current_state,
            "murders": project.get("murders", ["dev"]),
        },
        "documents": documents,
        "stats": {
            "progress": progress_pct,
            "tasks_done": tasks_done,
            "tasks_total": tasks_total,
            "pending_approvals": pending_ship,
            "ai_cost_usd": ai_cost,
            "ai_call_count": ai_calls,
        },
        "waves": {
            "active_count": active_waves,
            "pending_ship": pending_ship,
            "pending_human_tasks": pending_human_tasks,
            "budget_spent": total_budget_spent,
            "budget_limit": total_budget_limit,
            "mvis_total": total_mvis,
            "mvis_shipped": mvis_shipped,
        },
    }
