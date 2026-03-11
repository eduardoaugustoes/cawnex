"""Milestone CRUD + reordering."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from cawnex_core.models import Tenant, Task
from cawnex_core.models.project import Project, Milestone
from cawnex_core.enums import MilestoneStatus
from cawnex_core.schemas.project import (
    MilestoneCreate, MilestoneUpdate, MilestoneResponse, MilestoneReorder,
)
from cawnex_api.deps import get_db, get_tenant

router = APIRouter(prefix="/projects/{project_id}/milestones", tags=["milestones"])


async def _get_project(project_id: int, tenant: Tenant, db: AsyncSession) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.tenant_id == tenant.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")
    return project


def _milestone_to_response(milestone: Milestone, task_count: int = 0) -> MilestoneResponse:
    return MilestoneResponse(
        id=milestone.id,
        project_id=milestone.project_id,
        name=milestone.name,
        description=milestone.description,
        goal=milestone.goal,
        position=milestone.position,
        status=MilestoneStatus(milestone.status),
        github_milestone_id=milestone.github_milestone_id,
        task_count=task_count,
        created_at=milestone.created_at,
        updated_at=milestone.updated_at,
    )


@router.post("", response_model=MilestoneResponse, status_code=201)
async def create_milestone(
    project_id: int,
    body: MilestoneCreate,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(project_id, tenant, db)

    # Get next position
    max_pos = (await db.execute(
        select(func.max(Milestone.position)).where(Milestone.project_id == project_id)
    )).scalar() or -1

    milestone = Milestone(
        project_id=project_id,
        name=body.name,
        description=body.description,
        goal=body.goal,
        position=max_pos + 1,
        status=MilestoneStatus.PLANNED,
    )
    db.add(milestone)
    await db.flush()

    return _milestone_to_response(milestone)


@router.get("", response_model=list[MilestoneResponse])
async def list_milestones(
    project_id: int,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    await _get_project(project_id, tenant, db)

    milestones = (await db.execute(
        select(Milestone)
        .where(Milestone.project_id == project_id)
        .options(selectinload(Milestone.tasks))
        .order_by(Milestone.position)
    )).scalars().unique().all()

    return [
        _milestone_to_response(m, task_count=len(m.tasks) if m.tasks else 0)
        for m in milestones
    ]


@router.get("/{milestone_id}", response_model=MilestoneResponse)
async def get_milestone(
    project_id: int,
    milestone_id: int,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    await _get_project(project_id, tenant, db)

    milestone = (await db.execute(
        select(Milestone)
        .where(Milestone.id == milestone_id, Milestone.project_id == project_id)
        .options(selectinload(Milestone.tasks))
    )).scalar_one_or_none()
    if not milestone:
        raise HTTPException(404, "Milestone not found")

    return _milestone_to_response(milestone, task_count=len(milestone.tasks) if milestone.tasks else 0)


@router.patch("/{milestone_id}", response_model=MilestoneResponse)
async def update_milestone(
    project_id: int,
    milestone_id: int,
    body: MilestoneUpdate,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    await _get_project(project_id, tenant, db)

    milestone = (await db.execute(
        select(Milestone)
        .where(Milestone.id == milestone_id, Milestone.project_id == project_id)
        .options(selectinload(Milestone.tasks))
    )).scalar_one_or_none()
    if not milestone:
        raise HTTPException(404, "Milestone not found")

    if body.name is not None:
        milestone.name = body.name
    if body.description is not None:
        milestone.description = body.description
    if body.goal is not None:
        milestone.goal = body.goal
    if body.status is not None:
        milestone.status = body.status
    if body.position is not None:
        milestone.position = body.position

    await db.flush()
    await db.refresh(milestone)
    return _milestone_to_response(milestone, task_count=len(milestone.tasks) if milestone.tasks else 0)


@router.delete("/{milestone_id}", status_code=204)
async def delete_milestone(
    project_id: int,
    milestone_id: int,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    await _get_project(project_id, tenant, db)

    milestone = (await db.execute(
        select(Milestone)
        .where(Milestone.id == milestone_id, Milestone.project_id == project_id)
    )).scalar_one_or_none()
    if not milestone:
        raise HTTPException(404, "Milestone not found")

    # Unlink tasks (don't delete them)
    tasks = (await db.execute(
        select(Task).where(Task.milestone_id == milestone_id)
    )).scalars().all()
    for task in tasks:
        task.milestone_id = None

    await db.delete(milestone)
    await db.flush()


@router.post("/reorder", response_model=list[MilestoneResponse])
async def reorder_milestones(
    project_id: int,
    body: MilestoneReorder,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    await _get_project(project_id, tenant, db)

    milestones = (await db.execute(
        select(Milestone)
        .where(Milestone.project_id == project_id)
        .options(selectinload(Milestone.tasks))
    )).scalars().unique().all()

    ms_by_id = {m.id: m for m in milestones}

    for i, mid in enumerate(body.milestone_ids):
        if mid not in ms_by_id:
            raise HTTPException(400, f"Milestone {mid} not found in this project")
        ms_by_id[mid].position = i

    await db.flush()

    # Reload to avoid lazy-load issues
    milestones = (await db.execute(
        select(Milestone)
        .where(Milestone.project_id == project_id)
        .options(selectinload(Milestone.tasks))
        .order_by(Milestone.position)
    )).scalars().unique().all()

    return [
        _milestone_to_response(m, task_count=len(m.tasks) if m.tasks else 0)
        for m in milestones
    ]
