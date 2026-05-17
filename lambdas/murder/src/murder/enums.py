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
    INTEGRATING = "integrating"
    NEEDS_REWORK = "needs_rework"
    UNDER_COUNCIL_REVIEW = "under_council_review"
    UNDER_HUMAN_REVIEW = "under_human_review"
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


class HumanTaskSubtype(Enum):
    PROVIDE_SECRET = "provide_secret"
    UPLOAD_ASSET = "upload_asset"
    FILL_CONTENT = "fill_content"
    CONFIGURE_EXT = "configure_ext"
    PHYSICAL_ACTION = "physical_action"
    WAIT_EXTERNAL = "wait_external"
    CONFIRM = "confirm"


class HumanTaskStatus(Enum):
    PENDING = "pending"
    NOTIFIED = "notified"
    IN_PROGRESS = "in_progress"
    RESPONDED = "responded"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    VERIFICATION_FAILED = "verification_failed"
    EXPIRED = "expired"

    def is_terminal(self) -> bool:
        return self in (HumanTaskStatus.COMPLETED, HumanTaskStatus.EXPIRED)

    def can_transition_to(self, target: HumanTaskStatus) -> bool:
        return target in _HUMAN_TASK_TRANSITIONS.get(self, set())


_HUMAN_TASK_TRANSITIONS: dict[HumanTaskStatus, set[HumanTaskStatus]] = {
    HumanTaskStatus.PENDING: {HumanTaskStatus.NOTIFIED, HumanTaskStatus.EXPIRED},
    HumanTaskStatus.NOTIFIED: {
        HumanTaskStatus.IN_PROGRESS,
        HumanTaskStatus.RESPONDED,
        HumanTaskStatus.COMPLETED,
        HumanTaskStatus.EXPIRED,
    },
    HumanTaskStatus.IN_PROGRESS: {
        HumanTaskStatus.RESPONDED,
        HumanTaskStatus.COMPLETED,
        HumanTaskStatus.EXPIRED,
    },
    HumanTaskStatus.RESPONDED: {
        HumanTaskStatus.VERIFYING,
        HumanTaskStatus.COMPLETED,
    },
    HumanTaskStatus.VERIFYING: {
        HumanTaskStatus.COMPLETED,
        HumanTaskStatus.VERIFICATION_FAILED,
    },
    HumanTaskStatus.VERIFICATION_FAILED: {
        HumanTaskStatus.RESPONDED,
    },
}


class InputFieldType(Enum):
    STRING = "string"
    TEXT = "text"
    SECRET = "secret"
    FILE = "file"
    URL = "url"
    EMAIL = "email"
    COLOR = "color"
    ENUM = "enum"
    BOOLEAN = "boolean"
    NUMBER = "number"


class BlockerType(Enum):
    HUMAN_TASK = "human_task"
    SECRET = "secret"
    EXTERNAL = "external"


class PostProcessingType(Enum):
    NONE = "none"
    EXTRACT_TEXT = "extract_text"
    EXTRACT_META = "extract_meta"


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
    HUMAN_TASK_CREATED = "human_task_created"
    HUMAN_TASK_COMPLETED = "human_task_completed"
    TASK_BLOCKED = "task_blocked"
    TASK_UNBLOCKED = "task_unblocked"
    VERIFICATION_PASSED = "verification_passed"
    VERIFICATION_FAILED = "verification_failed"


class EventColor(Enum):
    GREEN = "green"
    RED = "red"
    PURPLE = "purple"
    YELLOW = "yellow"
    BLUE = "blue"
    ORANGE = "orange"
