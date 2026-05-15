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


# Per-model context windows. Used by call_claude to pre-check input size
# before submission and to derive a safe max_tokens from the remaining
# headroom. Keep this in sync with the Anthropic models page; missing
# entries fall back to MODEL_CONTEXT_DEFAULT.
MODEL_CONTEXT_DEFAULT: int = 200_000
MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    "claude-haiku-4-5-20251001": 200_000,
    "claude-haiku-4-5": 200_000,
    "claude-sonnet-4-20250514": 200_000,
    "claude-sonnet-4-5-20250929": 200_000,
    "claude-sonnet-4-6": 1_000_000,  # default response window; 1M beta requires header
    "claude-opus-4-6": 1_000_000,
    "claude-opus-4-7": 1_000_000,
}

# Per-model max output tokens (the API caps how much can be generated in a
# single response). Pulled from the published model spec — see the Anthropic
# models reference. Used as the ceiling when deriving dynamic max_tokens.
MODEL_MAX_OUTPUT_TOKENS: dict[str, int] = {
    "claude-haiku-4-5-20251001": 64_000,
    "claude-haiku-4-5": 64_000,
    "claude-sonnet-4-20250514": 64_000,
    "claude-sonnet-4-5-20250929": 64_000,
    "claude-sonnet-4-6": 64_000,
    "claude-opus-4-6": 128_000,
    "claude-opus-4-7": 128_000,
}
MODEL_MAX_OUTPUT_DEFAULT: int = 8_192

# Safety cushion in the context budget calc — we don't want to pack the
# input right up to the window because tokenization can differ slightly
# from count_tokens estimates and we want a small buffer for retries.
CONTEXT_SAFETY_CUSHION_TOKENS: int = 4_096


def context_window(model: str) -> int:
    return MODEL_CONTEXT_WINDOWS.get(model, MODEL_CONTEXT_DEFAULT)


def max_output_tokens(model: str) -> int:
    return MODEL_MAX_OUTPUT_TOKENS.get(model, MODEL_MAX_OUTPUT_DEFAULT)


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
