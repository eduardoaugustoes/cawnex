"""Crow runner — executes a single agent using Claude SDK's BetaAsyncToolRunner.

This is the core execution engine. Each crow:
1. Gets a system prompt + task brief
2. Receives tools based on its tool_packs
3. Runs the agent loop via BetaAsyncToolRunner.until_done()
4. Reports results + cost back to the orchestrator
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

import anthropic
from anthropic.lib.tools import (
    BetaAsyncToolRunner,
    BetaFunctionTool,
)

from cawnex_worker.tools.filesystem import ReadFile, WriteFile, ListDirectory, SearchFiles
from cawnex_worker.tools.shell import RunCommand
from cawnex_worker.tools.git import GitStatus, GitDiff, GitCommit, GitPush


# Tool packs — map pack names to tool instances
TOOL_PACKS: dict[str, list] = {
    "filesystem": [ReadFile, WriteFile, ListDirectory, SearchFiles],
    "shell": [RunCommand],
    "git": [GitStatus, GitDiff, GitCommit, GitPush],
}


@dataclass
class CrowResult:
    """Result of a crow execution."""
    content: str = ""
    tokens_input: int = 0
    tokens_output: int = 0
    cost_usd: float = 0.0
    duration_seconds: float = 0.0
    tool_calls: int = 0
    success: bool = True
    error: str | None = None
    events: list[dict] = field(default_factory=list)


class CrowRunner:
    """Runs a single crow (agent) using Claude's BetaAsyncToolRunner.

    The runner:
    - Builds the tool set from tool_packs
    - Injects the workspace path into all tool calls
    - Runs the agentic loop until the model stops calling tools
    - Tracks tokens, cost, and execution events
    """

    # Pricing per 1M tokens
    PRICING = {
        "claude-opus-4-6": {"input": 15.0, "output": 75.0},
        "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
        "claude-haiku-4-6": {"input": 0.80, "output": 4.0},
    }

    def __init__(self, api_key: str) -> None:
        self.client = anthropic.AsyncAnthropic(api_key=api_key)

    async def run(
        self,
        *,
        system_prompt: str,
        task_brief: str,
        model: str = "claude-sonnet-4-6",
        tool_packs: list[str] | None = None,
        workspace: str = ".",
        max_tokens: int = 16000,
        max_iterations: int = 50,
        on_event: Any = None,  # callback(event_dict) for streaming to Redis
    ) -> CrowResult:
        """Run the crow agent loop.

        Args:
            system_prompt: Agent's system prompt (personality + constraints).
            task_brief: The task to accomplish (user message).
            model: Claude model to use.
            tool_packs: List of tool pack names to enable.
            workspace: Path to the agent's working directory (nest).
            max_tokens: Max tokens per model response.
            max_iterations: Max tool-use iterations before stopping.
            on_event: Optional async callback for streaming events.
        """
        result = CrowResult()
        start = time.monotonic()

        # Build tools from packs
        tools = []
        for pack_name in (tool_packs or ["filesystem"]):
            pack_tools = TOOL_PACKS.get(pack_name, [])
            tools.extend(pack_tools)

        if not tools:
            result.error = "No tools configured"
            result.success = False
            return result

        # Build the initial message
        messages = [{"role": "user", "content": task_brief}]

        try:
            # Use the SDK's BetaAsyncToolRunner for the agent loop
            runner = BetaAsyncToolRunner(
                params={
                    "model": model,
                    "max_tokens": max_tokens,
                    "system": system_prompt,
                    "messages": messages,
                },
                options={},
                tools=tools,
                client=self.client,
                max_iterations=max_iterations,
            )

            # Run until the model is done (no more tool calls)
            response = await runner.until_done()

            # Extract final content
            for block in response.content:
                if hasattr(block, "text"):
                    result.content += block.text

            # Aggregate token usage from all iterations
            # The runner tracks messages internally
            result.tokens_input = response.usage.input_tokens
            result.tokens_output = response.usage.output_tokens

            # Estimate cost
            pricing = self.PRICING.get(model, self.PRICING["claude-sonnet-4-6"])
            result.cost_usd = (
                result.tokens_input * pricing["input"] / 1_000_000
                + result.tokens_output * pricing["output"] / 1_000_000
            )

            # Count tool calls from message history
            for msg in runner._params.get("messages", []):
                if isinstance(msg, dict) and msg.get("role") == "assistant":
                    content = msg.get("content", [])
                    if isinstance(content, list):
                        result.tool_calls += sum(
                            1 for c in content
                            if isinstance(c, dict) and c.get("type") == "tool_use"
                        )

        except anthropic.APIError as e:
            result.error = f"API error: {e}"
            result.success = False
        except Exception as e:
            result.error = f"Execution error: {e}"
            result.success = False

        result.duration_seconds = time.monotonic() - start
        return result
