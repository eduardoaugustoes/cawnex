"""Tests for milestone routes — focused on the new detail endpoint."""

from __future__ import annotations

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


def _milestone_container() -> Dict[str, Any]:
    return {
        "PK": "T#tenant-abc#P#proj-001",
        "SK": "BACKLOG#milestones",
        "milestones": [
            {
                "id": "ms-1",
                "name": "M1: Foundation",
                "description": "Platform delivers first autonomous task end-to-end.",
                "status": "active",
                "goals": [
                    {
                        "id": "g-1",
                        "name": "API Infrastructure",
                        "description": "REST API, auth, schema.",
                        "status": "active",
                    },
                    {
                        "id": "g-2",
                        "name": "Auth",
                        "description": "OAuth + RBAC.",
                        "status": "planned",
                    },
                ],
            },
            {
                "id": "ms-2",
                "name": "M2: Polish",
                "description": "Hardening + observability.",
                "status": "planned",
                "goals": [],
            },
        ],
    }


def _goal_mvis(goal_id: str) -> Dict[str, Any]:
    """Returns canned MVIs for goal-id-specific queries."""
    if goal_id == "g-1":
        return {
            "mvis": [
                {"id": "mvi-a", "status": "shipped", "tasks_total": 5},
                {"id": "mvi-b", "status": "executing", "tasks_total": 3},
                {"id": "mvi-c", "status": "draft", "tasks_total": 2},
            ]
        }
    if goal_id == "g-2":
        return {"mvis": []}
    return {}


# ---- happy paths -----------------------------------------------------------


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_get_milestone_detail_aggregates_goals_and_mvi_counts(mock_boto3: Mock) -> None:
    """MilestoneDetail aggregates MVIs per goal and buckets MVIs by status.

    Note: the response field is `mvi_counts`, not `tasks` — the counts bucket
    MVIs by lifecycle stage, not tasks. Tasks live inside MVIs and roll up
    via Project Hub's separate aggregation.
    """
    mock_table = Mock()

    def get_handler(**kwargs: Any) -> Dict[str, Any]:
        sk = kwargs["Key"]["SK"]
        if sk == "BACKLOG#milestones":
            return {"Item": _milestone_container()}
        if sk == "BACKLOG#goal#g-1#mvis":
            return {"Item": _goal_mvis("g-1")}
        if sk == "BACKLOG#goal#g-2#mvis":
            return {"Item": _goal_mvis("g-2")}
        return {}

    mock_table.get_item.side_effect = get_handler
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())
    resp = client.get("/projects/proj-001/milestones/ms-1")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["id"] == "ms-1"
    assert body["name"] == "M1: Foundation"
    assert body["status"] == "active"
    # Goals rolled up
    assert len(body["goals"]) == 2
    g1 = next(g for g in body["goals"] if g["id"] == "g-1")
    assert g1["mvi_count"] == 3
    assert g1["task_count"] == 10  # 5 + 3 + 2
    g2 = next(g for g in body["goals"] if g["id"] == "g-2")
    assert g2["mvi_count"] == 0

    # MVI status counts: 1 shipped (done), 1 executing (active), 1 draft (draft)
    assert body["mvi_counts"]["done"] == 1
    assert body["mvi_counts"]["active"] == 1
    assert body["mvi_counts"]["draft"] == 1
    assert "tasks" not in body  # old field name must be gone

    # Sections: 6 fixed titles, all pending placeholder
    assert len(body["sections"]) == 6
    assert all(s["status"] == "pending" for s in body["sections"])
    assert body["sections"][0]["title"] == "Business Achievement"

    # Messages and cost are placeholders for v1
    assert body["messages"] == []
    assert body["credits_spent"] == 0
    assert body["roi"] == 0


# ---- error paths -----------------------------------------------------------


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_get_milestone_detail_no_milestones_returns_404(mock_boto3: Mock) -> None:
    mock_table = Mock()
    mock_table.get_item.return_value = {}
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())
    resp = client.get("/projects/proj-001/milestones/ms-1")
    assert resp.status_code == 404
    assert "No milestones" in resp.json()["detail"]


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_get_milestone_detail_unknown_milestone_id(mock_boto3: Mock) -> None:
    mock_table = Mock()
    mock_table.get_item.return_value = {"Item": _milestone_container()}
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())
    resp = client.get("/projects/proj-001/milestones/ms-nope")
    assert resp.status_code == 404
    assert "ms-nope" in resp.json()["detail"]
