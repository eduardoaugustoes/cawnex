"""Prompt strategies for experiment harness.

Two variants:
  BaselineStrategy — current flat prompts (control)
  MemoryStrategy   — baseline + memory block in system prompt
"""

from __future__ import annotations

from worker.prompts import CROW_IDENTITIES


class BaselineStrategy:
    """Control — exact current behavior."""

    name = "baseline"

    def build_identities(self) -> dict[str, str]:
        return dict(CROW_IDENTITIES)


class MemoryStrategy:
    """Baseline + project memory appended to system prompt."""

    name = "memory"

    def __init__(self, memory_markdown: str) -> None:
        self._memory = memory_markdown

    def build_identities(self) -> dict[str, str]:
        return {
            k: f"{v}\n\n## Project Memory\n{self._memory}"
            for k, v in CROW_IDENTITIES.items()
        }
