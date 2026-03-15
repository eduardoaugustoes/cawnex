"""Environment variables and constants for Murder bounded context."""

from __future__ import annotations

import os

# DynamoDB
TABLE_NAME: str = os.environ.get("TABLE_NAME", "cawnex")

# Claude / Anthropic
ANTHROPIC_MODEL: str = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

# Money is stored as integer microdollars (1 USD = 1_000_000 microdollars).
# This eliminates floating-point rounding and DynamoDB's Decimal requirement.
MICROS_PER_DOLLAR: int = 1_000_000

# Budget limits (microdollars)
WAVE_BUDGET_LIMIT: int = 20 * MICROS_PER_DOLLAR   # $20
MVI_BUDGET_LIMIT: int = 5 * MICROS_PER_DOLLAR      # $5
CROW_BUDGET_LIMIT: int = 500_000                    # $0.50

# Pricing (Sonnet: $3/M input, $15/M output) — microdollars per token
# $3 / 1M tokens = 3 microdollars per token
PRICE_PER_INPUT_TOKEN: int = 3
# $15 / 1M tokens = 15 microdollars per token
PRICE_PER_OUTPUT_TOKEN: int = 15

# Budget warning threshold (percentage as integer, 80 = 80%)
BUDGET_WARNING_PCT: int = 80

# Fix cycle cap: after this many fixer completions without approval, fail the MVI
FIX_CYCLE_LIMIT: int = 2

# Task size enforcement
MAX_TASK_HOURS: int = 8
MAX_PLANNER_SPLITS: int = 2
