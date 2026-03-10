"""GitHub API client — PR creation, issue management, webhooks."""

from __future__ import annotations

from typing import Any

import httpx


class GitHubAPI:
    """Async GitHub API client for Cawnex git operations.

    Uses a Personal Access Token (PAT) or GitHub App installation token.
    """

    BASE_URL = "https://api.github.com"

    def __init__(self, token: str) -> None:
        self._token = token
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    # === Pull Requests ===

    async def create_pr(
        self,
        repo: str,
        *,
        title: str,
        body: str,
        head: str,
        base: str = "main",
        draft: bool = False,
    ) -> dict:
        """Create a pull request. repo = 'owner/repo'."""
        resp = await self._client.post(
            f"/repos/{repo}/pulls",
            json={
                "title": title,
                "body": body,
                "head": head,
                "base": base,
                "draft": draft,
            },
        )
        resp.raise_for_status()
        return resp.json()

    async def merge_pr(self, repo: str, pr_number: int, *, method: str = "squash") -> dict:
        """Merge a pull request."""
        resp = await self._client.put(
            f"/repos/{repo}/pulls/{pr_number}/merge",
            json={"merge_method": method},
        )
        resp.raise_for_status()
        return resp.json()

    async def get_pr(self, repo: str, pr_number: int) -> dict:
        resp = await self._client.get(f"/repos/{repo}/pulls/{pr_number}")
        resp.raise_for_status()
        return resp.json()

    async def list_pr_files(self, repo: str, pr_number: int) -> list[dict]:
        resp = await self._client.get(f"/repos/{repo}/pulls/{pr_number}/files")
        resp.raise_for_status()
        return resp.json()

    async def add_pr_comment(self, repo: str, pr_number: int, body: str) -> dict:
        resp = await self._client.post(
            f"/repos/{repo}/issues/{pr_number}/comments",
            json={"body": body},
        )
        resp.raise_for_status()
        return resp.json()

    # === Issues ===

    async def get_issue(self, repo: str, issue_number: int) -> dict:
        resp = await self._client.get(f"/repos/{repo}/issues/{issue_number}")
        resp.raise_for_status()
        return resp.json()

    async def list_issues(
        self, repo: str, *, labels: str | None = None, state: str = "open", per_page: int = 30
    ) -> list[dict]:
        params: dict[str, Any] = {"state": state, "per_page": per_page}
        if labels:
            params["labels"] = labels
        resp = await self._client.get(f"/repos/{repo}/issues", params=params)
        resp.raise_for_status()
        return resp.json()

    async def add_label(self, repo: str, issue_number: int, labels: list[str]) -> list[dict]:
        resp = await self._client.post(
            f"/repos/{repo}/issues/{issue_number}/labels",
            json={"labels": labels},
        )
        resp.raise_for_status()
        return resp.json()

    # === Repository ===

    async def get_repo(self, repo: str) -> dict:
        resp = await self._client.get(f"/repos/{repo}")
        resp.raise_for_status()
        return resp.json()

    async def get_file_content(self, repo: str, path: str, ref: str = "main") -> str | None:
        """Get file content decoded as UTF-8. Returns None if not found."""
        resp = await self._client.get(
            f"/repos/{repo}/contents/{path}",
            params={"ref": ref},
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        import base64
        return base64.b64decode(resp.json()["content"]).decode()

    # === Webhooks ===

    async def create_webhook(
        self, repo: str, *, url: str, events: list[str], secret: str | None = None
    ) -> dict:
        config: dict[str, Any] = {"url": url, "content_type": "json"}
        if secret:
            config["secret"] = secret
        resp = await self._client.post(
            f"/repos/{repo}/hooks",
            json={"config": config, "events": events, "active": True},
        )
        resp.raise_for_status()
        return resp.json()
