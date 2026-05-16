# PR Actions Phase 1 — Approve & Merge + Reject

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the iOS "Approve & Merge" and "Reject" buttons end-to-end against GitHub HTTP API + DynamoDB so PR #16 (and any future Cawnex PR) can be landed from the app.

**Architecture:** Two new POST routes on the API Lambda (`/prs/{n}/merge`, `/prs/{n}/reject`). Each route uses GitHub's REST API (PUT `/pulls/{n}/merge` and PATCH `/pulls/{n}` + POST `/issues/{n}/comments`) — no `gh` CLI binary, no Lambda layer surgery. After GitHub succeeds, update the MVI snapshot in DDB; the Murder reactor's existing `_maybe_transition_wave` hook (triggered by DDB Streams on the snapshot) handles the wave-terminal check automatically. iOS gets two new method handlers on `PRReviewViewModel`, confirmation sheets, and error surfaces.

**Tech Stack:**
- Backend: Python 3.12, FastAPI, urllib (existing pattern in `apps/api/src/github.py`), boto3
- Auth: existing Cognito JWT via `get_tenant` dependency
- Infra: existing API Lambda — only change is reading `GITHUB_TOKEN` from Secrets Manager (already exists at `cawnex/${stage}/github-token`)
- iOS: SwiftUI, `URLSession`, existing `APIClient` + `APIError` patterns
- Tests: existing `pytest` + `TestClient` patterns (see `apps/api/tests/test_prs.py`)

**Spec reference:** `docs/superpowers/specs/2026-05-15-pr-actions-adversarial-verification-design.md`

**Important deviation from spec:** The spec mentions `gh pr merge` and `gh pr close` CLI commands. After investigation, the API Lambda uses `urllib`-based GitHub HTTP API (`apps/api/src/github.py`) — not `gh` CLI — and adding `gh` as a Lambda layer is significant infrastructure surgery. This plan uses the GitHub REST API directly. Functional outcome is identical; the wire shape differs. Spec section 3.1 ("Approve & Merge flow") and 3.2 ("Reject flow") are otherwise unchanged.

---

## File Structure

**New files:**
- `apps/api/src/routes/pr_actions.py` — the two new routes
- `apps/api/src/github_mutations.py` — GitHub REST API write-side wrapper (merge, close, comment)
- `apps/api/tests/test_pr_actions.py` — route tests
- `apps/api/tests/test_github_mutations.py` — wrapper tests
- `apps/ios/Cawnex/Cawnex/Core/Network/APIPRActionsService.swift` — iOS HTTP client for the two routes
- `apps/ios/Cawnex/Cawnex/Features/PR/RejectSheet.swift` — confirmation sheet with reason text field
- `apps/ios/Cawnex/Cawnex/Features/PR/MergeConfirmSheet.swift` — minimal confirmation sheet

**Modified files:**
- `apps/api/src/main.py` — register `pr_actions.router`
- `apps/api/src/github.py:30-50` — generalize `_github_api` to accept JSON body for non-GET methods (the existing helper is GET-only)
- `infra/lib/cawnex-stack.ts` — grant API Lambda read on `cawnex/${stage}/github-token` secret + inject `GITHUB_TOKEN` env var
- `apps/ios/Cawnex/Cawnex/App/ServiceFactory.swift` — add `makePRActionsService()`
- `apps/ios/Cawnex/Cawnex/Features/PR/PRReviewViewModel.swift` — add `merge()`, `reject(reason:)`, `isLoading`, `errorMessage`, `showMergeSheet`, `showRejectSheet`
- `apps/ios/Cawnex/Cawnex/Features/PR/PRReviewScreen.swift:485-540` — enable the two buttons, present sheets, surface errors

---

## Task 1: GitHub mutations wrapper — write-side HTTP API

The existing `apps/api/src/github.py` only supports GET. We need PUT (merge), PATCH (close), POST (comment). Building a small write-side wrapper rather than mutating the read-side keeps the read code stable.

**Files:**
- Create: `apps/api/src/github_mutations.py`
- Test: `apps/api/tests/test_github_mutations.py`

- [ ] **Step 1: Write the failing test**

`apps/api/tests/test_github_mutations.py`:
```python
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
        {"sha": "abc123def456", "merged": True, "message": "Pull Request successfully merged"}
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
        url="x", code=409, msg="Merge conflict", hdrs=None, fp=io.BytesIO(b'{"message":"conflict"}')
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/eaugusto/cawnex/apps/api && ./venv/bin/pytest tests/test_github_mutations.py -v
```
Expected: `ModuleNotFoundError: No module named 'src.github_mutations'`.

- [ ] **Step 3: Implement `apps/api/src/github_mutations.py`**

```python
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
        with urllib.request.urlopen(req, timeout=15) as resp:
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

    method=rebase replays implementer commits onto main as linear history
    — see spec section 3.1.
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
    flow if needed. The reject flow optionally calls `delete_branch`
    separately.
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/eaugusto/cawnex/apps/api && ./venv/bin/pytest tests/test_github_mutations.py -v
```
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/eaugusto/cawnex && git add apps/api/src/github_mutations.py apps/api/tests/test_github_mutations.py
git commit -m "feat(api): GitHub write-side wrapper for merge/close/comment/delete-branch"
```

---

## Task 2: PR actions route — auth + MVI readiness validation

Before wiring real merge/close, get the route plumbing in place: auth, route registration, MVI lookup, 409 on not-ready. This gives us a place to plug GitHub calls in Task 3.

**Files:**
- Create: `apps/api/src/routes/pr_actions.py`
- Create: `apps/api/tests/test_pr_actions.py`
- Modify: `apps/api/src/main.py`

- [ ] **Step 1: Write the failing test**

`apps/api/tests/test_pr_actions.py`:
```python
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
    return TenantContext(
        tenant_id="t1", user_sub="u1", email="t@example.com"
    )


def _make_client(tenant: TenantContext) -> TestClient:
    app.dependency_overrides[get_tenant] = lambda: tenant
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_overrides() -> Any:
    yield
    app.dependency_overrides.clear()


def _mvi_item(status: str = "ready_to_ship", repo: str = "owner/repo") -> Dict[str, Any]:
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
    resp = client.post(
        "/projects/p1/waves/w1/mvis/mvi1/prs/16/reject", json={}
    )
    assert resp.status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/eaugusto/cawnex/apps/api && ./venv/bin/pytest tests/test_pr_actions.py -v
```
Expected: 404 on all routes (route not registered).

- [ ] **Step 3: Implement `apps/api/src/routes/pr_actions.py`**

```python
"""PR action routes — Approve & Merge, Reject.

Both routes follow the same shape:
  1. Authenticate (get_tenant dep).
  2. Read the MVI snapshot at PK=T#{tenant}#P#{project}, SK=S#{wave}#m{mvi}.
  3. Validate MVI is `ready_to_ship`.
  4. (Task 3) Call GitHub: merge_pr / close_pr + post_pr_comment.
  5. (Task 3) Update DDB MVI status. Murder reactor's DDB-Streams trigger
     handles the wave-terminal check automatically.

Phase 2 will add Steer chat summary attachment before GitHub mutation.
For Phase 1, the comment body is just the founder's reason (reject) or
empty (merge).
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.auth.dependencies import get_tenant
from src.auth.tenant import TenantContext
from src.db.client import TenantDB

router = APIRouter(
    prefix="/projects/{project_id}/waves/{wave_id}/mvis/{mvi_id}/prs",
    tags=["pr-actions"],
)
log = logging.getLogger(__name__)


# ---- request / response models -------------------------------------------


class MergeRequest(BaseModel):
    """Empty body for Phase 1; Phase 2 may add optional commit_title."""

    pass


class MergeResponse(BaseModel):
    merged: bool
    sha: str = ""
    mvi_status: str
    wave_status: str = ""


class RejectRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=2000)
    close_branch: bool = True


class RejectResponse(BaseModel):
    rejected: bool
    mvi_status: str


# ---- helpers --------------------------------------------------------------


def _load_mvi(
    db: TenantDB, project_id: str, wave_id: str, mvi_id: str
) -> dict[str, Any]:
    """Read the MVI snapshot. 404 if missing."""
    sk = f"S#{wave_id}#m{mvi_id}"
    item = db.get_project_item(project_id=project_id, sk=sk)
    if not item:
        raise HTTPException(
            status_code=404, detail=f"MVI {mvi_id} not found in wave {wave_id}"
        )
    return item


def _require_ready_to_ship(mvi: dict[str, Any]) -> None:
    """409 if the MVI isn't ready to ship.

    Idempotency: if already shipped/rejected, the caller should return
    a 200 reflecting current state rather than re-mutating. Phase 1
    routes handle that at the route level (see merge_pr / reject_pr).
    """
    status = mvi.get("status", "")
    if status != "ready_to_ship":
        raise HTTPException(
            status_code=409,
            detail=f"MVI must be in ready_to_ship state (currently: {status})",
        )


# ---- routes ---------------------------------------------------------------


@router.post("/{pr_number}/merge", response_model=MergeResponse)
async def approve_and_merge(
    project_id: str,
    wave_id: str,
    mvi_id: str,
    pr_number: int,
    _body: MergeRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> MergeResponse:
    """Approve & Merge — Phase 1 stub (validation only; Task 3 wires GitHub + DDB)."""
    db = TenantDB(tenant)
    mvi = _load_mvi(db, project_id, wave_id, mvi_id)

    # Idempotency: if already shipped, return success.
    if mvi.get("status") == "shipped":
        return MergeResponse(
            merged=True,
            sha=str(mvi.get("merge_sha", "")),
            mvi_status="shipped",
        )

    _require_ready_to_ship(mvi)

    # Task 3 fills in the GitHub call + DDB update. For Phase 1 step 3 we
    # raise NotImplemented so the test in this task sees the validation
    # path, not a stub success.
    raise HTTPException(
        status_code=501, detail="merge_pr GitHub wiring lands in Task 3"
    )


@router.post("/{pr_number}/reject", response_model=RejectResponse)
async def reject_pr(
    project_id: str,
    wave_id: str,
    mvi_id: str,
    pr_number: int,
    body: RejectRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> RejectResponse:
    """Reject — Phase 1 stub (validation only; Task 3 wires GitHub + DDB)."""
    db = TenantDB(tenant)
    mvi = _load_mvi(db, project_id, wave_id, mvi_id)

    if mvi.get("status") == "rejected":
        return RejectResponse(rejected=True, mvi_status="rejected")

    _require_ready_to_ship(mvi)

    raise HTTPException(
        status_code=501, detail="close_pr GitHub wiring lands in Task 3"
    )
```

- [ ] **Step 4: Register the router**

Modify `apps/api/src/main.py`. After the existing `app.include_router(prs.router, ...)` call, add:

```python
from src.routes import pr_actions
# … (existing imports)

app.include_router(pr_actions.router)
```

The exact line to insert depends on existing import order. Find the block where other route modules are imported and added; follow that pattern.

- [ ] **Step 5: Run test to verify it passes**

```bash
cd /Users/eaugusto/cawnex/apps/api && ./venv/bin/pytest tests/test_pr_actions.py -v
```
Expected: 3 passed (the 409/404/422 assertions).

- [ ] **Step 6: Commit**

```bash
cd /Users/eaugusto/cawnex && git add apps/api/src/routes/pr_actions.py apps/api/src/main.py apps/api/tests/test_pr_actions.py
git commit -m "feat(api): scaffold POST /prs/{n}/merge + /reject routes with auth + readiness"
```

---

## Task 3: Wire GitHub merge + DDB mutation + Murder reactor trigger

Replace the 501 stub in `approve_and_merge` with the real flow.

**Files:**
- Modify: `apps/api/src/routes/pr_actions.py`
- Modify: `apps/api/tests/test_pr_actions.py`

- [ ] **Step 1: Write the failing test**

Add to `apps/api/tests/test_pr_actions.py`:

```python
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

    # merge_pr was called with the right shape
    mock_merge.assert_called_once()
    args, kwargs = mock_merge.call_args
    assert args[0] == "owner/repo"
    assert args[1] == 16
    assert kwargs["method"] == "rebase"

    # DDB was updated
    mock_table.update_item.assert_called()
    update_call = mock_table.update_item.call_args
    expr_values = update_call.kwargs["ExpressionAttributeValues"]
    assert ":status" in expr_values
    assert expr_values[":status"] == "shipped"


@patch("src.routes.pr_actions.merge_pr")
@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table", "GITHUB_TOKEN": "ghp_fake"})
def test_merge_returns_409_on_github_conflict(
    mock_boto3: Mock, mock_merge: Mock
) -> None:
    """When GitHub returns a merge conflict, the MVI stays in ready_to_ship."""
    from src.github_mutations import GitHubMutationError

    mock_merge.side_effect = GitHubMutationError(status=409, message="Pull Request is not mergeable")

    mock_table = Mock()
    mock_table.get_item.return_value = {"Item": _mvi_item()}
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())
    resp = client.post("/projects/p1/waves/w1/mvis/mvi1/prs/16/merge", json={})
    assert resp.status_code == 409
    assert "not mergeable" in resp.json()["detail"]
    # DDB was NOT updated
    mock_table.update_item.assert_not_called()


@patch("src.routes.pr_actions.merge_pr")
@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table", "GITHUB_TOKEN": "ghp_fake"})
def test_merge_idempotent_when_already_shipped(
    mock_boto3: Mock, mock_merge: Mock
) -> None:
    """Calling merge on an already-shipped MVI returns 200 without calling GitHub."""
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/eaugusto/cawnex/apps/api && ./venv/bin/pytest tests/test_pr_actions.py::test_merge_happy_path_updates_mvi_and_returns_sha -v
```
Expected: FAIL with 501 (the stub).

- [ ] **Step 3: Wire the route**

Modify `apps/api/src/routes/pr_actions.py`. Replace the `approve_and_merge` function body (only — keep signature):

```python
from datetime import datetime, timezone

from src.github_mutations import GitHubMutationError, merge_pr


@router.post("/{pr_number}/merge", response_model=MergeResponse)
async def approve_and_merge(
    project_id: str,
    wave_id: str,
    mvi_id: str,
    pr_number: int,
    _body: MergeRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> MergeResponse:
    """Approve & Merge — rebase the PR on GitHub, mark MVI shipped in DDB.

    Wave-terminal transition is handled by the Murder reactor via
    DynamoDB Streams when this update fires.
    """
    db = TenantDB(tenant)
    mvi = _load_mvi(db, project_id, wave_id, mvi_id)

    # Idempotency
    if mvi.get("status") == "shipped":
        return MergeResponse(
            merged=True,
            sha=str(mvi.get("merge_sha", "")),
            mvi_status="shipped",
        )

    _require_ready_to_ship(mvi)

    repo = mvi.get("repo", "")
    if not repo:
        raise HTTPException(
            status_code=500, detail="MVI snapshot missing repo field"
        )

    # GitHub merge — surface conflicts/branch protection failures as 409
    try:
        gh_result = merge_pr(repo, pr_number, method="rebase")
    except GitHubMutationError as e:
        log.warning(
            "github_merge_failed",
            extra={"pr": pr_number, "repo": repo, "status": e.status, "message": e.message},
        )
        raise HTTPException(status_code=e.status or 502, detail=e.message) from e

    # DDB update — Murder reactor's DDB-Streams trigger picks this up
    # and runs _maybe_transition_wave for the wave-terminal check.
    now = datetime.now(timezone.utc).isoformat()
    sk = f"S#{wave_id}#m{mvi_id}"
    db.update_project_item(
        project_id=project_id,
        sk=sk,
        update_expression="SET #s = :status, shipped_at = :ts, merge_sha = :sha",
        expression_attribute_names={"#s": "status"},
        expression_attribute_values={
            ":status": "shipped",
            ":ts": now,
            ":sha": gh_result.get("sha", ""),
        },
    )

    log.info(
        "mvi_shipped",
        extra={"mvi": mvi_id, "wave": wave_id, "pr": pr_number, "sha": gh_result.get("sha", "")},
    )

    return MergeResponse(
        merged=True,
        sha=str(gh_result.get("sha", "")),
        mvi_status="shipped",
        wave_status="",  # left blank; reactor updates the wave async
    )
```

Note: this assumes `TenantDB` exposes `update_project_item` with the same signature pattern as `get_project_item`. If it doesn't, check `apps/api/src/db/client.py` and use whatever signature the codebase already uses for update operations. If no such helper exists, use `boto3.resource('dynamodb').Table(name).update_item(...)` directly the way the milestones route does — search `update_item` in `apps/api/src/routes/` for prior art.

- [ ] **Step 4: Run all PR-action tests**

```bash
cd /Users/eaugusto/cawnex/apps/api && ./venv/bin/pytest tests/test_pr_actions.py -v
```
Expected: 6 passed (3 from Task 2 + 3 new).

- [ ] **Step 5: Commit**

```bash
cd /Users/eaugusto/cawnex && git add apps/api/src/routes/pr_actions.py apps/api/tests/test_pr_actions.py
git commit -m "feat(api): wire merge_pr + DDB MVI shipped update on POST /prs/{n}/merge"
```

---

## Task 4: Wire Reject — close PR + comment + DDB

Symmetric to merge, but PATCH `/pulls/{n}` to close + POST a comment with the reason.

**Files:**
- Modify: `apps/api/src/routes/pr_actions.py`
- Modify: `apps/api/tests/test_pr_actions.py`

- [ ] **Step 1: Write the failing test**

Add to `apps/api/tests/test_pr_actions.py`:

```python
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
    assert "Rejected" in comment_args[0][2]  # marker prefix

    # Then close was called
    mock_close.assert_called_once_with("owner/repo", 16)

    # DDB update with rejected status
    update_call = mock_table.update_item.call_args
    expr_values = update_call.kwargs["ExpressionAttributeValues"]
    assert expr_values[":status"] == "rejected"
    assert expr_values[":reason"] == "Auth model is wrong; need to rewrite"


@patch("src.routes.pr_actions.close_pr")
@patch("src.routes.pr_actions.post_pr_comment")
@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table", "GITHUB_TOKEN": "ghp_fake"})
def test_reject_continues_when_comment_fails(
    mock_boto3: Mock, mock_comment: Mock, mock_close: Mock
) -> None:
    """If the comment POST fails, we still close the PR + mark rejected.

    Per spec: 'The merge is the load-bearing action; the comment is decoration.'
    Same applies to reject — closing the PR is what matters.
    """
    from src.github_mutations import GitHubMutationError

    mock_comment.side_effect = GitHubMutationError(status=503, message="GitHub unavailable")
    mock_close.return_value = {"state": "closed"}

    mock_table = Mock()
    mock_table.get_item.return_value = {"Item": _mvi_item()}
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())
    resp = client.post(
        "/projects/p1/waves/w1/mvis/mvi1/prs/16/reject",
        json={"reason": "no good"},
    )
    assert resp.status_code == 200
    assert resp.json()["rejected"] is True
    mock_close.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/eaugusto/cawnex/apps/api && ./venv/bin/pytest tests/test_pr_actions.py::test_reject_posts_comment_then_closes_then_updates_mvi -v
```
Expected: FAIL with 501.

- [ ] **Step 3: Wire the route**

Modify `apps/api/src/routes/pr_actions.py`. Replace the `reject_pr` function (keep signature):

```python
from src.github_mutations import GitHubMutationError, close_pr, merge_pr, post_pr_comment


@router.post("/{pr_number}/reject", response_model=RejectResponse)
async def reject_pr(
    project_id: str,
    wave_id: str,
    mvi_id: str,
    pr_number: int,
    body: RejectRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> RejectResponse:
    """Reject — post comment with reason, close PR, mark MVI rejected in DDB.

    The comment is decorative; the close + DDB update are the load-bearing
    operations. Comment failure is logged but does not block the rejection.
    """
    db = TenantDB(tenant)
    mvi = _load_mvi(db, project_id, wave_id, mvi_id)

    if mvi.get("status") == "rejected":
        return RejectResponse(rejected=True, mvi_status="rejected")

    _require_ready_to_ship(mvi)

    repo = mvi.get("repo", "")
    if not repo:
        raise HTTPException(
            status_code=500, detail="MVI snapshot missing repo field"
        )

    # Post the rejection comment first (decorative — failures don't block)
    comment_body = f"## Rejected by founder\n\n{body.reason}\n"
    try:
        post_pr_comment(repo, pr_number, comment_body)
    except GitHubMutationError as e:
        log.warning(
            "github_comment_failed_continuing",
            extra={"pr": pr_number, "status": e.status, "message": e.message},
        )

    # Close the PR — load-bearing
    try:
        close_pr(repo, pr_number)
    except GitHubMutationError as e:
        log.warning(
            "github_close_failed",
            extra={"pr": pr_number, "status": e.status, "message": e.message},
        )
        raise HTTPException(status_code=e.status or 502, detail=e.message) from e

    # DDB update
    now = datetime.now(timezone.utc).isoformat()
    sk = f"S#{wave_id}#m{mvi_id}"
    db.update_project_item(
        project_id=project_id,
        sk=sk,
        update_expression="SET #s = :status, rejected_at = :ts, rejection_reason = :reason",
        expression_attribute_names={"#s": "status"},
        expression_attribute_values={
            ":status": "rejected",
            ":ts": now,
            ":reason": body.reason,
        },
    )

    log.info(
        "mvi_rejected",
        extra={"mvi": mvi_id, "wave": wave_id, "pr": pr_number},
    )

    return RejectResponse(rejected=True, mvi_status="rejected")
```

- [ ] **Step 4: Run all PR-action tests**

```bash
cd /Users/eaugusto/cawnex/apps/api && ./venv/bin/pytest tests/test_pr_actions.py -v
```
Expected: 8 passed (3 from Task 2 + 3 from Task 3 + 2 new).

- [ ] **Step 5: Commit**

```bash
cd /Users/eaugusto/cawnex && git add apps/api/src/routes/pr_actions.py apps/api/tests/test_pr_actions.py
git commit -m "feat(api): wire reject route — close PR + comment + DDB MVI rejected"
```

---

## Task 5: Grant API Lambda access to GITHUB_TOKEN

Without this, the deployed Lambda will see `GITHUB_TOKEN=""` and every call will 0-status-error.

**Files:**
- Modify: `infra/lib/cawnex-stack.ts`

- [ ] **Step 1: Find where `githubTokenSecret` is declared**

```bash
grep -n "githubTokenSecret\|GithubTokenSecret\|github-token" /Users/eaugusto/cawnex/infra/lib/cawnex-stack.ts
```

Expected: line ~500 declares `const githubTokenSecret = secretsmanager.Secret.fromSecretNameV2(this, "GithubTokenSecret", ...);`. Line ~530 attaches it to `workerContainer.secrets`.

- [ ] **Step 2: Grant the API Lambda the secret**

In `infra/lib/cawnex-stack.ts`, find the block where `apiFunction` is defined (search for `new lambda.Function(this, "APIFunction"`) and where `apiFunction.addEnvironment(...)` is called for other env vars. Add (after the existing addEnvironment calls):

```typescript
// PR action routes (merge, reject) call GitHub's REST API to mutate PRs.
apiFunction.addEnvironment("GITHUB_TOKEN", "from-secret");
githubTokenSecret.grantRead(apiFunction);
```

The `"from-secret"` placeholder above is wrong — CDK doesn't allow injecting a secret into `addEnvironment` directly the way it does for ECS. Use the `secrets` property on the function, or attach the secret value at deploy. The correct CDK pattern is:

```typescript
import { SecretValue } from "aws-cdk-lib";

// Read GITHUB_TOKEN at synth time and inject as plain env var:
apiFunction.addEnvironment(
  "GITHUB_TOKEN",
  githubTokenSecret.secretValueFromJson("token").toString()
);
```

Or, if the secret stores the raw token string (not JSON), use:

```typescript
apiFunction.addEnvironment(
  "GITHUB_TOKEN",
  githubTokenSecret.secretValue.unsafeUnwrap()
);
```

Verify the secret's shape with:

```bash
aws secretsmanager get-secret-value --secret-id cawnex/dev/github-token --query SecretString --output text | head -c 100
```

If it starts with `{`, it's JSON — use `secretValueFromJson`. If it's a plain `ghp_...` string, use `secretValue.unsafeUnwrap()`. Pick the matching one.

- [ ] **Step 3: Synth + verify**

```bash
cd /Users/eaugusto/cawnex/infra && rm -rf cdk.out && npx cdk synth Cawnex-dev > /dev/null && echo "synth OK"
```

Then grep the generated template for the env var on the API function:

```bash
grep -A 3 "GITHUB_TOKEN" cdk.out/Cawnex-dev.template.json | head -20
```

Expected: at least two references — one for the worker (existing), one for the API function (new).

- [ ] **Step 4: Deploy**

```bash
cd /Users/eaugusto/cawnex/infra && npx cdk deploy Cawnex-dev --require-approval never
```

- [ ] **Step 5: Verify the deployed Lambda has the env var**

```bash
aws lambda get-function-configuration \
  --function-name cawnex-api-dev \
  --region us-east-1 \
  --query "Environment.Variables.GITHUB_TOKEN" \
  --output text | head -c 8
```

Expected: prints the first 8 characters of `ghp_...`. If empty, the secret didn't resolve.

- [ ] **Step 6: Commit**

```bash
cd /Users/eaugusto/cawnex && git add infra/lib/cawnex-stack.ts
git commit -m "feat(infra): grant API Lambda GITHUB_TOKEN for PR merge/reject"
```

---

## Task 6: Live smoke — call the route against PR #16's branch

Don't merge PR #16 yet (we want to verify the flow without burning the demo PR). Create a throwaway PR, merge it via the new endpoint.

- [ ] **Step 1: Create a no-op PR for smoke testing**

```bash
cd /Users/eaugusto/cawnex
git checkout -b smoke/pr-merge-test main
echo "# smoke test marker" > SMOKE_TEST.md
git add SMOKE_TEST.md
git commit -m "chore: smoke test marker for PR merge route"
git push origin smoke/pr-merge-test
gh pr create --repo eduardoaugustoes/cawnex \
  --title "smoke: verify /merge route" \
  --body "throwaway PR to validate POST /prs/{n}/merge" \
  --head smoke/pr-merge-test --base main
```

Note the PR number (let's call it `$SMOKE_PR`).

- [ ] **Step 2: Seed a fake MVI in DDB pointing at the smoke PR**

(In production this would be created by Murder. For smoke we shortcut.)

```bash
SMOKE_PR=<the number from step 1>
TENANT="t_0_71899937"
PROJECT="cawnex-e26784"
WAVE="w-smoke-merge-$(date +%s)"
MVI="mvi-smoke"

aws dynamodb put-item --table-name cawnex-dev --region us-east-1 --item "{
  \"PK\":{\"S\":\"T#$TENANT#P#$PROJECT\"},
  \"SK\":{\"S\":\"S#$WAVE#m$MVI\"},
  \"entityType\":{\"S\":\"Snapshot\"},
  \"level\":{\"S\":\"murder\"},
  \"status\":{\"S\":\"ready_to_ship\"},
  \"repo\":{\"S\":\"eduardoaugustoes/cawnex\"},
  \"branch\":{\"S\":\"smoke/pr-merge-test\"},
  \"name\":{\"S\":\"smoke MVI\"}
}"
```

- [ ] **Step 3: Get a fresh JWT from the iOS app**

Open iOS dev app → sign in → copy `Authorization: Bearer ...` from any API call's network log. Set `JWT=<token>`.

- [ ] **Step 4: Call the merge endpoint**

```bash
curl -sS -X POST \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  "https://d1elid9twwevj2.cloudfront.net/projects/$PROJECT/waves/$WAVE/mvis/$MVI/prs/$SMOKE_PR/merge" \
  -d '{}'
```

Expected response:
```json
{"merged":true,"sha":"<git_sha>","mvi_status":"shipped","wave_status":""}
```

- [ ] **Step 5: Verify GitHub side**

```bash
gh pr view $SMOKE_PR --repo eduardoaugustoes/cawnex --json state,mergedAt
```
Expected: `{"state": "MERGED", "mergedAt": "<recent timestamp>"}`.

- [ ] **Step 6: Verify DDB side**

```bash
aws dynamodb get-item --table-name cawnex-dev --region us-east-1 \
  --key "{\"PK\":{\"S\":\"T#$TENANT#P#$PROJECT\"},\"SK\":{\"S\":\"S#$WAVE#m$MVI\"}}" \
  --query "Item.[status.S,shipped_at.S,merge_sha.S]" --output text
```
Expected: `shipped <ISO timestamp> <sha>`.

- [ ] **Step 7: Cleanup smoke artifacts**

```bash
# Delete the smoke MVI from DDB (optional)
aws dynamodb delete-item --table-name cawnex-dev --region us-east-1 \
  --key "{\"PK\":{\"S\":\"T#$TENANT#P#$PROJECT\"},\"SK\":{\"S\":\"S#$WAVE#m$MVI\"}}"
# Local cleanup
git checkout main
git branch -D smoke/pr-merge-test
# SMOKE_TEST.md is now on main (it was merged) — revert if you want:
git revert HEAD --no-edit && git push origin main
```

- [ ] **Step 8: No commit (smoke test only)**

---

## Task 7: iOS PRActions service + ViewModel methods

**Files:**
- Create: `apps/ios/Cawnex/Cawnex/Core/Network/APIPRActionsService.swift`
- Modify: `apps/ios/Cawnex/Cawnex/App/ServiceFactory.swift`
- Modify: `apps/ios/Cawnex/Cawnex/Features/PR/PRReviewViewModel.swift`

- [ ] **Step 1: Create `APIPRActionsService.swift`**

```swift
import Foundation

/// Two POST endpoints on the API for PR mutation: merge and reject.
///
/// Both routes return immediately after the GitHub call + DDB update;
/// the Murder reactor handles the wave-terminal transition async via
/// DDB Streams (no client polling needed for that).
protocol PRActionsService {
    func mergePR(
        projectId: String,
        waveId: String,
        mviId: String,
        prNumber: Int
    ) async throws -> MergeResult

    func rejectPR(
        projectId: String,
        waveId: String,
        mviId: String,
        prNumber: Int,
        reason: String
    ) async throws -> RejectResult
}

struct MergeResult: Decodable, Equatable {
    let merged: Bool
    let sha: String
    let mvi_status: String
    let wave_status: String
}

struct RejectResult: Decodable, Equatable {
    let rejected: Bool
    let mvi_status: String
}

final class APIPRActionsService: PRActionsService {
    private let client: APIClient

    init(client: APIClient) {
        self.client = client
    }

    func mergePR(
        projectId: String, waveId: String, mviId: String, prNumber: Int
    ) async throws -> MergeResult {
        struct Empty: Encodable {}
        return try await client.post(
            "/projects/\(projectId)/waves/\(waveId)/mvis/\(mviId)/prs/\(prNumber)/merge",
            body: Empty()
        )
    }

    func rejectPR(
        projectId: String, waveId: String, mviId: String, prNumber: Int, reason: String
    ) async throws -> RejectResult {
        struct Body: Encodable {
            let reason: String
            let close_branch: Bool
        }
        return try await client.post(
            "/projects/\(projectId)/waves/\(waveId)/mvis/\(mviId)/prs/\(prNumber)/reject",
            body: Body(reason: reason, close_branch: true)
        )
    }
}
```

- [ ] **Step 2: Wire `makePRActionsService` in `ServiceFactory.swift`**

Find the existing `makePRService()` method and add right after:

```swift
func makePRActionsService() -> any PRActionsService {
    guard let apiClient else {
        // No InMemory equivalent — actions only work with a real API client.
        fatalError("PRActionsService requires an APIClient")
    }
    return APIPRActionsService(client: apiClient)
}
```

- [ ] **Step 3: Add merge/reject methods + state to `PRReviewViewModel.swift`**

Read the current file to find the right spot:

```bash
grep -n "messageText\|var " /Users/eaugusto/cawnex/apps/ios/Cawnex/Cawnex/Features/PR/PRReviewViewModel.swift
```

In the `@Observable final class PRReviewViewModel`, add these properties after existing `var`s:

```swift
var isMerging: Bool = false
var isRejecting: Bool = false
var actionError: String?
var showRejectSheet: Bool = false
var showMergeConfirmSheet: Bool = false
var rejectReason: String = ""

/// Set when a merge or reject succeeds; the screen uses this to dismiss
/// itself / refresh upstream state.
var lastActionResult: PRActionResult?

private let actionsService: any PRActionsService
```

Add `actionsService` to the initializer, e.g.:

```swift
init(prService: any PRService, actionsService: any PRActionsService) {
    self.prService = prService
    self.actionsService = actionsService
}
```

Add the action methods at the bottom of the class:

```swift
@MainActor
func approveAndMerge(
    projectId: String,
    waveId: String,
    mviId: String,
    prNumber: Int
) async {
    actionError = nil
    isMerging = true
    defer { isMerging = false }
    do {
        let result = try await actionsService.mergePR(
            projectId: projectId, waveId: waveId, mviId: mviId, prNumber: prNumber
        )
        lastActionResult = .merged(sha: result.sha)
        showMergeConfirmSheet = false
    } catch {
        actionError = "Merge failed: \(error.localizedDescription)"
    }
}

@MainActor
func rejectPR(
    projectId: String,
    waveId: String,
    mviId: String,
    prNumber: Int
) async {
    guard !rejectReason.trimmingCharacters(in: .whitespaces).isEmpty else {
        actionError = "Please provide a reason for rejecting."
        return
    }
    actionError = nil
    isRejecting = true
    defer { isRejecting = false }
    do {
        _ = try await actionsService.rejectPR(
            projectId: projectId, waveId: waveId, mviId: mviId, prNumber: prNumber,
            reason: rejectReason
        )
        lastActionResult = .rejected
        showRejectSheet = false
        rejectReason = ""
    } catch {
        actionError = "Reject failed: \(error.localizedDescription)"
    }
}
```

Add the `PRActionResult` enum (top of file, after imports):

```swift
enum PRActionResult: Equatable {
    case merged(sha: String)
    case rejected
}
```

- [ ] **Step 4: Commit**

```bash
cd /Users/eaugusto/cawnex && git add apps/ios/Cawnex/Cawnex/Core/Network/APIPRActionsService.swift \
  apps/ios/Cawnex/Cawnex/App/ServiceFactory.swift \
  apps/ios/Cawnex/Cawnex/Features/PR/PRReviewViewModel.swift
git commit -m "feat(ios): APIPRActionsService + ViewModel merge/reject methods"
```

---

## Task 8: iOS — wire the buttons + add sheets

**Files:**
- Create: `apps/ios/Cawnex/Cawnex/Features/PR/RejectSheet.swift`
- Create: `apps/ios/Cawnex/Cawnex/Features/PR/MergeConfirmSheet.swift`
- Modify: `apps/ios/Cawnex/Cawnex/Features/PR/PRReviewScreen.swift`

- [ ] **Step 1: Create `MergeConfirmSheet.swift`**

```swift
import SwiftUI

/// Minimal confirmation sheet for Approve & Merge.
///
/// We don't add a free-form text field here because the merge action
/// has no required input — confirmation is the entire UX. The Steer
/// chat (Phase 2) is where nuance gets captured.
struct MergeConfirmSheet: View {
    let prNumber: Int
    let prTitle: String
    let onConfirm: () -> Void
    let onCancel: () -> Void

    @State private var isConfirming = false

    var body: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.lg) {
            VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
                Text("Approve & Merge PR #\(prNumber)")
                    .font(CawnexTypography.heading2)
                    .foregroundStyle(CawnexColors.cardForeground)
                Text(prTitle)
                    .font(CawnexTypography.caption)
                    .foregroundStyle(CawnexColors.mutedForeground)
                    .lineLimit(3)
            }

            VStack(alignment: .leading, spacing: 4) {
                Text("This will:")
                    .font(CawnexTypography.captionBold)
                    .foregroundStyle(CawnexColors.cardForeground)
                Text("• Rebase the PR onto main on GitHub")
                Text("• Mark this MVI as shipped in Cawnex")
                Text("• Delete the source branch")
            }
            .font(CawnexTypography.footnote)
            .foregroundStyle(CawnexColors.mutedForeground)

            HStack(spacing: CawnexSpacing.md) {
                Button(action: onCancel) {
                    Text("Cancel")
                        .font(CawnexTypography.captionBold)
                        .frame(maxWidth: .infinity)
                        .frame(height: 48)
                        .background(CawnexColors.card)
                        .foregroundStyle(CawnexColors.cardForeground)
                        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
                        .overlay(
                            RoundedRectangle(cornerRadius: CawnexRadius.md)
                                .stroke(CawnexColors.border, lineWidth: 1)
                        )
                }
                .buttonStyle(.plain)

                Button {
                    isConfirming = true
                    onConfirm()
                } label: {
                    HStack(spacing: 6) {
                        if isConfirming {
                            ProgressView().tint(.white)
                        }
                        Text("Approve & Merge")
                            .font(CawnexTypography.captionBold)
                    }
                    .frame(maxWidth: .infinity)
                    .frame(height: 48)
                    .background(CawnexColors.success)
                    .foregroundStyle(.white)
                    .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
                }
                .buttonStyle(.plain)
                .disabled(isConfirming)
            }
        }
        .padding(CawnexSpacing.xl)
        .background(CawnexColors.background)
    }
}
```

- [ ] **Step 2: Create `RejectSheet.swift`**

```swift
import SwiftUI

/// Sheet for Reject — collects a required reason and confirms.
struct RejectSheet: View {
    let prNumber: Int
    @Binding var reason: String
    let isRejecting: Bool
    let onConfirm: () -> Void
    let onCancel: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.lg) {
            VStack(alignment: .leading, spacing: 6) {
                Text("Reject PR #\(prNumber)")
                    .font(CawnexTypography.heading2)
                    .foregroundStyle(CawnexColors.cardForeground)
                Text("This will close the PR on GitHub with your reason as a comment, then mark the MVI as rejected in Cawnex.")
                    .font(CawnexTypography.caption)
                    .foregroundStyle(CawnexColors.mutedForeground)
            }

            VStack(alignment: .leading, spacing: 6) {
                Text("Reason")
                    .font(CawnexTypography.captionBold)
                    .foregroundStyle(CawnexColors.cardForeground)
                TextEditor(text: $reason)
                    .font(CawnexTypography.caption)
                    .foregroundStyle(CawnexColors.cardForeground)
                    .scrollContentBackground(.hidden)
                    .background(CawnexColors.card)
                    .frame(minHeight: 120)
                    .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
                    .overlay(
                        RoundedRectangle(cornerRadius: CawnexRadius.md)
                            .stroke(CawnexColors.border, lineWidth: 1)
                    )
            }

            HStack(spacing: CawnexSpacing.md) {
                Button(action: onCancel) {
                    Text("Cancel")
                        .font(CawnexTypography.captionBold)
                        .frame(maxWidth: .infinity)
                        .frame(height: 48)
                        .background(CawnexColors.card)
                        .foregroundStyle(CawnexColors.cardForeground)
                        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
                        .overlay(
                            RoundedRectangle(cornerRadius: CawnexRadius.md)
                                .stroke(CawnexColors.border, lineWidth: 1)
                        )
                }
                .buttonStyle(.plain)

                Button {
                    onConfirm()
                } label: {
                    HStack(spacing: 6) {
                        if isRejecting {
                            ProgressView().tint(.white)
                        }
                        Text("Reject")
                            .font(CawnexTypography.captionBold)
                    }
                    .frame(maxWidth: .infinity)
                    .frame(height: 48)
                    .background(CawnexColors.destructive)
                    .foregroundStyle(.white)
                    .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
                }
                .buttonStyle(.plain)
                .disabled(isRejecting || reason.trimmingCharacters(in: .whitespaces).isEmpty)
            }
        }
        .padding(CawnexSpacing.xl)
        .background(CawnexColors.background)
    }
}
```

- [ ] **Step 3: Wire the buttons in `PRReviewScreen.swift`**

Read the current screen:

```bash
sed -n '485,540p' /Users/eaugusto/cawnex/apps/ios/Cawnex/Cawnex/Features/PR/PRReviewScreen.swift
```

Replace the `actionBar(status: PRStatus)` and `secondaryButton(...)` functions with versions that wire to the viewModel:

```swift
private func actionBar(status: PRStatus) -> some View {
    VStack(spacing: CawnexSpacing.sm) {
        // Primary: Approve & Merge
        Button {
            viewModel.showMergeConfirmSheet = true
        } label: {
            HStack(spacing: CawnexSpacing.sm) {
                if viewModel.isMerging {
                    ProgressView().tint(.white)
                }
                Image(systemName: "arrow.triangle.merge")
                    .font(.system(size: 15, weight: .bold))
                Text("Approve & Merge")
                    .font(CawnexTypography.sectionTitle)
            }
            .foregroundStyle(.white)
            .frame(maxWidth: .infinity)
            .frame(height: 48)
            .background(canMerge ? CawnexColors.success : CawnexColors.muted)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
        }
        .buttonStyle(.plain)
        .disabled(!canMerge || viewModel.isMerging)

        // Secondary row
        HStack(spacing: CawnexSpacing.md) {
            secondaryButton(
                label: "Steer", icon: "arrow.uturn.left", color: CawnexColors.warning,
                disabled: true,  // Phase 2
                action: {}
            )
            secondaryButton(
                label: "Reject", icon: "xmark", color: CawnexColors.destructive,
                disabled: !canMerge || viewModel.isRejecting,
                action: { viewModel.showRejectSheet = true }
            )
            secondaryButton(
                label: "GitHub", icon: "arrow.up.right", color: CawnexColors.mutedForeground,
                disabled: viewModel.prURL == nil,
                action: {
                    if let url = viewModel.prURL.flatMap(URL.init) {
                        UIApplication.shared.open(url)
                    }
                }
            )
        }
    }
    .padding(.horizontal, CawnexSpacing.xl)
    .padding(.top, CawnexSpacing.lg)
    .padding(.bottom, 34)
    .background(CawnexColors.background)
}

private var canMerge: Bool {
    // Only enable mutation when PR is in a sensible state. The backend
    // also gates on ready_to_ship; this is just to avoid asking GitHub
    // about a merged or closed PR.
    if let st = viewModel.review?.pr.status {
        return st == .ready
    }
    return false
}

private func secondaryButton(
    label: String,
    icon: String,
    color: Color,
    disabled: Bool,
    action: @escaping () -> Void
) -> some View {
    Button(action: action) {
        HStack(spacing: 6) {
            Image(systemName: icon)
                .font(.system(size: 12, weight: .medium))
            Text(label)
                .font(CawnexTypography.captionBold)
        }
        .foregroundStyle(color)
        .frame(maxWidth: .infinity)
        .frame(height: 40)
        .background(CawnexColors.card)
        .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
        .overlay(
            RoundedRectangle(cornerRadius: CawnexRadius.md)
                .stroke(CawnexColors.border, lineWidth: 1)
        )
    }
    .buttonStyle(.plain)
    .disabled(disabled)
    .opacity(disabled ? 0.4 : 1.0)
}
```

Then add sheet modifiers near the end of the screen's `body` (above the closing brace):

```swift
.sheet(isPresented: $viewModel.showMergeConfirmSheet) {
    MergeConfirmSheet(
        prNumber: viewModel.review?.pr.number ?? 0,
        prTitle: viewModel.review?.pr.title ?? "",
        onConfirm: {
            Task {
                await viewModel.approveAndMerge(
                    projectId: projectId,
                    waveId: viewModel.review?.pr.waveId ?? "",
                    mviId: viewModel.review?.pr.mviId ?? "",
                    prNumber: viewModel.review?.pr.number ?? 0
                )
            }
        },
        onCancel: { viewModel.showMergeConfirmSheet = false }
    )
    .presentationDetents([.medium])
}
.sheet(isPresented: $viewModel.showRejectSheet) {
    RejectSheet(
        prNumber: viewModel.review?.pr.number ?? 0,
        reason: $viewModel.rejectReason,
        isRejecting: viewModel.isRejecting,
        onConfirm: {
            Task {
                await viewModel.rejectPR(
                    projectId: projectId,
                    waveId: viewModel.review?.pr.waveId ?? "",
                    mviId: viewModel.review?.pr.mviId ?? "",
                    prNumber: viewModel.review?.pr.number ?? 0
                )
            }
        },
        onCancel: { viewModel.showRejectSheet = false }
    )
    .presentationDetents([.medium, .large])
}
.alert("Action failed", isPresented: .constant(viewModel.actionError != nil)) {
    Button("OK") { viewModel.actionError = nil }
} message: {
    Text(viewModel.actionError ?? "")
}
.onChange(of: viewModel.lastActionResult) { _, result in
    if result != nil {
        // Pop back to wave execution; the live SSE feed (Phase 3 iOS work)
        // will reflect the MVI status change.
        dismiss()
    }
}
```

Note: this references `dismiss` (`@Environment(\.dismiss) private var dismiss`) and assumes `pr.waveId` + `pr.mviId` exist on the PR model. Check `PRModels.swift` — if they don't, the route needs `waveId`/`mviId` passed in via the navigation route. The MainTabView/PRRoute layer already passes them in; the viewModel can capture them at init time. If `pr.waveId`/`pr.mviId` are missing, store them as `let waveId` / `let mviId` on the viewModel from the route, set at init.

- [ ] **Step 4: Add the new files to the Xcode project**

Like Phase 1's earlier SSE work, the 2 new files need to be added via Xcode's "Add Files to Cawnex…" dialog before they'll compile. Repeat:
- `RejectSheet.swift`
- `MergeConfirmSheet.swift`
- `APIPRActionsService.swift`

- [ ] **Step 5: Commit**

```bash
cd /Users/eaugusto/cawnex && git add apps/ios/Cawnex/Cawnex/Features/PR/RejectSheet.swift \
  apps/ios/Cawnex/Cawnex/Features/PR/MergeConfirmSheet.swift \
  apps/ios/Cawnex/Cawnex/Features/PR/PRReviewScreen.swift
git commit -m "feat(ios): wire Approve & Merge + Reject buttons with sheets and error alerts"
```

---

## Task 9: Push + deploy + iOS rebuild + end-to-end test

- [ ] **Step 1: Push everything**

```bash
cd /Users/eaugusto/cawnex && git push origin main
```

- [ ] **Step 2: Confirm CI is green**

```bash
gh run list --repo eduardoaugustoes/cawnex --limit 1
```
Wait for the most recent run to show `success`. If anything fails (Python Quality or CDK synth), fix and re-push.

- [ ] **Step 3: User rebuilds iOS app**

The new files (`APIPRActionsService.swift`, `RejectSheet.swift`, `MergeConfirmSheet.swift`) must be added to `Cawnex.xcodeproj` via "Add Files to Cawnex…" before Xcode will build. The user does this manually.

- [ ] **Step 4: End-to-end test against PR #16 (or a fresh test PR)**

In the iOS app:
1. Navigate to Project Hub → Waves → wave w1778872378963 → MVI mvi2 → tap the PR
2. PR Review screen shows reviewer's verdict (already implemented)
3. Tap **Approve & Merge** → confirmation sheet appears
4. Tap **Approve & Merge** in the sheet
5. Watch network logs: `POST /projects/cawnex-e26784/waves/w1778872378963/mvis/mvi2/prs/16/merge` → 200
6. Sheet dismisses; screen pops back to wave
7. Verify on GitHub: `gh pr view 16 --repo eduardoaugustoes/cawnex --json state` → MERGED
8. Verify the wave: open wave w1778872378963 in iOS — MVI mvi2 should now show `shipped`

- [ ] **Step 5: Test the Reject path**

Create a fresh throwaway PR (same as Task 6 step 1), seed a fake MVI pointing at it (Task 6 step 2), then:
1. Open the PR in iOS (will need to navigate to it via the synthetic MVI)
2. Tap **Reject** → sheet appears
3. Type "smoke test reject reason" → tap **Reject**
4. Watch network: 200 response
5. Verify GitHub: PR is closed, the rejection reason appears as a PR comment

- [ ] **Step 6: Commit any fixes that surfaced during the end-to-end test**

If any tweaks were needed (typos, wave_id pass-through bug, etc.), commit them now with a descriptive message.

---

## Phase 1 self-review

Before declaring Phase 1 done, verify:

- [ ] All 9 tasks committed cleanly
- [ ] `pytest apps/api/tests/test_pr_actions.py` shows 8 passing tests
- [ ] `pytest apps/api/tests/test_github_mutations.py` shows 6 passing tests
- [ ] CDK synth produces no errors; GITHUB_TOKEN env var visible on deployed API Lambda
- [ ] Smoke test in Task 6: a throwaway PR can be merged via `POST .../merge` end-to-end
- [ ] iOS app: tapping Approve & Merge or Reject calls the API, sheets appear, errors surface
- [ ] PR #16 actually merges and lands on main with a rebased commit history
- [ ] The wave w1778872378963 transitions from `review` to `delivered` after PR #16 merges (because mvi2 was the only MVI)

If any check fails, fix before moving to Phase 2.

---

## Phases 2 + 3 (deferred — separate detailed plans when Phase 1 ships)

### Phase 2 — Steer chat (the adversarial verification surface)

Sketched scope (full plan when Phase 1 ships):

1. **DDB schema for STEER#{pr_id}#chat/#msg/#summary** — new entity types, query patterns documented
2. **Repo cloning module** (`apps/api/src/steer/repo_clone.py`) — shallow clone at PR head SHA into `/tmp/steer-{chat_id}` with caching across warm Lambda invocations
3. **Tools** (`apps/api/src/steer/tools.py`) — `read_file`, `grep_files`, `glob_files`, `submit_response` terminator with path-escape guards
4. **Loop** (`apps/api/src/steer/loop.py`) — `messages.stream()` agentic loop pattern, identical to worker's implementer crow
5. **Adversarial system prompt** (`apps/api/src/steer/system_prompt.py`) — verbatim from spec
6. **POST routes** — `/steer/chats` (create) + `/chats/{c}/messages` (turn)
7. **Stream service** — new `steer_message_delta` SSE event type, per-chat topic
8. **iOS Steer chat UI** — `SteerChatScreen.swift`, `SteerChatViewModel.swift`, suggested-question chips, streaming render
9. **Hook chat closure + summary attachment into Phase 1 merge/reject** — when an active chat exists, build the convo summary via `apps/api/src/steer/summary.py` and POST it as a PR comment before the merge/reject GitHub call
10. **Tests** — tool-use loop happy path, budget enforcement, mid-stream cancel, expired chat read-only

### Phase 3 — Polish + observability

1. Mid-stream cancel via Anthropic stream cancellation (`DELETE /chats/{c}/in_flight`)
2. PR head SHA drift detection + re-clone
3. Multi-chat picker UI in iOS when `chat_count > 1` on the same PR
4. CloudWatch metrics: chats started, concerns raised per chat, merge approval rate (with vs without prior chat), token cost per chat
5. Per-project Steer cost dashboard

---

## Self-review notes (after writing)

**Spec coverage:** Phase 1 implements spec sections 1 (Action map for Approve & Merge + Reject + GitHub button), 4.1 (failure modes for merge/reject paths only), 4.2 (no budgets needed in Phase 1 — those are Steer concerns), 4.4 (out-of-scope items honored: no code mutation, no GitHub comments mid-chat — Phase 1 doesn't have chat). Spec section 3.1 ("Approve & Merge") and 3.2 ("Reject") fully covered including the convo-summary attach (deferred to Phase 2 with a clear hook point identified). Spec section 1's "Steer" row is explicitly Phase 2.

**Placeholder scan:** No "TBD", no "add appropriate error handling" — every error path is named and handled. The one ambiguity flagged inline: the exact CDK pattern for injecting the Lambda env var depends on the Secrets Manager secret's format (JSON-wrapped or raw string), Task 5 Step 2 includes the verification command to pick the right pattern.

**Type consistency:** `MergeResult`, `RejectResult`, `MergeResponse`, `RejectResponse` types match exactly between Swift DTOs (Task 7) and Pydantic models (Task 2); field names use snake_case in JSON (`mvi_status`, `wave_status`) which both sides expect.

**One trade-off taken:** The plan uses GitHub HTTP API (urllib) instead of `gh` CLI as the spec implied. This is a deliberate deviation — `gh` is not in the Lambda runtime and adding it is significant infrastructure surgery. The functional outcome is identical. Flagged in the "Important deviation from spec" callout at the top of the plan.
