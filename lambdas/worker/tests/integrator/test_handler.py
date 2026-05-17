"""Tests for the integrator handler — wires phases A/B/C with loud-fail."""

from unittest.mock import MagicMock, patch

from worker.integrator.findings import CheckResult, MergeConflict
from worker.integrator.handler import run_integrator
from worker.integrator.worktree import WorktreeError


def _ok_result() -> CheckResult:
    return CheckResult(status="ok", failures=[], duration_ms=10, command="x")


def test_run_integrator_happy_path_writes_findings_ready_for_council() -> None:
    blackboard = MagicMock()
    with patch(
        "worker.integrator.handler.add_pr_worktree",
        return_value="/mnt/repos/T/t/r/.pr-42",
    ), patch(
        "worker.integrator.handler.attempt_integration_merge"
    ) as merge, patch(
        "worker.integrator.handler.run_all_checks",
        return_value=(_ok_result(), _ok_result(), _ok_result()),
    ), patch(
        "worker.integrator.handler.remove_worktree"
    ):
        merge.return_value = MagicMock(
            status="ok",
            conflicts=[],
            integration_path="/mnt/repos/T/t/r/.integration",
        )
        run_integrator(
            blackboard=blackboard,
            project_id="p1",
            wave_id="w1",
            repo_path="/mnt/repos/T/t/r",
            pr_to_mvi={42: "m_1"},
        )
        assert blackboard.write_item.called
        written = blackboard.write_item.call_args.args[0]
        assert written["SK"] == "INTEGRATION#w1"
        assert written["overall"] == "ready_for_council"


def test_run_integrator_conflict_skips_checks_and_writes_needs_rework() -> None:
    blackboard = MagicMock()
    conflict = MergeConflict(
        pr_a=42, pr_b=43, files=["foo.py"], hunks=[], mvi_a="m1", mvi_b="m2"
    )
    with patch(
        "worker.integrator.handler.add_pr_worktree",
        return_value="/mnt/repos/T/t/r/.pr-42",
    ), patch(
        "worker.integrator.handler.attempt_integration_merge"
    ) as merge, patch(
        "worker.integrator.handler.run_all_checks"
    ) as checks, patch(
        "worker.integrator.handler.remove_worktree"
    ):
        merge.return_value = MagicMock(
            status="conflict",
            conflicts=[conflict],
            integration_path="/.integration",
        )
        run_integrator(
            blackboard=blackboard,
            project_id="p1",
            wave_id="w1",
            repo_path="/mnt/repos/T/t/r",
            pr_to_mvi={42: "m1", 43: "m2"},
        )
        checks.assert_not_called()
        written = blackboard.write_item.call_args.args[0]
        assert written["overall"] == "needs_rework"
        assert written["merge_status"] == "conflict"


def test_run_integrator_ready_for_council_preserves_worktrees() -> None:
    """Happy path hands worktrees to council via EFS; cleanup must be skipped."""
    blackboard = MagicMock()
    with patch(
        "worker.integrator.handler.add_pr_worktree",
        return_value="/mnt/repos/T/t/r/.pr-42",
    ), patch(
        "worker.integrator.handler.attempt_integration_merge"
    ) as merge, patch(
        "worker.integrator.handler.run_all_checks",
        return_value=(_ok_result(), _ok_result(), _ok_result()),
    ), patch(
        "worker.integrator.handler.remove_worktree"
    ) as remove:
        merge.return_value = MagicMock(
            status="ok",
            conflicts=[],
            integration_path="/mnt/repos/T/t/r/.integration",
        )
        run_integrator(
            blackboard=blackboard,
            project_id="p1",
            wave_id="w1",
            repo_path="/mnt/repos/T/t/r",
            pr_to_mvi={42: "m_1"},
        )
        remove.assert_not_called()


def test_run_integrator_needs_rework_still_cleans_up() -> None:
    """Conflict path is terminal for the wave's worktrees — must clean up."""
    blackboard = MagicMock()
    conflict = MergeConflict(
        pr_a=42, pr_b=43, files=["foo.py"], hunks=[], mvi_a="m1", mvi_b="m2"
    )
    with patch(
        "worker.integrator.handler.add_pr_worktree",
        return_value="/mnt/repos/T/t/r/.pr-42",
    ), patch(
        "worker.integrator.handler.attempt_integration_merge"
    ) as merge, patch(
        "worker.integrator.handler.run_all_checks"
    ), patch(
        "worker.integrator.handler.remove_worktree"
    ) as remove:
        merge.return_value = MagicMock(
            status="conflict",
            conflicts=[conflict],
            integration_path="/mnt/repos/T/t/r/.integration",
        )
        run_integrator(
            blackboard=blackboard,
            project_id="p1",
            wave_id="w1",
            repo_path="/mnt/repos/T/t/r",
            pr_to_mvi={42: "m1", 43: "m2"},
        )
        assert remove.called


def test_run_integrator_emits_pipeline_error_on_fetch_failure() -> None:
    blackboard = MagicMock()
    with patch(
        "worker.integrator.handler.add_pr_worktree",
        side_effect=WorktreeError("fetch failed"),
    ):
        run_integrator(
            blackboard=blackboard,
            project_id="p1",
            wave_id="w1",
            repo_path="/mnt/repos/T/t/r",
            pr_to_mvi={42: "m_1"},
        )
        assert blackboard.write_event.called
        written = blackboard.write_item.call_args.args[0]
        assert written["overall"] == "needs_rework"
