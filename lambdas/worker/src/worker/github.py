"""GitHub API helpers — issues, branches, PRs."""

from __future__ import annotations

import json
import urllib.request
from typing import Any

from worker.config import GITHUB_TOKEN


def github_api(
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    """Make a GitHub API request."""
    url = f"https://api.github.com{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"token {token or GITHUB_TOKEN}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("User-Agent", "cawnex-orchestration")
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())  # type: ignore[no-any-return]


def fetch_issue(
    repo: str,
    issue_number: int,
    token: str | None = None,
) -> dict[str, Any]:
    """Fetch a GitHub issue."""
    return github_api("GET", f"/repos/{repo}/issues/{issue_number}", token=token)


def create_branch(
    repo: str,
    branch_name: str,
    base: str = "main",
    token: str | None = None,
) -> str:
    """Create a branch from base. Returns the base SHA."""
    ref_data = github_api("GET", f"/repos/{repo}/git/ref/heads/{base}", token=token)
    sha: str = ref_data["object"]["sha"]
    github_api(
        "POST",
        f"/repos/{repo}/git/refs",
        {"ref": f"refs/heads/{branch_name}", "sha": sha},
        token=token,
    )
    return sha


def create_pr(
    repo: str,
    title: str,
    body: str,
    head: str,
    base: str = "main",
    token: str | None = None,
) -> dict[str, Any]:
    """Create a pull request."""
    return github_api(
        "POST",
        f"/repos/{repo}/pulls",
        {"title": title, "body": body, "head": head, "base": base},
        token=token,
    )
