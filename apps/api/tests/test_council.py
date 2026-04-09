"""Tests for council override routes."""

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


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_override_block_submits(mock_boto3: Mock) -> None:
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table
    mock_table.get_item.return_value = {
        "Item": {
            "PK": "T#tenant-abc#P#proj-1",
            "SK": "COUNCIL#wr_w01_abc",
            "status": "completed",
            "wave_id": "w01",
            "auto_mode": "supervised",
            "context": {},
            "human_overrides": [],
        }
    }

    client = _make_client(_make_tenant())

    response = client.post(
        "/projects/proj-1/council/wr_w01_abc/override",
        json={
            "action": "override_block",
            "reason": "Rate limiting will be added next wave",
            "advisor_overridden": "security",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "override_submitted"
    assert data["override_action"] == "override_block"


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_override_invalid_action_rejected(mock_boto3: Mock) -> None:
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())

    response = client.post(
        "/projects/proj-1/council/wr_w01_abc/override",
        json={"action": "invalid_action", "reason": "test"},
    )

    assert response.status_code == 400


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_override_session_not_found(mock_boto3: Mock) -> None:
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table
    mock_table.get_item.return_value = {}

    client = _make_client(_make_tenant())

    response = client.post(
        "/projects/proj-1/council/nonexistent/override",
        json={"action": "force_decision", "reason": "test"},
    )

    assert response.status_code == 404


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_override_wrong_status_rejected(mock_boto3: Mock) -> None:
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table
    mock_table.get_item.return_value = {
        "Item": {
            "PK": "T#tenant-abc#P#proj-1",
            "SK": "COUNCIL#wr_w01_abc",
            "status": "voting",  # not completed
        }
    }

    client = _make_client(_make_tenant())

    response = client.post(
        "/projects/proj-1/council/wr_w01_abc/override",
        json={"action": "force_decision", "reason": "test"},
    )

    assert response.status_code == 409
