"""Key builders and parsers for DynamoDB PK/SK patterns."""

from __future__ import annotations

import re
from typing import Any

_PK_RE = re.compile(r"^T#(?P<tenant>[^#]+)#P#(?P<project>.+)$")
_SK_CROW_RE = re.compile(
    r"^S#(?P<wave_id>[^#]+)#m(?P<mvi_id>[^#]+)#(?P<crow_id>.+)$"
)
_SK_MVI_RE = re.compile(r"^S#(?P<wave_id>[^#]+)#m(?P<mvi_id>[^#]+)$")
_SK_WAVE_RE = re.compile(r"^S#(?P<wave_id>[^#]+)$")
_SK_EVT_RE = re.compile(r"^EVT#(?P<wave_id>[^#]+)#(?P<event_ts>.+)$")


def build_pk(tenant: str, project: str) -> str:
    return f"T#{tenant}#P#{project}"


def build_sk(
    *,
    wave_id: str | None = None,
    mvi_id: str | None = None,
    crow_id: str | None = None,
    event_ts: str | None = None,
) -> str:
    if event_ts and wave_id:
        return f"EVT#{wave_id}#{event_ts}"
    if wave_id and mvi_id and crow_id:
        return f"S#{wave_id}#m{mvi_id}#{crow_id}"
    if wave_id and mvi_id:
        return f"S#{wave_id}#m{mvi_id}"
    if wave_id:
        return f"S#{wave_id}"
    raise ValueError("build_sk requires at least wave_id")


def parse_pk(pk: str) -> dict[str, str] | None:
    """Extract tenant and project from PK. Returns None if not parseable."""
    m = _PK_RE.match(pk)
    return m.groupdict() if m else None


def parse_sk(sk: str) -> dict[str, str] | None:
    """Extract wave/mvi/crow/event fields from SK. Returns None if not parseable."""
    for pattern in (_SK_CROW_RE, _SK_MVI_RE, _SK_WAVE_RE, _SK_EVT_RE):
        m = pattern.match(sk)
        if m:
            return m.groupdict()
    return None


def parse_item_keys(item: dict[str, Any]) -> dict[str, str] | None:
    """Extract all identity fields from a DynamoDB item's PK + SK."""
    pk_parts = parse_pk(item.get("PK", ""))
    sk_parts = parse_sk(item.get("SK", ""))
    if not pk_parts or not sk_parts:
        return None
    return {**pk_parts, **sk_parts}
