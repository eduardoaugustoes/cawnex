"""Tenant + LLM config management."""

from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cawnex_core.models import Tenant, LLMConfig
from sqlalchemy.orm import selectinload

from cawnex_core.schemas.tenant import TenantCreate, TenantResponse, LLMConfigCreate, LLMConfigResponse
from cawnex_api.config import settings
from cawnex_api.deps import get_db
from cawnex_providers import ProviderRegistry

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.post("", response_model=TenantResponse, status_code=201)
async def create_tenant(body: TenantCreate, db: AsyncSession = Depends(get_db)):
    # Check unique slug
    existing = await db.execute(select(Tenant).where(Tenant.slug == body.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(400, f"Slug '{body.slug}' already taken")

    tenant = Tenant(name=body.name, slug=body.slug)
    db.add(tenant)
    await db.flush()
    return tenant


@router.get("/{slug}", response_model=TenantResponse)
async def get_tenant(slug: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Tenant).where(Tenant.slug == slug).options(selectinload(Tenant.llm_config))
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(404, "Tenant not found")

    # Build response manually to handle has_api_key
    llm = None
    if tenant.llm_config:
        llm = LLMConfigResponse.from_orm_model(tenant.llm_config)
    return TenantResponse(
        id=tenant.id, name=tenant.name, slug=tenant.slug,
        is_active=tenant.is_active, llm_config=llm,
    )


@router.post("/{slug}/llm", response_model=LLMConfigResponse, status_code=201)
async def configure_llm(slug: str, body: LLMConfigCreate, db: AsyncSession = Depends(get_db)):
    """Set up BYOL — validate and encrypt the API key."""
    result = await db.execute(select(Tenant).where(Tenant.slug == slug))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(404, "Tenant not found")

    # Validate the key
    provider = ProviderRegistry.get(body.provider, body.api_key)
    valid = await provider.validate_key()
    if not valid:
        raise HTTPException(400, f"Invalid {body.provider} API key")

    # Encrypt
    fernet_key = settings.fernet_key.encode() if settings.fernet_key else Fernet.generate_key()
    fernet = Fernet(fernet_key)
    encrypted = fernet.encrypt(body.api_key.encode())

    # Upsert
    existing = await db.execute(select(LLMConfig).where(LLMConfig.tenant_id == tenant.id))
    llm_config = existing.scalar_one_or_none()

    if llm_config:
        llm_config.provider = body.provider
        llm_config.mode = body.mode
        llm_config.encrypted_api_key = encrypted
        llm_config.budget_limit_usd = body.budget_limit_usd
    else:
        llm_config = LLMConfig(
            tenant_id=tenant.id,
            provider=body.provider,
            mode=body.mode,
            encrypted_api_key=encrypted,
            budget_limit_usd=body.budget_limit_usd,
        )
        db.add(llm_config)

    await db.flush()
    return LLMConfigResponse(
        provider=llm_config.provider,
        mode=llm_config.mode,
        budget_limit_usd=llm_config.budget_limit_usd,
        budget_used_usd=llm_config.budget_used_usd,
        has_api_key=True,
    )
