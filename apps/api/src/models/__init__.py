from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ProjectState(str, Enum):
    """Enumeration of possible project states."""
    PLANNING = "planning"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ON_HOLD = "on_hold"


class ProjectReadResponse(BaseModel):
    """Response model for reading a project."""
    id: str = Field(..., description="Project ID")
    name: str = Field(..., description="Project name")
    description: Optional[str] = Field(None, description="Project description")
    state: Optional[ProjectState] = Field(
        None,
        description="Current state of the project (planning, in_progress, completed, on_hold)"
    )

    class Config:
        from_attributes = True
