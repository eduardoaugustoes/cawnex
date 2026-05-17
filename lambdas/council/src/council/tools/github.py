"""GitHub REST API: PR metadata only (no clone)."""

from __future__ import annotations

import json
import urllib.request
from typing import Any


def get_pr_metadata(repo: str, pr_number: int, github_token: str) -> dict[str, Any]:
    """Fetch PR metadata via GitHub REST API."""
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "cawnex-council",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read())
    except Exception as e:  # noqa: BLE001 -- network errors map to structured tool error
        return {"error": "github_api_error", "message": str(e)[:200]}

    return {
        "number": data.get("number"),
        "title": data.get("title", "")[:300],
        "author": data.get("user", {}).get("login", ""),
        "head_sha": data.get("head", {}).get("sha", ""),
        "body": (data.get("body") or "")[:2000],
    }
