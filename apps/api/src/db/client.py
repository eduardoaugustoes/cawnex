"""
DynamoDB client with tenant-scoped access.

All queries are prefixed with T#<tenant_id> to enforce tenant isolation.
No query can accidentally read another tenant's data.
"""

import os
from typing import Any, Dict, List, Optional, cast

import boto3
from boto3.dynamodb.conditions import Key

from src.auth.tenant import TenantContext  # noqa: TC001


class TenantDB:
    """Tenant-scoped DynamoDB access."""

    def __init__(self, tenant: TenantContext) -> None:
        """Initialize tenant-scoped database client.

        Args:
            tenant: TenantContext containing tenant identification
        """
        self._tenant = tenant
        self._table_name = os.environ["TABLE_NAME"]
        self._table = boto3.resource("dynamodb").Table(self._table_name)

    @property
    def tenant_pk(self) -> str:
        """Get tenant-prefixed partition key for DynamoDB isolation.

        Returns:
            String partition key in format T#<tenant_id>
        """
        return f"T#{self._tenant.tenant_id}"

    def get_item(self, sk: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single item by sort key within tenant scope.

        Args:
            sk: Sort key for the item to retrieve

        Returns:
            Dictionary containing item attributes, or None if not found
        """
        response = self._table.get_item(Key={"PK": self.tenant_pk, "SK": sk})
        item = response.get("Item")
        return cast("Optional[Dict[str, Any]]", item)

    def query(self, sk_prefix: str) -> List[Dict[str, Any]]:
        """Query items by sort key prefix within tenant scope.

        Args:
            sk_prefix: Sort key prefix to match against

        Returns:
            List of dictionaries containing matching item attributes
        """
        response = self._table.query(
            KeyConditionExpression=Key("PK").eq(self.tenant_pk)
            & Key("SK").begins_with(sk_prefix),
        )
        return cast("List[Dict[str, Any]]", response.get("Items", []))

    def put_item(self, sk: str, **attrs: Any) -> None:
        """Create or replace an item within tenant scope.

        Args:
            sk: Sort key for the item
            **attrs: Additional attributes to store with the item
        """
        self._table.put_item(Item={"PK": self.tenant_pk, "SK": sk, **attrs})

    def update_item(self, sk: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing item within tenant scope.

        Args:
            sk: Sort key for the item to update
            updates: Dictionary of attribute updates to apply

        Returns:
            Dictionary containing the updated item attributes
        """
        expression_parts = []
        names: Dict[str, str] = {}
        values: Dict[str, Any] = {}

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
        return cast("Dict[str, Any]", response.get("Attributes", {}))

    def delete_item(self, sk: str) -> None:
        """Delete an item within tenant scope.

        Args:
            sk: Sort key for the item to delete
        """
        self._table.delete_item(Key={"PK": self.tenant_pk, "SK": sk})
