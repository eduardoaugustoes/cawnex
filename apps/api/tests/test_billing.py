"""Tests for the billing usage route."""

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


def _project_entry(project_id: str, name: str) -> Dict[str, Any]:
    return {
        "PK": "T#tenant-abc",
        "SK": f"P#{project_id}",
        "project_id": project_id,
        "name": name,
        "entityType": "ProjectEntry",
    }


def _planner_crow(project_id: str, hours: List[int]) -> Dict[str, Any]:
    return {
        "PK": f"T#tenant-abc#P#{project_id}",
        "SK": f"S#w1#m1#cr_plan_01",
        "crow_type": "planner",
        "cost": {"credits": 100_000, "duration_ms": 60_000},
        "outcome": {"tasks": [{"estimated_hours": h} for h in hours]},
    }


def _impl_crow(
    project_id: str, *, credits: int = 1_500_000, files: int = 3
) -> Dict[str, Any]:
    return {
        "PK": f"T#tenant-abc#P#{project_id}",
        "SK": f"S#w1#m1#cr_impl_02",
        "crow_type": "implementer",
        "cost": {"credits": credits, "duration_ms": 180_000},
        "outcome": {"files_changed": [f"f{i}.py" for i in range(files)]},
    }


def _reviewer_crow(project_id: str) -> Dict[str, Any]:
    return {
        "PK": f"T#tenant-abc#P#{project_id}",
        "SK": f"S#w1#m1#cr_rev_03",
        "crow_type": "reviewer",
        "cost": {"credits": 200_000, "duration_ms": 45_000},
        "outcome": {"summary": "Looks good."},
    }


# ---- happy paths -----------------------------------------------------------


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_get_billing_usage_aggregates_across_projects(mock_boto3: Mock) -> None:
    """Two projects with planner + implementer + reviewer crows roll up."""
    mock_table = Mock()

    # First call: list tenant's projects (query under T#... with SK begins P#)
    # Subsequent calls: per-project crow snapshots (we query 2 helpers per
    # project — full list then planner subset)
    def query_handler(**kwargs: Any) -> Dict[str, Any]:
        from boto3.dynamodb.conditions import Attr  # noqa

        cond = kwargs["KeyConditionExpression"]
        # Inspect by stringifying _values when available
        values = getattr(cond, "_values", None)
        # First: tenant-scoped P# query
        if values and any(
            v == "P#"
            or (isinstance(v, str) and v.startswith("P#") and "#" not in v[2:])
            for v in (values if isinstance(values, tuple) else [values])
        ):
            return {
                "Items": [
                    _project_entry("proj-a", "Project A"),
                    _project_entry("proj-b", "Project B"),
                ]
            }
        # Default to returning all crow snapshots per project; the route's
        # filter strips out non-crow rows (it requires 3+ # in SK).
        # Simplest: track which project_id is being queried by PK
        return {"Items": []}

    # Easier approach: use side_effect list ordered by call sequence.
    # The route makes these queries per project:
    #   1. _list_projects: SK begins_with "P#"   -> projects
    #   For each project:
    #     2. _list_crow_snapshots: SK begins_with "S#"  -> crow snapshots
    #     3. _human_hours_for_project: SK begins_with "S#"  -> same data, route filters cr_plan
    # So total = 1 + 2 * num_projects = 5 calls for 2 projects.
    project_list = [
        _project_entry("proj-a", "Project A"),
        _project_entry("proj-b", "Project B"),
    ]
    proj_a_crows = [
        _planner_crow("proj-a", hours=[2, 4]),
        _impl_crow("proj-a", credits=1_500_000),
        _reviewer_crow("proj-a"),
    ]
    proj_b_crows = [
        _planner_crow("proj-b", hours=[1, 1, 1]),
        _impl_crow("proj-b", credits=500_000, files=1),
    ]
    mock_table.query.side_effect = [
        {"Items": project_list},
        {"Items": proj_a_crows},  # _list_crow_snapshots proj-a
        {"Items": proj_a_crows},  # _human_hours_for_project proj-a
        {"Items": proj_b_crows},  # _list_crow_snapshots proj-b
        {"Items": proj_b_crows},  # _human_hours_for_project proj-b
    ]
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())
    resp = client.get("/billing/usage")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Two projects with activity surface in the listings
    assert len(body["project_budgets"]) == 2
    assert {b["project_name"] for b in body["project_budgets"]} == {
        "Project A",
        "Project B",
    }

    # Cost breakdown matches the project budgets count
    assert len(body["cost_breakdown"]) == 2

    # Crow cost rollup: planner, implementer, reviewer
    crow_names = {c["crow_name"] for c in body["crow_costs"]}
    assert crow_names == {"Planner", "Implementer", "Reviewer"}

    # ROI: total credits = 100k+1.5M+200k + 100k+500k = 2.4M micros = $2.40
    # Human hours: (2+4) + (1+1+1) = 9 hours. Human equiv = 9 × $50 = $450.
    # ROI multiplier = 450 / 2.40 = 187
    assert body["roi"]["credits_spent"] == "2.40"
    assert body["roi"]["human_hours"] == 9
    assert body["roi"]["roi_multiplier"] == 187

    # Balance is placeholder
    assert body["balance"]["remaining"] is None
    assert body["balance"]["total"] is None

    assert body["breakdown_period"] == "All time"


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_get_billing_usage_skips_projects_with_no_activity(mock_boto3: Mock) -> None:
    """Projects without crow snapshots are excluded from the cost lists."""
    mock_table = Mock()
    project_list = [_project_entry("idle-proj", "Idle Project")]
    mock_table.query.side_effect = [
        {"Items": project_list},
        {"Items": []},  # no crow snapshots
        {"Items": []},  # no planner hours
    ]
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())
    resp = client.get("/billing/usage")
    assert resp.status_code == 200
    body = resp.json()
    assert body["project_budgets"] == []
    assert body["cost_breakdown"] == []
    # No spending -> ROI multiplier is 0, not infinity
    assert body["roi"]["roi_multiplier"] == 0
    assert body["roi"]["credits_spent"] == "0.00"


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_get_billing_usage_no_projects(mock_boto3: Mock) -> None:
    """Empty tenant returns clean zeros, not a 500."""
    mock_table = Mock()
    mock_table.query.return_value = {"Items": []}
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())
    resp = client.get("/billing/usage")
    assert resp.status_code == 200
    body = resp.json()
    assert body["project_budgets"] == []
    assert body["crow_costs"] == []
