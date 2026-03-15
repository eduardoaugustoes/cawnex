"""Environment variables and constants for Worker bounded context."""

from __future__ import annotations

import os

# DynamoDB
TABLE_NAME: str = os.environ.get("BLACKBOARD_TABLE", "cawnex")

# Claude / Anthropic
ANTHROPIC_MODEL: str = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

# GitHub
GITHUB_TOKEN: str = os.environ.get("GITHUB_TOKEN", "")

# EFS (Worker)
EFS_MOUNT: str = os.environ.get("EFS_MOUNT", "/mnt/repos")

# Pricing (Sonnet: $3/M input, $15/M output)
PRICE_PER_INPUT_TOKEN: float = 3.0 / 1_000_000
PRICE_PER_OUTPUT_TOKEN: float = 15.0 / 1_000_000

# Guard rails
MAX_CROW_RETRIES: int = int(os.environ.get("MAX_CROW_RETRIES", "3"))
CROW_TIMEOUT_SECONDS: int = int(os.environ.get("CROW_TIMEOUT_SECONDS", "600"))
