"""
DynamoDB client with tenant-scoped access.

All queries are prefixed with T#<tenant_id> to enforce tenant isolation.
No query can accidentally read another tenant's data.
"""

import os

import boto3
from boto3.dynamodb.conditions import Key

from src.auth.tenant import TenantContext


class TenantDB:
    """Tenant-scoped DynamoDB access."""

    def __init__(self, tenant: TenantContext):
        self._tenant = tenant
        self._table_name = os.environ["TABLE_NAME"]
        self._table = boto3.resource("dynamodb").Table(self._table_name)

    @property
    def tenant_pk(self) -> str:
        return f"T#{self._tenant.tenant_id}"

    def get_item(self, sk: str) -> dict | None:
        response = self._table.get_item(Key={"PK": self.tenant_pk, "SK": sk})
        return response.get("Item")

    def query(self, sk_prefix: str) -> list[dict]:
        response = self._table.query(
            KeyConditionExpression=Key("PK").eq(self.tenant_pk)
            & Key("SK").begins_with(sk_prefix),
        )
        return response.get("Items", [])

    def put_item(self, sk: str, **attrs) -> None:
        self._table.put_item(
            Item={"PK": self.tenant_pk, "SK": sk, **attrs}
        )

    def update_item(self, sk: str, updates: dict) -> dict:
        expression_parts = []
        names = {}
        values = {}

        for i, (key, value) in enumerate(updates.items()):
            attr_name = f"#k{i}"
            attr_value = f":v{i}"
            expression_parts.append(f"{attr_name} = {attr_value}")
            names[attr_name] = key
            values[attr_value] = value

        response = self._table.update_item(
            Key={"PK": self.tenant_pk, "SK": sk},
            UpdateExpression="SET " + ", ".join(expression_parts),
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
            ReturnValues="ALL_NEW",
        )
        return response.get("Attributes", {})

    def delete_item(self, sk: str) -> None:
        self._table.delete_item(Key={"PK": self.tenant_pk, "SK": sk})
