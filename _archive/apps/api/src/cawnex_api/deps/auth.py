"""Auth dependency — tenant resolution.

MVP: API key header → tenant lookup.
Future: JWT / OAuth / GitHub App installation.
"""

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from cawnex_core.models import Tenant
from cawnex_api.deps.db import get_db


async def get_tenant(
    x_tenant_slug: str = Header(..., description="Tenant slug"),
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    """Resolve tenant from header. Every request is tenant-scoped."""
    result = await db.execute(
        select(Tenant)
        .where(Tenant.slug == x_tenant_slug, Tenant.is_active.is_(True))
        .options(selectinload(Tenant.llm_config))
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant '{x_tenant_slug}' not found")
    return tenant
