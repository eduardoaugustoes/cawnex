"""Agent definition CRUD."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cawnex_core.models import Tenant, AgentDefinition
from cawnex_core.schemas.agent import AgentCreate, AgentResponse, AgentListResponse
from cawnex_api.deps import get_db, get_tenant

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("", response_model=AgentResponse, status_code=201)
async def create_agent(
    body: AgentCreate,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    agent = AgentDefinition(
        tenant_id=tenant.id,
        name=body.name,
        slug=body.slug,
        description=body.description,
        system_prompt=body.system_prompt,
        model=body.model,
        tool_packs=body.tool_packs,
        max_tokens=body.max_tokens,
        max_time_seconds=body.max_time_seconds,
        workspace_type=body.workspace_type,
    )
    db.add(agent)
    await db.flush()
    return agent


@router.get("", response_model=AgentListResponse)
async def list_agents(
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AgentDefinition).where(
            AgentDefinition.tenant_id == tenant.id,
            AgentDefinition.is_active.is_(True),
        )
    )
    agents = result.scalars().all()
    return AgentListResponse(items=agents, total=len(agents))


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: int,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AgentDefinition).where(
            AgentDefinition.id == agent_id,
            AgentDefinition.tenant_id == tenant.id,
        )
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")
    return agent
