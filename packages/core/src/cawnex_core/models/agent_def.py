"""Agent definition model — configurable autonomous workers."""

from __future__ import annotations

from typing import Optional

from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, Integer, JSON, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cawnex_core.enums import AssetOrigin
from cawnex_core.models.base import Base, TimestampMixin


class AgentDefinition(Base, TimestampMixin):
    """A configured agent type. Users create these — not hardcoded.

    Examples:
        - "Code Developer" with git + filesystem + shell tools
        - "Book Author" with filesystem + web_search + writing tools
        - "QA Reviewer" with git + filesystem tools
        - "Research Analyst" with web_search + data tools
    """

    __tablename__ = "agent_definitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True
    )  # NULL = system-wide template

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # The brain
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(
        String(100), default="claude-sonnet-4-6", nullable=False
    )

    # Capabilities — which tool packs this agent can use
    # e.g. ["git", "filesystem", "shell", "github"]
    tool_packs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    # Limits
    max_tokens: Mapped[int] = mapped_column(Integer, default=16000, nullable=False)
    max_time_seconds: Mapped[int] = mapped_column(Integer, default=900, nullable=False)  # 15 min
    retry_policy: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )  # {max_retries: 2, backoff: "linear"}

    # Workspace type this agent needs
    workspace_type: Mapped[str] = mapped_column(
        String(50), default="temp_dir", nullable=False
    )

    # State
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_template: Mapped[bool] = mapped_column(Boolean, default=False)  # System-provided template

    # Asset origin (for future marketplace)
    origin: Mapped[str] = mapped_column(
        String(50), default=AssetOrigin.SYSTEM, nullable=False
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<AgentDefinition '{self.name}' tools={self.tool_packs}>"
