"""Tests for the goals routes — focused on execution-state enrichment."""

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
        tenant_id="tenant-abc", user_sub="user-001", email="t@example.com"
    )


def _make_client(tenant: TenantContext) -> TestClient:
    app.dependency_overrides[get_tenant] = lambda: tenant
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_overrides() -> Any:
    yield
    app.dependency_overrides.clear()


def _backlog_milestones() -> Dict[str, Any]:
    return {
        "milestones": [
            {
                "id": "ms-1",
                "name": "M1",
                "description": "",
                "status": "active",
                "goals": [
                    {
                        "id": "g-1",
                        "name": "Goal One",
                        "description": "",
                        "status": "active",
                    },
                ],
            }
        ]
    }


def _plan_mvis(wave_id: str = "w-1") -> Dict[str, Any]:
    """The plan record at BACKLOG#goal#g-1#mvis — frozen at planning time."""
    return {
        "mvis": [
            {
                "id": "mvi2",
                "name": "Expose project state",
                "description": "...",
                "estimated_hours": 3,
                "wave_id": wave_id,
                "wave_status": "draft",  # stale
                "status": "planned",  # stale
            },
            {
                "id": "mvi-unrun",
                "name": "Some unrun MVI",
                "description": "...",
                "estimated_hours": 2,
                # no wave_id — never executed
                "status": "planned",
            },
        ]
    }


def _execution_snapshot() -> Dict[str, Any]:
    """Live execution snapshot at S#w-1#mmvi2 — written by Murder reactor."""
    return {
        "status": "ready_to_ship",
        "tasks_done": 8,
        "tasks_total": 8,
        "can_ship": True,
    }


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_goal_context_enriches_executed_mvi_with_snapshot_state(
    mock_boto3: Mock,
) -> None:
    """An MVI with a wave_id picks up live status + task counts from the snapshot."""
    mock_table = Mock()

    def get_handler(**kwargs: Any) -> Dict[str, Any]:
        sk = kwargs["Key"]["SK"]
        if sk == "BACKLOG#milestones":
            return {"Item": _backlog_milestones()}
        if sk == "BACKLOG#goal#g-1#mvis":
            return {"Item": _plan_mvis()}
        if sk == "S#w-1#mmvi2":
            return {"Item": _execution_snapshot()}
        # Docs are absent — endpoint still returns
        return {}

    mock_table.get_item.side_effect = get_handler
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())
    resp = client.get("/projects/proj-001/goals/g-1/context")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    mvis = {m["id"]: m for m in body["existing_mvis"]}
    # Executed MVI: snapshot fields overlaid
    assert mvis["mvi2"]["status"] == "ready_to_ship"
    assert mvis["mvi2"]["tasks_done"] == 8
    assert mvis["mvi2"]["tasks_total"] == 8
    assert mvis["mvi2"]["can_ship"] is True
    # Plan-only fields still present
    assert mvis["mvi2"]["name"] == "Expose project state"
    assert mvis["mvi2"]["estimated_hours"] == 3


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_goal_context_leaves_unrun_mvi_unchanged(mock_boto3: Mock) -> None:
    """An MVI without a wave_id passes through with its plan-time status."""
    mock_table = Mock()

    def get_handler(**kwargs: Any) -> Dict[str, Any]:
        sk = kwargs["Key"]["SK"]
        if sk == "BACKLOG#milestones":
            return {"Item": _backlog_milestones()}
        if sk == "BACKLOG#goal#g-1#mvis":
            return {"Item": _plan_mvis()}
        # No snapshot exists for mvi-unrun, and mvi2 we don't care here
        if sk == "S#w-1#mmvi2":
            return {}
        return {}

    mock_table.get_item.side_effect = get_handler
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())
    resp = client.get("/projects/proj-001/goals/g-1/context")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    mvis = {m["id"]: m for m in body["existing_mvis"]}
    # Unrun MVI keeps its plan-time fields exactly
    assert mvis["mvi-unrun"]["status"] == "planned"
    assert "tasks_done" not in mvis["mvi-unrun"]
    assert "tasks_total" not in mvis["mvi-unrun"]


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_goal_context_missing_snapshot_leaves_plan_status(mock_boto3: Mock) -> None:
    """When wave_id is set but snapshot doesn't exist, MVI keeps plan status."""
    mock_table = Mock()

    def get_handler(**kwargs: Any) -> Dict[str, Any]:
        sk = kwargs["Key"]["SK"]
        if sk == "BACKLOG#milestones":
            return {"Item": _backlog_milestones()}
        if sk == "BACKLOG#goal#g-1#mvis":
            return {"Item": _plan_mvis()}
        # Snapshot lookup returns nothing for both MVIs
        return {}

    mock_table.get_item.side_effect = get_handler
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())
    resp = client.get("/projects/proj-001/goals/g-1/context")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    mvi2 = next(m for m in body["existing_mvis"] if m["id"] == "mvi2")
    # Status stays at plan-time value because no snapshot existed
    assert mvi2["status"] == "planned"
