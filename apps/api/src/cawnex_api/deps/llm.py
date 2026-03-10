"""LLM provider dependency — resolves tenant's BYOL config to a provider instance."""

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from cawnex_core.models import Tenant
from cawnex_providers.base import LLMProvider
from cawnex_providers.registry import ProviderRegistry
from cawnex_api.config import settings
from cawnex_api.deps.auth import get_tenant
from cawnex_api.deps.db import get_db


async def get_llm(
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
) -> LLMProvider:
    """Resolve the tenant's BYOL LLM provider."""
    if not tenant.llm_config:
        raise HTTPException(
            400,
            "No LLM configuration found. Please set up your API key first.",
        )

    if not settings.fernet_key:
        raise HTTPException(500, "Server encryption key not configured")

    try:
        return ProviderRegistry.get_from_encrypted(
            provider=tenant.llm_config.provider,
            encrypted_key=tenant.llm_config.encrypted_api_key,
            fernet_key=settings.fernet_key.encode(),
        )
    except Exception as e:
        raise HTTPException(500, f"Failed to initialize LLM provider: {e}")
