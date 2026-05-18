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
    assert data["current_state"] == "draft"
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
def test_get_project_returns_404_when_not_found(mock_boto3: Mock) -> None:
    """GET /projects/{id} returns 404 when project doesn't exist."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table
    mock_table.get_item.return_value = {}

    client = _make_client(_make_tenant())

    response = client.get("/projects/nonexistent")

    assert response.status_code == 404


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_get_project_returns_current_state_draft(mock_boto3: Mock) -> None:
    """GET /projects/{id} returns current_state=draft for a project without docs."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    seeded: Dict[str, Any] = {
        "PK": "T#tenant-abc",
        "SK": "P#my-project-abc123",
        "project_id": "my-project-abc123",
        "name": "My Project",
        "one_liner": "A cool project",
        "status": "draft",
        "murders": ["dev"],
        "created_at": "2024-01-01T00:00:00+00:00",
    }

    # Mock get_item for project lookup
    # Mock query_project to return no docs (draft state)
    def mock_query_project(project_id: str, sk_prefix: str) -> List[Dict[str, Any]]:
        if sk_prefix == "DOC#":
            return []  # No docs, so state is draft
        return []

    with patch("src.routes.projects.TenantDB") as mock_db_class:
        mock_db_instance = Mock()
        mock_db_instance.get_item.return_value = seeded
        mock_db_instance.query_project.side_effect = mock_query_project
        mock_db_class.return_value = mock_db_instance

        client = _make_client(_make_tenant())
        response = client.get("/projects/my-project-abc123")

        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == "my-project-abc123"
        assert data["name"] == "My Project"
        assert data["status"] == "draft"
        assert data["current_state"] == "draft"


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_get_project_returns_current_state_active(mock_boto3: Mock) -> None:
    """GET /projects/{id} returns current_state=active when docs complete, no waves."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    seeded: Dict[str, Any] = {
        "PK": "T#tenant-abc",
        "SK": "P#active-proj",
        "project_id": "active-proj",
        "name": "Active Project",
        "one_liner": "Test",
        "status": "draft",
        "murders": ["dev"],
        "created_at": "2024-01-01T00:00:00+00:00",
    }

    def mock_query_project(project_id: str, sk_prefix: str) -> List[Dict[str, Any]]:
        if sk_prefix == "DOC#":
            return [
                {"SK": "DOC#vision", "doc_type": "vision", "status": "complete"},
                {"SK": "DOC#architecture", "doc_type": "architecture", "status": "complete"},
                {"SK": "DOC#glossary", "doc_type": "glossary", "status": "complete"},
                {"SK": "DOC#design", "doc_type": "design", "status": "complete"},
            ]
        return []  # No waves

    with patch("src.routes.projects.TenantDB") as mock_db_class:
        mock_db_instance = Mock()
        mock_db_instance.get_item.return_value = seeded
        mock_db_instance.query_project.side_effect = mock_query_project
        mock_db_class.return_value = mock_db_instance

        client = _make_client(_make_tenant())
        response = client.get("/projects/active-proj")

        assert response.status_code == 200
        data = response.json()
        assert data["current_state"] == "active"


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_get_project_compute_current_state_raises(mock_boto3: Mock) -> None:
    """GET /projects/{id} defaults to draft when compute_current_state raises."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    seeded: Dict[str, Any] = {
        "PK": "T#tenant-abc",
        "SK": "P#my-project-abc123",
        "project_id": "my-project-abc123",
        "name": "My Project",
        "one_liner": "A cool project",
        "status": "draft",
        "murders": ["dev"],
        "created_at": "2024-01-01T00:00:00+00:00",
    }

    with patch("src.routes.projects.TenantDB") as mock_db_class:
        mock_db_instance = Mock()
        mock_db_instance.get_item.return_value = seeded
        # Make compute_current_state raise an exception
        mock_db_instance.query_project.side_effect = RuntimeError("DB error")
        mock_db_class.return_value = mock_db_instance

        client = _make_client(_make_tenant())
        response = client.get("/projects/my-project-abc123")

        assert response.status_code == 200
        data = response.json()
        assert data["current_state"] == "draft"


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
    assert items[0]["current_state"] == "draft"


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_list_projects_includes_current_state(mock_boto3: Mock) -> None:
    """GET /projects includes computed current_state for each project."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    seeded: List[Dict[str, Any]] = [
        {
            "PK": "T#tenant-abc",
            "SK": "P#proj-1",
            "project_id": "proj-1",
            "name": "Active Project",
            "one_liner": "Test",
            "status": "draft",
            "murders": ["dev"],
            "created_at": "2024-01-01T00:00:00+00:00",
        }
    ]
    mock_table.query.return_value = {"Items": seeded}

    # Mock query_project to return docs complete
    def mock_query_project(project_id: str, sk_prefix: str) -> List[Dict[str, Any]]:
        if sk_prefix == "DOC#":
            return [
                {"SK": "DOC#vision", "doc_type": "vision", "status": "complete"},
                {
                    "SK": "DOC#architecture",
                    "doc_type": "architecture",
                    "status": "complete",
                },
                {"SK": "DOC#glossary", "doc_type": "glossary", "status": "complete"},
                {"SK": "DOC#design", "doc_type": "design", "status": "complete"},
            ]
        return []

    # Patch TenantDB directly for the list endpoint
    with patch("src.routes.projects.TenantDB") as mock_db_class:
        mock_db_instance = Mock()
        mock_db_instance.query.return_value = seeded
        mock_db_instance.query_project.side_effect = mock_query_project
        mock_db_class.return_value = mock_db_instance

        client = _make_client(_make_tenant())
        response = client.get("/projects")

        assert response.status_code == 200
        items = response.json()
        assert len(items) == 1
        assert "current_state" in items[0]
        assert items[0]["current_state"] == "active"


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_update_project_auto_mode(mock_boto3: Mock) -> None:
    """PATCH /projects/{id} updates auto_mode on root snapshot."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table
    mock_table.get_item.return_value = {
        "Item": {"PK": "T#tenant-abc#P#proj-1", "SK": "S#", "auto_mode": "off"}
    }
    mock_table.update_item.return_value = {"Attributes": {"auto_mode": "auto"}}

    client = _make_client(_make_tenant())

    response = client.patch("/projects/proj-1", json={"auto_mode": "auto"})

    assert response.status_code == 200
    assert response.json()["auto_mode"] == "auto"


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_update_project_invalid_auto_mode(mock_boto3: Mock) -> None:
    """PATCH /projects/{id} rejects invalid auto_mode values."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())

    response = client.patch("/projects/proj-1", json={"auto_mode": "turbo"})

    assert response.status_code == 422


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_update_project_not_found(mock_boto3: Mock) -> None:
    """PATCH /projects/{id} returns 404 when project doesn't exist."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table
    mock_table.get_item.return_value = {}

    client = _make_client(_make_tenant())

    response = client.patch("/projects/nonexistent", json={"auto_mode": "auto"})

    assert response.status_code == 404
