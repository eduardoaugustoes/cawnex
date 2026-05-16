"""Tests for the GitHub write-side wrapper."""

from __future__ import annotations

import io
import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.github_mutations import (
    GitHubMutationError,
    close_pr,
    merge_pr,
    post_pr_comment,
)


def _mock_response(body: dict[str, Any] | str, status: int = 200) -> MagicMock:
    """Build a fake urllib response object."""
    resp = MagicMock()
    if isinstance(body, dict):
        resp.read.return_value = json.dumps(body).encode()
    else:
        resp.read.return_value = body.encode()
    resp.status = status
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = None
    return resp


@patch.dict("os.environ", {"GITHUB_TOKEN": "ghp_fake"})
@patch("urllib.request.urlopen")
def test_merge_pr_returns_sha_on_success(mock_urlopen: MagicMock) -> None:
    mock_urlopen.return_value = _mock_response(
        {
            "sha": "abc123def456",
            "merged": True,
            "message": "Pull Request successfully merged",
        }
    )
    result = merge_pr("eduardoaugustoes/cawnex", 16, method="rebase")
    assert result["sha"] == "abc123def456"
    assert result["merged"] is True
    # Verify the call was a PUT to the merge endpoint
    req = mock_urlopen.call_args[0][0]
    assert req.method == "PUT"
    assert "/repos/eduardoaugustoes/cawnex/pulls/16/merge" in req.full_url


@patch.dict("os.environ", {"GITHUB_TOKEN": "ghp_fake"})
@patch("urllib.request.urlopen")
def test_merge_pr_sends_rebase_method_in_body(mock_urlopen: MagicMock) -> None:
    mock_urlopen.return_value = _mock_response({"sha": "x", "merged": True})
    merge_pr("o/r", 1, method="rebase")
    req = mock_urlopen.call_args[0][0]
    body = json.loads(req.data.decode())
    assert body["merge_method"] == "rebase"


@patch.dict("os.environ", {"GITHUB_TOKEN": "ghp_fake"})
@patch("urllib.request.urlopen")
def test_merge_pr_raises_on_conflict_409(mock_urlopen: MagicMock) -> None:
    import urllib.error

    mock_urlopen.side_effect = urllib.error.HTTPError(
        url="x",
        code=409,
        msg="Merge conflict",
        hdrs=None,
        fp=io.BytesIO(b'{"message":"conflict"}'),
    )
    with pytest.raises(GitHubMutationError) as exc_info:
        merge_pr("o/r", 1, method="rebase")
    assert exc_info.value.status == 409


@patch.dict("os.environ", {"GITHUB_TOKEN": "ghp_fake"})
@patch("urllib.request.urlopen")
def test_close_pr_uses_patch_state_closed(mock_urlopen: MagicMock) -> None:
    mock_urlopen.return_value = _mock_response({"state": "closed", "number": 16})
    close_pr("o/r", 16)
    req = mock_urlopen.call_args[0][0]
    assert req.method == "PATCH"
    body = json.loads(req.data.decode())
    assert body["state"] == "closed"


@patch.dict("os.environ", {"GITHUB_TOKEN": "ghp_fake"})
@patch("urllib.request.urlopen")
def test_post_pr_comment_uses_issues_endpoint(mock_urlopen: MagicMock) -> None:
    """PR comments go through /issues/{n}/comments (PRs are issues to GitHub)."""
    mock_urlopen.return_value = _mock_response({"id": 1, "body": "hello"})
    post_pr_comment("o/r", 16, "hello world")
    req = mock_urlopen.call_args[0][0]
    assert req.method == "POST"
    assert "/issues/16/comments" in req.full_url
    body = json.loads(req.data.decode())
    assert body["body"] == "hello world"


@patch.dict("os.environ", {"GITHUB_TOKEN": ""})
def test_missing_github_token_raises() -> None:
    with pytest.raises(GitHubMutationError) as exc_info:
        merge_pr("o/r", 1, method="rebase")
    assert "GITHUB_TOKEN" in str(exc_info.value)
