"""Anthropic API client for council advisor calls."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

import anthropic

from council.config import ANTHROPIC_AUTH_SECRET_ARN, ANTHROPIC_MODEL

_cached_token: str | None = None


@dataclass
class ClaudeResult:
    content: str
    tokens_in: int
    tokens_out: int
    duration_ms: int


def _get_token() -> str:
    global _cached_token
    if _cached_token:
        return _cached_token

    token = os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get(
        "CLAUDE_CODE_OAUTH_TOKEN"
    )
    if token:
        _cached_token = token
        return token

    if ANTHROPIC_AUTH_SECRET_ARN:
        import boto3

        client = boto3.client("secretsmanager")
        resp = client.get_secret_value(SecretId=ANTHROPIC_AUTH_SECRET_ARN)
        _cached_token = resp["SecretString"]
        return _cached_token  # type: ignore[return-value]

    raise RuntimeError("No Anthropic auth token found")


def call_claude(
    system: str,
    user: str,
    model: str = ANTHROPIC_MODEL,
    max_tokens: int = 1024,
) -> ClaudeResult:
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
