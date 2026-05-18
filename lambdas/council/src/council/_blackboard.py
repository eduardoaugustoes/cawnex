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

        DynamoDB Limit applies to items SCANNED before the filter is applied,
        not items RETURNED. With ~266 rows in the table and our COUNCIL row
        deep in the partition order, Limit=10 silently returned [] every poll
        because the first 10 examined rows had different SKs. Paginate fully
        until we hit a match or exhaust the table. Long-term, add a GSI on
        status to avoid the table scan entirely.
        """
        items: list[dict[str, Any]] = []
        scan_kwargs: dict[str, Any] = {
            "FilterExpression": "begins_with(SK, :sk) AND #s = :status",
            "ExpressionAttributeNames": {"#s": "status"},
            "ExpressionAttributeValues": {
                ":sk": "COUNCIL#",
                ":status": "pending",
            },
        }
        while True:
            response = self._table.scan(**scan_kwargs)
            items.extend(response.get("Items", []))
            last_key = response.get("LastEvaluatedKey")
            if not last_key or items:
                # Stop as soon as we have at least one pending session; one
                # pending row at a time is enough for the poll loop to make
                # forward progress.
                break
            scan_kwargs["ExclusiveStartKey"] = last_key
        return items
