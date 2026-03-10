"""Tenant (organization) and LLM configuration models."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, String, Float, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cawnex_core.enums import Provider, BYOLMode
from cawnex_core.models.base import Base, TimestampMixin


class Tenant(Base, TimestampMixin):
    """An organization using Cawnex. All data is scoped to a tenant."""

    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    # GitHub App installation
    github_installation_id: Mapped[Optional[int]] = mapped_column(nullable=True)

    # State
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    llm_config: Mapped[Optional[LLMConfig]] = relationship(
        back_populates="tenant", uselist=False, cascade="all, delete-orphan"
    )
    repositories: Mapped[list["Repository"]] = relationship(  # noqa: F821
        back_populates="tenant", cascade="all, delete-orphan"
    )
    issues: Mapped[list["Issue"]] = relationship(  # noqa: F821
        back_populates="tenant", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Tenant {self.slug}>"


class LLMConfig(Base, TimestampMixin):
    """BYOL configuration for a tenant. Encrypted API key storage."""

    __tablename__ = "llm_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    # Provider
    provider: Mapped[str] = mapped_column(
        String(50), default=Provider.ANTHROPIC, nullable=False
    )
    mode: Mapped[str] = mapped_column(
        String(50), default=BYOLMode.API_KEY, nullable=False
    )

    # Encrypted API key (Fernet)
    encrypted_api_key: Mapped[bytes] = mapped_column(nullable=False)

    # Model configuration per agent type (JSON)
    # e.g. {"refinement": "claude-opus-4-6", "dev": "claude-opus-4-6", "qa": "claude-sonnet-4-6"}
    model_config_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Budget
    budget_limit_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    budget_used_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    budget_reset_day: Mapped[int] = mapped_column(default=1, nullable=False)  # Day of month

    # Relationship
    tenant: Mapped[Tenant] = relationship(back_populates="llm_config")

    def __repr__(self) -> str:
        return f"<LLMConfig tenant={self.tenant_id} provider={self.provider}>"
