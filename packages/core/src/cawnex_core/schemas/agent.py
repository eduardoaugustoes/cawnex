"""Agent definition schemas."""

from typing import Optional

from pydantic import BaseModel


class AgentCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    system_prompt: str
    model: str = "claude-sonnet-4-6"
    tool_packs: list[str] = []
    max_tokens: int = 16000
    max_time_seconds: int = 900
    retry_policy: Optional[dict] = None
    workspace_type: str = "temp_dir"


class AgentResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str]
    model: str
    tool_packs: list[str]
    max_tokens: int
    max_time_seconds: int
    workspace_type: str
    is_active: bool
    is_template: bool

    model_config = {"from_attributes": True}


class AgentListResponse(BaseModel):
    items: list[AgentResponse]
    total: int
