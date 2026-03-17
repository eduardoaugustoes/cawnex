"""Environment variables and constants for Worker bounded context."""

from __future__ import annotations

import os
from dataclasses import dataclass

# DynamoDB
TABLE_NAME: str = os.environ.get("TABLE_NAME", "cawnex")
EVENTS_TABLE_NAME: str = os.environ.get("EVENTS_TABLE_NAME", "")

# Stage
STAGE: str = os.environ.get("STAGE", "dev")
EVENT_TTL_DAYS: int = 365 if STAGE == "prod" else 90

# Claude / Anthropic
ANTHROPIC_MODEL: str = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

# GitHub
GITHUB_TOKEN: str = os.environ.get("GITHUB_TOKEN", "")

# EFS (Worker)
EFS_MOUNT: str = os.environ.get("EFS_MOUNT", "/mnt/repos")

# Money is stored as integer microdollars (1 USD = 1_000_000 microdollars).
MICROS_PER_DOLLAR: int = 1_000_000

# Pricing (Sonnet: $3/M input, $15/M output) — microdollars per token
PRICE_PER_INPUT_TOKEN: int = 3
PRICE_PER_OUTPUT_TOKEN: int = 15

# Feature flags
MEMORY_INJECTION_ENABLED: bool = os.environ.get("MEMORY_INJECTION_ENABLED", "false").lower() == "true"

# Guard rails
MAX_CROW_RETRIES: int = int(os.environ.get("MAX_CROW_RETRIES", "3"))
CROW_TIMEOUT_SECONDS: int = int(os.environ.get("CROW_TIMEOUT_SECONDS", "600"))


@dataclass(frozen=True)
class ExecutionConfig:
    """Explicit config for executor — no module-level env reads."""

    efs_mount: str
    github_token: str
    memory_injection_enabled: bool = False

    @classmethod
    def from_env(cls) -> ExecutionConfig:
        return cls(
            efs_mount=EFS_MOUNT,
            github_token=GITHUB_TOKEN,
            memory_injection_enabled=MEMORY_INJECTION_ENABLED,
        )
