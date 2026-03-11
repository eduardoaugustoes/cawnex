"""Tenant and LLM config schemas."""

from pydantic import BaseModel, Field
from typing import Optional

from cawnex_core.enums import Provider, BYOLMode


class LLMConfigCreate(BaseModel):
    provider: Provider = Provider.ANTHROPIC
    mode: BYOLMode = BYOLMode.API_KEY
    api_key: str = Field(..., min_length=1, description="Plain text API key — will be encrypted")
    budget_limit_usd: Optional[float] = None
    model_config_json: Optional[str] = None


class LLMConfigResponse(BaseModel):
    provider: Provider
    mode: BYOLMode
    budget_limit_usd: Optional[float]
    budget_used_usd: float
    has_api_key: bool = True  # Never expose the actual key

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_model(cls, obj):
        return cls(
            provider=obj.provider,
            mode=obj.mode,
            budget_limit_usd=obj.budget_limit_usd,
            budget_used_usd=obj.budget_used_usd,
            has_api_key=obj.encrypted_api_key is not None,
        )


class TenantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=255, pattern=r"^[a-z0-9-]+$")


class TenantResponse(BaseModel):
    id: int
    name: str
    slug: str
    is_active: bool
    llm_config: Optional[LLMConfigResponse] = None

    model_config = {"from_attributes": True}
