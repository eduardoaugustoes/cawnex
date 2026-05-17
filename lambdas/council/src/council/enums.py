"""Enums for the Council bounded context."""

from enum import Enum


class AdvisorType(Enum):
    SECURITY = "security"
    ARCHITECTURE = "architecture"
    CLARITY = "clarity"
    PERFORMANCE = "performance"
    UX = "ux"
    COST = "cost"


VETO_ADVISORS = {AdvisorType.SECURITY, AdvisorType.CLARITY}


class VoteType(Enum):
    APPROVE = "approve"
    APPROVE_WITH_CONDITION = "approve_with_condition"
    ABSTAIN = "abstain"
    BLOCK = "block"


class CouncilStatus(Enum):
    PENDING = "pending"
    VOTING = "voting"
    DEBATING = "debating"
    COMPLETED = "completed"
    FAILED = "failed"


class SessionType(Enum):
    WAVE_REVIEW = "wave_review"
    WAVE_PLANNING = "wave_planning"


class DecisionAction(Enum):
    APPROVE = "approve"
    APPROVE_WITH_CONDITIONS = "approve_with_conditions"
    REJECT = "reject"
    ESCALATE = "escalate"
