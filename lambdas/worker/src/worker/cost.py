"""Cost calculation for the Worker bounded context.

All money is integer microdollars (1 USD = 1_000_000).
"""

from __future__ import annotations

from worker.config import PRICE_PER_INPUT_TOKEN, PRICE_PER_OUTPUT_TOKEN


def calculate_credits(tokens_in: int, tokens_out: int) -> int:
    """Convert token counts to microdollars (Sonnet pricing)."""
    return (tokens_in * PRICE_PER_INPUT_TOKEN) + (tokens_out * PRICE_PER_OUTPUT_TOKEN)
