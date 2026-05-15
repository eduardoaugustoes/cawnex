"""Stream service configuration — loaded once from env, immutable afterward."""

from __future__ import annotations

import os
from dataclasses import dataclass


REQUIRED_ENV_VARS = (
    "TABLE_NAME",
    "EVENTS_TABLE_NAME",
    "USER_POOL_ID",
    "AWS_REGION",
    "PIPE_SECRET",
)


@dataclass(frozen=True, slots=True)
class Config:
    table_name: str
    events_table_name: str
    user_pool_id: str
    region: str
    pipe_secret: str


def load_config() -> Config:
    """Load config from env. Raises RuntimeError on missing required vars."""
    missing = [name for name in REQUIRED_ENV_VARS if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")

    return Config(
        table_name=os.environ["TABLE_NAME"],
        events_table_name=os.environ["EVENTS_TABLE_NAME"],
        user_pool_id=os.environ["USER_POOL_ID"],
        region=os.environ["AWS_REGION"],
        pipe_secret=os.environ["PIPE_SECRET"],
    )
