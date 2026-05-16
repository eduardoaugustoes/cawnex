"""PR action routes — Approve & Merge, Reject.

Both routes follow the same shape:
  1. Authenticate (get_tenant dep).
  2. Read the MVI snapshot at PK=T#{tenant}#P#{project}, SK=S#{wave}#m{mvi}.
  3. Validate MVI is `ready_to_ship`.
  4. Call GitHub (PUT merge / PATCH close + POST comment).
  5. Update DDB MVI status. Murder reactor's DDB-Streams trigger handles
     the wave-terminal check automatically (no in-process call).

Phase 2 will add Steer chat summary attachment before the GitHub call.
For Phase 1, the reject comment is the founder's reason; merge posts
no comment.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.auth.dependencies import get_tenant
from src.auth.tenant import TenantContext
from src.db.client import TenantDB
from src.github_mutations import (
    GitHubMutationError,
    close_pr,
    merge_pr,
    post_pr_comment,
)

router = APIRouter(
    prefix="/projects/{project_id}/waves/{wave_id}/mvis/{mvi_id}/prs",
    tags=["pr-actions"],
)
log = logging.getLogger(__name__)


# ---- request / response models -------------------------------------------


class MergeRequest(BaseModel):
    """Empty body for Phase 1; Phase 2 may add optional commit_title."""


class MergeResponse(BaseModel):
    """Response shape for the Approve & Merge route."""

    merged: bool
    sha: str = ""
    mvi_status: str
    wave_status: str = ""


class RejectRequest(BaseModel):
    """Body for the Reject route — founder's reason is required."""

    reason: str = Field(..., min_length=1, max_length=2000)
    close_branch: bool = True


class RejectResponse(BaseModel):
    """Response shape for the Reject route."""

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
    """409 if the MVI isn't ready to ship."""
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
    """Approve & Merge — rebase the PR on GitHub, mark MVI shipped in DDB.

    Wave-terminal transition is handled by the Murder reactor via DynamoDB
    Streams when this snapshot update fires; the route does not call into
    Murder synchronously.
    """
    db = TenantDB(tenant)
    mvi = _load_mvi(db, project_id, wave_id, mvi_id)

    # Idempotency: if already shipped, return current state without
    # re-mutating GitHub or DDB.
    if mvi.get("status") == "shipped":
        return MergeResponse(
            merged=True,
            sha=str(mvi.get("merge_sha", "")),
            mvi_status="shipped",
        )

    _require_ready_to_ship(mvi)

    repo = mvi.get("repo", "")
    if not repo:
        raise HTTPException(status_code=500, detail="MVI snapshot missing repo field")

    # GitHub merge — conflicts/branch-protection failures surface as 409
    try:
        gh_result = merge_pr(repo, pr_number, method="rebase")
    except GitHubMutationError as e:
        log.warning(
            "github_merge_failed pr=%s repo=%s status=%s message=%s",
            pr_number,
            repo,
            e.status,
            e.message,
        )
        raise HTTPException(status_code=e.status or 502, detail=e.message) from e

    # DDB update — Murder reactor's DDB-Streams trigger picks this up and
    # runs _maybe_transition_wave for the wave-terminal check.
    now = datetime.now(timezone.utc).isoformat()
    sk = f"S#{wave_id}#m{mvi_id}"
    db.update_project_item(
        project_id=project_id,
        sk=sk,
        updates={
            "status": "shipped",
            "shipped_at": now,
            "merge_sha": gh_result.get("sha", ""),
        },
    )

    log.info(
        "mvi_shipped mvi=%s wave=%s pr=%s sha=%s",
        mvi_id,
        wave_id,
        pr_number,
        gh_result.get("sha", ""),
    )

    return MergeResponse(
        merged=True,
        sha=str(gh_result.get("sha", "")),
        mvi_status="shipped",
        wave_status="",  # left blank; reactor updates the wave async
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
    """Reject — post comment with reason, close PR, mark MVI rejected.

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
        raise HTTPException(status_code=500, detail="MVI snapshot missing repo field")

    # Post the rejection comment first (decorative — failures don't block)
    comment_body = f"## Rejected by founder\n\n{body.reason}\n"
    try:
        post_pr_comment(repo, pr_number, comment_body)
    except GitHubMutationError as e:
        log.warning(
            "github_comment_failed_continuing pr=%s status=%s message=%s",
            pr_number,
            e.status,
            e.message,
        )

    # Close the PR — load-bearing
    try:
        close_pr(repo, pr_number)
    except GitHubMutationError as e:
        log.warning(
            "github_close_failed pr=%s status=%s message=%s",
            pr_number,
            e.status,
            e.message,
        )
        raise HTTPException(status_code=e.status or 502, detail=e.message) from e

    # DDB update
    now = datetime.now(timezone.utc).isoformat()
    sk = f"S#{wave_id}#m{mvi_id}"
    db.update_project_item(
        project_id=project_id,
        sk=sk,
        updates={
            "status": "rejected",
            "rejected_at": now,
            "rejection_reason": body.reason,
        },
    )

    log.info(
        "mvi_rejected mvi=%s wave=%s pr=%s",
        mvi_id,
        wave_id,
        pr_number,
    )

    return RejectResponse(rejected=True, mvi_status="rejected")
