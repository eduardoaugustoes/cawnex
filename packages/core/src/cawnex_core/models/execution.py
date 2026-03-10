"""Execution model — a single agent run."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, String, Text, Integer, Float, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cawnex_core.enums import AgentType, ExecutionStatus
from cawnex_core.models.base import Base, TimestampMixin


class Execution(Base, TimestampMixin):
    """A single agent execution. One issue may spawn multiple executions."""

    __tablename__ = "executions"

    id: Mapped[int] = mapped_column(primary_key=True)
    issue_id: Mapped[int] = mapped_column(
        ForeignKey("issues.id", ondelete="CASCADE"), nullable=False
    )

    # Agent info
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False)
    model_used: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Status
    status: Mapped[str] = mapped_column(
        String(50), default=ExecutionStatus.QUEUED, nullable=False
    )

    # Git context
    worktree_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    branch_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    pr_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    pr_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Result
    result_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

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
    issue: Mapped["Issue"] = relationship(back_populates="executions")  # noqa: F821
    events: Mapped[list["ExecutionEvent"]] = relationship(  # noqa: F821
        back_populates="execution", cascade="all, delete-orphan",
        order_by="ExecutionEvent.created_at",
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
        return f"<Execution {self.id} {self.agent_type} {self.status}>"
