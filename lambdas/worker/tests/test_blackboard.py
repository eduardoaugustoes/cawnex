"""Tests for Worker blackboard — DynamoDB CRUD with DynamoDB Local."""

import pytest

from worker.blackboard import Blackboard


@pytest.fixture
def blackboard(dynamodb_table) -> Blackboard:  # type: ignore[no-untyped-def]
    return Blackboard(table=dynamodb_table)


class TestBlackboardWriteItem:
    def test_write_item_and_read(self, blackboard: Blackboard) -> None:
        blackboard.write_item(
            {
                "PK": "T#acme#P#cawnex",
                "SK": "S#w001#mauth#cr01",
                "level": "crow",
                "status": "pending",
            }
        )
        item = blackboard.read(pk="T#acme#P#cawnex", sk="S#w001#mauth#cr01")
        assert item is not None
        assert item["level"] == "crow"
        assert "ts" in item

    def test_read_nonexistent_returns_none(self, blackboard: Blackboard) -> None:
        item = blackboard.read(pk="T#acme#P#missing", sk="S#w999")
        assert item is None


class TestBlackboardConditionalUpdate:
    def test_conditional_update_succeeds(self, blackboard: Blackboard) -> None:
        blackboard.write_item(
            {"PK": "T#acme#P#cawnex", "SK": "S#w001#cr01", "status": "pending"}
        )
        success = blackboard.conditional_status_update(
            pk="T#acme#P#cawnex",
            sk="S#w001#cr01",
            from_status="pending",
            to_status="running",
        )
        assert success
        item = blackboard.read("T#acme#P#cawnex", "S#w001#cr01")
        assert item is not None
        assert item["status"] == "running"

    def test_conditional_update_fails_wrong_status(
        self, blackboard: Blackboard
    ) -> None:
        blackboard.write_item(
            {"PK": "T#acme#P#cawnex", "SK": "S#w001#cr01", "status": "running"}
        )
        success = blackboard.conditional_status_update(
            pk="T#acme#P#cawnex",
            sk="S#w001#cr01",
            from_status="pending",
            to_status="running",
        )
        assert not success


class TestBlackboardUpdate:
    def test_update_fields(self, blackboard: Blackboard) -> None:
        blackboard.write_item(
            {"PK": "T#acme#P#cawnex", "SK": "S#w001", "status": "pending", "n": 0}
        )
        blackboard.update(
            pk="T#acme#P#cawnex",
            sk="S#w001",
            updates={"status": "running", "n": 5},
        )
        item = blackboard.read("T#acme#P#cawnex", "S#w001")
        assert item is not None
        assert item["status"] == "running"
        assert item["n"] == 5


class TestBlackboardGSI:
    def test_query_gsi(self, blackboard: Blackboard) -> None:
        blackboard.write_item(
            {
                "PK": "T#acme#P#cawnex",
                "SK": "S#w001#mauth#cr01",
                "GSI1PK": "DISPATCH#pending",
                "GSI1SK": "T#acme#P#cawnex#S#w001#mauth#cr01",
                "level": "crow",
                "status": "pending",
            }
        )
        items = blackboard.query_gsi(
            index_name="GSI1",
            pk="DISPATCH#pending",
        )
        assert len(items) == 1
        assert items[0]["level"] == "crow"
