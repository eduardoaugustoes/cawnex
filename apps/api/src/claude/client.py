"""Claude API client for the Cawnex API Lambda."""

import os
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List

import anthropic
from anthropic.types import MessageParam

# Pricing per 1M tokens (USD)
PRICING: Dict[str, Dict[str, float]] = {
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00},
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
}

DEFAULT_MODEL = "claude-haiku-4-5-20251001"


@dataclass
class ChatResult:
    """Result from a Claude API call."""

    content: str
    tokens_in: int
    tokens_out: int
    duration_ms: int
    model: str
    cost_usd: Decimal


def calculate_cost(model: str, tokens_in: int, tokens_out: int) -> Decimal:
    """Calculate cost in USD for a Claude API call."""
    prices = PRICING.get(model, PRICING[DEFAULT_MODEL])
    raw = (tokens_in * prices["input"] + tokens_out * prices["output"]) / 1_000_000
    return Decimal(str(round(raw, 6)))


_cached_token: str = ""


def _get_token() -> str:
    """Get Anthropic OAuth token from env or Secrets Manager."""
    global _cached_token
    if _cached_token:
        return _cached_token

    # Try direct env var first (local dev)
    token = os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get(
        "CLAUDE_CODE_OAUTH_TOKEN", ""
    )
    if token:
        _cached_token = token
        return token

    # Fall back to Secrets Manager (Lambda runtime)
    secret_arn = os.environ.get("ANTHROPIC_AUTH_SECRET_ARN", "")
    if secret_arn:
        import boto3

        client = boto3.client("secretsmanager")
        resp = client.get_secret_value(SecretId=secret_arn)
        token = str(resp["SecretString"])  # Explicit string cast for mypy
        _cached_token = token
        return token

    raise RuntimeError("No auth: set ANTHROPIC_AUTH_TOKEN or ANTHROPIC_AUTH_SECRET_ARN")


def _get_client() -> anthropic.Anthropic:
    """Create Anthropic client with OAuth token."""
    return anthropic.Anthropic(
        api_key=None,
        auth_token=_get_token(),
        default_headers={"anthropic-beta": "oauth-2025-04-20"},
    )


def chat(
    system: str,
    messages: List[MessageParam],
    model: str = DEFAULT_MODEL,
    max_tokens: int = 2048,
) -> ChatResult:
    """Call Claude with a system prompt and message history."""
    client = _get_client()
    start = time.monotonic()

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=messages,
    )

    duration_ms = int((time.monotonic() - start) * 1000)
    content = "\n".join(b.text for b in response.content if b.type == "text")
    tokens_in = response.usage.input_tokens
    tokens_out = response.usage.output_tokens

    return ChatResult(
        content=content,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        duration_ms=duration_ms,
        model=model,
        cost_usd=calculate_cost(model, tokens_in, tokens_out),
    )
