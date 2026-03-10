"""Vision board — living document + AI chat with BYOL LLM."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from cawnex_core.models import Tenant
from cawnex_core.models.project import Project, Vision, VisionMessage, Milestone
from cawnex_core.schemas.project import (
    VisionResponse, VisionUpdate, VisionChatMessage,
    VisionMessageResponse, VisionApply,
)
from cawnex_providers.base import LLMProvider
from cawnex_api.deps import get_db, get_tenant, get_llm

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{project_id}/vision", tags=["vision"])

VISION_SYSTEM_PROMPT = """You are a product strategist AI assistant helping build a project vision document.

Your job is to help the user define and refine their product vision through conversation.
When the user asks you to add, modify, or create content for their vision, respond with
the updated vision document section in markdown format.

## Current Vision Document
{vision_content}

## Project Context
- Project: {project_name}
- Repositories: {repos}
- Milestones: {milestones}

## Guidelines
- Write in clear, concise markdown
- Structure the vision with sections: Overview, Problem, Solution, Target Users, Tech Stack, Key Features, Success Metrics
- When suggesting changes, output the FULL updated vision document (not just the diff)
- Be opinionated — suggest improvements, challenge weak assumptions
- Keep it practical and actionable, not aspirational fluff
- If the user is vague, ask clarifying questions before writing
- Match the user's language (if they write in Portuguese, respond in Portuguese)
"""

VISION_MODEL = "claude-sonnet-4-6"  # Use sonnet for vision chat (cost-effective)
VISION_MAX_TOKENS = 4096


async def _get_project_with_context(
    project_id: int, tenant: Tenant, db: AsyncSession
) -> Project:
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id, Project.tenant_id == tenant.id)
        .options(
            selectinload(Project.vision),
            selectinload(Project.milestones),
            selectinload(Project.project_repositories),
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")
    return project


def _build_system_prompt(project: Project) -> str:
    repos_str = "None linked"
    if project.project_repositories:
        # Can't access repository.github_full_name without eager load, use IDs
        repos_str = ", ".join(
            f"repo_id={pr.repository_id} (role={pr.role or 'unset'})"
            for pr in project.project_repositories
        )

    milestones_str = "None defined"
    if project.milestones:
        milestones_str = ", ".join(
            f"{m.name} ({m.status})" for m in project.milestones
        )

    return VISION_SYSTEM_PROMPT.format(
        vision_content=project.vision.content if project.vision else "(empty)",
        project_name=project.name,
        repos=repos_str,
        milestones=milestones_str,
    )


async def _get_chat_history(project_id: int, db: AsyncSession, limit: int = 20) -> list[dict]:
    """Load recent chat history as messages for the LLM."""
    msgs = (await db.execute(
        select(VisionMessage)
        .where(VisionMessage.project_id == project_id)
        .order_by(VisionMessage.created_at.desc())
        .limit(limit)
    )).scalars().all()

    # Reverse to chronological order
    messages = []
    for m in reversed(msgs):
        messages.append({"role": m.role, "content": m.content})
    return messages


@router.get("", response_model=VisionResponse)
async def get_vision(
    project_id: int,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project_with_context(project_id, tenant, db)
    if not project.vision:
        raise HTTPException(404, "Vision not initialized")

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
    project = await _get_project_with_context(project_id, tenant, db)
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
    llm: LLMProvider = Depends(get_llm),
):
    """Send a message to the vision AI. Returns the AI response (non-streaming)."""
    project = await _get_project_with_context(project_id, tenant, db)
    if not project.vision:
        raise HTTPException(404, "Vision not initialized")

    # Save user message (commit immediately so it persists even if LLM fails)
    user_msg = VisionMessage(
        project_id=project_id,
        role="user",
        content=body.message,
        applied=False,
    )
    db.add(user_msg)
    await db.flush()
    await db.commit()

    # Build context
    system = _build_system_prompt(project)
    history = await _get_chat_history(project_id, db, limit=20)

    # History already includes the user message we just saved
    messages = history

    # Call LLM
    try:
        response = await llm.complete(
            model=VISION_MODEL,
            system=system,
            messages=messages,
            max_tokens=VISION_MAX_TOKENS,
        )
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        raise HTTPException(502, f"LLM call failed: {e}")

    # Save assistant response
    assistant_msg = VisionMessage(
        project_id=project_id,
        role="assistant",
        content=response.content,
        applied=False,
    )
    db.add(assistant_msg)
    await db.flush()
    await db.refresh(assistant_msg)

    return VisionMessageResponse.model_validate(assistant_msg)


@router.post("/chat/stream")
async def chat_with_vision_stream(
    project_id: int,
    body: VisionChatMessage,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
    llm: LLMProvider = Depends(get_llm),
):
    """Send a message to the vision AI. Returns SSE stream of the response."""
    project = await _get_project_with_context(project_id, tenant, db)
    if not project.vision:
        raise HTTPException(404, "Vision not initialized")

    # Save user message (commit immediately so it persists even if LLM fails)
    user_msg = VisionMessage(
        project_id=project_id,
        role="user",
        content=body.message,
        applied=False,
    )
    db.add(user_msg)
    await db.flush()
    await db.commit()

    # Build context
    system = _build_system_prompt(project)
    history = await _get_chat_history(project_id, db, limit=20)
    messages = history  # Already includes the user message we just saved

    async def event_stream():
        full_content = ""
        try:
            async for event in llm.stream(
                model=VISION_MODEL,
                system=system,
                messages=messages,
                max_tokens=VISION_MAX_TOKENS,
            ):
                event_type = event.get("type", "")
                data = event.get("data")

                if event_type == "content_block_delta":
                    if hasattr(data, "delta") and hasattr(data.delta, "text"):
                        chunk = data.delta.text
                        full_content += chunk
                        yield f"data: {json.dumps({'type': 'delta', 'text': chunk})}\n\n"
                elif event_type == "message_stop":
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        # Save complete assistant message
        if full_content:
            async with db.begin_nested():
                assistant_msg = VisionMessage(
                    project_id=project_id,
                    role="assistant",
                    content=full_content,
                    applied=False,
                )
                db.add(assistant_msg)
                await db.flush()
                yield f"data: {json.dumps({'type': 'saved', 'message_id': assistant_msg.id})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/apply", response_model=VisionResponse)
async def apply_suggestion(
    project_id: int,
    body: VisionApply,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Apply an AI suggestion — replaces the full vision content."""
    project = await _get_project_with_context(project_id, tenant, db)
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

    # Replace vision content entirely (AI outputs full document)
    vision = project.vision
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
    project = await _get_project_with_context(project_id, tenant, db)

    msgs = (await db.execute(
        select(VisionMessage)
        .where(VisionMessage.project_id == project_id)
        .order_by(VisionMessage.created_at.desc())
        .limit(limit)
    )).scalars().all()

    return [VisionMessageResponse.model_validate(m) for m in reversed(msgs)]
