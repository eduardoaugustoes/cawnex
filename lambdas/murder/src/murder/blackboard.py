"""DynamoDB CRUD helpers for the Murder bounded context."""

from __future__ import annotations

import time
from typing import Any

from boto3.dynamodb.conditions import Key as DKey


class ConditionalCheckFailed(Exception):
    """Raised when a DynamoDB conditional check fails."""


class Blackboard:
    """DynamoDB wrapper for the Murder blackboard."""

    def __init__(self, table: Any) -> None:
        self._table = table

    def write_item(self, item: dict[str, Any]) -> None:
        """Write a pre-built item (including GSI keys)."""
        if "ts" not in item:
            item["ts"] = int(time.time())
        self._table.put_item(Item=item)

    def read(self, pk: str, sk: str) -> dict[str, Any] | None:
        """Read a single record. Returns None if not found."""
        resp = self._table.get_item(Key={"PK": pk, "SK": sk})
        item: dict[str, Any] | None = resp.get("Item")
        return item

    def query(self, pk: str, sk_prefix: str = "") -> list[dict[str, Any]]:
        """Query all records for a partition key, optionally filtered by SK prefix."""
        if sk_prefix:
            resp = self._table.query(
                KeyConditionExpression=DKey("PK").eq(pk)
                & DKey("SK").begins_with(sk_prefix)
            )
        else:
            resp = self._table.query(KeyConditionExpression=DKey("PK").eq(pk))
        items: list[dict[str, Any]] = resp.get("Items", [])
        return items

    def conditional_status_update(
        self,
        pk: str,
        sk: str,
        from_status: str,
        to_status: str,
    ) -> bool:
        """Conditional update: change status only if current status matches."""
        try:
            self._table.update_item(
                Key={"PK": pk, "SK": sk},
                UpdateExpression="SET #s = :to_s",
                ConditionExpression="#s = :from_s",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":to_s": to_status,
                    ":from_s": from_status,
                },
            )
            return True
        except self._table.meta.client.exceptions.ConditionalCheckFailedException:
            return False

    def update(
        self,
        pk: str,
        sk: str,
        updates: dict[str, Any],
    ) -> None:
        """Update specific fields on a record."""
        expr_parts: list[str] = []
        values: dict[str, Any] = {}
        names: dict[str, str] = {}
        for k, v in updates.items():
            safe = k.replace("-", "_")
            expr_parts.append(f"#{safe} = :{safe}")
            values[f":{safe}"] = v
            names[f"#{safe}"] = k
        self._table.update_item(
            Key={"PK": pk, "SK": sk},
            UpdateExpression="SET " + ", ".join(expr_parts),
            ExpressionAttributeValues=values,
            ExpressionAttributeNames=names,
        )
