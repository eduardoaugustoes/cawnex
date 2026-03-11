"""Artifact model — outputs produced by agents."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cawnex_core.enums import ArtifactType
from cawnex_core.models.base import Base, TimestampMixin


class Artifact(Base, TimestampMixin):
    """Any output produced by a workflow execution.

    Examples:
        - Pull Request (pr_number, repo, branch, url)
        - Document (markdown file, word count)
        - Report (PDF, charts, data)
        - Dataset (CSV, rows, columns)
        - Email Draft (to, subject, body)
    """

    __tablename__ = "artifacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    execution_id: Mapped[int] = mapped_column(
        ForeignKey("executions.id", ondelete="CASCADE"), nullable=False
    )

    # Type
    artifact_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Content
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Inline content or summary
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # Path to file
    url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # External URL

    # Type-specific metadata
    # PR: {pr_number, repo, branch, diff_stats}
    # Document: {format, word_count, sections}
    # Dataset: {format, rows, columns}
    extra: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    # Relationships
    task: Mapped["Task"] = relationship(back_populates="artifacts")  # noqa: F821
    execution: Mapped["Execution"] = relationship(back_populates="artifacts")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Artifact {self.artifact_type}: '{self.title[:40]}'>"
