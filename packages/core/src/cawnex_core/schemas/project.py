"""Project, Vision, and Milestone schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from cawnex_core.enums import ProjectStatus, MilestoneStatus


# === Project ===

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: Optional[str] = None  # auto-generated from name if omitted


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[ProjectStatus] = None


class ProjectRepoLink(BaseModel):
    repository_id: int
    role: Optional[str] = None  # "primary", "frontend", "backend", etc.


class ProjectRepoCreate(BaseModel):
    """Link an existing repo or create a new one."""
    github_full_name: str  # "owner/repo"
    role: Optional[str] = None
    create_if_missing: bool = False  # If true, create the GH repo first


class ProjectRepositoryResponse(BaseModel):
    id: int
    repository_id: int
    github_full_name: str
    role: Optional[str]
    added_at: datetime

    model_config = {"from_attributes": True}


class ProjectResponse(BaseModel):
    id: int
    name: str
    slug: str
    status: ProjectStatus
    config: Optional[dict]
    repositories: list[ProjectRepositoryResponse] = []
    has_vision: bool = False
    milestone_count: int = 0
    task_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    items: list[ProjectResponse]
    total: int
    page: int
    limit: int


# === Vision ===

class VisionUpdate(BaseModel):
    content: str


class VisionChatMessage(BaseModel):
    message: str


class VisionMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    applied: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class VisionResponse(BaseModel):
    id: int
    project_id: int
    content: str
    version: int
    updated_at: datetime
    messages: list[VisionMessageResponse] = []

    model_config = {"from_attributes": True}


class VisionApply(BaseModel):
    """Apply an AI suggestion to the vision document."""
    message_id: int


# === Milestone ===

class MilestoneCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    goal: Optional[str] = None


class MilestoneUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    goal: Optional[str] = None
    status: Optional[MilestoneStatus] = None
    position: Optional[int] = None


class MilestoneResponse(BaseModel):
    id: int
    project_id: int
    name: str
    description: Optional[str]
    goal: Optional[str]
    position: int
    status: MilestoneStatus
    github_milestone_id: Optional[int]
    task_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MilestoneReorder(BaseModel):
    """Reorder milestones by providing ordered list of IDs."""
    milestone_ids: list[int]
