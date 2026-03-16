"""Project Hub route — aggregated view for the Project Hub screen."""

from typing import Annotated, Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from src.auth.dependencies import get_tenant
from src.auth.tenant import TenantContext
from src.db.client import TenantDB

router = APIRouter(prefix="/projects/{project_id}", tags=["hub"])

DOC_TYPES = ["vision", "architecture", "glossary", "design"]


@router.get("/hub")
async def get_project_hub(
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

    return {
        "project": {
            "id": project_id,
            "name": project.get("name", ""),
            "one_liner": project.get("one_liner", ""),
            "status": project.get("status", "draft"),
            "murders": project.get("murders", ["dev"]),
        },
        "documents": documents,
        "stats": {
            "progress": 0,
            "tasks_done": 0,
            "tasks_total": 0,
            "pending_approvals": 0,
            "ai_cost_usd": ai_cost,
            "ai_call_count": ai_calls,
        },
    }
