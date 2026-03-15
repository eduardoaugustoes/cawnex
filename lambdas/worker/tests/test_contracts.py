"""Tests for contracts — Contract 3 (crow completion)."""

import pytest

from worker.contracts import ContractViolation, validate_crow_completion


class TestContract3CrowCompletion:
    def test_valid_completed_crow(self) -> None:
        snapshot = {
            "status": "completed",
            "cost": {"tokens_in": 5000, "tokens_out": 2000, "credits": 0.12},
            "completed_at": "2026-03-14T10:00:00Z",
            "outcome": {"summary": "Created auth middleware"},
        }
        validate_crow_completion(snapshot)

    def test_valid_failed_crow(self) -> None:
        snapshot = {
            "status": "failed",
            "cost": {"tokens_in": 100, "tokens_out": 50, "credits": 0.001},
            "completed_at": "2026-03-14T10:00:00Z",
        }
        validate_crow_completion(snapshot)

    def test_completed_without_outcome_raises(self) -> None:
        snapshot = {
            "status": "completed",
            "cost": {"tokens_in": 5000, "tokens_out": 2000, "credits": 0.12},
            "completed_at": "2026-03-14T10:00:00Z",
        }
        with pytest.raises(ContractViolation, match="outcome"):
            validate_crow_completion(snapshot)

    def test_missing_cost_raises(self) -> None:
        snapshot = {
            "status": "completed",
            "completed_at": "2026-03-14T10:00:00Z",
            "outcome": {"summary": "Done"},
        }
        with pytest.raises(ContractViolation, match="cost"):
            validate_crow_completion(snapshot)

    def test_missing_completed_at_raises(self) -> None:
        snapshot = {
            "status": "completed",
            "cost": {"tokens_in": 5000, "tokens_out": 2000, "credits": 0.12},
            "outcome": {"summary": "Done"},
        }
        with pytest.raises(ContractViolation, match="completed_at"):
            validate_crow_completion(snapshot)
