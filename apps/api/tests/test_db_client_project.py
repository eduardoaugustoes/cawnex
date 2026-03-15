"""Tests for project-scoped TenantDB methods."""

from typing import Any, Dict
from unittest.mock import Mock, patch

import pytest

from src.auth.tenant import TenantContext
from src.db.client import TenantDB


@pytest.fixture
def tenant_context() -> TenantContext:
    return TenantContext(
        tenant_id="tenant-xyz", user_sub="user-999", email="test@example.com"
    )


def test_project_pk_format(tenant_context: TenantContext) -> None:
    """project_pk returns T#<tenant>#P#<project_id>."""
    with patch("src.db.client.boto3"):
        with patch.dict("os.environ", {"TABLE_NAME": "test-table"}):
            db = TenantDB(tenant_context)
            assert db.project_pk("proj-123") == "T#tenant-xyz#P#proj-123"


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_put_and_get_project_item(mock_boto3: Mock, tenant_context: TenantContext) -> None:
    """put_project_item stores with project PK; get_project_item retrieves it."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    stored: Dict[str, Any] = {
        "PK": "T#tenant-xyz#P#proj-123",
        "SK": "S#wave-1",
        "level": "wave",
        "status": "planning",
    }
    mock_table.get_item.return_value = {"Item": stored}

    db = TenantDB(tenant_context)
    db.put_project_item(project_id="proj-123", sk="S#wave-1", level="wave", status="planning")

    mock_table.put_item.assert_called_once_with(
        Item={
            "PK": "T#tenant-xyz#P#proj-123",
            "SK": "S#wave-1",
            "level": "wave",
            "status": "planning",
        }
    )

    result = db.get_project_item(project_id="proj-123", sk="S#wave-1")
    assert result is not None
    assert result["status"] == "planning"
    mock_table.get_item.assert_called_once_with(
        Key={"PK": "T#tenant-xyz#P#proj-123", "SK": "S#wave-1"}
    )


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_query_project(mock_boto3: Mock, tenant_context: TenantContext) -> None:
    """query_project returns items matching the project PK and SK prefix."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    items = [
        {"PK": "T#tenant-xyz#P#proj-123", "SK": "S#w1", "level": "wave"},
        {"PK": "T#tenant-xyz#P#proj-123", "SK": "S#w1#m1", "level": "murder"},
    ]
    mock_table.query.return_value = {"Items": items}

    db = TenantDB(tenant_context)
    result = db.query_project(project_id="proj-123", sk_prefix="S#w1")

    assert len(result) == 2
    assert result[0]["level"] == "wave"
    assert result[1]["level"] == "murder"


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_update_project_item(mock_boto3: Mock, tenant_context: TenantContext) -> None:
    """update_project_item calls update_item with the project PK and returns attributes."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    updated_attrs: Dict[str, Any] = {
        "PK": "T#tenant-xyz#P#proj-123",
        "SK": "S#w1#m1",
        "status": "shipped",
        "shipped_at": "2024-01-01T00:00:00+00:00",
    }
    mock_table.update_item.return_value = {"Attributes": updated_attrs}

    db = TenantDB(tenant_context)
    result = db.update_project_item(
        project_id="proj-123",
        sk="S#w1#m1",
        updates={"status": "shipped", "shipped_at": "2024-01-01T00:00:00+00:00"},
    )

    assert result["status"] == "shipped"
    call_kwargs = mock_table.update_item.call_args.kwargs
    assert call_kwargs["Key"] == {"PK": "T#tenant-xyz#P#proj-123", "SK": "S#w1#m1"}
    assert call_kwargs["ReturnValues"] == "ALL_NEW"
    assert "SET" in call_kwargs["UpdateExpression"]


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_get_project_item_not_found(mock_boto3: Mock, tenant_context: TenantContext) -> None:
    """get_project_item returns None when item does not exist."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table
    mock_table.get_item.return_value = {}

    db = TenantDB(tenant_context)
    result = db.get_project_item(project_id="proj-123", sk="S#nonexistent")

    assert result is None
