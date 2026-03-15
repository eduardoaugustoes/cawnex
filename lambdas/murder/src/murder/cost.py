"""Cost calculation — tokens to microdollars, budget checks.

All money is integer microdollars (1 USD = 1_000_000).
"""

from __future__ import annotations

from dataclasses import dataclass

from murder.config import (
    BUDGET_WARNING_PCT,
    CROW_BUDGET_LIMIT,
    MVI_BUDGET_LIMIT,
    PRICE_PER_INPUT_TOKEN,
    PRICE_PER_OUTPUT_TOKEN,
    WAVE_BUDGET_LIMIT,
)


def calculate_credits(tokens_in: int, tokens_out: int) -> int:
    """Convert token counts to microdollars (Sonnet pricing)."""
    return (tokens_in * PRICE_PER_INPUT_TOKEN) + (tokens_out * PRICE_PER_OUTPUT_TOKEN)


@dataclass
class BudgetCheckResult:
    allowed: bool
    warning: bool
    exceeded: bool
    remaining: int


def check_budget(
    spent: int,
    limit: int,
    proposed: int,
    warning_pct: int = BUDGET_WARNING_PCT,
) -> BudgetCheckResult:
    """Check if a proposed spend fits within budget."""
    new_total = spent + proposed
    exceeded = new_total > limit
    warning_threshold = limit * warning_pct // 100
    warning = spent >= warning_threshold and not exceeded
    return BudgetCheckResult(
        allowed=not exceeded,
        warning=warning,
        exceeded=exceeded,
        remaining=max(0, limit - spent),
    )


def check_wave_budget(
    spent: int,
    proposed: int,
    limit: int | None = None,
) -> BudgetCheckResult:
    """Check budget at wave level."""
    return check_budget(spent, limit or WAVE_BUDGET_LIMIT, proposed)


def check_mvi_budget(
    spent: int,
    proposed: int,
    limit: int | None = None,
) -> BudgetCheckResult:
    """Check budget at MVI level."""
    return check_budget(spent, limit or MVI_BUDGET_LIMIT, proposed)


def check_crow_budget(
    spent: int,
    proposed: int,
    limit: int | None = None,
) -> BudgetCheckResult:
    """Check budget at crow level."""
    return check_budget(spent, limit or CROW_BUDGET_LIMIT, proposed)
