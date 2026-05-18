"""Integrator entry: orchestrate worktree setup -> merge -> checks -> findings."""

from __future__ import annotations

import logging
import time
import traceback
from datetime import datetime, timezone
from typing import Any

from worker.integrator.checks.runner import overall_from_checks, run_all_checks
from worker.integrator.events import emit_pipeline_error
from worker.integrator.findings import IntegratorFindings
from worker.integrator.integration import attempt_integration_merge
from worker.integrator.worktree import WorktreeError, add_pr_worktree, remove_worktree

logger = logging.getLogger("integrator.handler")


def run_integrator(
    blackboard: Any,
    project_id: str,
    wave_id: str,
    repo_path: str,
    pr_to_mvi: dict[int, str],
    pk: str | None = None,
) -> None:
    """Run the full integrator flow for a wave.

    Always writes an IntegratorFindings record to DDB so the Murder reactor
    has something to route on, even on failure paths.

    `pk` is the full DDB partition key (T#{tenant}#P#{project}) for the
    INTEGRATION row write. If omitted (legacy callers) we fall back to
    f"P#{project_id}" which only works for the legacy untenanted path.
    """
    started_at = datetime.now(timezone.utc).isoformat()
    start = time.time()
    integration_branch = f"council-review-{wave_id}"
    worktree_paths: dict[int, str] = {}
    integration_path = f"{repo_path}/.integration"
    # IMPORTANT: the INTEGRATION row must land in the same partition the
    # wave + Murder reactor live in, otherwise Murder's DDB-stream handler
    # will fire react_to_integration_complete with a row that points to a
    # non-existent partition and Council will never get a session.
    target_pk = pk or f"P#{project_id}"

    fetch_error: WorktreeError | None = None
    try:
        for pr_number in sorted(pr_to_mvi.keys()):
            worktree_paths[pr_number] = add_pr_worktree(repo_path, pr_number)
    except WorktreeError as e:
        fetch_error = e
        emit_pipeline_error(
            blackboard=blackboard,
            project_id=project_id,
            wave_id=wave_id,
            phase="integrator-fetch",
            error_class=type(e).__name__,
            error_message=str(e),
            traceback_head=traceback.format_exc()[:1000],
            retry_count=0,
            final=True,
        )

    findings = IntegratorFindings(
        PK=target_pk,
        SK=f"INTEGRATION#{wave_id}",
        wave_id=wave_id,
        pr_numbers=sorted(pr_to_mvi.keys()),
        integration_branch=integration_branch,
        merge_status="conflict",
        merge_conflicts=[],
        lint=None,
        typecheck=None,
        tests=None,
        worktree_paths=worktree_paths,
        integration_worktree=integration_path,
        overall="needs_rework",
        rework_reasons=[],
        started_at=started_at,
        completed_at="",
        duration_ms=0,
    )

    if fetch_error:
        findings.rework_reasons = [f"unable to fetch PRs: {fetch_error}"]
        _finalize_and_write(blackboard, findings, start)
        return

    try:
        merge_result = attempt_integration_merge(
            repo_path=repo_path,
            integration_branch=integration_branch,
            pr_to_mvi=pr_to_mvi,
        )
    except Exception as e:  # noqa: BLE001 -- loud-fail catch with pipeline_error emission
        emit_pipeline_error(
            blackboard=blackboard,
            project_id=project_id,
            wave_id=wave_id,
            phase="integrator-merge",
            error_class=type(e).__name__,
            error_message=str(e),
            traceback_head=traceback.format_exc()[:1000],
            final=True,
        )
        findings.rework_reasons = [f"merge phase crashed: {type(e).__name__}"]
        _finalize_and_write(blackboard, findings, start)
        _cleanup(repo_path, worktree_paths, integration_path)
        return

    findings.merge_status = merge_result.status
    findings.merge_conflicts = merge_result.conflicts
    findings.integration_worktree = merge_result.integration_path

    if merge_result.status == "conflict":
        findings.overall = "needs_rework"
        findings.rework_reasons = [
            f"merge conflict between PR #{c.pr_a} and PR #{c.pr_b} ({len(c.files)} files)"
            for c in merge_result.conflicts
        ]
        _finalize_and_write(blackboard, findings, start)
        _cleanup(repo_path, worktree_paths, integration_path)
        return

    try:
        lint, typecheck, tests = run_all_checks(merge_result.integration_path)
    except Exception as e:  # noqa: BLE001 -- loud-fail catch with pipeline_error emission
        emit_pipeline_error(
            blackboard=blackboard,
            project_id=project_id,
            wave_id=wave_id,
            phase="integrator-checks",
            error_class=type(e).__name__,
            error_message=str(e),
            traceback_head=traceback.format_exc()[:1000],
            final=True,
        )
        findings.rework_reasons = [f"check phase crashed: {type(e).__name__}"]
        _finalize_and_write(blackboard, findings, start)
        _cleanup(repo_path, worktree_paths, integration_path)
        return

    findings.lint = lint
    findings.typecheck = typecheck
    findings.tests = tests
    overall, reasons = overall_from_checks(lint, typecheck, tests)
    findings.overall = overall
    findings.rework_reasons = reasons

    _finalize_and_write(blackboard, findings, start)
    # Council reads worktree_paths + integration_worktree from these findings.
    # Keep them on EFS when handing off to council; the council pipeline
    # (or the wave-delivered/cancelled reactor path) cleans up later.
    if overall != "ready_for_council":
        _cleanup(repo_path, worktree_paths, integration_path)


def _finalize_and_write(
    blackboard: Any, findings: IntegratorFindings, start: float
) -> None:
    findings.completed_at = datetime.now(timezone.utc).isoformat()
    findings.duration_ms = int((time.time() - start) * 1000)
    blackboard.write_item(findings.to_dict())


def _cleanup(
    repo_path: str, worktree_paths: dict[int, str], integration_path: str
) -> None:
    """Remove PR worktrees and the integration worktree.

    Called on failure paths and on `needs_rework`. The `ready_for_council`
    path skips this so council advisors can read the post-merge state via
    EFS; cleanup of those worktrees happens later (when the wave is
    delivered or cancelled).
    """
    for path in worktree_paths.values():
        remove_worktree(repo_path, path)
    remove_worktree(repo_path, integration_path)
