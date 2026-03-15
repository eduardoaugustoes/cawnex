"""Status enums for the Murder bounded context."""

from __future__ import annotations

from enum import Enum


class WaveStatus(Enum):
    PLANNING = "planning"
    PROPOSED = "proposed"
    REVISED = "revised"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    PAUSED = "paused"
    REVIEW = "review"
    STEERED = "steered"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

    def is_terminal(self) -> bool:
        return self in (WaveStatus.DELIVERED, WaveStatus.CANCELLED)

    def can_transition_to(self, target: WaveStatus) -> bool:
        return target in _WAVE_TRANSITIONS.get(self, set())


_WAVE_TRANSITIONS: dict[WaveStatus, set[WaveStatus]] = {
    WaveStatus.PLANNING: {WaveStatus.PROPOSED, WaveStatus.CANCELLED},
    WaveStatus.PROPOSED: {
        WaveStatus.APPROVED,
        WaveStatus.REVISED,
        WaveStatus.REJECTED,
    },
    WaveStatus.REVISED: {WaveStatus.PROPOSED, WaveStatus.CANCELLED},
    WaveStatus.REJECTED: {WaveStatus.PLANNING},
    WaveStatus.APPROVED: {WaveStatus.EXECUTING},
    WaveStatus.EXECUTING: {
        WaveStatus.REVIEW,
        WaveStatus.PAUSED,
        WaveStatus.STEERED,
        WaveStatus.CANCELLED,
    },
    WaveStatus.PAUSED: {
        WaveStatus.EXECUTING,
        WaveStatus.STEERED,
        WaveStatus.CANCELLED,
    },
    WaveStatus.STEERED: {WaveStatus.EXECUTING, WaveStatus.PROPOSED},
    WaveStatus.REVIEW: {WaveStatus.DELIVERED, WaveStatus.STEERED},
}


class MVIStatus(Enum):
    DRAFT = "draft"
    REFINED = "refined"
    QUEUED = "queued"
    EXECUTING = "executing"
    FAILED = "failed"
    READY_TO_SHIP = "ready_to_ship"
    REJECTED = "rejected"
    SHIPPED = "shipped"
    CANCELLED = "cancelled"

    def is_terminal(self) -> bool:
        return self in (MVIStatus.SHIPPED, MVIStatus.CANCELLED)

    def can_transition_to(self, target: MVIStatus) -> bool:
        return target in _MVI_TRANSITIONS.get(self, set())


_MVI_TRANSITIONS: dict[MVIStatus, set[MVIStatus]] = {
    MVIStatus.DRAFT: {MVIStatus.REFINED, MVIStatus.CANCELLED},
    MVIStatus.REFINED: {MVIStatus.QUEUED, MVIStatus.CANCELLED},
    MVIStatus.QUEUED: {MVIStatus.EXECUTING, MVIStatus.CANCELLED},
    MVIStatus.EXECUTING: {
        MVIStatus.READY_TO_SHIP,
        MVIStatus.FAILED,
        MVIStatus.CANCELLED,
    },
    MVIStatus.FAILED: {MVIStatus.QUEUED, MVIStatus.CANCELLED},
    MVIStatus.READY_TO_SHIP: {
        MVIStatus.SHIPPED,
        MVIStatus.REJECTED,
    },
    MVIStatus.REJECTED: {MVIStatus.QUEUED, MVIStatus.CANCELLED},
}


class CrowStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

    def can_transition_to(self, target: CrowStatus) -> bool:
        return target in _CROW_TRANSITIONS.get(self, set())


_CROW_TRANSITIONS: dict[CrowStatus, set[CrowStatus]] = {
    CrowStatus.PENDING: {CrowStatus.RUNNING},
    CrowStatus.RUNNING: {CrowStatus.COMPLETED, CrowStatus.FAILED},
}


class CrowType(Enum):
    PLANNER = "planner"
    IMPLEMENTER = "implementer"
    REVIEWER = "reviewer"
    FIXER = "fixer"

    @property
    def max_retries(self) -> int:
        return _CROW_MAX_RETRIES[self]


_CROW_MAX_RETRIES: dict[CrowType, int] = {
    CrowType.PLANNER: 1,
    CrowType.IMPLEMENTER: 3,
    CrowType.REVIEWER: 2,
    CrowType.FIXER: 3,
}


class BehaviorState(Enum):
    ASSIGNED = "assigned"
    WORKING = "working"
    LANDED = "landed"
    ERROR = "error"
    BLOCKED = "blocked"


class SnapshotLevel(Enum):
    ROOT = "root"
    WAVE = "wave"
    COUNCIL = "council"
    MURDER = "murder"
    CROW = "crow"


class VoteType(Enum):
    APPROVE = "approve"
    APPROVE_WITH_CONDITION = "approve_with_condition"
    ABSTAIN = "abstain"
    BLOCK = "block"

    def is_blocking(self) -> bool:
        return self == VoteType.BLOCK


class AdvisorType(Enum):
    SECURITY = "security"
    QUALITY = "quality"
    PERFORMANCE = "performance"
    MARKET = "market"
    MATURITY = "maturity"
    CLARITY = "clarity"

    def has_veto(self) -> bool:
        return self in (AdvisorType.SECURITY, AdvisorType.CLARITY)


class EventType(Enum):
    CROW_ASSIGNED = "crow_assigned"
    CROW_COMPLETED = "crow_completed"
    CROW_FAILED = "crow_failed"
    MVI_READY = "mvi_ready"
    MVI_SHIPPED = "mvi_shipped"
    WAVE_STARTED = "wave_started"
    WAVE_DELIVERED = "wave_delivered"
    BUDGET_WARNING = "budget_warning"
    BUDGET_EXCEEDED = "budget_exceeded"


class EventColor(Enum):
    GREEN = "green"
    RED = "red"
    PURPLE = "purple"
    YELLOW = "yellow"
    BLUE = "blue"
