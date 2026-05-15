"""Tests for the PR review route."""

from __future__ import annotations

import time
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


def _implementer(*, pr_number: int = 42, repo: str = "owner/repo") -> Dict[str, Any]:
    return {
        "PK": "T#tenant-abc#P#proj-001",
        "SK": "S#w1#m1#cr_impl_02",
        "crow_type": "implementer",
        "status": "completed",
        "completed_at": "2026-05-15T10:05:00+00:00",
        "branch": "cawnex/w1-m1",
        "repo": repo,
        "cost": {"credits": 600_000, "duration_ms": 120_000},
        "outcome": {"files_changed": ["a.py", "b.py"]},
        "pr": {
            "number": pr_number,
            "url": f"https://github.com/{repo}/pull/{pr_number}",
        },
    }


def _reviewer_approved() -> Dict[str, Any]:
    return {
        "PK": "T#tenant-abc#P#proj-001",
        "SK": "S#w1#m1#cr_rev_03",
        "crow_type": "reviewer",
        "status": "completed",
        "completed_at": "2026-05-15T10:10:00+00:00",
        "cost": {"credits": 100_000, "duration_ms": 30_000},
        "outcome": {
            "approved": True,
            "blocking_issues": [],
            "non_blocking_issues": ["Consider renaming x to user_id"],
            "summary": "Looks good. Tests pass. Approved.",
        },
    }


def _planner() -> Dict[str, Any]:
    return {
        "PK": "T#tenant-abc#P#proj-001",
        "SK": "S#w1#m1#cr_plan_01",
        "crow_type": "planner",
        "status": "completed",
        "completed_at": "2026-05-15T10:00:00+00:00",
        "cost": {"credits": 50_000, "duration_ms": 15_000},
        "outcome": {
            "tasks": [
                {"name": "Task A", "estimated_hours": 2},
                {"name": "Task B", "estimated_hours": 4},
            ],
            "summary": "Decomposed into 2 tasks.",
        },
    }


def _mvi() -> Dict[str, Any]:
    return {
        "PK": "T#tenant-abc#P#proj-001",
        "SK": "S#w1#m1",
        "name": "Add login",
        "description": "Add a login screen with email + password",
    }


GH_PR_PAYLOAD = {
    "number": 42,
    "title": "feat: add login screen",
    "state": "open",
    "merged_at": None,
    "additions": 142,
    "deletions": 23,
    "changed_files": 6,
    "head": {"ref": "cawnex/w1-m1"},
}


# ---- happy path ------------------------------------------------------------


@patch("src.routes.prs.fetch_pr", return_value=GH_PR_PAYLOAD)
@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_get_pr_review_full_data(mock_boto3: Mock, mock_fetch: Mock) -> None:
    """Implementer + reviewer + planner all present, GitHub returns data."""
    mock_table = Mock()
    impl = _implementer()
    reviewer = _reviewer_approved()
    planner = _planner()

    # Query order in the route: implementer, reviewer, planner.
    mock_table.query.side_effect = [
        {"Items": [impl]},
        {"Items": [reviewer]},
        {"Items": [planner]},
    ]

    # get_item: first the GH cache lookup (miss), then the MVI lookup
    def get_handler(**kwargs: Any) -> Dict[str, Any]:
        sk = kwargs["Key"]["SK"]
        if sk.startswith("GHCACHE#"):
            return {}  # cache miss
        if sk == "S#w1#m1":
            return {"Item": _mvi()}
        return {}

    mock_table.get_item.side_effect = get_handler
    mock_table.put_item.return_value = {}
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())
    resp = client.get("/projects/proj-001/waves/w1/mvis/1/prs/42")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["title"] == "feat: add login screen"
    assert body["status"] == "ready"
    assert body["files_changed"] == 6
    assert body["lines_added"] == 142
    assert body["lines_removed"] == 23
    assert body["verdict"]["status"] == "approved"
    # 1 non_blocking_issue becomes a warning finding
    assert any(f["type"] == "warning" for f in body["verdict"]["findings"])
    # plan steps cover all three crows
    crow_names = [s["crow_name"] for s in body["plan_steps"]]
    assert crow_names == ["Planner", "Implementer", "Reviewer"]
    # Placeholders
    assert body["suggested_questions"] == []
    assert body["conversation"] == []
    # GitHub was called once because cache missed
    mock_fetch.assert_called_once_with("owner/repo", 42)


@patch("src.routes.prs.fetch_pr")
@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_get_pr_review_uses_cache_when_fresh(
    mock_boto3: Mock, mock_fetch: Mock
) -> None:
    """A fresh cache row short-circuits the GitHub call."""
    mock_table = Mock()
    impl = _implementer()
    reviewer = _reviewer_approved()
    planner = _planner()
    mock_table.query.side_effect = [
        {"Items": [impl]},
        {"Items": [reviewer]},
        {"Items": [planner]},
    ]

    fresh_expires = int(time.time()) + 3600

    def get_handler(**kwargs: Any) -> Dict[str, Any]:
        sk = kwargs["Key"]["SK"]
        if sk.startswith("GHCACHE#"):
            return {
                "Item": {
                    "PK": "T#tenant-abc",
                    "SK": sk,
                    "payload": GH_PR_PAYLOAD,
                    "expires_at": fresh_expires,
                }
            }
        if sk == "S#w1#m1":
            return {"Item": _mvi()}
        return {}

    mock_table.get_item.side_effect = get_handler
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())
    resp = client.get("/projects/proj-001/waves/w1/mvis/1/prs/42")
    assert resp.status_code == 200, resp.text
    mock_fetch.assert_not_called()  # cache hit


@patch("src.routes.prs.fetch_pr")
@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_get_pr_review_refreshes_expired_cache(
    mock_boto3: Mock, mock_fetch: Mock
) -> None:
    """Expired cache row forces a new GitHub fetch + write."""
    mock_fetch.return_value = GH_PR_PAYLOAD
    mock_table = Mock()
    impl = _implementer()
    reviewer = _reviewer_approved()
    planner = _planner()
    mock_table.query.side_effect = [
        {"Items": [impl]},
        {"Items": [reviewer]},
        {"Items": [planner]},
    ]

    stale_expires = int(time.time()) - 100

    def get_handler(**kwargs: Any) -> Dict[str, Any]:
        sk = kwargs["Key"]["SK"]
        if sk.startswith("GHCACHE#"):
            return {
                "Item": {
                    "PK": "T#tenant-abc",
                    "SK": sk,
                    "payload": {"stale": True},
                    "expires_at": stale_expires,
                }
            }
        if sk == "S#w1#m1":
            return {"Item": _mvi()}
        return {}

    mock_table.get_item.side_effect = get_handler
    mock_table.put_item.return_value = {}
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())
    resp = client.get("/projects/proj-001/waves/w1/mvis/1/prs/42")
    assert resp.status_code == 200
    mock_fetch.assert_called_once()
    # Cache was refreshed
    mock_table.put_item.assert_called()


# ---- error paths -----------------------------------------------------------


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_get_pr_review_no_implementer_returns_404(mock_boto3: Mock) -> None:
    mock_table = Mock()
    mock_table.query.return_value = {"Items": []}
    mock_table.get_item.return_value = {}
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())
    resp = client.get("/projects/proj-001/waves/w1/mvis/1/prs/42")
    assert resp.status_code == 404
    assert "No completed implementer" in resp.json()["detail"]


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_get_pr_review_implementer_has_no_pr(mock_boto3: Mock) -> None:
    """Implementer completed but produced no PR — 404 with clear message."""
    mock_table = Mock()
    impl = _implementer()
    impl["pr"] = {}  # no PR number
    mock_table.query.return_value = {"Items": [impl]}
    mock_table.get_item.return_value = {}
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())
    resp = client.get("/projects/proj-001/waves/w1/mvis/1/prs/42")
    assert resp.status_code == 404
    assert "has no PR" in resp.json()["detail"]


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_get_pr_review_pr_number_mismatch(mock_boto3: Mock) -> None:
    """URL pr_number must match what implementer stored — prevents stale
    iOS state from surfacing the wrong PR."""
    mock_table = Mock()
    impl = _implementer(pr_number=99)  # stored PR is 99
    mock_table.query.return_value = {"Items": [impl]}
    mock_table.get_item.return_value = {}
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())
    resp = client.get("/projects/proj-001/waves/w1/mvis/1/prs/42")  # requesting 42
    assert resp.status_code == 400
    assert "mismatch" in resp.json()["detail"].lower()


@patch("src.routes.prs.fetch_pr")
@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_get_pr_review_github_unreachable_returns_minimal_data(
    mock_boto3: Mock, mock_fetch: Mock
) -> None:
    """If GitHub returns an error, fall back to DDB-only data, don't 5xx."""
    from src.github import GitHubAPIError

    mock_fetch.side_effect = GitHubAPIError(503, "service unavailable")
    mock_table = Mock()
    impl = _implementer()
    reviewer = _reviewer_approved()
    planner = _planner()
    mock_table.query.side_effect = [
        {"Items": [impl]},
        {"Items": [reviewer]},
        {"Items": [planner]},
    ]
    mock_table.get_item.side_effect = lambda **kwargs: (
        {"Item": _mvi()} if kwargs["Key"]["SK"] == "S#w1#m1" else {}
    )
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())
    resp = client.get("/projects/proj-001/waves/w1/mvis/1/prs/42")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Title falls back to "PR #42" when GitHub is unreachable
    assert body["title"] == "PR #42"
    assert body["lines_added"] == 0  # GitHub didn't return data
    # We still get the implementer's branch + reviewer's verdict
    assert body["branch"] == "cawnex/w1-m1"
    assert body["verdict"]["status"] == "approved"
