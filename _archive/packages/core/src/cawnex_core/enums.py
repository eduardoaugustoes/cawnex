"""Cawnex enumerations — single source of truth for all status/type values."""

from enum import StrEnum


# === LLM / BYOL ===

class Provider(StrEnum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"


class BYOLMode(StrEnum):
    API_KEY = "api_key"
    SUBSCRIPTION_RELAY = "subscription_relay"


# === Tasks ===

class TaskStatus(StrEnum):
    PENDING = "pending"
    REFINING = "refining"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


class TaskSource(StrEnum):
    GITHUB = "github"
    LINEAR = "linear"
    JIRA = "jira"
    API = "api"
    MANUAL = "manual"
    SCHEDULE = "schedule"
    CHAT = "chat"


# === Executions ===

class ExecutionStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


# === Events ===

class EventType(StrEnum):
    PLANNING = "planning"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    OUTPUT = "output"
    ERROR = "error"
    AGENT_MESSAGE = "agent_message"
    GUARD_WARNING = "guard_warning"
    GUARD_CANCEL = "guard_cancel"
    STATUS_CHANGE = "status_change"
    APPROVAL_REQUEST = "approval_request"
    APPROVAL_RESPONSE = "approval_response"


# === Artifacts ===

class ArtifactType(StrEnum):
    PULL_REQUEST = "pull_request"
    DOCUMENT = "document"
    REPORT = "report"
    DATASET = "dataset"
    EMAIL_DRAFT = "email_draft"
    CODE = "code"
    FILE = "file"
    CUSTOM = "custom"


# === Workspaces ===

class WorkspaceType(StrEnum):
    GIT_WORKTREE = "git_worktree"
    TEMP_DIR = "temp_dir"
    CLOUD_STORAGE = "cloud_storage"


# === Triggers ===

class TriggerSource(StrEnum):
    GITHUB = "github"
    LINEAR = "linear"
    JIRA = "jira"
    API = "api"
    SCHEDULE = "schedule"
    CHAT = "chat"
    MANUAL = "manual"


# === Projects ===

class ProjectStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class MilestoneStatus(StrEnum):
    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETED = "completed"


# === Assets (agents, workflows, tools) ===

class AssetOrigin(StrEnum):
    SYSTEM = "system"
    MARKETPLACE = "marketplace"
    CUSTOM = "custom"
