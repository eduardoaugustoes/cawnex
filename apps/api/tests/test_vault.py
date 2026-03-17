"""Tests for vault routes — secret management."""

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


@patch("src.routes.vault.boto3")
@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table", "VAULT_KMS_KEY_ID": ""})
def test_create_secret_returns_201(mock_db_boto3: Mock, mock_vault_boto3: Mock) -> None:
    """POST /vault/secrets stores secret and returns metadata."""
    mock_table = Mock()
    mock_db_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())
    response = client.post(
        "/projects/proj-001/vault/secrets",
        json={
            "name": "whatsapp_api_token",
            "value": "EAAGm0xyz",
            "description": "Meta token",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "whatsapp_api_token"
    assert data["description"] == "Meta token"
    assert "created_at" in data

    # Verify value is NOT in the response
    assert "value" not in data
    assert "encrypted_value" not in data


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_list_secrets_never_returns_values(mock_boto3: Mock) -> None:
    """GET /vault/secrets returns metadata only, never values."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    mock_table.query.return_value = {
        "Items": [
            {
                "PK": "T#tenant-abc#VAULT",
                "SK": "P#proj-001#S#whatsapp_api_token",
                "name": "whatsapp_api_token",
                "encrypted_value": b"encrypted-bytes",
                "description": "Meta token",
                "created_at": "2026-03-16T10:00:00Z",
            },
        ]
    }

    client = _make_client(_make_tenant())
    response = client.get("/projects/proj-001/vault/secrets")

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    secret = data["secrets"][0]
    assert secret["name"] == "whatsapp_api_token"
    assert "encrypted_value" not in secret
    assert "value" not in secret


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_delete_secret(mock_boto3: Mock) -> None:
    """DELETE /vault/secrets/{name} removes the secret."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    mock_table.get_item.return_value = {
        "Item": {
            "PK": "T#tenant-abc#VAULT",
            "SK": "P#proj-001#S#whatsapp_api_token",
            "name": "whatsapp_api_token",
        }
    }

    client = _make_client(_make_tenant())
    response = client.delete("/projects/proj-001/vault/secrets/whatsapp_api_token")

    assert response.status_code == 200
    assert response.json()["deleted"] == "whatsapp_api_token"
    mock_table.delete_item.assert_called_once()


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_delete_secret_not_found(mock_boto3: Mock) -> None:
    """DELETE /vault/secrets/{name} returns 404 if secret doesn't exist."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table
    mock_table.get_item.return_value = {}

    client = _make_client(_make_tenant())
    response = client.delete("/projects/proj-001/vault/secrets/nonexistent")

    assert response.status_code == 404


@patch("src.routes.vault.boto3")
@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table", "VAULT_KMS_KEY_ID": ""})
def test_rotate_secret(mock_db_boto3: Mock, mock_vault_boto3: Mock) -> None:
    """PUT /vault/secrets/{name}/rotate updates the encrypted value."""
    mock_table = Mock()
    mock_db_boto3.resource.return_value.Table.return_value = mock_table

    mock_table.get_item.return_value = {
        "Item": {
            "PK": "T#tenant-abc#VAULT",
            "SK": "P#proj-001#S#whatsapp_api_token",
            "name": "whatsapp_api_token",
        }
    }

    client = _make_client(_make_tenant())
    response = client.put(
        "/projects/proj-001/vault/secrets/whatsapp_api_token/rotate",
        json={"value": "new-token-value"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "whatsapp_api_token"
    assert "rotated_at" in data

    # Verify value is NOT in the response
    assert "value" not in data
    assert "encrypted_value" not in data

    # Verify update was called
    mock_table.update_item.assert_called_once()


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_rotate_secret_not_found(mock_boto3: Mock) -> None:
    """PUT /vault/secrets/{name}/rotate returns 404 if secret doesn't exist."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table
    mock_table.get_item.return_value = {}

    client = _make_client(_make_tenant())
    response = client.put(
        "/projects/proj-001/vault/secrets/nonexistent/rotate",
        json={"value": "new-value"},
    )

    assert response.status_code == 404
