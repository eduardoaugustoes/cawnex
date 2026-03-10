"""Cawnex enumerations — single source of truth for all status/type values."""

from enum import StrEnum


class Provider(StrEnum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"


class BYOLMode(StrEnum):
    API_KEY = "api_key"
    SUBSCRIPTION_RELAY = "subscription_relay"


class AgentType(StrEnum):
    REFINEMENT = "refinement"
    DEV = "dev"
    QA = "qa"
    DOCS = "docs"
    BACKEND = "backend"
    FRONTEND = "frontend"
    MOBILE = "mobile"
    SECURITY = "security"
    PLANNING = "planning"


class IssueStatus(StrEnum):
    PENDING = "pending"
    REFINING = "refining"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


class ExecutionStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class EventType(StrEnum):
    PLANNING = "planning"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    OUTPUT = "output"
    ERROR = "error"
    PEER_MESSAGE = "peer_message"
    GUARD_WARNING = "guard_warning"
    GUARD_CANCEL = "guard_cancel"
    STATUS_CHANGE = "status_change"


class IssueSource(StrEnum):
    GITHUB = "github"
    LINEAR = "linear"
    JIRA = "jira"
    MANUAL = "manual"
