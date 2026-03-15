"""Tests for blackboard — DynamoDB CRUD with DynamoDB Local.

These tests require DynamoDB Local running:
    docker run -p 8000:8000 amazon/dynamodb-local
"""

import pytest

from murder.blackboard import Blackboard
from murder.stream import deserialize_stream_record


@pytest.fixture
def blackboard(dynamodb_table) -> Blackboard:  # type: ignore[no-untyped-def]
    return Blackboard(table=dynamodb_table)


class TestBlackboardWriteItem:
    def test_write_item_and_read(self, blackboard: Blackboard) -> None:
        blackboard.write_item(
            {
                "PK": "T#acme#P#cawnex",
                "SK": "S#w001",
                "level": "wave",
                "status": "planning",
            }
        )
        item = blackboard.read(pk="T#acme#P#cawnex", sk="S#w001")
        assert item is not None
        assert item["level"] == "wave"
        assert item["status"] == "planning"
        assert "ts" in item

    def test_read_nonexistent_returns_none(self, blackboard: Blackboard) -> None:
        item = blackboard.read(pk="T#acme#P#missing", sk="S#w999")
        assert item is None


class TestBlackboardQuery:
    def test_query_by_pk(self, blackboard: Blackboard) -> None:
        blackboard.write_item({"PK": "T#acme#P#cawnex", "SK": "S#w001", "level": "wave"})
        blackboard.write_item({"PK": "T#acme#P#cawnex", "SK": "S#w001#mauth", "level": "murder"})
        blackboard.write_item({"PK": "T#acme#P#cawnex", "SK": "S#w001#mauth#cr01", "level": "crow"})

        items = blackboard.query(pk="T#acme#P#cawnex")
        assert len(items) == 3

    def test_query_with_sk_prefix(self, blackboard: Blackboard) -> None:
        blackboard.write_item({"PK": "T#acme#P#cawnex", "SK": "S#w001", "level": "wave"})
        blackboard.write_item({"PK": "T#acme#P#cawnex", "SK": "S#w001#mauth", "level": "murder"})
        blackboard.write_item({"PK": "T#acme#P#cawnex", "SK": "EVT#w001#ts1", "type": "event"})

        items = blackboard.query(pk="T#acme#P#cawnex", sk_prefix="S#w001")
        assert len(items) == 2

    def test_query_empty_result(self, blackboard: Blackboard) -> None:
        items = blackboard.query(pk="T#acme#P#missing")
        assert items == []


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
            {"PK": "T#acme#P#cawnex", "SK": "S#w001", "status": "planning", "n": 0}
        )
        blackboard.update(
            pk="T#acme#P#cawnex",
            sk="S#w001",
            updates={"status": "executing", "n": 5},
        )
        item = blackboard.read("T#acme#P#cawnex", "S#w001")
        assert item is not None
        assert item["status"] == "executing"
        assert item["n"] == 5


class TestDeserializeStreamRecord:
    def test_deserialize_strings_and_numbers(self) -> None:
        stream_item = {
            "PK": {"S": "T#acme#P#cawnex"},
            "SK": {"S": "S#w001"},
            "status": {"S": "planning"},
            "budget_limit": {"N": "20"},
            "active": {"BOOL": True},
            "notes": {"NULL": True},
        }
        result = deserialize_stream_record(stream_item)
        assert result["PK"] == "T#acme#P#cawnex"
        assert result["status"] == "planning"
        assert result["budget_limit"] == "20"
        assert result["active"] is True
        assert result["notes"] is None

    def test_deserialize_nested_map(self) -> None:
        stream_item = {
            "cost": {
                "M": {
                    "tokens_in": {"N": "5000"},
                    "credits": {"N": "0.12"},
                }
            }
        }
        result = deserialize_stream_record(stream_item)
        assert result["cost"]["tokens_in"] == "5000"
        assert result["cost"]["credits"] == "0.12"

    def test_deserialize_list(self) -> None:
        stream_item = {
            "files": {
                "L": [
                    {"S": "auth.py"},
                    {"S": "test_auth.py"},
                ]
            }
        }
        result = deserialize_stream_record(stream_item)
        assert result["files"] == ["auth.py", "test_auth.py"]
