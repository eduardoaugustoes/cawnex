"""Project, Vision, VisionMessage, Milestone, and ProjectRepository models."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, String, Text, Integer, Boolean, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cawnex_core.enums import ProjectStatus, MilestoneStatus
from cawnex_core.models.base import Base, TimestampMixin


class Project(Base, TimestampMixin):
    """A user project — the top-level container for repos, vision, milestones, and tasks."""

    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_project_tenant_slug"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default=ProjectStatus.DRAFT, nullable=False
    )

    # Future override layer — null means inherit tenant defaults
    config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="projects")  # noqa: F821
    vision: Mapped[Optional["Vision"]] = relationship(
        back_populates="project", uselist=False, cascade="all, delete-orphan"
    )
    vision_messages: Mapped[list["VisionMessage"]] = relationship(
        back_populates="project", cascade="all, delete-orphan",
        order_by="VisionMessage.created_at",
    )
    milestones: Mapped[list["Milestone"]] = relationship(
        back_populates="project", cascade="all, delete-orphan",
        order_by="Milestone.position",
    )
    project_repositories: Mapped[list["ProjectRepository"]] = relationship(
        back_populates="project", cascade="all, delete-orphan",
    )
    tasks: Mapped[list["Task"]] = relationship(  # noqa: F821
        back_populates="project",
    )

    def __repr__(self) -> str:
        return f"<Project '{self.name}' ({self.status})>"


class ProjectRepository(Base, TimestampMixin):
    """Many-to-many link between a project and its repositories."""

    __tablename__ = "project_repositories"
    __table_args__ = (
        UniqueConstraint("project_id", "repository_id", name="uq_project_repo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )  # "primary", "frontend", "backend", "infra", etc.

    # Relationships
    project: Mapped[Project] = relationship(back_populates="project_repositories")
    repository: Mapped["Repository"] = relationship()  # noqa: F821

    def __repr__(self) -> str:
        return f"<ProjectRepository project={self.project_id} repo={self.repository_id} role={self.role}>"


class Vision(Base, TimestampMixin):
    """Living vision document for a project, built through AI conversation."""

    __tablename__ = "visions"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Relationships
    project: Mapped[Project] = relationship(back_populates="vision")

    def __repr__(self) -> str:
        return f"<Vision project={self.project_id} v{self.version}>"


class VisionMessage(Base, TimestampMixin):
    """Chat history for the vision board conversation."""

    __tablename__ = "vision_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )

    role: Mapped[str] = mapped_column(String(20), nullable=False)  # "user", "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    applied: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    project: Mapped[Project] = relationship(back_populates="vision_messages")

    def __repr__(self) -> str:
        return f"<VisionMessage {self.role} applied={self.applied}>"


class Milestone(Base, TimestampMixin):
    """A named phase within a project, grouping tasks toward a goal."""

    __tablename__ = "milestones"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    goal: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default=MilestoneStatus.PLANNED, nullable=False
    )

    # GitHub sync
    github_milestone_id: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Relationships
    project: Mapped[Project] = relationship(back_populates="milestones")
    tasks: Mapped[list["Task"]] = relationship(  # noqa: F821
        back_populates="milestone",
    )

    def __repr__(self) -> str:
        return f"<Milestone '{self.name}' ({self.status})>"
