"""Issue schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from cawnex_core.enums import IssueStatus, IssueSource


class IssueResponse(BaseModel):
    id: int
    repository_id: int
    external_id: str
    source: IssueSource
    url: Optional[str]
    title: str
    description: Optional[str]
    status: IssueStatus
    refined_story: Optional[str]
    acceptance_criteria: Optional[str]
    technical_notes: Optional[str]
    complexity: Optional[str]
    total_cost_usd: float
    total_tokens: int
    created_at: datetime

    model_config = {"from_attributes": True}


class IssueApproval(BaseModel):
    approved: bool
    feedback: Optional[str] = None


class IssueListResponse(BaseModel):
    items: list[IssueResponse]
    total: int
    page: int
    limit: int
