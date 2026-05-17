"""Tests for the async streaming + tool-use loop."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from council.claude_client import run_tool_use_loop


def _make_event(
    block_type: str,
    name: str = "",
    block_id: str = "t1",
    block_input: dict[str, Any] | None = None,
) -> MagicMock:
    """Build a fake content_block_start event."""
    block = MagicMock()
    block.type = block_type
    block.id = block_id
    block.name = name
    block.input = block_input or {}
    event = MagicMock()
    event.type = "content_block_start"
    event.content_block = block
    return event


class _FakeStream:
    def __init__(self, events: list[Any], usage: tuple[int, int] = (10, 5)) -> None:
        self._events = events
        self._usage = usage

    def __aiter__(self) -> Any:
        async def gen() -> Any:
            for e in self._events:
                yield e

        return gen()

    async def get_final_message(self) -> MagicMock:
        msg = MagicMock()
        msg.usage = MagicMock(input_tokens=self._usage[0], output_tokens=self._usage[1])
        return msg


def _install_streamer(mock_client: MagicMock, stream_factory: Any) -> None:
    ctx = mock_client.return_value.messages.stream.return_value
    ctx.__aenter__ = AsyncMock(side_effect=lambda: stream_factory())
    ctx.__aexit__ = AsyncMock(return_value=None)


@pytest.mark.asyncio
async def test_tool_use_loop_terminates_on_submit_vote() -> None:
    with patch("council.claude_client.anthropic.AsyncAnthropic") as mock_client:
        _install_streamer(
            mock_client,
            lambda: _FakeStream(
                [
                    _make_event(
                        "tool_use",
                        name="submit_vote",
                        block_input={
                            "vote": "approve",
                            "confidence": 0.8,
                            "reasoning": "looks good",
                        },
                    )
                ]
            ),
        )
        result = await run_tool_use_loop(
            system_prompt="you are security",
            user_message="evaluate the wave",
            tools=[],
            max_tool_calls=15,
            wall_clock_seconds=180,
            tool_executor=lambda name, args: {"result": "ok"},
        )
    assert result.terminated_by == "submit_vote"
    assert result.final_vote is not None
    assert result.final_vote["vote"] == "approve"


@pytest.mark.asyncio
async def test_tool_use_loop_terminates_on_call_cap() -> None:
    with patch("council.claude_client.anthropic.AsyncAnthropic") as mock_client:
        _install_streamer(
            mock_client,
            lambda: _FakeStream(
                [
                    _make_event(
                        "tool_use",
                        name="grep",
                        block_input={"pattern": "x"},
                    )
                ]
            ),
        )
        result = await run_tool_use_loop(
            system_prompt="x",
            user_message="x",
            tools=[],
            max_tool_calls=3,
            wall_clock_seconds=10,
            tool_executor=lambda n, a: {"result": "ok"},
        )
    assert result.terminated_by == "call_cap"
    assert result.tool_calls_made > 3
