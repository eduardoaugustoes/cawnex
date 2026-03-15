"""Contract validation for the Worker bounded context."""

from __future__ import annotations

from typing import Any


class ContractViolation(Exception):
    """Raised when a contract precondition or postcondition is violated."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractViolation(message)


def validate_crow_completion(snapshot: dict[str, Any]) -> None:
    """Contract 3: Worker completes a crow snapshot."""
    status = snapshot.get("status")
    _require(
        status in ("completed", "failed"),
        "Contract 3: status must be 'completed' or 'failed'",
    )
    _require(
        "cost" in snapshot,
        "Contract 3: cost must be tracked",
    )
    _require(
        bool(snapshot.get("completed_at")),
        "Contract 3: completed_at timestamp required",
    )
    if status == "completed":
        _require(
            bool(snapshot.get("outcome")),
            "Contract 3: completed crow must have outcome",
        )
