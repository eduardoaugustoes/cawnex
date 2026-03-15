"""Anthropic API client wrapper."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

import anthropic

from worker.config import ANTHROPIC_MODEL


@dataclass
class ClaudeResult:
    raw_output: str
    tokens_in: int
    tokens_out: int
    duration_ms: int
    model: str


def _get_client() -> anthropic.Anthropic:
    """Create Anthropic client with OAuth token."""
    token = (
        os.environ.get("ANTHROPIC_AUTH_TOKEN")
        or os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
        or ""
    )
    if not token:
        raise RuntimeError(
            "No auth: set ANTHROPIC_AUTH_TOKEN or run 'claude setup-token'"
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
) -> ClaudeResult:
    """Call Claude API. Measures duration internally."""
    client = _get_client()
    start = time.monotonic()

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    duration_ms = int((time.monotonic() - start) * 1000)
    text = "\n".join(b.text for b in response.content if b.type == "text")

    return ClaudeResult(
        raw_output=text,
        tokens_in=response.usage.input_tokens,
        tokens_out=response.usage.output_tokens,
        duration_ms=duration_ms,
        model=model,
    )
