"""Tests for DynamoDB client."""

from typing import Any, Dict
from unittest.mock import Mock, patch

import pytest

from src.auth.tenant import TenantContext
from src.db.client import TenantDB


@pytest.fixture
def tenant_context() -> TenantContext:
    """Create a test tenant context."""
    return TenantContext(
        tenant_id="test-tenant-123", user_sub="user-456", email="test@example.com"
    )


@pytest.fixture
def mock_table() -> Mock:
    """Create a mock DynamoDB table."""
    return Mock()


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_tenant_db_init(mock_boto3: Mock, tenant_context: TenantContext) -> None:
    """Test TenantDB initialization."""
    mock_resource = Mock()
    mock_table = Mock()
    mock_boto3.resource.return_value = mock_resource
    mock_resource.Table.return_value = mock_table

    db = TenantDB(tenant_context)

    assert db._tenant == tenant_context
    assert db._table_name == "test-table"
    mock_boto3.resource.assert_called_once_with("dynamodb")
    mock_resource.Table.assert_called_once_with("test-table")


def test_tenant_pk(tenant_context: TenantContext) -> None:
    """Test tenant_pk property generates correct format."""
    with patch("src.db.client.boto3"):
        with patch.dict("os.environ", {"TABLE_NAME": "test-table"}):
            db = TenantDB(tenant_context)
            assert db.tenant_pk == "T#test-tenant-123"


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_get_item_found(mock_boto3: Mock, tenant_context: TenantContext) -> None:
    """Test get_item returns item when found."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    # Mock response with item
    mock_response = {
        "Item": {"PK": "T#test-tenant-123", "SK": "item-1", "data": "value"}
    }
    mock_table.get_item.return_value = mock_response

    db = TenantDB(tenant_context)
    result = db.get_item("item-1")

    assert result == {"PK": "T#test-tenant-123", "SK": "item-1", "data": "value"}
    mock_table.get_item.assert_called_once_with(
        Key={"PK": "T#test-tenant-123", "SK": "item-1"}
    )


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_get_item_not_found(mock_boto3: Mock, tenant_context: TenantContext) -> None:
    """Test get_item returns None when item not found."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    # Mock response without item
    mock_response: Dict[str, Any] = {}
    mock_table.get_item.return_value = mock_response

    db = TenantDB(tenant_context)
    result = db.get_item("nonexistent-item")

    assert result is None


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_put_item(mock_boto3: Mock, tenant_context: TenantContext) -> None:
    """Test put_item stores item with tenant prefix."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    db = TenantDB(tenant_context)
    db.put_item("item-1", data="value", status="active")

    mock_table.put_item.assert_called_once_with(
        Item={
            "PK": "T#test-tenant-123",
            "SK": "item-1",
            "data": "value",
            "status": "active",
        }
    )


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_delete_item(mock_boto3: Mock, tenant_context: TenantContext) -> None:
    """Test delete_item removes item with tenant prefix."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    db = TenantDB(tenant_context)
    db.delete_item("item-1")

    mock_table.delete_item.assert_called_once_with(
        Key={"PK": "T#test-tenant-123", "SK": "item-1"}
    )
