"""Vision board — living document + AI chat."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from cawnex_core.models import Tenant
from cawnex_core.models.project import Project, Vision, VisionMessage
from cawnex_core.schemas.project import (
    VisionResponse, VisionUpdate, VisionChatMessage,
    VisionMessageResponse, VisionApply,
)
from cawnex_api.deps import get_db, get_tenant

router = APIRouter(prefix="/projects/{project_id}/vision", tags=["vision"])


async def _get_project(project_id: int, tenant: Tenant, db: AsyncSession) -> Project:
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id, Project.tenant_id == tenant.id)
        .options(selectinload(Project.vision))
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@router.get("", response_model=VisionResponse)
async def get_vision(
    project_id: int,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(project_id, tenant, db)
    if not project.vision:
        raise HTTPException(404, "Vision not initialized")

    # Load messages
    msgs = (await db.execute(
        select(VisionMessage)
        .where(VisionMessage.project_id == project_id)
        .order_by(VisionMessage.created_at)
    )).scalars().all()

    return VisionResponse(
        id=project.vision.id,
        project_id=project.vision.project_id,
        content=project.vision.content,
        version=project.vision.version,
        updated_at=project.vision.updated_at,
        messages=[VisionMessageResponse.model_validate(m) for m in msgs],
    )


@router.put("", response_model=VisionResponse)
async def update_vision(
    project_id: int,
    body: VisionUpdate,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Direct update of vision content (manual edit, not via chat)."""
    project = await _get_project(project_id, tenant, db)
    if not project.vision:
        raise HTTPException(404, "Vision not initialized")

    vision = project.vision
    vision.content = body.content
    vision.version += 1
    await db.flush()
    await db.refresh(vision)

    return VisionResponse(
        id=vision.id,
        project_id=vision.project_id,
        content=vision.content,
        version=vision.version,
        updated_at=vision.updated_at,
    )


@router.post("/chat", response_model=VisionMessageResponse, status_code=201)
async def chat_with_vision(
    project_id: int,
    body: VisionChatMessage,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Send a message to the vision AI assistant.

    The AI response will include suggested changes to the vision document.
    Use POST /vision/apply to accept suggestions.

    TODO: This is a placeholder — actual AI integration will stream responses
    via SSE and use the tenant's BYOL config for the LLM call.
    """
    project = await _get_project(project_id, tenant, db)
    if not project.vision:
        raise HTTPException(404, "Vision not initialized")

    # Save user message
    user_msg = VisionMessage(
        project_id=project_id,
        role="user",
        content=body.message,
        applied=False,
    )
    db.add(user_msg)
    await db.flush()

    # TODO: Call LLM via tenant's BYOL config
    # For now, return a placeholder assistant response
    assistant_msg = VisionMessage(
        project_id=project_id,
        role="assistant",
        content=f"[AI integration pending] Received: {body.message}",
        applied=False,
    )
    db.add(assistant_msg)
    await db.flush()

    return VisionMessageResponse.model_validate(assistant_msg)


@router.post("/apply", response_model=VisionResponse)
async def apply_suggestion(
    project_id: int,
    body: VisionApply,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Apply an AI suggestion to the vision document."""
    project = await _get_project(project_id, tenant, db)
    if not project.vision:
        raise HTTPException(404, "Vision not initialized")

    # Find the message
    msg = (await db.execute(
        select(VisionMessage).where(
            VisionMessage.id == body.message_id,
            VisionMessage.project_id == project_id,
            VisionMessage.role == "assistant",
        )
    )).scalar_one_or_none()
    if not msg:
        raise HTTPException(404, "Message not found or not an assistant message")
    if msg.applied:
        raise HTTPException(400, "Message already applied")

    # Apply: append suggestion to vision content
    # TODO: smarter merge — AI should return structured diffs
    vision = project.vision
    if vision.content:
        vision.content += "\n\n" + msg.content
    else:
        vision.content = msg.content
    vision.version += 1
    msg.applied = True

    await db.flush()
    await db.refresh(vision)

    return VisionResponse(
        id=vision.id,
        project_id=vision.project_id,
        content=vision.content,
        version=vision.version,
        updated_at=vision.updated_at,
    )


@router.get("/messages", response_model=list[VisionMessageResponse])
async def list_messages(
    project_id: int,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
):
    """Get chat history for the vision board."""
    project = await _get_project(project_id, tenant, db)

    msgs = (await db.execute(
        select(VisionMessage)
        .where(VisionMessage.project_id == project_id)
        .order_by(VisionMessage.created_at.desc())
        .limit(limit)
    )).scalars().all()

    return [VisionMessageResponse.model_validate(m) for m in reversed(msgs)]
