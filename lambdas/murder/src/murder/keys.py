"""Key builders for DynamoDB PK/SK patterns."""

from __future__ import annotations


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
