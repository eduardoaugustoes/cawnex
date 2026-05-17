"""Build investigation_trace as tool calls happen."""

from __future__ import annotations

from typing import Any

from council.models import ToolCall


class TraceBuilder:
    def __init__(self) -> None:
        self._calls: list[ToolCall] = []

    def record(
        self,
        tool_name: str,
        args: dict[str, Any],
        result_summary: str,
        duration_ms: int,
        error: str | None = None,
    ) -> None:
        self._calls.append(
            ToolCall(
                tool_name=tool_name,
                args=args,
                result_summary=result_summary[:200],
                duration_ms=duration_ms,
                error=error,
            )
        )

    def build(self) -> list[ToolCall]:
        return list(self._calls)

    def call_count(self) -> int:
        return len(self._calls)

    def error_count(self) -> int:
        return sum(1 for c in self._calls if c.error is not None)
