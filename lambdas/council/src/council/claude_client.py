"""Anthropic streaming + tool-use loop for advisor investigations."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import anthropic

logger = logging.getLogger("council.claude_client")


@dataclass
class ToolUseResult:
    final_vote: dict[str, Any] | None
    terminated_by: str  # submit_vote | call_cap | time_cap | api_error | no_tool_call
    tool_calls_made: int
    tokens_consumed: int
    trace_entries: list[dict[str, Any]] = field(default_factory=list)


SUBMIT_VOTE_TOOL: dict[str, Any] = {
    "name": "submit_vote",
    "description": (
        "Submit your final vote on this wave. Call this exactly once to finish."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "vote": {
                "type": "string",
                "enum": [
                    "approve",
                    "approve_with_condition",
                    "abstain",
                    "block",
                ],
            },
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "reasoning": {"type": "string"},
            "blockers": {"type": "array", "items": {"type": "string"}},
            "condition": {"type": "string"},
            "cited_evidence": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string"},
                        "line_range": {
                            "type": "array",
                            "items": {"type": "integer"},
                        },
                        "pr_number": {"type": "integer"},
                        "reason": {"type": "string"},
                    },
                },
            },
        },
        "required": ["vote", "confidence", "reasoning"],
    },
}


async def run_tool_use_loop(
    system_prompt: str,
    user_message: str,
    tools: list[dict[str, Any]],
    max_tool_calls: int,
    wall_clock_seconds: int,
    tool_executor: Callable[[str, dict[str, Any]], dict[str, Any]],
    model: str = "claude-haiku-4-5-20251001",
) -> ToolUseResult:
    """Run an advisor's tool-use loop against Anthropic. Returns ToolUseResult."""
    full_tools = tools + [SUBMIT_VOTE_TOOL]
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]
    tool_calls_made = 0
    tokens_in = 0
    tokens_out = 0
    trace_entries: list[dict[str, Any]] = []
    start = time.time()

    client = anthropic.AsyncAnthropic()

    while True:
        elapsed = time.time() - start
        if elapsed > wall_clock_seconds:
            return ToolUseResult(
                final_vote=None,
                terminated_by="time_cap",
                tool_calls_made=tool_calls_made,
                tokens_consumed=tokens_in + tokens_out,
                trace_entries=trace_entries,
            )

        try:
            async with client.messages.stream(
                model=model,
                max_tokens=4000,
                system=system_prompt,
                tools=full_tools,
                messages=messages,
            ) as stream:
                tool_use_blocks: list[dict[str, Any]] = []
                async for event in stream:
                    if (
                        getattr(event, "type", None) == "content_block_start"
                        and getattr(event.content_block, "type", None) == "tool_use"
                    ):
                        tool_use_blocks.append(
                            {
                                "id": event.content_block.id,
                                "name": event.content_block.name,
                                "input": event.content_block.input,
                            }
                        )
                final_msg = await stream.get_final_message()
                tokens_in += final_msg.usage.input_tokens
                tokens_out += final_msg.usage.output_tokens
        except anthropic.APIError as e:
            logger.error(
                json.dumps(
                    {
                        "event": "advisor_api_error",
                        "error_class": type(e).__name__,
                        "message": str(e)[:200],
                    }
                )
            )
            return ToolUseResult(
                final_vote=None,
                terminated_by="api_error",
                tool_calls_made=tool_calls_made,
                tokens_consumed=tokens_in + tokens_out,
                trace_entries=trace_entries,
            )

        if not tool_use_blocks:
            return ToolUseResult(
                final_vote=None,
                terminated_by="no_tool_call",
                tool_calls_made=tool_calls_made,
                tokens_consumed=tokens_in + tokens_out,
                trace_entries=trace_entries,
            )

        for block in tool_use_blocks:
            if block["name"] == "submit_vote":
                return ToolUseResult(
                    final_vote=block["input"],
                    terminated_by="submit_vote",
                    tool_calls_made=tool_calls_made,
                    tokens_consumed=tokens_in + tokens_out,
                    trace_entries=trace_entries,
                )

        tool_results: list[dict[str, Any]] = []
        for block in tool_use_blocks:
            tool_calls_made += 1
            if tool_calls_made > max_tool_calls:
                return ToolUseResult(
                    final_vote=None,
                    terminated_by="call_cap",
                    tool_calls_made=tool_calls_made,
                    tokens_consumed=tokens_in + tokens_out,
                    trace_entries=trace_entries,
                )

            tool_start = time.time()
            result = tool_executor(block["name"], block["input"])
            duration_ms = int((time.time() - tool_start) * 1000)

            result_str = json.dumps(result)[:5000]
            trace_entries.append(
                {
                    "tool_name": block["name"],
                    "args": block["input"],
                    "result_summary": result_str[:200],
                    "duration_ms": duration_ms,
                    "error": result.get("tool_error") or result.get("error"),
                }
            )

            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block["id"],
                    "content": result_str,
                }
            )

        messages.append(
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": b["id"],
                        "name": b["name"],
                        "input": b["input"],
                    }
                    for b in tool_use_blocks
                ],
            }
        )
        messages.append({"role": "user", "content": tool_results})
