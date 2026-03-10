"""Execution event model — streaming log of agent actions."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cawnex_core.enums import EventType
from cawnex_core.models.base import Base, TimestampMixin


class ExecutionEvent(Base, TimestampMixin):
    """A single event in an execution's timeline. Streamed to dashboard via SSE/WS."""

    __tablename__ = "execution_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    execution_id: Mapped[int] = mapped_column(
        ForeignKey("executions.id", ondelete="CASCADE"), nullable=False
    )

    # Event info
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Optional metadata (tool name, file path, etc.)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationship
    execution: Mapped["Execution"] = relationship(back_populates="events")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Event {self.event_type} exec={self.execution_id}>"
