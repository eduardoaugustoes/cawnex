"""GitHub REST API write-side wrapper.

Mirrors the read-side `src/github.py` pattern (urllib, GITHUB_TOKEN env)
but for mutating operations: merge a PR, close a PR, comment on a PR.

Why not `gh` CLI: the Lambda runtime doesn't ship with `gh` and adding
it as a layer is significant infra surgery for three HTTP calls. The
REST API does the same thing and is already how `src/github.py` works.

Errors are surfaced as `GitHubMutationError(status, message)`; callers
(the routes) map these to HTTP responses for the iOS client.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Literal


class GitHubMutationError(Exception):
    """Raised when a GitHub write operation fails."""

    def __init__(self, status: int, message: str) -> None:
        """Construct with HTTP status code + GitHub-reported reason."""
        self.status = status
        self.message = message
        super().__init__(f"GitHub mutation error {status}: {message}")


MergeMethod = Literal["merge", "squash", "rebase"]


def _request(
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Make an authenticated request to GitHub's REST API."""
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise GitHubMutationError(0, "GITHUB_TOKEN env var is not set")

    url = f"https://api.github.com{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"token {token}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("User-Agent", "cawnex-api")
    if data is not None:
        req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 — controlled
            payload = resp.read().decode()
            return json.loads(payload) if payload else {}
    except urllib.error.HTTPError as e:
        message = e.reason
        try:
            err_body = json.loads(e.read().decode())
            message = err_body.get("message", message)
        except Exception:  # noqa: BLE001
            pass
        raise GitHubMutationError(e.code, message) from e
    except urllib.error.URLError as e:
        raise GitHubMutationError(0, str(e.reason)) from e


def merge_pr(
    repo: str,
    pr_number: int,
    *,
    method: MergeMethod = "rebase",
    commit_title: str | None = None,
    commit_message: str | None = None,
) -> dict[str, Any]:
    """PUT /repos/{owner}/{repo}/pulls/{pr_number}/merge.

    Returns the merge response (contains `sha`, `merged`, `message`).
    Raises GitHubMutationError on conflict, branch protection failure, etc.

    method=rebase replays implementer commits onto main as linear history.
    """
    body: dict[str, Any] = {"merge_method": method}
    if commit_title is not None:
        body["commit_title"] = commit_title
    if commit_message is not None:
        body["commit_message"] = commit_message
    return _request("PUT", f"/repos/{repo}/pulls/{pr_number}/merge", body)


def close_pr(repo: str, pr_number: int) -> dict[str, Any]:
    """PATCH /repos/{owner}/{repo}/pulls/{pr_number} with state=closed.

    Does not delete the branch; iOS surfaces a follow-up "Delete branch?"
    flow if needed.
    """
    return _request("PATCH", f"/repos/{repo}/pulls/{pr_number}", {"state": "closed"})


def post_pr_comment(repo: str, pr_number: int, body: str) -> dict[str, Any]:
    """POST /repos/{owner}/{repo}/issues/{pr_number}/comments.

    PR comments go through the issues endpoint (PRs are issues to GitHub).
    Body is markdown.
    """
    return _request(
        "POST", f"/repos/{repo}/issues/{pr_number}/comments", {"body": body}
    )


def delete_branch(repo: str, branch: str) -> dict[str, Any]:
    """DELETE /repos/{owner}/{repo}/git/refs/heads/{branch}.

    Used by Approve & Merge (post-merge cleanup) and optionally by Reject.
    GitHub returns 204 No Content on success; an empty dict is returned.
    """
    return _request("DELETE", f"/repos/{repo}/git/refs/heads/{branch}")
