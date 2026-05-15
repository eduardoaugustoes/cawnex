"""Minimal GitHub API client for read-only PR enrichment.

Mirrors the worker's pattern (lambdas/worker/src/worker/github.py) but
trimmed to what the API surface needs: fetch a PR by number.

Token is read from the GITHUB_TOKEN env var. Failures are surfaced as
exceptions; callers (the PR route) are expected to wrap with a try/except
and fall back to the DDB-only minimal data on error.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


class GitHubAPIError(Exception):
    """Raised when GitHub returns a non-success status."""

    def __init__(self, status: int, message: str) -> None:
        """Construct with HTTP status code + GitHub-reported reason."""
        self.status = status
        self.message = message
        super().__init__(f"GitHub API error {status}: {message}")


def _github_api(
    method: str,
    path: str,
    token: str | None = None,
) -> dict[str, Any]:
    """Make a GET request to GitHub. Raises GitHubAPIError on non-200."""
    url = f"https://api.github.com{path}"
    req = urllib.request.Request(url, method=method)
    auth = token or os.environ.get("GITHUB_TOKEN", "")
    if auth:
        req.add_header("Authorization", f"token {auth}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("User-Agent", "cawnex-api")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())  # type: ignore[no-any-return]
    except urllib.error.HTTPError as e:
        raise GitHubAPIError(e.code, e.reason) from e
    except urllib.error.URLError as e:
        raise GitHubAPIError(0, str(e.reason)) from e


def fetch_pr(repo: str, pr_number: int, token: str | None = None) -> dict[str, Any]:
    """Fetch a pull request's metadata."""
    return _github_api("GET", f"/repos/{repo}/pulls/{pr_number}", token=token)
