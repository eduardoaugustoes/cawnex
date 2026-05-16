"""Data models package.

Defines Pydantic models for API request/response types.
"""

from typing import List

from pydantic import BaseModel, Field


class ProjectState(BaseModel):
    """Computed state of a project derived from underlying entities."""

    state: str = Field(
        ...,
        description=(
            'Current state of the project: "draft", "active", "running", '
            '"idle", or "completed"'
        ),
    )


class ProjectReadResponse(BaseModel):
    """Response for reading a single project with computed state."""

    project_id: str
    name: str
    one_liner: str
    status: str = Field(
        description="Stored status field (always 'draft' for backward compatibility)"
    )
    current_state: str = Field(
        description="Computed current state derived from project execution reality"
    )
    murders: List[str]
    created_at: str
