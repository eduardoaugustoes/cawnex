"""Environment variables and constants for the Council Lambda."""

import os

TABLE_NAME: str = os.environ.get("TABLE_NAME", "cawnex")
EVENTS_TABLE_NAME: str = os.environ.get("EVENTS_TABLE_NAME", "")
STAGE: str = os.environ.get("STAGE", "dev")
ANTHROPIC_MODEL: str = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
ANTHROPIC_AUTH_SECRET_ARN: str = os.environ.get("ANTHROPIC_AUTH_SECRET_ARN", "")

MAX_ROUNDS: int = 3
MAX_WAVE_REJECTIONS: int = 2
ADVISOR_TIMEOUT_SECONDS: int = 30
EVENT_TTL_DAYS: int = 365 if STAGE == "prod" else 90
