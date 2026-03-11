"""Workflow and WorkflowStep models — configurable agent pipelines."""

from __future__ import annotations

from typing import Optional

from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, Integer, Boolean, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cawnex_core.enums import AssetOrigin
from cawnex_core.models.base import Base, TimestampMixin


class Workflow(Base, TimestampMixin):
    """A configurable pipeline of agents. Defines order, approvals, and error handling.

    Examples:
        - "Code Shipping": Refine → Implement → Review → Document
        - "Book Writing": Outline → Research → Write → Edit → Format
        - "Deep Research": Scope → Gather → Analyze → Synthesize → Review
    """

    __tablename__ = "workflows"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True
    )  # NULL = system-wide template

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Trigger configuration
    # e.g. {"source": "github", "event": "issue_labeled", "filters": {"label": "cawnex"}}
    trigger_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # State
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_template: Mapped[bool] = mapped_column(Boolean, default=False)

    # Asset origin (for future marketplace)
    origin: Mapped[str] = mapped_column(
        String(50), default=AssetOrigin.SYSTEM, nullable=False
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    steps: Mapped[list["WorkflowStep"]] = relationship(
        back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="WorkflowStep.order",
    )

    def __repr__(self) -> str:
        return f"<Workflow '{self.name}' steps={len(self.steps) if self.steps else '?'}>"


class WorkflowStep(Base, TimestampMixin):
    """A single step in a workflow pipeline."""

    __tablename__ = "workflow_steps"

    id: Mapped[int] = mapped_column(primary_key=True)
    workflow_id: Mapped[int] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[int] = mapped_column(
        ForeignKey("agent_definitions.id", ondelete="CASCADE"), nullable=False
    )

    # Pipeline position
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Input/output
    input_from: Mapped[str] = mapped_column(
        String(100), default="previous_step", nullable=False
    )  # "task", "previous_step", "step:<name>"

    # Human checkpoint
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)

    # Error handling
    on_reject: Mapped[str] = mapped_column(
        String(100), default="fail", nullable=False
    )  # "retry", "fail", "goto:<step_name>"
    on_fail: Mapped[str] = mapped_column(
        String(100), default="fail", nullable=False
    )  # "retry", "fail", "skip"

    # Optional condition (only run if met)
    condition: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    workflow: Mapped[Workflow] = relationship(back_populates="steps")
    agent: Mapped["AgentDefinition"] = relationship()  # noqa: F821

    def __repr__(self) -> str:
        return f"<WorkflowStep {self.order}: '{self.name}'>"
