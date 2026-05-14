"""Tests for the agentic tool-use loop in call_claude."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

from worker.claude import call_claude


class FakeTools:
    """Minimal ToolExecutor double that records calls and returns canned results."""

    def __init__(self, results: dict[str, Any] | None = None) -> None:
        self.results = results or {}
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def execute(self, name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((name, tool_input))
        if name in self.results:
            return self.results[name]
        return {"content": f"stub for {name}", "size_bytes": 0, "truncated": False}


def _text_block(text: str) -> MagicMock:
    b = MagicMock()
    b.type = "text"
    b.text = text
    return b


def _tool_use_block(
    tool_id: str, name: str, tool_input: dict[str, Any]
) -> MagicMock:
    b = MagicMock()
    b.type = "tool_use"
    b.id = tool_id
    b.name = name
    b.input = tool_input
    return b


def _response(
    content: list[MagicMock],
    stop_reason: str = "end_turn",
    tokens_in: int = 10,
    tokens_out: int = 5,
    cache_creation: int = 0,
    cache_read: int = 0,
) -> MagicMock:
    r = MagicMock()
    r.content = content
    r.stop_reason = stop_reason
    r.usage.input_tokens = tokens_in
    r.usage.output_tokens = tokens_out
    r.usage.cache_creation_input_tokens = cache_creation
    r.usage.cache_read_input_tokens = cache_read
    return r


@patch("worker.claude._get_client")
def test_one_shot_path_unchanged_when_no_tools(mock_client_fn: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client_fn.return_value = mock_client
    mock_client.messages.create.return_value = _response(
        [_text_block("hello world")], stop_reason="end_turn"
    )

    result = call_claude("sys", "user prompt", model="x", max_tokens=100)

    assert result.raw_output == "hello world"
    assert result.tokens_in == 10
    assert result.tokens_out == 5
    assert result.turns == 1
    assert mock_client.messages.create.call_count == 1


@patch("worker.claude._get_client")
def test_loop_executes_tool_and_continues(mock_client_fn: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client_fn.return_value = mock_client

    mock_client.messages.create.side_effect = [
        # Turn 1: model requests read_file
        _response(
            [
                _text_block("I will read the spec first."),
                _tool_use_block("toolu_1", "read_file", {"path": "spec.md"}),
            ],
            stop_reason="tool_use",
            tokens_in=100,
            tokens_out=20,
        ),
        # Turn 2: model produces the final JSON
        _response(
            [_text_block('{"changes": [], "summary": "done"}')],
            stop_reason="end_turn",
            tokens_in=150,
            tokens_out=30,
        ),
    ]

    tools = FakeTools(results={"read_file": {"content": "spec body"}})

    result = call_claude(
        "sys",
        "user prompt",
        model="x",
        tools=[{"name": "read_file", "input_schema": {"type": "object"}}],
        tool_executor=tools,
    )

    assert result.turns == 2
    assert mock_client.messages.create.call_count == 2
    assert tools.calls == [("read_file", {"path": "spec.md"})]
    # Aggregated tokens
    assert result.tokens_in == 250
    assert result.tokens_out == 50
    # Final output is on raw_output (text from both turns joined)
    assert '"changes": []' in result.raw_output
    assert result.tool_calls == [
        {
            "name": "read_file",
            "input": {"path": "spec.md"},
            "result_keys": ["content"],
        }
    ]


@patch("worker.claude._get_client")
def test_loop_appends_tool_result_to_next_user_turn(
    mock_client_fn: MagicMock,
) -> None:
    mock_client = MagicMock()
    mock_client_fn.return_value = mock_client

    mock_client.messages.create.side_effect = [
        _response(
            [_tool_use_block("toolu_a", "read_file", {"path": "a.py"})],
            stop_reason="tool_use",
        ),
        _response([_text_block("final")], stop_reason="end_turn"),
    ]

    tools = FakeTools(results={"read_file": {"content": "module body"}})
    call_claude(
        "sys",
        "user",
        tools=[{"name": "read_file", "input_schema": {"type": "object"}}],
        tool_executor=tools,
    )

    # Inspect the second call to messages.create — its messages should contain
    # an assistant turn with the tool_use block, then a user turn with tool_result.
    second_call_kwargs = mock_client.messages.create.call_args_list[1].kwargs
    messages = second_call_kwargs["messages"]
    assert messages[0]["role"] == "user"  # initial
    assert messages[1]["role"] == "assistant"  # contains tool_use blocks
    assert messages[2]["role"] == "user"  # contains tool_result blocks
    tool_results = messages[2]["content"]
    assert tool_results[0]["type"] == "tool_result"
    assert tool_results[0]["tool_use_id"] == "toolu_a"
    # Content is a JSON string carrying the tool's output dict
    payload = json.loads(tool_results[0]["content"])
    assert payload["content"] == "module body"
    assert tool_results[0]["is_error"] is False


@patch("worker.claude._get_client")
def test_loop_marks_is_error_for_tool_errors(mock_client_fn: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client_fn.return_value = mock_client

    mock_client.messages.create.side_effect = [
        _response(
            [_tool_use_block("toolu_x", "read_file", {"path": "missing.md"})],
            stop_reason="tool_use",
        ),
        _response([_text_block("oh well")], stop_reason="end_turn"),
    ]

    tools = FakeTools(results={"read_file": {"error": "file not found: missing.md"}})
    call_claude(
        "sys",
        "user",
        tools=[{"name": "read_file", "input_schema": {"type": "object"}}],
        tool_executor=tools,
    )

    second_call = mock_client.messages.create.call_args_list[1].kwargs
    tool_results = second_call["messages"][2]["content"]
    assert tool_results[0]["is_error"] is True


@patch("worker.claude._get_client")
def test_loop_respects_max_iterations(mock_client_fn: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client_fn.return_value = mock_client

    # Model keeps requesting tools forever — return tool_use every turn
    mock_client.messages.create.return_value = _response(
        [_tool_use_block("t", "read_file", {"path": "x"})],
        stop_reason="tool_use",
    )

    tools = FakeTools()
    result = call_claude(
        "sys",
        "user",
        tools=[{"name": "read_file", "input_schema": {"type": "object"}}],
        tool_executor=tools,
        max_iterations=3,
    )

    assert mock_client.messages.create.call_count == 3
    assert result.turns == 3


@patch("worker.claude._get_client")
def test_loop_aggregates_cache_tokens(mock_client_fn: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client_fn.return_value = mock_client

    mock_client.messages.create.side_effect = [
        _response(
            [_tool_use_block("t1", "read_file", {"path": "a"})],
            stop_reason="tool_use",
            cache_creation=500,
            cache_read=0,
        ),
        _response(
            [_text_block("done")],
            stop_reason="end_turn",
            cache_creation=0,
            cache_read=500,
        ),
    ]

    tools = FakeTools()
    result = call_claude(
        "sys",
        "user",
        tools=[{"name": "read_file", "input_schema": {"type": "object"}}],
        tool_executor=tools,
    )

    assert result.cache_creation == 500
    assert result.cache_read == 500


@patch("worker.claude._get_client")
def test_loop_continues_when_only_text_and_no_tool_use(
    mock_client_fn: MagicMock,
) -> None:
    """If stop_reason is end_turn even with tools enabled, the loop terminates."""
    mock_client = MagicMock()
    mock_client_fn.return_value = mock_client

    mock_client.messages.create.return_value = _response(
        [_text_block("no tools needed, here's the answer")],
        stop_reason="end_turn",
    )

    tools = FakeTools()
    result = call_claude(
        "sys",
        "user",
        tools=[{"name": "read_file", "input_schema": {"type": "object"}}],
        tool_executor=tools,
    )

    assert result.turns == 1
    assert "no tools needed" in result.raw_output
