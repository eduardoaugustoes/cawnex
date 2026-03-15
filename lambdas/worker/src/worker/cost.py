"""Cost calculation for the Worker bounded context."""

from __future__ import annotations

from worker.config import PRICE_PER_INPUT_TOKEN, PRICE_PER_OUTPUT_TOKEN


def calculate_credits(tokens_in: int, tokens_out: int) -> float:
    """Convert token counts to credit cost (Sonnet pricing)."""
    return (tokens_in * PRICE_PER_INPUT_TOKEN) + (tokens_out * PRICE_PER_OUTPUT_TOKEN)
