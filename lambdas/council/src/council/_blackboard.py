"""DynamoDB CRUD for the Council Lambda."""

from __future__ import annotations

from typing import Any

from boto3.dynamodb.conditions import Key


class Blackboard:
    def __init__(self, table: Any, events_table: Any | None = None) -> None:
        self._table = table
        self._events_table = events_table or table

    def write_item(self, item: dict[str, Any]) -> None:
        self._table.put_item(Item=item)

    def read(self, pk: str, sk: str) -> dict[str, Any] | None:
        resp = self._table.get_item(Key={"PK": pk, "SK": sk})
        return resp.get("Item")

    def query(self, pk: str, sk_prefix: str = "") -> list[dict[str, Any]]:
        if sk_prefix:
            resp = self._table.query(
                KeyConditionExpression=Key("PK").eq(pk)
                & Key("SK").begins_with(sk_prefix),
            )
        else:
            resp = self._table.query(
                KeyConditionExpression=Key("PK").eq(pk),
            )
        return resp.get("Items", [])

    def update(self, pk: str, sk: str, updates: dict[str, Any]) -> None:
        expr_parts = []
        names: dict[str, str] = {}
        values: dict[str, Any] = {}
        for i, (k, v) in enumerate(updates.items()):
            safe_key = f"#k{i}"
            val_key = f":v{i}"
            names[safe_key] = k
            values[val_key] = v
            expr_parts.append(f"{safe_key} = {val_key}")

        self._table.update_item(
            Key={"PK": pk, "SK": sk},
            UpdateExpression="SET " + ", ".join(expr_parts),
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
        )

    def write_event(self, item: dict[str, Any]) -> None:
        self._events_table.put_item(Item=item)

    def scan_pending_council_sessions(self) -> list[dict[str, Any]]:
        """Find COUNCIL# rows with status=pending.

        Small bounded scan for M2; replace with a GSI when pending volume warrants.
        """
        response = self._table.scan(
            FilterExpression="begins_with(SK, :sk) AND #s = :status",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":sk": "COUNCIL#", ":status": "pending"},
            Limit=10,
        )
        return response.get("Items", [])
