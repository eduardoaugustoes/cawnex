"""Document routes — save completed AI-guided documents.

Documents are built client-side via the AI chat proxy.
This endpoint persists the final result when the founder is done.
"""

from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.auth.dependencies import get_tenant
from src.auth.tenant import TenantContext
from src.db.client import TenantDB

router = APIRouter(
    prefix="/projects/{project_id}/documents",
    tags=["documents"],
)


class SectionInput(BaseModel):
    """A completed document section."""

    id: str
    title: str
    content: str
    status: str = "complete"


class SaveDocumentRequest(BaseModel):
    """Request body for saving a completed document."""

    sections: List[SectionInput]


class DocumentResponse(BaseModel):
    """Response after saving or retrieving a document."""

    doc_type: str
    status: str
    sections: List[Dict[str, str]]
    created_at: str
    updated_at: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.put("/{doc_type}", response_model=DocumentResponse)
async def save_document(
    project_id: str,
    doc_type: str,
    body: SaveDocumentRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> Dict[str, Any]:
    """Save or update a completed document for a project.

    Called by the iOS app when the founder finishes the AI-guided flow.
    Overwrites any existing document of the same type.
    """
    if doc_type not in ("vision", "architecture", "glossary", "design"):
        raise HTTPException(status_code=400, detail=f"Invalid document type: {doc_type}")

    db = TenantDB(tenant)
    now = _now_iso()

    sections_data = [
        {"id": s.id, "title": s.title, "content": s.content, "status": s.status}
        for s in body.sections
    ]

    all_complete = all(s.status == "complete" for s in body.sections)
    status = "complete" if all_complete else "in_progress"

    db.put_project_item(
        project_id=project_id,
        sk=f"DOC#{doc_type}",
        entityType="Document",
        doc_type=doc_type,
        status=status,
        sections=sections_data,
        created_at=now,
        updated_at=now,
    )

    return {
        "doc_type": doc_type,
        "status": status,
        "sections": sections_data,
        "created_at": now,
        "updated_at": now,
    }


@router.get("/{doc_type}", response_model=Optional[DocumentResponse])
async def get_document(
    project_id: str,
    doc_type: str,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> Any:
    """Retrieve a saved document for a project. Returns null if not saved yet."""
    if doc_type not in ("vision", "architecture", "glossary", "design"):
        raise HTTPException(status_code=400, detail=f"Invalid document type: {doc_type}")

    db = TenantDB(tenant)
    item = db.get_project_item(project_id=project_id, sk=f"DOC#{doc_type}")

    if item is None:
        return None

    return {
        "doc_type": item.get("doc_type", doc_type),
        "status": item.get("status", "in_progress"),
        "sections": item.get("sections", []),
        "created_at": item.get("created_at", ""),
        "updated_at": item.get("updated_at", ""),
    }
