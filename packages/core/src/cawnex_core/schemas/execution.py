"""Execution and event schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from cawnex_core.enums import ExecutionStatus, EventType


class ExecutionResponse(BaseModel):
    id: int
    task_id: int
    agent_id: Optional[int]
    agent_name: str
    model_used: Optional[str]
    status: ExecutionStatus
    workspace_type: Optional[str]
    workspace_path: Optional[str]
    result_summary: Optional[str]
    error_message: Optional[str]
    input_context: Optional[dict]
    output_context: Optional[dict]
    tokens_input: int
    tokens_output: int
    cost_usd: float
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_seconds: Optional[float]
    attempt: int
    parent_execution_id: Optional[int]
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
    event_type: str
    content: str
    metadata_json: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}
