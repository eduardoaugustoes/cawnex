"""Tests for PR action routes (merge, reject)."""

from __future__ import annotations

from typing import Any, Dict
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from src.auth.dependencies import get_tenant
from src.auth.tenant import TenantContext
from src.main import app


def _make_tenant() -> TenantContext:
    return TenantContext(tenant_id="t1", user_sub="u1", email="t@example.com")


def _make_client(tenant: TenantContext) -> TestClient:
    app.dependency_overrides[get_tenant] = lambda: tenant
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_overrides() -> Any:
    yield
    app.dependency_overrides.clear()


def _mvi_item(
    status: str = "ready_to_ship", repo: str = "owner/repo"
) -> Dict[str, Any]:
    return {
        "PK": "T#t1#P#p1",
        "SK": "S#w1#mmvi1",
        "entityType": "Snapshot",
        "level": "murder",
        "status": status,
        "repo": repo,
        "branch": "cawnex/w1-mvi1",
    }


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table", "GITHUB_TOKEN": "ghp_fake"})
def test_merge_rejected_when_mvi_not_ready(mock_boto3: Mock) -> None:
    """409 when MVI is not in ready_to_ship state."""
    mock_table = Mock()
    mock_table.get_item.return_value = {"Item": _mvi_item(status="executing")}
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())
    resp = client.post("/projects/p1/waves/w1/mvis/mvi1/prs/16/merge", json={})
    assert resp.status_code == 409
    assert "ready_to_ship" in resp.json()["detail"]


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table", "GITHUB_TOKEN": "ghp_fake"})
def test_merge_returns_404_when_mvi_missing(mock_boto3: Mock) -> None:
    """404 when MVI snapshot doesn't exist."""
    mock_table = Mock()
    mock_table.get_item.return_value = {}
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())
    resp = client.post("/projects/p1/waves/w1/mvis/mvi1/prs/16/merge", json={})
    assert resp.status_code == 404


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table", "GITHUB_TOKEN": "ghp_fake"})
def test_reject_requires_reason(mock_boto3: Mock) -> None:
    """Reject without a `reason` field returns 422."""
    mock_table = Mock()
    mock_table.get_item.return_value = {"Item": _mvi_item()}
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())
    resp = client.post("/projects/p1/waves/w1/mvis/mvi1/prs/16/reject", json={})
    assert resp.status_code == 422


# ---- merge happy path + failure modes -------------------------------------


@patch("src.routes.pr_actions.merge_pr")
@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table", "GITHUB_TOKEN": "ghp_fake"})
def test_merge_happy_path_updates_mvi_and_returns_sha(
    mock_boto3: Mock, mock_merge: Mock
) -> None:
    """merge_pr called, DDB MVI updated, response includes sha + shipped status."""
    mock_merge.return_value = {"sha": "abc123def", "merged": True}

    mock_table = Mock()
    mock_table.get_item.return_value = {"Item": _mvi_item()}
    mock_table.update_item.return_value = {
        "Attributes": {"status": "shipped", "merge_sha": "abc123def"}
    }
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())
    resp = client.post("/projects/p1/waves/w1/mvis/mvi1/prs/16/merge", json={})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["merged"] is True
    assert body["sha"] == "abc123def"
    assert body["mvi_status"] == "shipped"

    # merge_pr was called correctly
    mock_merge.assert_called_once()
    args, kwargs = mock_merge.call_args
    assert args[0] == "owner/repo"
    assert args[1] == 16
    assert kwargs["method"] == "rebase"

    # DDB was updated
    mock_table.update_item.assert_called()


@patch("src.routes.pr_actions.merge_pr")
@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table", "GITHUB_TOKEN": "ghp_fake"})
def test_merge_returns_409_on_github_conflict(
    mock_boto3: Mock, mock_merge: Mock
) -> None:
    """When GitHub returns a merge conflict, the MVI stays in ready_to_ship."""
    from src.github_mutations import GitHubMutationError

    mock_merge.side_effect = GitHubMutationError(
        status=409, message="Pull Request is not mergeable"
    )

    mock_table = Mock()
    mock_table.get_item.return_value = {"Item": _mvi_item()}
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())
    resp = client.post("/projects/p1/waves/w1/mvis/mvi1/prs/16/merge", json={})
    assert resp.status_code == 409
    assert "not mergeable" in resp.json()["detail"]
    mock_table.update_item.assert_not_called()


@patch("src.routes.pr_actions.merge_pr")
@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table", "GITHUB_TOKEN": "ghp_fake"})
def test_merge_idempotent_when_already_shipped(
    mock_boto3: Mock, mock_merge: Mock
) -> None:
    """Merging an already-shipped MVI returns 200 without re-calling GitHub."""
    shipped = _mvi_item(status="shipped")
    shipped["merge_sha"] = "previous-sha"

    mock_table = Mock()
    mock_table.get_item.return_value = {"Item": shipped}
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())
    resp = client.post("/projects/p1/waves/w1/mvis/mvi1/prs/16/merge", json={})
    assert resp.status_code == 200
    assert resp.json()["sha"] == "previous-sha"
    mock_merge.assert_not_called()


# ---- reject happy path + comment-failure-tolerance ------------------------


@patch("src.routes.pr_actions.post_pr_comment")
@patch("src.routes.pr_actions.close_pr")
@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table", "GITHUB_TOKEN": "ghp_fake"})
def test_reject_posts_comment_then_closes_then_updates_mvi(
    mock_boto3: Mock, mock_close: Mock, mock_comment: Mock
) -> None:
    """Reject posts the reason as a PR comment, closes the PR, marks MVI rejected."""
    mock_comment.return_value = {"id": 99}
    mock_close.return_value = {"state": "closed", "number": 16}

    mock_table = Mock()
    mock_table.get_item.return_value = {"Item": _mvi_item()}
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())
    resp = client.post(
        "/projects/p1/waves/w1/mvis/mvi1/prs/16/reject",
        json={"reason": "Auth model is wrong; need to rewrite"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["rejected"] is True
    assert body["mvi_status"] == "rejected"

    # Comment was posted with the reason
    mock_comment.assert_called_once()
    comment_args = mock_comment.call_args
    assert comment_args[0][0] == "owner/repo"
    assert comment_args[0][1] == 16
    assert "Auth model is wrong" in comment_args[0][2]
    assert "Rejected" in comment_args[0][2]

    # Then close was called
    mock_close.assert_called_once_with("owner/repo", 16)


@patch("src.routes.pr_actions.close_pr")
@patch("src.routes.pr_actions.post_pr_comment")
@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table", "GITHUB_TOKEN": "ghp_fake"})
def test_reject_continues_when_comment_fails(
    mock_boto3: Mock, mock_comment: Mock, mock_close: Mock
) -> None:
    """If the comment POST fails, we still close the PR + mark rejected."""
    from src.github_mutations import GitHubMutationError

    mock_comment.side_effect = GitHubMutationError(
        status=503, message="GitHub unavailable"
    )
    mock_close.return_value = {"state": "closed"}

    mock_table = Mock()
    mock_table.get_item.return_value = {"Item": _mvi_item()}
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())
    resp = client.post(
        "/projects/p1/waves/w1/mvis/mvi1/prs/16/reject", json={"reason": "no good"}
    )
    assert resp.status_code == 200
    assert resp.json()["rejected"] is True
    mock_close.assert_called_once()
