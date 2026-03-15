"""Status enums for the Worker bounded context."""

from __future__ import annotations

from enum import Enum


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
