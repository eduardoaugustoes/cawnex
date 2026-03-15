"""Snapshot dataclasses for the Worker bounded context."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from worker.enums import CrowStatus, CrowType
from worker.keys import build_pk, build_sk


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Cost:
    tokens_in: int
    tokens_out: int
    credits: float
    duration_ms: int

    @classmethod
    def zero(cls) -> Cost:
        return cls(tokens_in=0, tokens_out=0, credits=0.0, duration_ms=0)

    def __add__(self, other: Cost) -> Cost:
        return Cost(
            tokens_in=self.tokens_in + other.tokens_in,
            tokens_out=self.tokens_out + other.tokens_out,
            credits=self.credits + other.credits,
            duration_ms=self.duration_ms + other.duration_ms,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "credits": self.credits,
            "duration_ms": self.duration_ms,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Cost:
        return cls(
            tokens_in=int(d["tokens_in"]),
            tokens_out=int(d["tokens_out"]),
            credits=float(d["credits"]),
            duration_ms=int(d["duration_ms"]),
        )


@dataclass
class CrowSnapshot:
    tenant: str
    project: str
    wave_id: str
    mvi_id: str
    crow_id: str
    crow_type: CrowType
    status: CrowStatus
    instructions: str
    repo: str
    branch: str
    budget_remaining: float
    behavior_state: str = "assigned"
    retry_count: int = 0
    outcome: dict[str, Any] | None = None
    cost: Cost = field(default_factory=Cost.zero)
    git_commit: str = ""
    pr: dict[str, Any] | None = None
    completed_at: str = ""
    created_at: str = field(default_factory=_now_iso)

    @property
    def pk(self) -> str:
        return build_pk(self.tenant, self.project)

    @property
    def sk(self) -> str:
        return build_sk(wave_id=self.wave_id, mvi_id=self.mvi_id, crow_id=self.crow_id)

    def to_item(self) -> dict[str, Any]:
        item: dict[str, Any] = {
            "PK": self.pk,
            "SK": self.sk,
            "level": "crow",
            "status": self.status.value,
            "crow_type": self.crow_type.value,
            "behavior_state": self.behavior_state,
            "instructions": self.instructions,
            "repo": self.repo,
            "branch": self.branch,
            "budget_remaining": self.budget_remaining,
            "retry_count": self.retry_count,
            "cost": self.cost.to_dict(),
            "created_at": self.created_at,
            "entityType": "Snapshot",
        }
        if self.outcome is not None:
            item["outcome"] = self.outcome
        if self.git_commit:
            item["git_commit"] = self.git_commit
        if self.pr is not None:
            item["pr"] = self.pr
        if self.completed_at:
            item["completed_at"] = self.completed_at

        # GSI1 for worker dispatch — only when pending
        if self.status == CrowStatus.PENDING:
            item["GSI1PK"] = "DISPATCH#pending"
            item["GSI1SK"] = f"{self.pk}#S#{self.wave_id}#m{self.mvi_id}#{self.crow_id}"

        return item


@dataclass
class EventRecord:
    tenant: str
    project: str
    wave_id: str
    event_type: str
    message: str
    color: str
    extra: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=_now_iso)

    @property
    def pk(self) -> str:
        return build_pk(self.tenant, self.project)

    @property
    def sk(self) -> str:
        return f"EVT#{self.wave_id}#{self.timestamp}"

    def to_item(self) -> dict[str, Any]:
        item: dict[str, Any] = {
            "PK": self.pk,
            "SK": self.sk,
            "type": self.event_type,
            "message": self.message,
            "color": self.color,
            "timestamp": self.timestamp,
            "entityType": "Event",
        }
        if self.extra:
            item.update(self.extra)
        return item
