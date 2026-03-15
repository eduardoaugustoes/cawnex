"""Tests for projects routes."""

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
    client = TestClient(app)
    return client


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Any:
    yield
    app.dependency_overrides.clear()


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_create_project_returns_201(mock_boto3: Mock) -> None:
    """POST /projects with valid body returns 201 with project data."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())

    response = client.post(
        "/projects",
        json={"name": "My Project", "one_liner": "A cool project", "murders": ["dev"]},
    )

    assert response.status_code == 201
    data = response.json()
    assert "project_id" in data
    assert data["name"] == "My Project"
    assert data["status"] == "draft"
    assert data["murders"] == ["dev"]


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_create_project_generates_slug_id(mock_boto3: Mock) -> None:
    """project_id is a slug derived from the project name."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())

    response = client.post(
        "/projects",
        json={"name": "Hello World Project"},
    )

    assert response.status_code == 201
    project_id: str = response.json()["project_id"]
    assert project_id.startswith("hello-world-project")


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_create_project_defaults_murders_to_dev(mock_boto3: Mock) -> None:
    """When no murders specified, defaults to dev."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())

    response = client.post("/projects", json={"name": "Test"})

    assert response.status_code == 201
    assert response.json()["murders"] == ["dev"]


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_list_projects_returns_empty(mock_boto3: Mock) -> None:
    """GET /projects returns empty list when no projects exist."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table
    mock_table.query.return_value = {"Items": []}

    client = _make_client(_make_tenant())

    response = client.get("/projects")

    assert response.status_code == 200
    assert response.json() == []


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_list_projects_returns_items(mock_boto3: Mock) -> None:
    """GET /projects returns list of project summaries from DynamoDB."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    seeded: List[Dict[str, Any]] = [
        {
            "PK": "T#tenant-abc",
            "SK": "P#my-project-abc123",
            "project_id": "my-project-abc123",
            "name": "My Project",
            "one_liner": "A cool project",
            "status": "draft",
            "murders": ["dev", "infra"],
            "created_at": "2024-01-01T00:00:00+00:00",
        }
    ]
    mock_table.query.return_value = {"Items": seeded}

    client = _make_client(_make_tenant())

    response = client.get("/projects")

    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["project_id"] == "my-project-abc123"
    assert items[0]["name"] == "My Project"
    assert items[0]["one_liner"] == "A cool project"
    assert items[0]["murders"] == ["dev", "infra"]
    assert items[0]["status"] == "draft"
