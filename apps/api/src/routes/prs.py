"""PR detail route — fetches GitHub PR info enriched with reviewer outcome.

PR data is stitched from three sources:

1. **DDB implementer snapshot**: `branch`, `pr.number`, `pr.url`, branch, cost.
2. **GitHub API** (cached 1h): `title`, `state`, `additions`, `deletions`,
   `changed_files`. Fetched fresh on cache miss, served from
   `T#{tenant}#GHCACHE` partition with `expires_at` TTL on subsequent hits.
3. **DDB reviewer outcome**: `approved`, `blocking_issues`, `summary` —
   used to build the iOS PRVerdict block.

Fields iOS expects that we don't track yet (suggestedQuestions,
conversation) are returned as empty arrays per the spec's placeholder policy.
"""

from __future__ import annotations

import logging
import time
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.auth.dependencies import get_tenant
from src.auth.tenant import TenantContext
from src.db.client import TenantDB
from src.github import GitHubAPIError, fetch_pr

router = APIRouter(
    prefix="/projects/{project_id}/waves/{wave_id}/mvis/{mvi_id}/prs",
    tags=["prs"],
)

log = logging.getLogger(__name__)

# DDB cache: PK = "T#{tenant}#GHCACHE", SK = "PR#{repo}#{pr_number}"
# expires_at is epoch seconds; rows past expiry are ignored and refreshed.
GH_CACHE_TTL_SECONDS = 60 * 60  # 1h


# ---- response models -------------------------------------------------------


class PRFinding(BaseModel):
    """One finding in the reviewer's verdict (passing check or warning)."""

    id: str
    text: str
    type: str  # "check" | "warning"


class PRVerdict(BaseModel):
    """Reviewer outcome shaped for the iOS verdict block."""

    status: str  # "approved" | "changes_needed" | "rejected"
    crow_name: str
    confidence: str  # "high" | "medium" | "low"
    files_analyzed: int
    summary: str
    findings: list[PRFinding]


class PlanStep(BaseModel):
    """One step of the plan/execute reconciliation shown on iOS."""

    id: str
    crow_name: str
    plan: str
    executed: str
    hint: str | None = None


class PRChatMessage(BaseModel):
    """One conversation message — currently always empty list."""

    id: str
    role: str  # "user" | "ai"
    content: str
    risk_badge: str | None = None


class PRReviewResponse(BaseModel):
    """API response shape matching iOS PRReviewDetail."""

    title: str
    branch: str
    status: str  # "ready" | "changes_requested" | "merged"
    breadcrumb_mvi: str
    breadcrumb_task: str
    credits_cost: int
    ai_minutes: int
    files_changed: int
    lines_added: int
    lines_removed: int
    verdict: PRVerdict
    plan_steps: list[PlanStep]
    suggested_questions: list[str]
    conversation: list[PRChatMessage]


# ---- DDB helpers -----------------------------------------------------------


def _find_implementer(
    db: TenantDB, project_id: str, wave_id: str, mvi_id: str
) -> dict[str, Any] | None:
    sk_prefix = f"S#{wave_id}#m{mvi_id}#cr_impl"
    rows = db.query_project(project_id=project_id, sk_prefix=sk_prefix)
    completed = [r for r in rows if r.get("status") == "completed"]
    if not completed:
        return None
    completed.sort(key=lambda r: r.get("completed_at", ""), reverse=True)
    return completed[0]


def _find_reviewer(
    db: TenantDB, project_id: str, wave_id: str, mvi_id: str
) -> dict[str, Any] | None:
    sk_prefix = f"S#{wave_id}#m{mvi_id}#cr_rev"
    rows = db.query_project(project_id=project_id, sk_prefix=sk_prefix)
    completed = [r for r in rows if r.get("status") == "completed"]
    if not completed:
        return None
    completed.sort(key=lambda r: r.get("completed_at", ""), reverse=True)
    return completed[0]


def _find_planner(
    db: TenantDB, project_id: str, wave_id: str, mvi_id: str
) -> dict[str, Any] | None:
    sk_prefix = f"S#{wave_id}#m{mvi_id}#cr_plan"
    rows = db.query_project(project_id=project_id, sk_prefix=sk_prefix)
    completed = [r for r in rows if r.get("status") == "completed"]
    if not completed:
        return None
    completed.sort(key=lambda r: r.get("completed_at", ""), reverse=True)
    return completed[0]


# ---- GitHub cache ----------------------------------------------------------


def _gh_cache_key(repo: str, pr_number: int) -> str:
    """SK for the GitHub PR cache entry."""
    return f"PR#{repo}#{pr_number}"


def _read_gh_cache(db: TenantDB, repo: str, pr_number: int) -> dict[str, Any] | None:
    """Read a cached GitHub PR payload if it's still fresh.

    Returns the payload dict or None if absent / expired / unreadable.
    Cache lives in the tenant-scoped partition under SK="GHCACHE#PR#...".
    """
    sk = f"GHCACHE#{_gh_cache_key(repo, pr_number)}"
    row = db.get_item(sk=sk)
    if row is None:
        return None
    expires = int(row.get("expires_at", 0) or 0)
    if expires < int(time.time()):
        return None
    payload = row.get("payload")
    return payload if isinstance(payload, dict) else None


def _write_gh_cache(
    db: TenantDB, repo: str, pr_number: int, payload: dict[str, Any]
) -> None:
    """Persist a GitHub PR payload to the cache."""
    sk = f"GHCACHE#{_gh_cache_key(repo, pr_number)}"
    db.put_item(
        sk=sk,
        payload=payload,
        cached_at=int(time.time()),
        expires_at=int(time.time()) + GH_CACHE_TTL_SECONDS,
    )


# ---- assembly helpers ------------------------------------------------------


def _ms_to_minutes(ms: int) -> int:
    if ms <= 0:
        return 0
    return max(1, round(ms / 60_000))


def _gh_state_to_ios_status(gh: dict[str, Any]) -> str:
    """Map GitHub PR state to iOS PRStatus rawValue.

    GitHub state is 'open' or 'closed'; we treat closed+merged as 'merged'.
    Reviewer rejection isn't represented in PR state — iOS distinguishes via
    the verdict block, so for status we only map open/merged.
    """
    state = (gh.get("state") or "open").lower()
    if state == "closed" and gh.get("merged_at"):
        return "merged"
    return "ready"


def _build_verdict(
    reviewer: dict[str, Any] | None, implementer: dict[str, Any] | None
) -> PRVerdict:
    """Translate reviewer outcome into the iOS PRVerdict shape."""
    if reviewer is None:
        return PRVerdict(
            status="changes_needed",
            crow_name="Reviewer",
            confidence="medium",
            files_analyzed=_implementer_files_changed(implementer),
            summary="No reviewer outcome yet.",
            findings=[],
        )
    outcome = reviewer.get("outcome") or {}
    blocking = list(outcome.get("blocking_issues") or [])
    non_blocking = list(outcome.get("non_blocking_issues") or [])
    approved = outcome.get("approved")
    if approved is None:
        approved = len(blocking) == 0
    status = "approved" if approved else "changes_needed" if blocking else "rejected"

    findings: list[PRFinding] = []
    for idx, item in enumerate(non_blocking[:5]):
        findings.append(PRFinding(id=f"warn-{idx}", text=str(item), type="warning"))
    for idx, item in enumerate(blocking[:5]):
        findings.append(
            PRFinding(
                id=f"block-{idx}",
                text=str(item),
                type="check" if approved else "warning",
            )
        )

    return PRVerdict(
        status=status,
        crow_name="Reviewer",
        confidence="high",
        files_analyzed=_implementer_files_changed(implementer),
        summary=str(outcome.get("summary", ""))[:1000]
        or "Reviewer summary unavailable.",
        findings=findings,
    )


def _implementer_files_changed(impl: dict[str, Any] | None) -> int:
    if impl is None:
        return 0
    out = impl.get("outcome") or {}
    files = out.get("files_changed") or []
    return len(files) if isinstance(files, list) else 0


def _build_plan_steps(
    planner: dict[str, Any] | None,
    implementer: dict[str, Any] | None,
    reviewer: dict[str, Any] | None,
) -> list[PlanStep]:
    """Build one PlanStep per crow that ran, summarizing plan vs execution."""
    steps: list[PlanStep] = []
    if planner is not None:
        outcome = planner.get("outcome") or {}
        tasks = outcome.get("tasks") or []
        plan_summary = (
            f"Decomposed MVI into {len(tasks)} tasks."
            if isinstance(tasks, list) and tasks
            else outcome.get("summary", "Planned the work.") or "Planned the work."
        )
        steps.append(
            PlanStep(
                id="ps-planner",
                crow_name="Planner",
                plan=str(plan_summary)[:500],
                executed=str(outcome.get("summary", "") or "")[:500],
            )
        )
    if implementer is not None:
        outcome = implementer.get("outcome") or {}
        files = outcome.get("files_changed") or []
        executed = (
            f"Changed {len(files)} file(s): " + ", ".join(files[:5])
            if isinstance(files, list) and files
            else outcome.get("summary", "") or "Implementation in progress."
        )
        steps.append(
            PlanStep(
                id="ps-implementer",
                crow_name="Implementer",
                plan="Apply the planner's task list.",
                executed=str(executed)[:500],
            )
        )
    if reviewer is not None:
        outcome = reviewer.get("outcome") or {}
        approved = outcome.get("approved")
        if approved is None:
            approved = not (outcome.get("blocking_issues") or [])
        steps.append(
            PlanStep(
                id="ps-reviewer",
                crow_name="Reviewer",
                plan="Review the diff against the MVI spec.",
                executed=("Approved." if approved else "Requested changes.")
                + " "
                + str(outcome.get("summary", ""))[:300],
            )
        )
    return steps


def _wave_credits_to_dollars(crows: list[dict[str, Any]]) -> int:
    """Sum all crow costs to whole-dollar credit count."""
    total_micros = 0
    for c in crows:
        cost = c.get("cost") or {}
        total_micros += int(cost.get("credits", 0) or 0)
    return round(total_micros / 1_000_000)


def _wave_total_minutes(crows: list[dict[str, Any]]) -> int:
    total_ms = 0
    for c in crows:
        cost = c.get("cost") or {}
        total_ms += int(cost.get("duration_ms", 0) or 0)
    return _ms_to_minutes(total_ms)


# ---- route -----------------------------------------------------------------


@router.get("/{pr_number}", response_model=PRReviewResponse)
async def get_pr_review(
    project_id: str,
    wave_id: str,
    mvi_id: str,
    pr_number: int,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> PRReviewResponse:
    """Return PR review detail for the iOS PRReviewScreen.

    Sources: DDB (implementer/reviewer/planner snapshots, MVI),
    GitHub API (PR metadata, 1h cached). Empty arrays for placeholder
    fields (suggested_questions, conversation) per spec.
    """
    db = TenantDB(tenant)

    impl = _find_implementer(db, project_id, wave_id, mvi_id)
    if impl is None:
        raise HTTPException(
            status_code=404,
            detail=f"No completed implementer for wave {wave_id} mvi {mvi_id}",
        )

    pr_record = impl.get("pr") or {}
    if not pr_record.get("number"):
        raise HTTPException(
            status_code=404,
            detail=(
                f"Implementer for mvi {mvi_id} has no PR — implementer.pr is empty"
            ),
        )
    # The pr_number on the URL must match what's stored — protects against
    # stale iOS state surfacing wrong PRs across waves.
    stored_number = int(pr_record["number"])
    if stored_number != pr_number:
        raise HTTPException(
            status_code=400,
            detail=(
                f"pr_number mismatch: implementer has PR {stored_number}, "
                f"URL requested {pr_number}"
            ),
        )

    repo = impl.get("repo") or ""
    if not repo:
        raise HTTPException(
            status_code=409,
            detail="Implementer snapshot has no repo — cannot fetch PR",
        )

    # GitHub enrichment (with cache)
    gh_payload = _read_gh_cache(db, repo, pr_number)
    if gh_payload is None:
        try:
            gh_payload = fetch_pr(repo, pr_number)
            _write_gh_cache(db, repo, pr_number, gh_payload)
        except GitHubAPIError as e:
            log.warning("GitHub fetch failed (status=%s): %s", e.status, e.message)
            # Fall back to minimal data from DDB if GitHub is unreachable
            gh_payload = {}

    reviewer = _find_reviewer(db, project_id, wave_id, mvi_id)
    planner = _find_planner(db, project_id, wave_id, mvi_id)

    mvi_sk = f"S#{wave_id}#m{mvi_id}"
    mvi = db.get_project_item(project_id=project_id, sk=mvi_sk) or {}
    mvi_name = mvi.get("name", mvi_id)

    crows_for_totals = [c for c in (planner, impl, reviewer) if c is not None]
    return PRReviewResponse(
        title=gh_payload.get("title", "") or f"PR #{pr_number}",
        branch=impl.get("branch", gh_payload.get("head", {}).get("ref", "")),
        status=_gh_state_to_ios_status(gh_payload),
        breadcrumb_mvi=f"MVI {mvi_name}",
        breadcrumb_task=mvi.get("description", "")[:80],
        credits_cost=_wave_credits_to_dollars(crows_for_totals),
        ai_minutes=_wave_total_minutes(crows_for_totals),
        files_changed=int(gh_payload.get("changed_files", 0) or 0)
        or _implementer_files_changed(impl),
        lines_added=int(gh_payload.get("additions", 0) or 0),
        lines_removed=int(gh_payload.get("deletions", 0) or 0),
        verdict=_build_verdict(reviewer, impl),
        plan_steps=_build_plan_steps(planner, impl, reviewer),
        suggested_questions=[],
        conversation=[],
    )
