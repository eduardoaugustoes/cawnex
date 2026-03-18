"""Anthropic API client for the Monarch Lambda."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

import anthropic

from monarch.config import ANTHROPIC_AUTH_SECRET_ARN, ANTHROPIC_MODEL


@dataclass
class ClaudeResult:
    content: str
    tokens_in: int
    tokens_out: int
    duration_ms: int


_cached_token: str = ""


def _get_token() -> str:
    global _cached_token
    if _cached_token:
        return _cached_token

    token = (
        os.environ.get("ANTHROPIC_AUTH_TOKEN")
        or os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
        or ""
    ).strip()
    if token:
        _cached_token = token
        return token

    if ANTHROPIC_AUTH_SECRET_ARN:
        import boto3

        client = boto3.client("secretsmanager")
        resp = client.get_secret_value(SecretId=ANTHROPIC_AUTH_SECRET_ARN)
        token = str(resp["SecretString"]).strip()
        _cached_token = token
        return token

    raise RuntimeError("No auth: set ANTHROPIC_AUTH_TOKEN or ANTHROPIC_AUTH_SECRET_ARN")


def call_claude(
    system: str,
    user: str,
    model: str = ANTHROPIC_MODEL,
    max_tokens: int = 2048,
) -> ClaudeResult:
    """Call Claude with a system prompt and single user message."""
    token = _get_token()
    client = anthropic.Anthropic(
        api_key=None,
        auth_token=token,
        default_headers={"anthropic-beta": "oauth-2025-04-20"},
    )
    start = time.monotonic()
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    duration_ms = int((time.monotonic() - start) * 1000)
    content = "\n".join(b.text for b in response.content if b.type == "text")
    return ClaudeResult(
        content=content,
        tokens_in=response.usage.input_tokens,
        tokens_out=response.usage.output_tokens,
        duration_ms=duration_ms,
    )
