"""Contract validation — ensures every DynamoDB write matches the agreed interface."""

from __future__ import annotations

from typing import Any

from murder.enums import CrowType


class ContractViolation(Exception):
    """Raised when a contract precondition or postcondition is violated."""


VALID_CROW_TYPES = {t.value for t in CrowType}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractViolation(message)


def validate_crow_assignment(snapshot: dict[str, Any]) -> None:
    """Contract 2: Murder writes a crow snapshot."""
    _require(
        snapshot.get("level") == "crow",
        "Contract 2: level must be 'crow'",
    )
    _require(
        snapshot.get("status") == "pending",
        "Contract 2: status must be 'pending'",
    )
    _require(
        snapshot.get("crow_type") in VALID_CROW_TYPES,
        f"Contract 2: invalid crow_type '{snapshot.get('crow_type')}' — "
        f"must be one of {VALID_CROW_TYPES}",
    )
    _require(
        bool(snapshot.get("instructions")),
        "Contract 2: instructions cannot be empty",
    )
    _require(
        bool(snapshot.get("repo")),
        "Contract 2: repo is required",
    )
    _require(
        bool(snapshot.get("branch")),
        "Contract 2: branch is required",
    )
    _require(
        (snapshot.get("budget_remaining") or 0) > 0,
        "Contract 2: budget_remaining must be > 0",
    )


def validate_mvi_ready_to_ship(snapshot: dict[str, Any]) -> None:
    """Contract 4: Murder marks MVI ready to ship."""
    _require(
        snapshot.get("status") == "ready_to_ship",
        "Contract 4: status must be 'ready_to_ship'",
    )
    _require(
        snapshot.get("can_ship") is True,
        "Contract 4: can_ship must be true",
    )
    checklist = snapshot.get("merge_checklist", [])
    _require(
        len(checklist) > 0,
        "Contract 4: merge_checklist cannot be empty",
    )
    all_passed = all(item.get("passed") for item in checklist)
    _require(
        all_passed,
        "Contract 4: all checklist items must have passed=true",
    )
