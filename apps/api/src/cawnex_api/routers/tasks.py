"""Task CRUD + execution tracking."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from cawnex_core.models import Tenant, Task, Execution, ExecutionEvent
from cawnex_core.schemas.task import TaskCreate, TaskResponse, TaskListResponse, TaskApproval
from cawnex_core.schemas.execution import ExecutionResponse, ExecutionListResponse, EventResponse
from cawnex_core.enums import TaskStatus
from cawnex_api.deps import get_db, get_tenant

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(
    body: TaskCreate,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    task = Task(
        tenant_id=tenant.id,
        title=body.title,
        description=body.description,
        source=body.source,
        source_ref=body.source_ref,
        source_url=body.source_url,
        context=body.context,
        labels=",".join(body.labels) if body.labels else None,
    )
    db.add(task)
    await db.flush()
    return task


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
    status: TaskStatus | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    query = select(Task).where(Task.tenant_id == tenant.id)
    if status:
        query = query.where(Task.status == status)

    # Count
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Paginate
    tasks = (await db.execute(
        query.order_by(Task.created_at.desc()).offset((page - 1) * limit).limit(limit)
    )).scalars().all()

    return TaskListResponse(items=tasks, total=total, page=page, limit=limit)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.tenant_id == tenant.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(404, "Task not found")
    return task


@router.post("/{task_id}/approve", response_model=TaskResponse)
async def approve_task(
    task_id: int,
    body: TaskApproval,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.tenant_id == tenant.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(404, "Task not found")
    if task.status != TaskStatus.AWAITING_APPROVAL:
        raise HTTPException(400, f"Task is '{task.status}', not awaiting approval")

    if body.approved:
        task.status = TaskStatus.APPROVED
        task.notes = body.feedback
    else:
        task.status = TaskStatus.REJECTED
        task.notes = body.feedback

    await db.flush()
    return task


# === Executions ===

@router.get("/{task_id}/executions", response_model=ExecutionListResponse)
async def list_executions(
    task_id: int,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    # Verify task belongs to tenant
    task = (await db.execute(
        select(Task).where(Task.id == task_id, Task.tenant_id == tenant.id)
    )).scalar_one_or_none()
    if not task:
        raise HTTPException(404, "Task not found")

    query = select(Execution).where(Execution.task_id == task_id)
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    executions = (await db.execute(
        query.order_by(Execution.created_at.desc()).offset((page - 1) * limit).limit(limit)
    )).scalars().all()

    return ExecutionListResponse(items=executions, total=total, page=page, limit=limit)


@router.get("/{task_id}/executions/{execution_id}/events", response_model=list[EventResponse])
async def list_events(
    task_id: int,
    execution_id: int,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    # Verify ownership chain
    task = (await db.execute(
        select(Task).where(Task.id == task_id, Task.tenant_id == tenant.id)
    )).scalar_one_or_none()
    if not task:
        raise HTTPException(404, "Task not found")

    events = (await db.execute(
        select(ExecutionEvent)
        .where(ExecutionEvent.execution_id == execution_id)
        .order_by(ExecutionEvent.created_at)
    )).scalars().all()

    return events
