"""Tests for the task detail route."""

from __future__ import annotations

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


def _planner_with_tasks(tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "PK": "T#tenant-abc#P#proj-001",
        "SK": "S#w1#m1#cr_plan_01",
        "crow_type": "planner",
        "status": "completed",
        "completed_at": "2026-05-15T10:00:00+00:00",
        "outcome": {"tasks": tasks},
    }


def _implementer(
    *,
    pr_number: int | None = None,
    credits: int = 600_000,
    duration_ms: int = 120_000,
    files_changed: int | None = None,
) -> Dict[str, Any]:
    outcome: Dict[str, Any] = {
        "files_changed": (
            ["a.py", "b.py"]
            if files_changed is None
            else [f"f{i}.py" for i in range(files_changed)]
        ),
    }
    impl: Dict[str, Any] = {
        "PK": "T#tenant-abc#P#proj-001",
        "SK": "S#w1#m1#cr_impl_02",
        "crow_type": "implementer",
        "status": "completed",
        "completed_at": "2026-05-15T10:05:00+00:00",
        "model": "claude-haiku-4-5-20251001",
        "behavior_state": "landed",
        "branch": "cawnex/w1-m1",
        "cost": {"credits": credits, "duration_ms": duration_ms},
        "outcome": outcome,
    }
    if pr_number is not None:
        impl["pr"] = {
            "number": pr_number,
            "url": f"https://github.com/x/y/pull/{pr_number}",
        }
    return impl


def _mvi() -> Dict[str, Any]:
    return {
        "PK": "T#tenant-abc#P#proj-001",
        "SK": "S#w1#m1",
        "name": "Add login",
        "status": "ready_to_ship",
    }


# ---- happy paths -----------------------------------------------------------


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_get_task_detail_planner_only(mock_boto3: Mock) -> None:
    """Planner ran but no implementer yet — returns task with idle crow and no PR."""
    planner = _planner_with_tasks(
        [
            {
                "name": "Read spec",
                "description": "Read the design spec.",
                "estimated_hours": 1,
            },
            {
                "name": "Implement compute_state",
                "description": "Create the function.",
                "estimated_hours": 4,
            },
        ]
    )

    # We need query() to differentiate planner vs implementer by SK prefix.
    mock_table = Mock()
    # Route queries planner FIRST, then implementer. Side-effect list runs
    # in order; both queries on the same wave/MVI happen in a fixed sequence.
    mock_table.query.side_effect = [{"Items": [planner]}, {"Items": []}]
    mock_table.get_item.return_value = {"Item": _mvi()}

    mock_boto3.resource.return_value.Table.return_value = mock_table
    client = _make_client(_make_tenant())

    resp = client.get("/projects/proj-001/tasks/w1:1:1")  # task_index = 1
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == "w1:1:1"
    assert body["name"] == "Implement compute_state"
    assert body["description"] == "Create the function."
    assert body["human_estimate"] == "~4 hrs"
    assert body["status"] == "pending"  # no implementer yet
    assert body["pr"] is None
    # Placeholders are empty arrays — iOS handles the UI state
    assert body["implementation_steps"] == []
    assert body["acceptance_criteria"] == []
    # Crow defaults
    assert body["assigned_crow"]["behavior_state"] == "idle"
    assert body["assigned_crow"]["model"] == "—"


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_get_task_detail_with_implementer_and_pr(mock_boto3: Mock) -> None:
    """Implementer has landed with a PR — TaskDetail surfaces it."""
    planner = _planner_with_tasks(
        [
            {"name": "Task A", "description": "desc A", "estimated_hours": 2},
            {"name": "Task B", "description": "desc B", "estimated_hours": 4},
        ]
    )
    impl = _implementer(pr_number=42, credits=2_000_000, duration_ms=180_000)

    mock_table = Mock()
    # Route invokes the planner query, then prorate_cost (uses planner+impl
    # to call query a second time for impl). Plus there's a second prorate
    # inside _compute_roi. Set up a side_effect list mapping each query.
    mock_table.query.side_effect = [
        {"Items": [planner]},  # planner lookup
        {"Items": [impl]},  # implementer lookup
    ]
    mock_table.get_item.return_value = {"Item": _mvi()}
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())
    resp = client.get("/projects/proj-001/tasks/w1:1:0")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["name"] == "Task A"
    assert body["pr"] is not None
    # Composite pr_id so iOS can pass it to the PR endpoint.
    assert body["pr"]["number"] == "w1:1:42"
    assert body["pr"]["title"] == "PR #42"
    assert body["pr"]["branch"] == "cawnex/w1-m1"
    assert body["assigned_crow"]["behavior_state"] == "landed"
    # Cost: 2_000_000 microdollars / 2 tasks = $1.00
    assert body["ai_cost"] == "1.00"
    # ROI: 2 hours × $50/hr / $1 = 100
    assert body["roi"] == 100


# ---- error paths -----------------------------------------------------------


def test_get_task_detail_bad_task_id_shape() -> None:
    client = _make_client(_make_tenant())
    resp = client.get("/projects/proj-001/tasks/not-a-composite")
    assert resp.status_code == 400
    assert "wave_id:mvi_id:task_index" in resp.json()["detail"]


def test_get_task_detail_bad_task_index() -> None:
    client = _make_client(_make_tenant())
    resp = client.get("/projects/proj-001/tasks/w1:1:notanint")
    assert resp.status_code == 400
    assert "task_index must be an integer" in resp.json()["detail"]


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_get_task_detail_no_planner_returns_404(mock_boto3: Mock) -> None:
    mock_table = Mock()
    mock_table.query.return_value = {"Items": []}
    mock_table.get_item.return_value = {}
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())
    resp = client.get("/projects/proj-001/tasks/w1:1:0")
    assert resp.status_code == 404
    assert "No completed planner" in resp.json()["detail"]


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_get_task_detail_task_index_out_of_range(mock_boto3: Mock) -> None:
    planner = _planner_with_tasks(
        [{"name": "only task", "description": "x", "estimated_hours": 1}]
    )
    mock_table = Mock()
    # Only planner is queried — the out-of-range check fails before the
    # implementer lookup.
    mock_table.query.return_value = {"Items": [planner]}
    mock_table.get_item.return_value = {"Item": _mvi()}
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())
    resp = client.get("/projects/proj-001/tasks/w1:1:5")  # only 1 task exists
    assert resp.status_code == 404
    assert "task_index 5 out of range" in resp.json()["detail"]


# ---- helper coverage -------------------------------------------------------


def test_human_hours_to_estimate_label() -> None:
    from src.routes.tasks import _human_hours_to_estimate_label

    assert _human_hours_to_estimate_label(2) == "~2 hrs"
    assert _human_hours_to_estimate_label("4") == "~4 hrs"
    assert _human_hours_to_estimate_label(0.5) == "~30 min"
    assert _human_hours_to_estimate_label(1.5) == "~1.5 hrs"
    assert _human_hours_to_estimate_label(0) == "—"
    assert _human_hours_to_estimate_label(None) == "—"
    assert _human_hours_to_estimate_label("nonsense") == "—"


def test_compute_roi_zero_inputs_returns_zero() -> None:
    from decimal import Decimal

    from src.routes.tasks import _compute_roi

    assert _compute_roi(0, Decimal("1")) == 0
    assert _compute_roi(2, Decimal("0")) == 0
    assert _compute_roi(None, Decimal("1")) == 0
    assert _compute_roi(4, Decimal("2")) == int(4 * 50 / 2)  # 100
