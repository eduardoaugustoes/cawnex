"""Workflow CRUD."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from cawnex_core.models import Tenant, Workflow, WorkflowStep, AgentDefinition
from cawnex_core.schemas.workflow import WorkflowCreate, WorkflowResponse
from cawnex_api.deps import get_db, get_tenant

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.post("", response_model=WorkflowResponse, status_code=201)
async def create_workflow(
    body: WorkflowCreate,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    workflow = Workflow(
        tenant_id=tenant.id,
        name=body.name,
        slug=body.slug,
        description=body.description,
        trigger_config=body.trigger_config,
    )
    db.add(workflow)
    await db.flush()

    # Resolve agent slugs → ids and create steps
    for step_data in body.steps:
        agent = (await db.execute(
            select(AgentDefinition).where(
                AgentDefinition.slug == step_data.agent_slug,
                AgentDefinition.tenant_id == tenant.id,
            )
        )).scalar_one_or_none()
        if not agent:
            raise HTTPException(400, f"Agent '{step_data.agent_slug}' not found")

        step = WorkflowStep(
            workflow_id=workflow.id,
            agent_id=agent.id,
            order=step_data.order,
            name=step_data.name,
            input_from=step_data.input_from,
            requires_approval=step_data.requires_approval,
            on_reject=step_data.on_reject,
            on_fail=step_data.on_fail,
            condition=step_data.condition,
        )
        db.add(step)

    await db.flush()

    # Reload with steps
    result = await db.execute(
        select(Workflow)
        .where(Workflow.id == workflow.id)
        .options(selectinload(Workflow.steps))
    )
    return result.scalar_one()


@router.get("", response_model=list[WorkflowResponse])
async def list_workflows(
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Workflow)
        .where(Workflow.tenant_id == tenant.id, Workflow.is_active.is_(True))
        .options(selectinload(Workflow.steps))
    )
    return result.scalars().all()
