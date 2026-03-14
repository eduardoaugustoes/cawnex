"""Subscription provider — uses Claude Code CLI subprocess for Max subscription users."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator

from cawnex_providers.base import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class SubscriptionProvider(LLMProvider):
    """Claude Max subscription provider — runs via Claude Code CLI subprocess.

    No API key needed. Uses the logged-in Claude session on the machine.
    Cost: $0 per call (covered by Max subscription).
    """

    # Claude CLI command — try bare 'claude' first, fallback to npx
    _CLI_COMMANDS = [
        ["claude"],
        ["npx", "@anthropic-ai/claude-code"],
    ]

    def __init__(self, model: str = "claude-sonnet-4-6") -> None:
        self._default_model = model
        self._cli_cmd: list[str] | None = None  # resolved lazily

    async def _resolve_cli(self) -> list[str]:
        """Find a working Claude CLI command."""
        if self._cli_cmd is not None:
            return self._cli_cmd

        for cmd in self._CLI_COMMANDS:
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd, "--version",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await asyncio.wait_for(proc.communicate(), timeout=15)
                if proc.returncode == 0:
                    self._cli_cmd = cmd
                    return cmd
            except (FileNotFoundError, asyncio.TimeoutError):
                continue

        raise RuntimeError(
            "Claude CLI not found. Install with: npm install -g @anthropic-ai/claude-code"
        )

    async def complete(
        self,
        *,
        model: str | None = None,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Run a completion via claude --print subprocess."""
        cli = await self._resolve_cli()
        prompt = self._build_prompt(system, messages)

        cmd = [
            *cli, "--print",
            "--output-format", "text",
            "--model", model or self._default_model,
            "--max-turns", "1",
            "-p", prompt,
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=120
            )
        except asyncio.TimeoutError:
            raise RuntimeError("Claude CLI timed out after 120s")

        if proc.returncode != 0:
            err = stderr.decode().strip() if stderr else "unknown error"
            raise RuntimeError(f"Claude CLI failed (code {proc.returncode}): {err}")

        content = stdout.decode().strip()

        return LLMResponse(
            content=content,
            stop_reason="end_turn",
            model=model or self._default_model,
        )

    async def stream(
        self,
        *,
        model: str | None = None,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 4096,
    ) -> AsyncIterator[dict]:
        """Stream via claude --print --output-format stream-json subprocess."""
        cli = await self._resolve_cli()
        prompt = self._build_prompt(system, messages)

        cmd = [
            *cli, "--print",
            "--output-format", "stream-json",
            "--model", model or self._default_model,
            "--max-turns", "1",
            "-p", prompt,
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        async for line in proc.stdout:
            line = line.decode().strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                event_type = event.get("type", "")

                if event_type == "assistant" and "message" in event:
                    # Content delta
                    msg = event["message"]
                    if isinstance(msg, str):
                        yield {"type": "content_block_delta", "data": _TextDelta(msg)}
                elif event_type == "result":
                    # Final result
                    text = event.get("result", "")
                    if text:
                        yield {"type": "content_block_delta", "data": _TextDelta(text)}
                    yield {"type": "message_stop", "data": None}
            except json.JSONDecodeError:
                continue

        await proc.wait()

    async def validate_key(self) -> bool:
        """Check if claude CLI is available and logged in."""
        try:
            await self._resolve_cli()
            return True
        except Exception:
            return False

    def estimate_cost(self, tokens_input: int, tokens_output: int, model: str) -> float:
        """Subscription mode = $0 per call."""
        return 0.0

    @staticmethod
    def _build_prompt(system: str, messages: list[dict]) -> str:
        """Flatten system + messages into a single prompt string for --print mode."""
        parts = []
        if system:
            parts.append(f"<system>\n{system}\n</system>\n")

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                parts.append(f"<user>\n{content}\n</user>")
            elif role == "assistant":
                parts.append(f"<assistant>\n{content}\n</assistant>")

        return "\n".join(parts)


class _TextDelta:
    """Mimics the Anthropic SDK delta object for compatibility with stream consumers."""
    def __init__(self, text: str):
        self.delta = _DeltaContent(text)


class _DeltaContent:
    def __init__(self, text: str):
        self.text = text
