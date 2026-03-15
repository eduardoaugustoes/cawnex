"""Snapshot dataclasses for the Murder bounded context."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from murder.enums import (
    CrowStatus,
    CrowType,
    MVIStatus,
    SnapshotLevel,
    WaveStatus,
)
from murder.keys import build_pk, build_sk


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
class Progress:
    mvis_total: int
    mvis_shipped: int
    tasks_done: int
    tasks_total: int

    def to_dict(self) -> dict[str, int]:
        return {
            "mvis_total": self.mvis_total,
            "mvis_shipped": self.mvis_shipped,
            "tasks_done": self.tasks_done,
            "tasks_total": self.tasks_total,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Progress:
        return cls(
            mvis_total=int(d["mvis_total"]),
            mvis_shipped=int(d["mvis_shipped"]),
            tasks_done=int(d["tasks_done"]),
            tasks_total=int(d["tasks_total"]),
        )


@dataclass
class WaveBudget:
    spent: float
    limit: float

    @property
    def remaining(self) -> float:
        return self.limit - self.spent

    @property
    def is_exceeded(self) -> bool:
        return self.spent > self.limit

    @property
    def is_warning(self) -> bool:
        return self.spent >= self.limit * 0.80

    def to_dict(self) -> dict[str, float]:
        return {"spent": self.spent, "limit": self.limit}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> WaveBudget:
        return cls(spent=float(d["spent"]), limit=float(d["limit"]))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class WaveSnapshot:
    tenant: str
    project: str
    wave_id: str
    status: WaveStatus
    human_directive: str
    progress: Progress = field(
        default_factory=lambda: Progress(
            mvis_total=0, mvis_shipped=0, tasks_done=0, tasks_total=0
        )
    )
    budget: WaveBudget = field(
        default_factory=lambda: WaveBudget(spent=0.0, limit=20.0)
    )
    created_at: str = field(default_factory=_now_iso)

    @property
    def pk(self) -> str:
        return build_pk(self.tenant, self.project)

    @property
    def sk(self) -> str:
        return build_sk(wave_id=self.wave_id)

    @property
    def level(self) -> SnapshotLevel:
        return SnapshotLevel.WAVE

    def to_item(self) -> dict[str, Any]:
        return {
            "PK": self.pk,
            "SK": self.sk,
            "level": self.level.value,
            "status": self.status.value,
            "human_directive": self.human_directive,
            "progress": self.progress.to_dict(),
            "budget": self.budget.to_dict(),
            "created_at": self.created_at,
            "entityType": "Snapshot",
        }

    @classmethod
    def from_item(cls, item: dict[str, Any]) -> WaveSnapshot:
        pk = item["PK"]
        parts = pk.split("#")
        tenant = parts[1]
        project = parts[3]
        sk = item["SK"]
        wave_id = sk.replace("S#", "")
        return cls(
            tenant=tenant,
            project=project,
            wave_id=wave_id,
            status=WaveStatus(item["status"]),
            human_directive=item.get("human_directive", ""),
            progress=(
                Progress.from_dict(item["progress"])
                if "progress" in item
                else Progress(mvis_total=0, mvis_shipped=0, tasks_done=0, tasks_total=0)
            ),
            budget=(
                WaveBudget.from_dict(item["budget"])
                if "budget" in item
                else WaveBudget(spent=0.0, limit=20.0)
            ),
            created_at=item.get("created_at", ""),
        )


@dataclass
class MVISnapshot:
    tenant: str
    project: str
    wave_id: str
    mvi_id: str
    name: str
    status: MVIStatus
    repo: str
    branch: str
    description: str = ""
    acceptance_criteria: str = ""
    tasks_done: int = 0
    tasks_total: int = 0
    can_ship: bool = False
    merge_checklist: list[dict[str, Any]] = field(default_factory=list)
    cost: Cost = field(default_factory=Cost.zero)
    created_at: str = field(default_factory=_now_iso)

    @property
    def pk(self) -> str:
        return build_pk(self.tenant, self.project)

    @property
    def sk(self) -> str:
        return build_sk(wave_id=self.wave_id, mvi_id=self.mvi_id)

    @property
    def level(self) -> SnapshotLevel:
        return SnapshotLevel.MURDER

    def to_item(self) -> dict[str, Any]:
        return {
            "PK": self.pk,
            "SK": self.sk,
            "level": self.level.value,
            "status": self.status.value,
            "name": self.name,
            "description": self.description,
            "acceptance_criteria": self.acceptance_criteria,
            "tasks_done": self.tasks_done,
            "tasks_total": self.tasks_total,
            "can_ship": self.can_ship,
            "merge_checklist": self.merge_checklist,
            "cost": self.cost.to_dict(),
            "repo": self.repo,
            "branch": self.branch,
            "created_at": self.created_at,
            "entityType": "Snapshot",
        }


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

    @property
    def level(self) -> SnapshotLevel:
        return SnapshotLevel.CROW

    def to_item(self) -> dict[str, Any]:
        item: dict[str, Any] = {
            "PK": self.pk,
            "SK": self.sk,
            "level": self.level.value,
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
