"""Base provider interface — all LLM providers implement this."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator


@dataclass
class ToolCall:
    """A tool call requested by the model."""
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class ToolResult:
    """Result of a tool execution, sent back to the model."""
    tool_use_id: str
    content: str
    is_error: bool = False


@dataclass
class LLMResponse:
    """Normalized response from any LLM provider."""
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = ""
    tokens_input: int = 0
    tokens_output: int = 0
    model: str = ""

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


class LLMProvider(ABC):
    """Abstract interface for LLM providers. BYOL — user's key, our orchestration."""

    @abstractmethod
    async def complete(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Send a completion request and return normalized response."""
        ...

    @abstractmethod
    async def stream(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 4096,
    ) -> AsyncIterator[dict]:
        """Stream completion events. Yields dicts with type + data."""
        ...

    @abstractmethod
    async def validate_key(self) -> bool:
        """Test if the API key is valid. Returns True if so."""
        ...

    @abstractmethod
    def estimate_cost(self, tokens_input: int, tokens_output: int, model: str) -> float:
        """Estimate cost in USD for given token counts."""
        ...
