"""Tests for project hub route."""

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
def test_get_hub_returns_project_and_documents(mock_boto3: Mock) -> None:
    """GET /projects/{id}/hub returns project info and document statuses."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    # Project root snapshot
    mock_table.get_item.return_value = {
        "Item": {
            "PK": "T#tenant-abc#P#my-proj",
            "SK": "S#",
            "name": "My Project",
            "one_liner": "A project",
            "status": "draft",
            "murders": ["dev"],
        }
    }

    # DOC# query
    mock_table.query.return_value = {
        "Items": [
            {"doc_type": "vision", "status": "complete"},
        ]
    }

    client = _make_client(_make_tenant())
    response = client.get("/projects/my-proj/hub")

    assert response.status_code == 200
    data = response.json()
    assert data["project"]["name"] == "My Project"
    assert "current_state" in data["project"]
    assert len(data["documents"]) == 4

    doc_map = {d["type"]: d["status"] for d in data["documents"]}
    assert doc_map["vision"] == "complete"
    assert doc_map["architecture"] == "not_started"
    assert doc_map["glossary"] == "not_started"
    assert doc_map["design"] == "not_started"


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_get_hub_project_not_found(mock_boto3: Mock) -> None:
    """GET /projects/{id}/hub returns 404 when project doesn't exist."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table
    mock_table.get_item.return_value = {}

    client = _make_client(_make_tenant())
    response = client.get("/projects/nonexistent/hub")

    assert response.status_code == 404
