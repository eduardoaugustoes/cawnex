"""Tests for Murder contracts — Contract 2 and Contract 4."""

import pytest

from murder.contracts import (
    ContractViolation,
    validate_crow_assignment,
    validate_mvi_ready_to_ship,
)


class TestContract2CrowAssignment:
    def test_valid_crow_assignment(self) -> None:
        snapshot = {
            "level": "crow",
            "status": "pending",
            "crow_type": "planner",
            "instructions": "Plan the auth implementation",
            "repo": "owner/repo",
            "branch": "cawnex/w001-auth",
            "budget_remaining": 5.0,
        }
        validate_crow_assignment(snapshot)

    def test_wrong_status_raises(self) -> None:
        snapshot = {
            "level": "crow",
            "status": "completed",
            "crow_type": "planner",
            "instructions": "Plan auth",
            "repo": "owner/repo",
            "branch": "cawnex/w001-auth",
            "budget_remaining": 5.0,
        }
        with pytest.raises(ContractViolation, match="pending"):
            validate_crow_assignment(snapshot)

    def test_empty_instructions_raises(self) -> None:
        snapshot = {
            "level": "crow",
            "status": "pending",
            "crow_type": "planner",
            "instructions": "",
            "repo": "owner/repo",
            "branch": "cawnex/w001-auth",
            "budget_remaining": 5.0,
        }
        with pytest.raises(ContractViolation, match="instructions"):
            validate_crow_assignment(snapshot)

    def test_zero_budget_raises(self) -> None:
        snapshot = {
            "level": "crow",
            "status": "pending",
            "crow_type": "planner",
            "instructions": "Plan auth",
            "repo": "owner/repo",
            "branch": "cawnex/w001-auth",
            "budget_remaining": 0.0,
        }
        with pytest.raises(ContractViolation, match="budget"):
            validate_crow_assignment(snapshot)

    def test_invalid_crow_type_raises(self) -> None:
        snapshot = {
            "level": "crow",
            "status": "pending",
            "crow_type": "invalid_type",
            "instructions": "Plan auth",
            "repo": "owner/repo",
            "branch": "cawnex/w001-auth",
            "budget_remaining": 5.0,
        }
        with pytest.raises(ContractViolation, match="crow_type"):
            validate_crow_assignment(snapshot)


class TestContract4MVIReadyToShip:
    def test_valid_ready_to_ship(self) -> None:
        snapshot = {
            "status": "ready_to_ship",
            "can_ship": True,
            "merge_checklist": [
                {"label": "All tasks completed", "passed": True},
                {"label": "PR created", "passed": True},
                {"label": "Reviewer approved", "passed": True},
            ],
        }
        validate_mvi_ready_to_ship(snapshot)

    def test_incomplete_checklist_raises(self) -> None:
        snapshot = {
            "status": "ready_to_ship",
            "can_ship": True,
            "merge_checklist": [
                {"label": "All tasks completed", "passed": True},
                {"label": "PR created", "passed": False},
            ],
        }
        with pytest.raises(ContractViolation, match="checklist"):
            validate_mvi_ready_to_ship(snapshot)

    def test_wrong_status_raises(self) -> None:
        snapshot = {
            "status": "executing",
            "can_ship": True,
            "merge_checklist": [{"label": "Done", "passed": True}],
        }
        with pytest.raises(ContractViolation, match="ready_to_ship"):
            validate_mvi_ready_to_ship(snapshot)

    def test_can_ship_false_raises(self) -> None:
        snapshot = {
            "status": "ready_to_ship",
            "can_ship": False,
            "merge_checklist": [{"label": "Done", "passed": True}],
        }
        with pytest.raises(ContractViolation, match="can_ship"):
            validate_mvi_ready_to_ship(snapshot)

    def test_empty_checklist_raises(self) -> None:
        snapshot = {
            "status": "ready_to_ship",
            "can_ship": True,
            "merge_checklist": [],
        }
        with pytest.raises(ContractViolation, match="checklist"):
            validate_mvi_ready_to_ship(snapshot)
