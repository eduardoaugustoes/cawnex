"""Tests for document routes."""

from typing import Any
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
def test_save_document_returns_complete(mock_boto3: Mock) -> None:
    """PUT /documents/vision saves sections and returns status."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())
    response = client.put(
        "/projects/my-proj/documents/vision",
        json={
            "sections": [
                {
                    "id": "s1",
                    "title": "Problem",
                    "content": "The problem.",
                    "status": "complete",
                },
                {
                    "id": "s2",
                    "title": "Target",
                    "content": "Users.",
                    "status": "complete",
                },
            ]
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["doc_type"] == "vision"
    assert data["status"] == "complete"


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_save_document_in_progress(mock_boto3: Mock) -> None:
    """PUT with mixed statuses returns in_progress."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())
    response = client.put(
        "/projects/my-proj/documents/vision",
        json={
            "sections": [
                {
                    "id": "s1",
                    "title": "Problem",
                    "content": "Done.",
                    "status": "complete",
                },
                {"id": "s2", "title": "Target", "content": "", "status": "pending"},
            ]
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_save_document_invalid_type(mock_boto3: Mock) -> None:
    """PUT with invalid doc type returns 400."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())
    response = client.put(
        "/projects/my-proj/documents/invalid",
        json={"sections": []},
    )

    assert response.status_code == 400


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_get_document_returns_saved(mock_boto3: Mock) -> None:
    """GET /documents/vision returns saved document."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table
    mock_table.get_item.return_value = {
        "Item": {
            "doc_type": "vision",
            "status": "complete",
            "sections": [
                {
                    "id": "s1",
                    "title": "Problem",
                    "content": "Done.",
                    "status": "complete",
                }
            ],
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }
    }

    client = _make_client(_make_tenant())
    response = client.get("/projects/my-proj/documents/vision")

    assert response.status_code == 200
    data = response.json()
    assert data["doc_type"] == "vision"
    assert data["status"] == "complete"
    assert len(data["sections"]) == 1


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_get_document_not_found_returns_null(mock_boto3: Mock) -> None:
    """GET for non-existent document returns null."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table
    mock_table.get_item.return_value = {}

    client = _make_client(_make_tenant())
    response = client.get("/projects/my-proj/documents/vision")

    assert response.status_code == 200
    assert response.json() is None
