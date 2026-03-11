"""Subscription relay runner — uses Claude Code CLI as the agent runtime.

Instead of making API calls with an API key, this spawns Claude Code
as a subprocess. The user's Claude Max subscription covers all token costs.

Claude Code in --print mode with --output-format stream-json gives us:
- Structured JSON output per event
- Tool use (filesystem, shell, git) built-in
- Token tracking + cost tracking
- Session management
- No API key needed — uses the logged-in subscription

This is the BYOL "subscription_relay" mode.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cawnex_worker.crows.runner import CrowResult


class SubscriptionRunner:
    """Runs a crow using Claude Code CLI subprocess (Max subscription).

    Instead of anthropic.AsyncAnthropic, spawns:
      claude --print --output-format stream-json --allowedTools "Bash,Edit,Read,Write" ...

    Advantages:
    - No API key required
    - Unlimited tokens (Max subscription)
    - Claude Code's built-in tools (better than our custom ones)
    - Built-in file editing, bash, git operations
    - Cost is $0 per execution (flat subscription)

    The tradeoff is less granular control vs the SDK runner,
    but for most agent tasks this is sufficient and much cheaper.
    """

    CLAUDE_CMD = "npx"
    CLAUDE_ARGS = ["@anthropic-ai/claude-code"]

    def __init__(self, claude_cmd: str | None = None) -> None:
        """Initialize the subscription runner.

        Args:
            claude_cmd: Override for the claude CLI command.
                       Default uses npx @anthropic-ai/claude-code.
        """
        if claude_cmd:
            self.CLAUDE_CMD = claude_cmd
            self.CLAUDE_ARGS = []

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
        on_event: Any = None,
    ) -> CrowResult:
        """Run a crow via Claude Code subprocess.

        Same interface as CrowRunner.run() for drop-in replacement.
        """
        result = CrowResult()
        start = time.monotonic()

        # Map tool packs to Claude Code tool names
        allowed_tools = self._resolve_tools(tool_packs or ["filesystem", "shell", "git"])

        # Build the full prompt with system context
        full_prompt = f"{system_prompt}\n\n---\n\n{task_brief}"

        # Build command
        cmd = [self.CLAUDE_CMD] + self.CLAUDE_ARGS + [
            "--print",
            "--verbose",
            "--output-format", "stream-json",
            "--no-session-persistence",
            "--model", model,
            "--allowedTools", ",".join(allowed_tools),
            "-p", full_prompt,
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workspace,
            )

            # Read streaming JSON output
            events: list[dict] = []
            stdout_data = b""

            async for line in process.stdout:
                stdout_data += line
                line_str = line.decode().strip()
                if not line_str:
                    continue

                try:
                    event = json.loads(line_str)
                    events.append(event)

                    # Stream events to callback if provided
                    if on_event:
                        await on_event(event)

                    # Extract result from final event
                    if event.get("type") == "result":
                        result.content = event.get("result", "")
                        result.success = not event.get("is_error", False)

                        # Extract usage
                        usage = event.get("usage", {})
                        result.tokens_input = usage.get("input_tokens", 0)
                        result.tokens_output = usage.get("output_tokens", 0)

                        # Cost is 0 for subscription mode
                        result.cost_usd = event.get("total_cost_usd", 0.0)

                    # Count tool uses
                    if event.get("type") == "assistant" and event.get("subtype") == "tool_use":
                        result.tool_calls += 1

                except json.JSONDecodeError:
                    # Non-JSON output (stderr leaking, etc.)
                    pass

            await process.wait()

            if process.returncode != 0 and not result.content:
                stderr = (await process.stderr.read()).decode()
                result.error = f"Claude Code exited with code {process.returncode}: {stderr[:500]}"
                result.success = False

            result.events = events

        except FileNotFoundError:
            result.error = "Claude Code CLI not found. Install with: npm install -g @anthropic-ai/claude-code"
            result.success = False
        except Exception as e:
            result.error = f"Subprocess error: {e}"
            result.success = False

        result.duration_seconds = time.monotonic() - start
        return result

    def _resolve_tools(self, tool_packs: list[str]) -> list[str]:
        """Map Cawnex tool packs to Claude Code built-in tool names."""
        tool_map = {
            "filesystem": ["Read", "Write", "Edit", "MultiEdit"],
            "shell": ["Bash"],
            "git": ["Bash"],  # Git ops via bash
            "github": ["Bash"],  # GitHub CLI via bash
            "web_search": ["WebSearch", "WebFetch"],
        }

        tools = set()
        for pack in tool_packs:
            tools.update(tool_map.get(pack, []))

        return sorted(tools) if tools else ["Read", "Write", "Edit", "Bash"]


class HybridRunner:
    """Smart runner that picks API key or subscription based on config.

    Tries subscription first (cheaper), falls back to API key.
    """

    def __init__(
        self,
        api_key: str | None = None,
        use_subscription: bool = False,
        claude_cmd: str | None = None,
    ) -> None:
        self.api_key = api_key
        self.use_subscription = use_subscription

        if use_subscription:
            self._runner = SubscriptionRunner(claude_cmd=claude_cmd)
        elif api_key:
            from cawnex_worker.crows.runner import CrowRunner
            self._runner = CrowRunner(api_key=api_key)
        else:
            raise ValueError("Either api_key or use_subscription must be set")

    async def run(self, **kwargs) -> CrowResult:
        return await self._runner.run(**kwargs)
