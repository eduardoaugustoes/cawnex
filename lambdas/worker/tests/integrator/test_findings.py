"""Tests for IntegratorFindings dataclass + serialization."""

from worker.integrator.findings import (
    CheckResult,
    IntegratorFindings,
    MergeConflict,
)


def test_check_result_skipped_is_not_failure() -> None:
    result = CheckResult(status="skipped", failures=[], duration_ms=0, command="mypy")
    assert result.status == "skipped"


def test_merge_conflict_carries_mvi_ownership() -> None:
    conflict = MergeConflict(
        pr_a=42,
        pr_b=43,
        files=["foo.py"],
        hunks=["<<<<<<<..."],
        mvi_a="m_1",
        mvi_b="m_2",
    )
    assert conflict.mvi_a == "m_1"


def test_integrator_findings_serializes() -> None:
    findings = IntegratorFindings(
        PK="P#proj1",
        SK="INTEGRATION#w1",
        wave_id="w1",
        pr_numbers=[42, 43],
        integration_branch="council-review-w1",
        merge_status="ok",
        merge_conflicts=[],
        lint=CheckResult(
            status="ok", failures=[], duration_ms=100, command="black --check ."
        ),
        typecheck=None,
        tests=None,
        worktree_paths={42: "/mnt/repos/T/t1/r/.pr-42"},
        integration_worktree="/mnt/repos/T/t1/r/.integration",
        overall="ready_for_council",
        rework_reasons=[],
        started_at="2026-05-16T00:00:00Z",
        completed_at="2026-05-16T00:01:00Z",
        duration_ms=60000,
    )
    d = findings.to_dict()
    assert d["overall"] == "ready_for_council"
    assert d["merge_status"] == "ok"
    assert d["entityType"] == "IntegratorFindings"
    assert d["lint"]["status"] == "ok"
    assert d["typecheck"] is None
    assert d["worktree_paths"] == {"42": "/mnt/repos/T/t1/r/.pr-42"}
