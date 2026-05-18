"""Anthropic API client wrapper.

Two modes:

* **One-shot** (`tools=None`) — single `messages.create` + assembled text.
  Preserved for planner / reviewer / fixer crows whose JSON output fits in
  one response without needing tools.

* **Agentic loop** (`tools=[...]` + `tool_executor`) — loops `messages.create`,
  executes worktree tools (read_file/glob_files/etc), and re-prompts until
  either (a) Claude stops requesting tools OR (b) Claude calls the special
  `submit_result` terminator tool. The terminator tool's `input` is captured
  verbatim as `ClaudeResult.structured_output` — guaranteed valid JSON
  matching the schema, parsed server-side by the API. This kills the entire
  "Haiku writes prose instead of JSON" class of bug because the API rejects
  malformed structured tool input before it ever reaches us.

Defenses against token-budget failures, layered:

* **`count_tokens` precheck** — before every API call, ask the API how many
  tokens the request will cost. If it exceeds the model's context window
  minus a safety cushion, raise InputTooLarge with diagnostic info instead
  of paying for a request the API would reject anyway.
* **Dynamic max_tokens** — derive the per-call output ceiling from
  `model_context_window - count_tokens_input - safety_cushion`. Even if the
  caller passes a generous ceiling, we cap to what the API will actually
  honor.
* **Truncation flag** — `stop_reason == "max_tokens"` sets
  `ClaudeResult.truncated`, so callers can distinguish "ran out of room"
  from "produced empty output".
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

import anthropic

from worker.config import (
    ANTHROPIC_MODEL,
    CONTEXT_SAFETY_CUSHION_TOKENS,
    context_window,
    max_output_tokens,
)

# Reserved tool name that terminates the agentic loop. Claude calling it is
# equivalent to "I'm done — here's the structured output." The loop captures
# `tool_use.input` (which the API has already validated against the schema)
# and returns it as ClaudeResult.structured_output.
SUBMIT_RESULT_TOOL_NAME = "submit_result"

# The Anthropic SDK refuses non-streaming requests when generation could
# exceed 10 minutes. Haiku 4.5 generates roughly ~100 tok/sec, so anything
# at or above ~16K max_tokens trips the guard. Switch to streaming above
# this threshold; small one-shot calls keep using messages.create which
# is simpler and avoids the SSE overhead.
STREAM_THRESHOLD_TOKENS = 16_000


class InputTooLarge(RuntimeError):
    """Raised when the proposed request exceeds the model's context budget.

    Carries enough diagnostic info that the executor can fail the crow with a
    precise reason rather than waiting for the API to 4xx.
    """

    def __init__(
        self,
        input_tokens: int,
        budget: int,
        model: str,
        turns_so_far: int,
        message_count: int,
    ) -> None:
        self.input_tokens = input_tokens
        self.budget = budget
        self.model = model
        self.turns_so_far = turns_so_far
        self.message_count = message_count
        super().__init__(
            f"input tokens={input_tokens} exceeds budget {budget} "
            f"(model={model}, turns={turns_so_far}, messages={message_count})"
        )


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
    truncated: bool = False
    # Populated when Claude terminates the loop by calling submit_result.
    # The dict is validated server-side against the tool's input_schema,
    # so it's guaranteed to be a parseable JSON object with the required
    # keys. Preferred over raw_output for structured-output crows.
    structured_output: dict[str, Any] | None = None


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


def _compute_safe_max_tokens(
    model: str, input_token_count: int, caller_max: int
) -> int:
    """Cap caller_max to what the API will honor for the remaining headroom.

    Returns the smaller of:
      * caller_max (the executor's intent)
      * the model's published max output tokens
      * remaining context headroom (window - input - safety cushion)
    """
    headroom = context_window(model) - input_token_count - CONTEXT_SAFETY_CUSHION_TOKENS
    if headroom < 1:
        # Caller will see this via the InputTooLarge raise — keep at least 1
        # so this helper never produces a non-positive max_tokens.
        return 1
    return max(1, min(caller_max, max_output_tokens(model), headroom))


def call_claude(
    system_prompt: str,
    user_prompt: str,
    model: str = ANTHROPIC_MODEL,
    max_tokens: int = 8192,
    tools: list[dict[str, Any]] | None = None,
    tool_executor: ToolExecutor | None = None,
    max_iterations: int = 25,
    force_terminator_tool: str | None = None,
) -> ClaudeResult:
    """Call Claude. One-shot when tools is None, agentic loop when tools is provided.

    The loop terminates when one of:
      1. Claude calls the `submit_result` terminator tool (structured output).
      2. stop_reason != "tool_use" (Claude has no more tools to call).
      3. max_iterations reached.

    When `force_terminator_tool` is set, the API is told the model MUST call
    some tool every turn (`tool_choice={"type": "any"}`). Combined with the
    presence of the terminator tool in `tools`, this makes "prose instead of
    JSON" impossible: the model either calls a read tool to keep exploring,
    or calls the terminator with server-validated structured output.

    Each iteration counts input tokens before sending; if the input would
    exceed the model's window, InputTooLarge is raised with diagnostics.
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

    # tool_executor is only needed when the model might call non-terminator
    # tools. Terminator-only crows (planner, reviewer) pass tools=[terminator]
    # with no executor — the loop catches submit_result before it would ever
    # try to execute anything else.
    has_non_terminator_tools = bool(
        tools and any(t.get("name") != SUBMIT_RESULT_TOOL_NAME for t in tools)
    )
    if has_non_terminator_tools and tool_executor is None:
        raise ValueError(
            "tool_executor is required when tools include non-terminator tools"
        )

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
        # Layer 1: count input tokens before sending so we never submit a
        # request the API will reject for context overflow.
        try:
            count_kwargs: dict[str, Any] = {
                "model": model,
                "system": system_prompt,
                "messages": messages,
            }
            if tools:
                count_kwargs["tools"] = tools
            token_count = client.messages.count_tokens(**count_kwargs)
            input_tokens = int(token_count.input_tokens)
        except Exception as e:
            # count_tokens is advisory — if it fails we still try the request
            # rather than block the crow on a flaky precheck.
            log.warning("count_tokens failed (proceeding anyway): %s", e)
            input_tokens = 0

        budget = context_window(model) - CONTEXT_SAFETY_CUSHION_TOKENS - max_tokens
        if input_tokens > 0 and input_tokens > budget:
            log.error(
                "InputTooLarge: input=%d budget=%d (window=%d cushion=%d max_tokens=%d)",
                input_tokens,
                budget,
                context_window(model),
                CONTEXT_SAFETY_CUSHION_TOKENS,
                max_tokens,
            )
            raise InputTooLarge(
                input_tokens=input_tokens,
                budget=budget,
                model=model,
                turns_so_far=aggregate.turns,
                message_count=len(messages),
            )

        # Layer 2: derive a max_tokens that fits the remaining headroom.
        # Even if the caller passed 64k but the input is huge, we shrink to
        # what the window can actually accept.
        effective_max_tokens = (
            _compute_safe_max_tokens(model, input_tokens, max_tokens)
            if input_tokens > 0
            else max_tokens
        )

        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": effective_max_tokens,
            "system": system_prompt,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
            # Force "must call some tool" when the caller wants a terminator-
            # guaranteed result. Cannot pin to the terminator specifically —
            # the model needs to be free to call read tools first — but "any"
            # eliminates the "wrote prose, no tool" failure mode entirely.
            if force_terminator_tool:
                kwargs["tool_choice"] = {"type": "any"}

        # The Anthropic SDK refuses non-streaming requests when the model
        # might take longer than 10 minutes to respond — which Haiku 4.5 can
        # exceed once max_tokens >= ~16K. Stream for large outputs and
        # collect via get_final_message(). The resulting Message has the
        # same shape as a non-streaming response, so downstream code is
        # unchanged.
        should_stream = effective_max_tokens >= STREAM_THRESHOLD_TOKENS
        try:
            if should_stream:
                with client.messages.stream(**kwargs) as stream:
                    response = stream.get_final_message()
            else:
                response = client.messages.create(**kwargs)
        except Exception as e:
            log.error("Claude API error: %s", e)
            log.error("system_prompt[:200]: %s", system_prompt[:200])
            log.error(
                "iteration: %d, turns so far: %d, input_tokens=%d, max_tokens=%d, streamed=%s",
                iteration,
                aggregate.turns,
                input_tokens,
                effective_max_tokens,
                should_stream,
            )
            raise

        aggregate.turns += 1
        aggregate.tokens_in += response.usage.input_tokens
        aggregate.tokens_out += response.usage.output_tokens
        cache_create = getattr(response.usage, "cache_creation_input_tokens", 0) or 0
        cache_read = getattr(response.usage, "cache_read_input_tokens", 0) or 0
        aggregate.cache_creation += cache_create
        aggregate.cache_read += cache_read

        # Collect text + tool_use blocks from this turn.
        turn_text_parts: list[str] = []
        tool_use_blocks: list[Any] = []
        submit_block: Any = None
        for block in response.content:
            if block.type == "text":
                turn_text_parts.append(block.text)
            elif block.type == "tool_use":
                if block.name == SUBMIT_RESULT_TOOL_NAME:
                    submit_block = block
                else:
                    tool_use_blocks.append(block)
        turn_text = "\n".join(turn_text_parts)
        if turn_text:
            text_chunks.append(turn_text)

        # Terminator: Claude called submit_result. Capture its (server-validated)
        # input as the structured output and stop.
        if submit_block is not None:
            aggregate.structured_output = dict(submit_block.input)
            aggregate.raw_output = "\n".join(text_chunks)
            aggregate.duration_ms = int((time.monotonic() - start) * 1000)
            aggregate.truncated = response.stop_reason == "max_tokens"
            aggregate.tool_calls.append(
                {
                    "name": submit_block.name,
                    "input_keys": sorted(dict(submit_block.input).keys()),
                    "result_keys": ["__terminator__"],
                }
            )
            return aggregate

        # No tool requested OR no tools available — done
        if not tools or response.stop_reason != "tool_use" or not tool_use_blocks:
            aggregate.raw_output = "\n".join(text_chunks)
            aggregate.duration_ms = int((time.monotonic() - start) * 1000)
            aggregate.truncated = response.stop_reason == "max_tokens"
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
