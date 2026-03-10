"""Repository model."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cawnex_core.models.base import Base, TimestampMixin


class Repository(Base, TimestampMixin):
    """A git repository connected to Cawnex."""

    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )

    # Git info
    github_full_name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )  # e.g. "eduardoaugustoes/cawnex"
    default_branch: Mapped[str] = mapped_column(String(100), default="main")
    clone_url: Mapped[str] = mapped_column(String(500), nullable=False)

    # Auto-detected metadata
    language: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    framework: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # CAWNEX.md content (cached from repo)
    cawnex_md: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # State
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="repositories")  # noqa: F821
    issues: Mapped[list["Issue"]] = relationship(  # noqa: F821
        back_populates="repository", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Repository {self.github_full_name}>"
