"""Snapshot dataclasses for the Murder bounded context.

All money fields are integer microdollars (1 USD = 1_000_000).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from murder.config import MICROS_PER_DOLLAR, WAVE_BUDGET_LIMIT
from murder.enums import (
    BlockerType,
    CrowStatus,
    CrowType,
    HumanTaskStatus,
    HumanTaskSubtype,
    MVIStatus,
    SnapshotLevel,
    WaveStatus,
)
from murder.keys import build_pk, build_sk


@dataclass
class Cost:
    tokens_in: int
    tokens_out: int
    credits: int
    duration_ms: int

    @classmethod
    def zero(cls) -> Cost:
        return cls(tokens_in=0, tokens_out=0, credits=0, duration_ms=0)

    def __add__(self, other: Cost) -> Cost:
        return Cost(
            tokens_in=self.tokens_in + other.tokens_in,
            tokens_out=self.tokens_out + other.tokens_out,
            credits=self.credits + other.credits,
            duration_ms=self.duration_ms + other.duration_ms,
        )

    def to_dict(self) -> dict[str, int]:
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
            credits=int(d["credits"]),
            duration_ms=int(d["duration_ms"]),
        )

    def to_dollars(self) -> float:
        """Convert credits (microdollars) to dollars for display."""
        return self.credits / MICROS_PER_DOLLAR


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
    spent: int
    limit: int

    @property
    def remaining(self) -> int:
        return self.limit - self.spent

    @property
    def is_exceeded(self) -> bool:
        return self.spent > self.limit

    @property
    def is_warning(self) -> bool:
        return self.spent >= self.limit * 80 // 100

    def to_dict(self) -> dict[str, int]:
        return {"spent": self.spent, "limit": self.limit}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> WaveBudget:
        return cls(spent=int(d["spent"]), limit=int(d["limit"]))

    def spent_dollars(self) -> float:
        """Convert spent to dollars for display."""
        return self.spent / MICROS_PER_DOLLAR

    def limit_dollars(self) -> float:
        """Convert limit to dollars for display."""
        return self.limit / MICROS_PER_DOLLAR


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
        default_factory=lambda: WaveBudget(spent=0, limit=WAVE_BUDGET_LIMIT)
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
                else WaveBudget(spent=0, limit=WAVE_BUDGET_LIMIT)
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
    budget_remaining: int
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
            "crow_id": self.crow_id,
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
class Blocker:
    blocker_type: BlockerType
    reference: str
    resolved: bool = False
    resolved_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "blocker_type": self.blocker_type.value,
            "reference": self.reference,
            "resolved": self.resolved,
        }
        if self.resolved_at:
            d["resolved_at"] = self.resolved_at
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Blocker:
        return cls(
            blocker_type=BlockerType(d["blocker_type"]),
            reference=d["reference"],
            resolved=d.get("resolved", False),
            resolved_at=d.get("resolved_at", ""),
        )


@dataclass
class HumanTaskSnapshot:
    tenant: str
    project: str
    wave_id: str
    mvi_id: str
    human_task_id: str
    subtype: HumanTaskSubtype
    status: HumanTaskStatus
    ask: str
    instructions: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    verification: dict[str, Any] | None = None
    post_processing: str = "none"
    blocks: list[str] = field(default_factory=list)
    blocker_history: list[dict[str, Any]] = field(default_factory=list)
    response: dict[str, Any] | None = None
    steer: str | None = None
    assigned_to: str = "human"
    estimated_human_hours: float = 0
    deadline_hint: str = ""
    notification_id: str = ""
    completed_at: str = ""
    created_at: str = field(default_factory=_now_iso)

    @property
    def pk(self) -> str:
        return build_pk(self.tenant, self.project)

    @property
    def sk(self) -> str:
        return f"S#{self.wave_id}#m{self.mvi_id}#{self.human_task_id}"

    @property
    def level(self) -> str:
        return "crow"

    @property
    def task_type(self) -> str:
        return "human"

    def to_item(self) -> dict[str, Any]:
        item: dict[str, Any] = {
            "PK": self.pk,
            "SK": self.sk,
            "id": self.human_task_id,
            "level": self.level,
            "task_type": self.task_type,
            "human_task_subtype": self.subtype.value,
            "status": self.status.value,
            "ask": self.ask,
            "instructions": self.instructions,
            "assigned_to": self.assigned_to,
            "created_at": self.created_at,
            "entityType": "Snapshot",
        }
        if self.input_schema:
            item["input_schema"] = self.input_schema
        if self.verification is not None:
            item["verification"] = self.verification
        if self.post_processing != "none":
            item["post_processing"] = self.post_processing
        if self.blocks:
            item["blocks"] = self.blocks
        if self.blocker_history:
            item["blocker_history"] = self.blocker_history
        if self.response is not None:
            item["response"] = self.response
        if self.steer is not None:
            item["steer"] = self.steer
        if self.estimated_human_hours:
            item["estimated_human_hours"] = Decimal(str(self.estimated_human_hours))
        if self.deadline_hint:
            item["deadline_hint"] = self.deadline_hint
        if self.notification_id:
            item["notification_id"] = self.notification_id
        if self.completed_at:
            item["completed_at"] = self.completed_at
        return item

    @classmethod
    def from_item(cls, item: dict[str, Any]) -> HumanTaskSnapshot:
        pk = item["PK"]
        parts = pk.split("#")
        tenant = parts[1]
        project = parts[3]
        sk = item["SK"]
        sk_parts = sk.split("#")
        wave_id = sk_parts[1]
        mvi_id = sk_parts[2][1:]  # strip leading 'm'
        human_task_id = item.get("id", sk_parts[3])
        return cls(
            tenant=tenant,
            project=project,
            wave_id=wave_id,
            mvi_id=mvi_id,
            human_task_id=human_task_id,
            subtype=HumanTaskSubtype(item["human_task_subtype"]),
            status=HumanTaskStatus(item["status"]),
            ask=item.get("ask", ""),
            instructions=item.get("instructions", ""),
            input_schema=item.get("input_schema", {}),
            verification=item.get("verification"),
            post_processing=item.get("post_processing", "none"),
            blocks=item.get("blocks", []),
            blocker_history=item.get("blocker_history", []),
            response=item.get("response"),
            steer=item.get("steer"),
            assigned_to=item.get("assigned_to", "human"),
            estimated_human_hours=float(item.get("estimated_human_hours", 0)),
            deadline_hint=item.get("deadline_hint", ""),
            notification_id=item.get("notification_id", ""),
            completed_at=item.get("completed_at", ""),
            created_at=item.get("created_at", ""),
        )


@dataclass
class SecretMetadata:
    tenant: str
    project: str
    name: str
    description: str = ""
    created_at: str = field(default_factory=_now_iso)
    rotated_at: str = ""

    @property
    def pk(self) -> str:
        return f"T#{self.tenant}#VAULT"

    @property
    def sk(self) -> str:
        return f"P#{self.project}#S#{self.name}"

    def to_item(self) -> dict[str, Any]:
        item: dict[str, Any] = {
            "PK": self.pk,
            "SK": self.sk,
            "name": self.name,
            "project": self.project,
            "description": self.description,
            "created_at": self.created_at,
            "entityType": "Secret",
        }
        if self.rotated_at:
            item["rotated_at"] = self.rotated_at
        return item

    @classmethod
    def from_item(cls, item: dict[str, Any]) -> SecretMetadata:
        pk = item["PK"]
        tenant = pk.split("#")[1]
        return cls(
            tenant=tenant,
            project=item["project"],
            name=item["name"],
            description=item.get("description", ""),
            created_at=item.get("created_at", ""),
            rotated_at=item.get("rotated_at", ""),
        )


@dataclass
class CheckRecord:
    tenant: str
    project: str
    human_task_id: str
    check_type: str
    instructions: str
    ttl: str
    max_retries: int = 3
    retry_count: int = 0
    retry_delay_hours: float = 1
    required_secrets: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now_iso)

    @property
    def pk(self) -> str:
        return build_pk(self.tenant, self.project)

    @property
    def sk(self) -> str:
        return f"CHECK#{self.human_task_id}"

    def to_item(self) -> dict[str, Any]:
        return {
            "PK": self.pk,
            "SK": self.sk,
            "human_task_id": self.human_task_id,
            "check_type": self.check_type,
            "instructions": self.instructions,
            "ttl": self.ttl,
            "max_retries": self.max_retries,
            "retry_count": self.retry_count,
            "retry_delay_hours": self.retry_delay_hours,
            "required_secrets": self.required_secrets,
            "created_at": self.created_at,
            "entityType": "Check",
        }

    @classmethod
    def from_item(cls, item: dict[str, Any]) -> CheckRecord:
        pk = item["PK"]
        parts = pk.split("#")
        tenant = parts[1]
        project = parts[3]
        return cls(
            tenant=tenant,
            project=project,
            human_task_id=item["human_task_id"],
            check_type=item["check_type"],
            instructions=item["instructions"],
            ttl=item["ttl"],
            max_retries=int(item.get("max_retries", 3)),
            retry_count=int(item.get("retry_count", 0)),
            retry_delay_hours=float(item.get("retry_delay_hours", 1)),
            required_secrets=item.get("required_secrets", []),
            created_at=item.get("created_at", ""),
        )


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

    @property
    def events_pk(self) -> str:
        """PK for the dedicated events table."""
        return f"T#{self.tenant}#P#{self.project}#W#{self.wave_id}"

    @property
    def events_sk(self) -> str:
        """SK for the dedicated events table."""
        return f"{self.timestamp}#{self.event_type}"

    def to_item(self) -> dict[str, Any]:
        """Write to main table (legacy, kept for backward compat in tests)."""
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

    def to_events_item(self, ttl_days: int = 90) -> dict[str, Any]:
        """Write to dedicated events table with TTL."""
        import time as _time

        item: dict[str, Any] = {
            "PK": self.events_pk,
            "SK": self.events_sk,
            "GSI1PK": f"T#{self.tenant}#P#{self.project}",
            "GSI1SK": self.timestamp,
            "event_type": self.event_type,
            "message": self.message,
            "color": self.color,
            "timestamp": self.timestamp,
            "expires_at": int(_time.time()) + (ttl_days * 86400),
            "entityType": "Event",
        }
        if self.extra:
            item["extra"] = self.extra
        return item
