"""Tests for Claude API wrapper — SDK mocks, duration tracking."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from worker.claude import ClaudeResult, _get_client, call_claude


@patch.dict(os.environ, {"ANTHROPIC_AUTH_TOKEN": ""}, clear=False)
def test_get_client_raises_without_token() -> None:
    with pytest.raises(RuntimeError, match="No auth"):
        _get_client()


@patch.dict(os.environ, {"ANTHROPIC_AUTH_TOKEN": "test-token"}, clear=False)
@patch("worker.claude.anthropic.Anthropic")
def test_get_client_uses_oauth(mock_anthropic: MagicMock) -> None:
    _get_client()
    mock_anthropic.assert_called_once_with(
        api_key=None,
        auth_token="test-token",
        default_headers={"anthropic-beta": "oauth-2025-04-20"},
    )


@patch("worker.claude._get_client")
def test_call_claude_returns_result(mock_client_fn: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client_fn.return_value = mock_client

    mock_block = MagicMock()
    mock_block.type = "text"
    mock_block.text = '{"tasks": []}'

    mock_response = MagicMock()
    mock_response.content = [mock_block]
    mock_response.usage.input_tokens = 100
    mock_response.usage.output_tokens = 50
    mock_client.messages.create.return_value = mock_response

    result = call_claude("system", "user", model="test-model", max_tokens=1000)

    assert isinstance(result, ClaudeResult)
    assert result.raw_output == '{"tasks": []}'
    assert result.tokens_in == 100
    assert result.tokens_out == 50
    assert result.model == "test-model"
    assert result.duration_ms >= 0


@patch("worker.claude._get_client")
def test_call_claude_measures_duration(mock_client_fn: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client_fn.return_value = mock_client

    mock_block = MagicMock()
    mock_block.type = "text"
    mock_block.text = "output"

    mock_response = MagicMock()
    mock_response.content = [mock_block]
    mock_response.usage.input_tokens = 10
    mock_response.usage.output_tokens = 5
    mock_client.messages.create.return_value = mock_response

    result = call_claude("sys", "usr")
    assert result.duration_ms >= 0


@patch("worker.claude._get_client")
def test_call_claude_concatenates_text_blocks(mock_client_fn: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client_fn.return_value = mock_client

    block1 = MagicMock(type="text", text="hello")
    block2 = MagicMock(type="tool_use", text="ignored")
    block3 = MagicMock(type="text", text="world")

    mock_response = MagicMock()
    mock_response.content = [block1, block2, block3]
    mock_response.usage.input_tokens = 10
    mock_response.usage.output_tokens = 5
    mock_client.messages.create.return_value = mock_response

    result = call_claude("sys", "usr")
    assert result.raw_output == "hello\nworld"


@patch("worker.claude._get_client")
def test_call_claude_passes_params(mock_client_fn: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client_fn.return_value = mock_client

    mock_block = MagicMock(type="text", text="ok")
    mock_response = MagicMock()
    mock_response.content = [mock_block]
    mock_response.usage.input_tokens = 1
    mock_response.usage.output_tokens = 1
    mock_client.messages.create.return_value = mock_response

    call_claude("sys_prompt", "usr_prompt", model="claude-x", max_tokens=4096)

    mock_client.messages.create.assert_called_once_with(
        model="claude-x",
        max_tokens=4096,
        system="sys_prompt",
        messages=[{"role": "user", "content": "usr_prompt"}],
    )
