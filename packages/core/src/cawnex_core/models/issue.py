"""Issue model."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, String, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cawnex_core.enums import IssueStatus, IssueSource
from cawnex_core.models.base import Base, TimestampMixin


class Issue(Base, TimestampMixin):
    """A tracked issue that Cawnex will work on."""

    __tablename__ = "issues"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )

    # External reference
    external_id: Mapped[str] = mapped_column(String(100), nullable=False)  # GitHub issue number
    source: Mapped[str] = mapped_column(
        String(50), default=IssueSource.GITHUB, nullable=False
    )
    url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Content
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    labels: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array

    # Refined content (filled by Refinement Crow)
    refined_story: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    acceptance_criteria: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    technical_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    complexity: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # S/M/L/XL

    # Status
    status: Mapped[str] = mapped_column(
        String(50), default=IssueStatus.PENDING, nullable=False
    )

    # Cost tracking (aggregated from executions)
    total_cost_usd: Mapped[float] = mapped_column(default=0.0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="issues")  # noqa: F821
    repository: Mapped["Repository"] = relationship(back_populates="issues")  # noqa: F821
    executions: Mapped[list["Execution"]] = relationship(  # noqa: F821
        back_populates="issue", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Issue #{self.external_id} {self.title[:40]}>"
