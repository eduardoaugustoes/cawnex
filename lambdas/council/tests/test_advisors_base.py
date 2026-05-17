"""Tests for the advisor base loop wrapper."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from council.advisors.base import run_advisor
from council.enums import AdvisorType, VoteType


def _make_result(
    *,
    final_vote: dict[str, Any] | None,
    terminated_by: str,
    tool_calls_made: int,
    tokens_consumed: int,
    trace_entries: list[dict[str, Any]] | None = None,
) -> MagicMock:
    """Make a plain (non-awaitable) MagicMock matching the ToolUseResult shape."""
    result = MagicMock()
    result.final_vote = final_vote
    result.terminated_by = terminated_by
    result.tool_calls_made = tool_calls_made
    result.tokens_consumed = tokens_consumed
    result.trace_entries = trace_entries or []
    return result


@pytest.mark.asyncio
async def test_run_advisor_returns_vote_on_submit() -> None:
    fake_result = _make_result(
        final_vote={"vote": "approve", "confidence": 0.9, "reasoning": "good"},
        terminated_by="submit_vote",
        tool_calls_made=4,
        tokens_consumed=1500,
    )

    async def fake_loop(*args: Any, **kwargs: Any) -> Any:
        return fake_result

    with patch("council.advisors.base.run_tool_use_loop", side_effect=fake_loop):
        vote = await run_advisor(
            advisor=AdvisorType.SECURITY,
            packet={"wave_id": "w1"},
            context={
                "repo_path": "/r",
                "worktree_paths": {},
                "integration_path": "/i",
                "repo": "org/r",
                "github_token": "t",
            },
        )
    assert vote.advisor == AdvisorType.SECURITY
    assert vote.vote == VoteType.APPROVE
    assert vote.confidence == 0.9


@pytest.mark.asyncio
async def test_run_advisor_returns_abstain_on_call_cap() -> None:
    fake_result = _make_result(
        final_vote=None,
        terminated_by="call_cap",
        tool_calls_made=16,
        tokens_consumed=5000,
    )

    async def fake_loop(*args: Any, **kwargs: Any) -> Any:
        return fake_result

    with patch("council.advisors.base.run_tool_use_loop", side_effect=fake_loop):
        vote = await run_advisor(
            advisor=AdvisorType.ARCHITECTURE,
            packet={"wave_id": "w1"},
            context={
                "repo_path": "/r",
                "worktree_paths": {},
                "integration_path": "/i",
                "repo": "org/r",
                "github_token": "t",
            },
        )
    assert vote.vote == VoteType.ABSTAIN
    assert "cap" in vote.reasoning
