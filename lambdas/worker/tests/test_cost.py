"""Tests for cost — credit calculation only.

All money values are integer microdollars (1 USD = 1_000_000).
"""

from worker.config import MICROS_PER_DOLLAR
from worker.cost import calculate_credits


class TestCalculateCredits:
    def test_basic_calculation(self) -> None:
        credits = calculate_credits(tokens_in=2000, tokens_out=500)
        assert credits > 0
        assert isinstance(credits, int)

    def test_zero_tokens(self) -> None:
        credits = calculate_credits(tokens_in=0, tokens_out=0)
        assert credits == 0

    def test_input_cheaper_than_output(self) -> None:
        input_only = calculate_credits(tokens_in=1000, tokens_out=0)
        output_only = calculate_credits(tokens_in=0, tokens_out=1000)
        assert output_only > input_only

    def test_known_values(self) -> None:
        # $3/M input = 3 microdollars/token × 1M tokens = $3
        credits = calculate_credits(tokens_in=1_000_000, tokens_out=0)
        assert credits == 3 * MICROS_PER_DOLLAR
        # $15/M output = 15 microdollars/token × 1M tokens = $15
        credits = calculate_credits(tokens_in=0, tokens_out=1_000_000)
        assert credits == 15 * MICROS_PER_DOLLAR
