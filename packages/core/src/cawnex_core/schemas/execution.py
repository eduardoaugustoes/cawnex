"""Execution and event schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from cawnex_core.enums import AgentType, ExecutionStatus, EventType


class ExecutionResponse(BaseModel):
    id: int
    issue_id: int
    agent_type: AgentType
    model_used: Optional[str]
    status: ExecutionStatus
    branch_name: Optional[str]
    pr_url: Optional[str]
    pr_number: Optional[int]
    result_summary: Optional[str]
    error_message: Optional[str]
    tokens_input: int
    tokens_output: int
    cost_usd: float
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_seconds: Optional[float]
    attempt: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ExecutionListResponse(BaseModel):
    items: list[ExecutionResponse]
    total: int
    page: int
    limit: int


class EventResponse(BaseModel):
    id: int
    execution_id: int
    event_type: EventType
    content: str
    metadata_json: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}
