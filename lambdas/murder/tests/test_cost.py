"""Tests for cost — credit calculation and budget checks.

All money values are integer microdollars (1 USD = 1_000_000).
"""

from murder.config import MICROS_PER_DOLLAR
from murder.cost import (
    calculate_credits,
    check_budget,
    check_crow_budget,
    check_mvi_budget,
    check_wave_budget,
)


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
        # Sonnet pricing: $3/M input = 3 microdollars/token
        credits = calculate_credits(tokens_in=1_000_000, tokens_out=0)
        assert credits == 3 * MICROS_PER_DOLLAR  # $3
        # $15/M output = 15 microdollars/token
        credits = calculate_credits(tokens_in=0, tokens_out=1_000_000)
        assert credits == 15 * MICROS_PER_DOLLAR  # $15


class TestCheckBudget:
    def test_within_budget(self) -> None:
        result = check_budget(
            spent=10 * MICROS_PER_DOLLAR,
            limit=20 * MICROS_PER_DOLLAR,
            proposed=5 * MICROS_PER_DOLLAR,
        )
        assert result.allowed
        assert not result.warning
        assert not result.exceeded

    def test_exceeds_budget(self) -> None:
        result = check_budget(
            spent=18 * MICROS_PER_DOLLAR,
            limit=20 * MICROS_PER_DOLLAR,
            proposed=5 * MICROS_PER_DOLLAR,
        )
        assert not result.allowed
        assert result.exceeded

    def test_warning_threshold(self) -> None:
        result = check_budget(
            spent=16_500_000,  # $16.50
            limit=20 * MICROS_PER_DOLLAR,
            proposed=1 * MICROS_PER_DOLLAR,
        )
        assert result.allowed
        assert result.warning

    def test_at_exact_limit(self) -> None:
        result = check_budget(
            spent=15 * MICROS_PER_DOLLAR,
            limit=20 * MICROS_PER_DOLLAR,
            proposed=5 * MICROS_PER_DOLLAR,
        )
        assert result.allowed


class TestCheckWaveBudget:
    def test_default_wave_limit(self) -> None:
        result = check_wave_budget(spent=0, proposed=500_000)  # $0.50
        assert result.allowed

    def test_wave_budget_exceeded(self) -> None:
        result = check_wave_budget(
            spent=19 * MICROS_PER_DOLLAR,
            proposed=2 * MICROS_PER_DOLLAR,
        )
        assert not result.allowed


class TestCheckMVIBudget:
    def test_default_mvi_limit(self) -> None:
        result = check_mvi_budget(spent=0, proposed=500_000)  # $0.50
        assert result.allowed

    def test_mvi_budget_exceeded(self) -> None:
        result = check_mvi_budget(
            spent=4_500_000,    # $4.50
            proposed=1_000_000,  # $1.00
        )
        assert not result.allowed


class TestCheckCrowBudget:
    def test_default_crow_limit(self) -> None:
        result = check_crow_budget(spent=0, proposed=100_000)  # $0.10
        assert result.allowed

    def test_crow_budget_exceeded(self) -> None:
        result = check_crow_budget(
            spent=450_000,   # $0.45
            proposed=100_000,  # $0.10
        )
        assert not result.allowed
