"""Tests for waves routes."""

from typing import Any, Dict, List
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
def test_create_wave_returns_201(mock_boto3: Mock) -> None:
    """POST /projects/{project_id}/waves returns 201 when project exists."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    # get_item returns a project record
    mock_table.get_item.return_value = {
        "Item": {
            "PK": "T#tenant-abc",
            "SK": "P#proj-001",
            "project_id": "proj-001",
            "name": "My Project",
            "repo": "github.com/org/repo",
            "status": "active",
        }
    }

    client = _make_client(_make_tenant())

    response = client.post(
        "/projects/proj-001/waves",
        json={"directive": "Add login feature"},
    )

    assert response.status_code == 201
    data = response.json()
    assert "wave_id" in data
    assert "mvi_id" in data
    assert data["status"] == "planning"


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_create_wave_project_not_found(mock_boto3: Mock) -> None:
    """POST /projects/{project_id}/waves returns 404 when project does not exist."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    # get_item returns no Item
    mock_table.get_item.return_value = {}

    client = _make_client(_make_tenant())

    response = client.post(
        "/projects/nonexistent/waves",
        json={"directive": "Add login feature"},
    )

    assert response.status_code == 404
    assert "Project not found" in response.json()["detail"]


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_get_wave_returns_structure(mock_boto3: Mock) -> None:
    """GET /projects/{project_id}/waves/{wave_id} returns wave, mvis, crows."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    wave_item: Dict[str, Any] = {
        "PK": "T#tenant-abc#P#proj-001",
        "SK": "S#w1700000000000",
        "level": "wave",
        "status": "planning",
        "human_directive": "Add login",
    }
    mvi_item: Dict[str, Any] = {
        "PK": "T#tenant-abc#P#proj-001",
        "SK": "S#w1700000000000#madd-login",
        "level": "murder",
        "status": "queued",
        "name": "Add login",
    }
    crow_item: Dict[str, Any] = {
        "PK": "T#tenant-abc#P#proj-001",
        "SK": "S#w1700000000000#madd-login#crow-planner",
        "level": "crow",
        "status": "idle",
    }
    mock_table.query.return_value = {"Items": [wave_item, mvi_item, crow_item]}

    client = _make_client(_make_tenant())

    response = client.get("/projects/proj-001/waves/w1700000000000")

    assert response.status_code == 200
    data = response.json()
    assert data["wave"]["level"] == "wave"
    assert len(data["mvis"]) == 1
    assert data["mvis"][0]["level"] == "murder"
    assert len(data["crows"]) == 1
    assert data["crows"][0]["level"] == "crow"


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_get_wave_not_found(mock_boto3: Mock) -> None:
    """GET /projects/{project_id}/waves/{wave_id} returns 404 when wave missing."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    mock_table.query.return_value = {"Items": []}

    client = _make_client(_make_tenant())

    response = client.get("/projects/proj-001/waves/nonexistent")

    assert response.status_code == 404
    assert "Wave not found" in response.json()["detail"]
