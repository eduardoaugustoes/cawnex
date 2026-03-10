"""Workflow schemas."""

from typing import Optional

from pydantic import BaseModel


class WorkflowStepCreate(BaseModel):
    order: int
    name: str
    agent_slug: str  # Resolved to agent_id
    input_from: str = "previous_step"
    requires_approval: bool = False
    on_reject: str = "fail"
    on_fail: str = "fail"
    condition: Optional[str] = None


class WorkflowCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    trigger_config: Optional[dict] = None
    steps: list[WorkflowStepCreate]


class WorkflowStepResponse(BaseModel):
    id: int
    order: int
    name: str
    agent_id: int
    input_from: str
    requires_approval: bool
    on_reject: str
    on_fail: str

    model_config = {"from_attributes": True}


class WorkflowResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str]
    trigger_config: Optional[dict]
    is_active: bool
    is_template: bool
    steps: list[WorkflowStepResponse] = []

    model_config = {"from_attributes": True}
