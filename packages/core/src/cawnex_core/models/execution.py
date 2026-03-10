"""Execution model — a single agent run within a workflow."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, String, Text, Integer, Float, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cawnex_core.enums import ExecutionStatus
from cawnex_core.models.base import Base, TimestampMixin


class Execution(Base, TimestampMixin):
    """A single agent execution. One task may spawn multiple executions (one per workflow step)."""

    __tablename__ = "executions"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[int] = mapped_column(
        ForeignKey("agent_definitions.id", ondelete="SET NULL"), nullable=True
    )
    workflow_step_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("workflow_steps.id", ondelete="SET NULL"), nullable=True
    )

    # What agent ran (denormalized for fast queries)
    agent_name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_used: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Status
    status: Mapped[str] = mapped_column(
        String(50), default=ExecutionStatus.QUEUED, nullable=False
    )

    # Workspace (generic — could be worktree, temp dir, cloud storage)
    workspace_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    workspace_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Result
    result_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Input/output context (passed between workflow steps)
    input_context: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    output_context: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Cost tracking
    tokens_input: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_output: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Timing
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Retry tracking
    attempt: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    parent_execution_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("executions.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    task: Mapped["Task"] = relationship(back_populates="executions")  # noqa: F821
    agent: Mapped[Optional["AgentDefinition"]] = relationship()  # noqa: F821
    events: Mapped[list["ExecutionEvent"]] = relationship(  # noqa: F821
        back_populates="execution", cascade="all, delete-orphan",
        order_by="ExecutionEvent.created_at",
    )
    artifacts: Mapped[list["Artifact"]] = relationship(  # noqa: F821
        back_populates="execution", cascade="all, delete-orphan"
    )
    parent: Mapped[Optional["Execution"]] = relationship(
        remote_side="Execution.id", uselist=False
    )

    @property
    def is_terminal(self) -> bool:
        return self.status in (
            ExecutionStatus.COMPLETED,
            ExecutionStatus.FAILED,
            ExecutionStatus.CANCELLED,
        )

    def __repr__(self) -> str:
        return f"<Execution {self.id} agent='{self.agent_name}' status={self.status}>"
