"""Task model — any unit of work that enters the system."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, String, Text, Integer, Float, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cawnex_core.enums import TaskStatus, TaskSource
from cawnex_core.models.base import Base, TimestampMixin


class Task(Base, TimestampMixin):
    """A unit of work. Could be a GitHub issue, a book chapter brief, a research question, etc."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    milestone_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("milestones.id", ondelete="SET NULL"), nullable=True
    )
    workflow_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("workflows.id", ondelete="SET NULL"), nullable=True
    )

    # External reference
    source: Mapped[str] = mapped_column(
        String(50), default=TaskSource.MANUAL, nullable=False
    )
    source_ref: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Content
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    labels: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array

    # Refined content (filled by refinement agent)
    refined_brief: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    acceptance_criteria: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    complexity: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    # Context — arbitrary metadata for the workflow
    # e.g. {"repo": "owner/repo", "branch": "main"} for code
    # e.g. {"genre": "sci-fi", "target_audience": "young adults"} for books
    context: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Status
    status: Mapped[str] = mapped_column(
        String(50), default=TaskStatus.PENDING, nullable=False
    )

    # Cost tracking (aggregated from executions)
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="tasks")  # noqa: F821
    project: Mapped[Optional["Project"]] = relationship(back_populates="tasks")  # noqa: F821
    milestone: Mapped[Optional["Milestone"]] = relationship(back_populates="tasks")  # noqa: F821
    workflow: Mapped[Optional["Workflow"]] = relationship()  # noqa: F821
    executions: Mapped[list["Execution"]] = relationship(  # noqa: F821
        back_populates="task", cascade="all, delete-orphan"
    )
    artifacts: Mapped[list["Artifact"]] = relationship(  # noqa: F821
        back_populates="task", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Task {self.id} '{self.title[:40]}'>"
