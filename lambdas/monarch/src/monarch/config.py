"""Environment variables and constants for Monarch bounded context."""

from __future__ import annotations

import os

TABLE_NAME: str = os.environ.get("TABLE_NAME", "cawnex")
EVENTS_TABLE_NAME: str = os.environ.get("EVENTS_TABLE_NAME", "")
STAGE: str = os.environ.get("STAGE", "dev")
EVENT_TTL_DAYS: int = 365 if STAGE == "prod" else 90

ANTHROPIC_MODEL: str = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
ANTHROPIC_AUTH_SECRET_ARN: str = os.environ.get("ANTHROPIC_AUTH_SECRET_ARN", "")

ECS_CLUSTER_NAME: str = os.environ.get("ECS_CLUSTER_NAME", "")
ECS_SERVICE_NAME: str = os.environ.get("ECS_SERVICE_NAME", "")

WRITER_SYSTEM = "You are a technical writer. Output clean, well-structured content."

DOC_PROMPTS: dict[str, str] = {
    "vision": (
        "Generate a concise product vision document for: {description}. "
        "Include these sections: Problem Statement, Target User, "
        "Core Value Proposition, Key Differentiators, Success Metrics, Non-Goals. "
        "Return only the document content, no preamble."
    ),
    "architecture": (
        "Generate a technical architecture document for: {description}. "
        "Tech stack: {tech_stack}. "
        "Include these sections: System Overview, High-Level Components, "
        "Data Flow, Technology Decisions. "
        "Return only the document content, no preamble."
    ),
    "glossary": (
        "Generate a glossary for: {description}. "
        "Include these sections: Domain Terms, Technical Terms. "
        "Return only the document content, no preamble."
    ),
    "design": (
        "Generate a design brief for: {description}. "
        "Include these sections: API Design, Error Handling. "
        "Return only the document content, no preamble."
    ),
}

MAX_DOC_TOKENS: int = 2048
