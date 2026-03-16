"""Tests for AI chat proxy route."""

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


@patch("src.routes.ai.chat")
@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_ai_chat_returns_response(mock_boto3: Mock, mock_chat: Mock) -> None:
    """POST /ai/chat proxies Claude and returns response."""
    from decimal import Decimal

    from src.claude.client import ChatResult

    mock_chat.return_value = ChatResult(
        content='{"is_sufficient": true, "synthesized_content": "Done.", "ai_message": "Great."}',
        tokens_in=100,
        tokens_out=50,
        duration_ms=500,
        model="claude-haiku-4-5-20251001",
        cost_usd=Decimal("0.000280"),
    )

    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())
    response = client.post(
        "/ai/chat",
        json={
            "system": "You are a helpful assistant.",
            "messages": [{"role": "user", "content": "Hello"}],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "content" in data
    assert data["tokens_in"] == 100
    assert data["tokens_out"] == 50
    mock_chat.assert_called_once()


@patch("src.routes.ai.chat", side_effect=RuntimeError("No auth"))
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_ai_chat_auth_error_returns_503(mock_chat: Mock) -> None:
    """POST /ai/chat returns 503 when Claude auth fails."""
    client = _make_client(_make_tenant())
    response = client.post(
        "/ai/chat",
        json={
            "system": "test",
            "messages": [{"role": "user", "content": "Hello"}],
        },
    )

    assert response.status_code == 503


@patch("src.routes.ai.chat")
@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_ai_chat_tracks_cost_on_project(mock_boto3: Mock, mock_chat: Mock) -> None:
    """POST /ai/chat with project_id increments cost on project snapshot."""
    from decimal import Decimal

    from src.claude.client import ChatResult

    mock_chat.return_value = ChatResult(
        content="response",
        tokens_in=100,
        tokens_out=50,
        duration_ms=500,
        model="claude-haiku-4-5-20251001",
        cost_usd=Decimal("0.000280"),
    )

    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())
    client.post(
        "/ai/chat",
        json={
            "system": "test",
            "messages": [{"role": "user", "content": "Hello"}],
            "project_id": "my-proj",
        },
    )

    mock_table.update_item.assert_called_once()
