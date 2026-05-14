"""Anthropic API client wrapper.

Supports two modes:

* **One-shot** — pass `tools=None` (default). Calls `messages.create` once
  and returns the assembled text. Preserves the original behavior used by
  planner / reviewer / fixer crows.

* **Agentic loop** — pass `tools=[...]` (Claude tool schemas) and a
  `tool_executor` with an `execute(name, input) -> dict` method. Loops
  until Claude returns `stop_reason == "end_turn"` (or hits `max_iterations`),
  feeding tool results back as user messages between turns.

The agentic loop aggregates `input_tokens`, `output_tokens`, and cache token
counts across every API call in the loop. Only the FINAL assistant turn's
text is treated as the parseable output — intermediate text blocks (where
Claude is narrating tool use) are joined into `raw_output` too, but the
JSON contract Claude is asked to produce is expected on the last turn.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

import anthropic

from worker.config import ANTHROPIC_MODEL


@dataclass
class ClaudeResult:
    raw_output: str
    tokens_in: int
    tokens_out: int
    duration_ms: int
    model: str
    cache_creation: int = 0
    cache_read: int = 0
    turns: int = 1
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


class ToolExecutor(Protocol):
    """Anything with an execute(name, input) -> dict callable can drive the loop."""

    def execute(self, name: str, tool_input: dict[str, Any]) -> dict[str, Any]: ...


def _get_client() -> anthropic.Anthropic:
    """Create Anthropic client with OAuth token."""
    token = (
        os.environ.get("ANTHROPIC_AUTH_TOKEN")
        or os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
        or ""
    ).strip()
    if not token:
        raise RuntimeError(
            "No auth: set ANTHROPIC_AUTH_TOKEN or run 'claude setup-token'"
        )
    import logging

    logging.getLogger(__name__).info(
        "Anthropic client: token_len=%d prefix=%s has_newline=%s sdk=%s",
        len(token),
        token[:12] + "...",
        repr("\n" in token),
        anthropic.__version__,
    )
    return anthropic.Anthropic(
        api_key=None,
        auth_token=token,
        default_headers={"anthropic-beta": "oauth-2025-04-20"},
    )


def call_claude(
    system_prompt: str,
    user_prompt: str,
    model: str = ANTHROPIC_MODEL,
    max_tokens: int = 8192,
    tools: list[dict[str, Any]] | None = None,
    tool_executor: ToolExecutor | None = None,
    max_iterations: int = 25,
) -> ClaudeResult:
    """Call Claude. One-shot when tools is None, agentic loop when tools is provided.

    The agentic loop appends every assistant turn (including tool_use blocks)
    to messages, executes tools via tool_executor.execute, appends a tool_result
    user turn, and re-calls until Claude stops requesting tools or we hit
    max_iterations.
    """
    import logging

    log = logging.getLogger(__name__)
    log.info(
        "call_claude: model=%s max_tokens=%d system_len=%d user_len=%d tools=%s",
        model,
        max_tokens,
        len(system_prompt),
        len(user_prompt),
        len(tools) if tools else 0,
    )

    if tools is not None and tool_executor is None:
        raise ValueError("tool_executor is required when tools is provided")

    client = _get_client()
    start = time.monotonic()

    messages: list[dict[str, Any]] = [{"role": "user", "content": user_prompt}]
    aggregate = ClaudeResult(
        raw_output="",
        tokens_in=0,
        tokens_out=0,
        duration_ms=0,
        model=model,
        turns=0,
    )
    text_chunks: list[str] = []

    for iteration in range(max_iterations):
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools

        try:
            response = client.messages.create(**kwargs)
        except Exception as e:
            log.error("Claude API error: %s", e)
            log.error("system_prompt[:200]: %s", system_prompt[:200])
            log.error("iteration: %d, turns so far: %d", iteration, aggregate.turns)
            raise

        aggregate.turns += 1
        aggregate.tokens_in += response.usage.input_tokens
        aggregate.tokens_out += response.usage.output_tokens
        cache_create = getattr(response.usage, "cache_creation_input_tokens", 0) or 0
        cache_read = getattr(response.usage, "cache_read_input_tokens", 0) or 0
        aggregate.cache_creation += cache_create
        aggregate.cache_read += cache_read

        # Collect text from this turn
        turn_text_parts: list[str] = []
        tool_use_blocks: list[Any] = []
        for block in response.content:
            if block.type == "text":
                turn_text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_use_blocks.append(block)
        turn_text = "\n".join(turn_text_parts)
        if turn_text:
            text_chunks.append(turn_text)

        # No tool requested OR no tools available — done
        if not tools or response.stop_reason != "tool_use" or not tool_use_blocks:
            aggregate.raw_output = "\n".join(text_chunks)
            aggregate.duration_ms = int((time.monotonic() - start) * 1000)
            return aggregate

        # Append assistant turn verbatim (including tool_use blocks) so the
        # API can match tool_use_ids on the next user turn.
        messages.append({"role": "assistant", "content": response.content})

        # Execute every tool the model requested in this turn
        tool_results: list[dict[str, Any]] = []
        for tu in tool_use_blocks:
            assert tool_executor is not None  # narrowed by the tools check above
            try:
                result = tool_executor.execute(tu.name, dict(tu.input))
            except Exception as e:  # belt-and-suspenders — execute() shouldn't raise
                result = {"error": f"tool crashed: {e}"}
            aggregate.tool_calls.append(
                {"name": tu.name, "input": dict(tu.input), "result_keys": list(result.keys())}
            )
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": _format_tool_result(result),
                    "is_error": "error" in result,
                }
            )

        messages.append({"role": "user", "content": tool_results})

    # Hit the iteration cap. Return whatever we have.
    log.warning(
        "call_claude: hit max_iterations=%d. tokens_in=%d tokens_out=%d",
        max_iterations,
        aggregate.tokens_in,
        aggregate.tokens_out,
    )
    aggregate.raw_output = "\n".join(text_chunks)
    aggregate.duration_ms = int((time.monotonic() - start) * 1000)
    return aggregate


def _format_tool_result(result: dict[str, Any]) -> str:
    """Convert a tool result dict to the string Claude sees as the tool_result content.

    Tool results in the API can be a string or list of content blocks. We use a
    JSON-ish string so Claude can parse keys (`content`, `matches`, `error`, etc.).
    """
    import json

    try:
        return json.dumps(result, default=str)
    except (TypeError, ValueError):
        return repr(result)
