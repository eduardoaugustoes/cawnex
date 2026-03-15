"""JSON extraction from Claude output — with fallbacks."""

from __future__ import annotations

import json
from typing import Any


def parse_json_output(raw: str) -> dict[str, Any] | list[Any] | None:
    """Try to parse JSON from Claude's output.

    Handles: clean JSON, markdown fences, JSON embedded in text.
    Returns None if no valid JSON found.
    """
    if not raw or not raw.strip():
        return None

    text = raw.strip()

    # Strip markdown fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # Try direct parse first
    try:
        return json.loads(text)  # type: ignore[no-any-return]
    except json.JSONDecodeError:
        pass

    # Try to find JSON object in text
    start = text.find("{")
    if start >= 0:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])  # type: ignore[no-any-return]
                    except json.JSONDecodeError:
                        break

    # Try to find JSON array in text
    start = text.find("[")
    if start >= 0:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "[":
                depth += 1
            elif text[i] == "]":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])  # type: ignore[no-any-return]
                    except json.JSONDecodeError:
                        break

    return None
