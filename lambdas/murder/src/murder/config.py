"""Environment variables and constants for Murder bounded context."""

from __future__ import annotations

import os

# DynamoDB
TABLE_NAME: str = os.environ.get("BLACKBOARD_TABLE", "cawnex")

# Claude / Anthropic
ANTHROPIC_MODEL: str = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

# Budget limits (USD)
WAVE_BUDGET_LIMIT: float = float(os.environ.get("WAVE_BUDGET_LIMIT", "20.0"))
MVI_BUDGET_LIMIT: float = float(os.environ.get("MVI_BUDGET_LIMIT", "5.0"))
CROW_BUDGET_LIMIT: float = float(os.environ.get("CROW_BUDGET_LIMIT", "0.50"))

# Pricing (Sonnet: $3/M input, $15/M output)
PRICE_PER_INPUT_TOKEN: float = 3.0 / 1_000_000
PRICE_PER_OUTPUT_TOKEN: float = 15.0 / 1_000_000

# Budget warning threshold
BUDGET_WARNING_THRESHOLD: float = 0.80
