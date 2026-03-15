"""Tests for MVI routes."""

from typing import Any, Dict
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from src.auth.dependencies import get_tenant
from src.auth.tenant import TenantContext
from src.main import app


def _make_tenant() -> TenantContext:
    return TenantContext(
        tenant_id="tenant-abc", user_sub="user-001", email="test@example.com"
    )


def _make_client(tenant: TenantContext) -> TestClient:
    app.dependency_overrides[get_tenant] = lambda: tenant
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Any:
    yield
    app.dependency_overrides.clear()


def _ready_mvi() -> Dict[str, Any]:
    return {
        "PK": "T#tenant-abc#P#proj-001",
        "SK": "S#w123#madd-login",
        "level": "murder",
        "status": "ready_to_ship",
        "can_ship": True,
        "name": "Add login",
    }


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_ship_mvi_success(mock_boto3: Mock) -> None:
    """POST ship returns 200 with status=shipped when MVI is ready_to_ship and can_ship."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    mock_table.get_item.return_value = {"Item": _ready_mvi()}
    mock_table.update_item.return_value = {
        "Attributes": {**_ready_mvi(), "status": "shipped"}
    }

    client = _make_client(_make_tenant())

    response = client.post("/projects/proj-001/waves/w123/mvis/add-login/ship")

    assert response.status_code == 200
    assert response.json()["status"] == "shipped"


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_ship_mvi_not_found(mock_boto3: Mock) -> None:
    """POST ship returns 404 when MVI does not exist."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    mock_table.get_item.return_value = {}

    client = _make_client(_make_tenant())

    response = client.post("/projects/proj-001/waves/w123/mvis/nonexistent/ship")

    assert response.status_code == 404
    assert "MVI not found" in response.json()["detail"]


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_ship_mvi_wrong_status(mock_boto3: Mock) -> None:
    """POST ship returns 409 when MVI status is not ready_to_ship."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    queued_mvi: Dict[str, Any] = {**_ready_mvi(), "status": "queued"}
    mock_table.get_item.return_value = {"Item": queued_mvi}

    client = _make_client(_make_tenant())

    response = client.post("/projects/proj-001/waves/w123/mvis/add-login/ship")

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert "not ready to ship" in detail
    assert "queued" in detail


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_ship_mvi_cannot_ship(mock_boto3: Mock) -> None:
    """POST ship returns 409 when MVI has can_ship=False."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    blocked_mvi: Dict[str, Any] = {**_ready_mvi(), "can_ship": False}
    mock_table.get_item.return_value = {"Item": blocked_mvi}

    client = _make_client(_make_tenant())

    response = client.post("/projects/proj-001/waves/w123/mvis/add-login/ship")

    assert response.status_code == 409
    assert "cannot be shipped" in response.json()["detail"]
