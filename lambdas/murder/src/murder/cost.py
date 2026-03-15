"""Cost calculation — tokens to credits, budget checks."""

from __future__ import annotations

from dataclasses import dataclass

from murder.config import (
    CROW_BUDGET_LIMIT,
    MVI_BUDGET_LIMIT,
    PRICE_PER_INPUT_TOKEN,
    PRICE_PER_OUTPUT_TOKEN,
    WAVE_BUDGET_LIMIT,
)


def calculate_credits(tokens_in: int, tokens_out: int) -> float:
    """Convert token counts to credit cost (Sonnet pricing)."""
    return (tokens_in * PRICE_PER_INPUT_TOKEN) + (tokens_out * PRICE_PER_OUTPUT_TOKEN)


@dataclass
class BudgetCheckResult:
    allowed: bool
    warning: bool
    exceeded: bool
    remaining: float


def check_budget(
    spent: float,
    limit: float,
    proposed: float,
    warning_threshold: float = 0.80,
) -> BudgetCheckResult:
    """Check if a proposed spend fits within budget."""
    new_total = spent + proposed
    exceeded = new_total > limit
    warning = spent >= limit * warning_threshold and not exceeded
    return BudgetCheckResult(
        allowed=not exceeded,
        warning=warning,
        exceeded=exceeded,
        remaining=max(0.0, limit - spent),
    )


def check_wave_budget(
    spent: float,
    proposed: float,
    limit: float | None = None,
) -> BudgetCheckResult:
    """Check budget at wave level."""
    return check_budget(spent, limit or WAVE_BUDGET_LIMIT, proposed)


def check_mvi_budget(
    spent: float,
    proposed: float,
    limit: float | None = None,
) -> BudgetCheckResult:
    """Check budget at MVI level."""
    return check_budget(spent, limit or MVI_BUDGET_LIMIT, proposed)


def check_crow_budget(
    spent: float,
    proposed: float,
    limit: float | None = None,
) -> BudgetCheckResult:
    """Check budget at crow level."""
    return check_budget(spent, limit or CROW_BUDGET_LIMIT, proposed)
