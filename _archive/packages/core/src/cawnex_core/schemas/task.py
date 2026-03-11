"""Task schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from cawnex_core.enums import TaskStatus, TaskSource


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    source: TaskSource = TaskSource.MANUAL
    source_ref: Optional[str] = None
    source_url: Optional[str] = None
    workflow_slug: Optional[str] = None  # Resolved to workflow_id
    context: Optional[dict] = None
    labels: Optional[list[str]] = None


class TaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    source: TaskSource
    source_ref: Optional[str]
    source_url: Optional[str]
    status: TaskStatus
    refined_brief: Optional[str]
    acceptance_criteria: Optional[str]
    notes: Optional[str]
    complexity: Optional[str]
    context: Optional[dict]
    total_cost_usd: float
    total_tokens: int
    created_at: datetime

    model_config = {"from_attributes": True}


class TaskApproval(BaseModel):
    approved: bool
    feedback: Optional[str] = None


class TaskListResponse(BaseModel):
    items: list[TaskResponse]
    total: int
    page: int
    limit: int
