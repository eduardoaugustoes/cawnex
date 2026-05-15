"""Tests for the notifications route."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
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


def _event(
    event_type: str, message: str, *, minutes_ago: int = 5, project_id: str = "proj-1"
) -> Dict[str, Any]:
    ts = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()
    return {
        "PK": f"T#tenant-abc#P#{project_id}#W#w1",
        "SK": f"{ts}#{event_type}",
        "GSI1PK": f"T#tenant-abc#P#{project_id}",
        "GSI1SK": ts,
        "event_type": event_type,
        "message": message,
        "timestamp": ts,
    }


# ---- happy paths -----------------------------------------------------------


@patch("src.routes.notifications.boto3")
@patch.dict(
    "os.environ", {"EVENTS_TABLE_NAME": "cawnex-events-test", "TABLE_NAME": "x"}
)
def test_get_notifications_buckets_by_action_vs_recent(mock_boto3: Mock) -> None:
    """mvi_ready / mvi_failed go to needsAction; mvi_shipped goes to recent."""
    mock_table = Mock()
    mock_table.scan.return_value = {
        "Items": [
            _event(
                "mvi_failed", "MVI failed: implementer empty changes", minutes_ago=1
            ),
            _event("mvi_ready", "MVI ready to ship", minutes_ago=10),
            _event("mvi_shipped", "MVI shipped successfully", minutes_ago=60),
            _event(
                "crow_completed", "Implementer landed", minutes_ago=5
            ),  # filtered out
        ]
    }
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())
    resp = client.get("/notifications")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # needs_action has mvi_ready + mvi_failed
    needs_action_types = {n["type"] for n in body["needs_action"]}
    assert needs_action_types == {"mvi_ready", "task_failed"}

    # recent has mvi_shipped
    recent_types = {n["type"] for n in body["recent"]}
    assert recent_types == {"mvi_shipped"}

    # crow_completed didn't surface (no mapping)
    all_types = needs_action_types | recent_types
    assert "crow_completed" not in all_types


@patch("src.routes.notifications.boto3")
@patch.dict(
    "os.environ", {"EVENTS_TABLE_NAME": "cawnex-events-test", "TABLE_NAME": "x"}
)
def test_get_notifications_humanizes_timestamps(mock_boto3: Mock) -> None:
    """1m ago / 14m ago / 2h ago should appear in timestamps."""
    mock_table = Mock()
    mock_table.scan.return_value = {
        "Items": [
            _event("mvi_failed", "Failed A", minutes_ago=1),
            _event("mvi_ready", "Ready B", minutes_ago=120),
        ]
    }
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())
    resp = client.get("/notifications")
    body = resp.json()
    timestamps = {n["timestamp"] for n in body["needs_action"]}
    assert any("m ago" in ts or "just now" in ts for ts in timestamps)
    assert any("h ago" in ts for ts in timestamps)


@patch("src.routes.notifications.boto3")
@patch.dict(
    "os.environ", {"EVENTS_TABLE_NAME": "cawnex-events-test", "TABLE_NAME": "x"}
)
def test_get_notifications_no_events(mock_boto3: Mock) -> None:
    mock_table = Mock()
    mock_table.scan.return_value = {"Items": []}
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())
    resp = client.get("/notifications")
    assert resp.status_code == 200
    body = resp.json()
    assert body["needs_action"] == []
    assert body["recent"] == []


@patch.dict("os.environ", {"EVENTS_TABLE_NAME": "", "TABLE_NAME": "x"}, clear=False)
def test_get_notifications_missing_events_table_returns_empty() -> None:
    """If EVENTS_TABLE_NAME isn't configured, return empty rather than 500."""
    client = _make_client(_make_tenant())
    resp = client.get("/notifications")
    assert resp.status_code == 200
    body = resp.json()
    assert body["needs_action"] == []
    assert body["recent"] == []
