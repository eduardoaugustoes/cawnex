"""LLM provider dependency — resolves tenant's BYOL config to a provider instance.

Supports both API key mode and subscription mode (Claude Max via CLI).
"""

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
    """Resolve the tenant's BYOL LLM provider — works for both API key and subscription."""
    if not tenant.llm_config:
        raise HTTPException(
            400,
            "No LLM configuration found. Run: cawnex init",
        )

    mode = tenant.llm_config.mode  # "api_key" or "subscription_relay"

    try:
        return ProviderRegistry.get_for_tenant(
            mode=mode,
            provider=tenant.llm_config.provider,
            encrypted_key=tenant.llm_config.encrypted_api_key if mode == "api_key" else None,
            fernet_key=settings.fernet_key.encode() if settings.fernet_key else None,
        )
    except Exception as e:
        raise HTTPException(500, f"Failed to initialize LLM provider: {e}")
