"""Tests for the deterministic state machine."""

from murder.enums import CrowStatus, CrowType
from murder.state_machine import (
    AssignCrow,
    FailMVI,
    MarkMVIReady,
    NoAction,
    SplitRequired,
    determine_next,
)


class TestPlannerCompleted:
    def test_with_tasks_assigns_implementer(self) -> None:
        action = determine_next(
            CrowType.PLANNER, CrowStatus.COMPLETED,
            {"tasks": [{"name": "t1"}]}, 0,
        )
        assert isinstance(action, AssignCrow)
        assert action.crow_type == CrowType.IMPLEMENTER

    def test_no_tasks_fails_mvi(self) -> None:
        action = determine_next(
            CrowType.PLANNER, CrowStatus.COMPLETED, {"tasks": []}, 0,
        )
        assert isinstance(action, FailMVI)
        assert "no tasks" in action.reason

    def test_none_outcome_fails_mvi(self) -> None:
        action = determine_next(
            CrowType.PLANNER, CrowStatus.COMPLETED, None, 0,
        )
        assert isinstance(action, FailMVI)


    def test_oversized_task_triggers_split(self) -> None:
        action = determine_next(
            CrowType.PLANNER, CrowStatus.COMPLETED,
            {"tasks": [{"name": "Implement JWT auth", "estimated_hours": 16}]}, 0,
        )
        assert isinstance(action, SplitRequired)
        assert len(action.oversized_tasks) == 1
        assert action.oversized_tasks[0]["name"] == "Implement JWT auth"

    def test_tasks_within_limit_assigns_implementer(self) -> None:
        action = determine_next(
            CrowType.PLANNER, CrowStatus.COMPLETED,
            {"tasks": [
                {"name": "Add endpoint", "estimated_hours": 4},
                {"name": "Add test", "estimated_hours": 3},
            ]}, 0,
        )
        assert isinstance(action, AssignCrow)
        assert action.crow_type == CrowType.IMPLEMENTER

    def test_split_count_exceeded_fails_mvi(self) -> None:
        action = determine_next(
            CrowType.PLANNER, CrowStatus.COMPLETED,
            {"tasks": [{"name": "Implement JWT auth", "estimated_hours": 16}]},
            0,
            split_count=2,
        )
        assert isinstance(action, FailMVI)
        assert "task limit" in action.reason

    def test_string_estimated_hours_handles_comparison(self) -> None:
        """Claude may return estimated_hours as string — must not crash."""
        action = determine_next(
            CrowType.PLANNER, CrowStatus.COMPLETED,
            {"tasks": [
                {"name": "Build UI", "estimated_hours": "4"},
                {"name": "Add tests", "estimated_hours": "2"},
            ]}, 0,
        )
        assert isinstance(action, AssignCrow)
        assert action.crow_type == CrowType.IMPLEMENTER

    def test_string_oversized_hours_triggers_split(self) -> None:
        """String estimated_hours exceeding limit must still trigger split."""
        action = determine_next(
            CrowType.PLANNER, CrowStatus.COMPLETED,
            {"tasks": [{"name": "Big task", "estimated_hours": "16"}]}, 0,
        )
        assert isinstance(action, SplitRequired)

    def test_tasks_without_estimated_hours_proceeds_normally(self) -> None:
        action = determine_next(
            CrowType.PLANNER, CrowStatus.COMPLETED,
            {"tasks": [{"name": "Add endpoint"}, {"name": "Add test"}]}, 0,
        )
        assert isinstance(action, AssignCrow)
        assert action.crow_type == CrowType.IMPLEMENTER


class TestPlannerFailed:
    def test_first_failure_retries(self) -> None:
        action = determine_next(
            CrowType.PLANNER, CrowStatus.FAILED, None, 0,
        )
        assert isinstance(action, AssignCrow)
        assert action.crow_type == CrowType.PLANNER

    def test_max_retries_fails_mvi(self) -> None:
        action = determine_next(
            CrowType.PLANNER, CrowStatus.FAILED, None, 1,
        )
        assert isinstance(action, FailMVI)


class TestImplementerCompleted:
    def test_assigns_reviewer(self) -> None:
        action = determine_next(
            CrowType.IMPLEMENTER, CrowStatus.COMPLETED, {}, 0,
        )
        assert isinstance(action, AssignCrow)
        assert action.crow_type == CrowType.REVIEWER


class TestImplementerFailed:
    def test_retry_under_max(self) -> None:
        action = determine_next(
            CrowType.IMPLEMENTER, CrowStatus.FAILED, None, 2,
        )
        assert isinstance(action, AssignCrow)
        assert action.crow_type == CrowType.IMPLEMENTER

    def test_max_retries_fails_mvi(self) -> None:
        action = determine_next(
            CrowType.IMPLEMENTER, CrowStatus.FAILED, None, 3,
        )
        assert isinstance(action, FailMVI)


class TestReviewerCompleted:
    def test_approved_marks_ready(self) -> None:
        action = determine_next(
            CrowType.REVIEWER, CrowStatus.COMPLETED,
            {"approved": True}, 0,
        )
        assert isinstance(action, MarkMVIReady)

    def test_not_approved_assigns_fixer(self) -> None:
        action = determine_next(
            CrowType.REVIEWER, CrowStatus.COMPLETED,
            {"approved": False, "issues": ["bug"]}, 0,
        )
        assert isinstance(action, AssignCrow)
        assert action.crow_type == CrowType.FIXER

    def test_empty_blocking_issues_approves_even_with_non_blocking(self) -> None:
        action = determine_next(
            CrowType.REVIEWER, CrowStatus.COMPLETED,
            {
                "approved": False,
                "blocking_issues": [],
                "non_blocking_issues": ["rename x to user_id"],
                "issues": ["rename x to user_id"],
            },
            0,
        )
        assert isinstance(action, MarkMVIReady)

    def test_blocking_issues_present_assigns_fixer(self) -> None:
        action = determine_next(
            CrowType.REVIEWER, CrowStatus.COMPLETED,
            {
                "approved": False,
                "blocking_issues": ["SQL injection at db.py:42"],
                "non_blocking_issues": [],
                "issues": ["SQL injection at db.py:42"],
            },
            0,
        )
        assert isinstance(action, AssignCrow)
        assert action.crow_type == CrowType.FIXER

    def test_backward_compat_no_blocking_issues_field_uses_approved(self) -> None:
        action = determine_next(
            CrowType.REVIEWER, CrowStatus.COMPLETED,
            {"approved": True, "issues": []},
            0,
        )
        assert isinstance(action, MarkMVIReady)

    def test_backward_compat_approved_false_without_blocking_issues_assigns_fixer(self) -> None:
        action = determine_next(
            CrowType.REVIEWER, CrowStatus.COMPLETED,
            {"approved": False, "issues": ["missing test"]},
            0,
        )
        assert isinstance(action, AssignCrow)
        assert action.crow_type == CrowType.FIXER

    def test_reviewer_rejects_after_max_fix_cycles_fails_mvi(self) -> None:
        """When fix_count >= FIX_CYCLE_LIMIT and reviewer still rejects, fail the MVI."""
        action = determine_next(
            CrowType.REVIEWER, CrowStatus.COMPLETED,
            {"blocking_issues": ["SQL injection at db.py:42"]},
            0,
            fix_count=2,
        )
        assert isinstance(action, FailMVI)
        assert "max fix cycles" in action.reason
        assert "2" in action.reason

    def test_reviewer_rejects_within_fix_limit_assigns_fixer(self) -> None:
        """When fix_count < FIX_CYCLE_LIMIT and reviewer rejects, assign fixer."""
        action = determine_next(
            CrowType.REVIEWER, CrowStatus.COMPLETED,
            {"blocking_issues": ["SQL injection at db.py:42"]},
            0,
            fix_count=1,
        )
        assert isinstance(action, AssignCrow)
        assert action.crow_type == CrowType.FIXER


class TestReviewerFailed:
    def test_retry_under_max(self) -> None:
        action = determine_next(
            CrowType.REVIEWER, CrowStatus.FAILED, None, 1,
        )
        assert isinstance(action, AssignCrow)
        assert action.crow_type == CrowType.REVIEWER

    def test_max_retries_fails_mvi(self) -> None:
        action = determine_next(
            CrowType.REVIEWER, CrowStatus.FAILED, None, 2,
        )
        assert isinstance(action, FailMVI)


class TestFixerCompleted:
    def test_fixer_completed_within_limit_assigns_reviewer(self) -> None:
        action = determine_next(
            CrowType.FIXER, CrowStatus.COMPLETED, {}, 1,
        )
        assert isinstance(action, AssignCrow)
        assert action.crow_type == CrowType.REVIEWER

    def test_fixer_completed_always_assigns_reviewer_regardless_of_retry_count(self) -> None:
        """Fix limit is now checked on REVIEWER path, not FIXER path."""
        action = determine_next(
            CrowType.FIXER, CrowStatus.COMPLETED, {}, 5,
        )
        assert isinstance(action, AssignCrow)
        assert action.crow_type == CrowType.REVIEWER


class TestFixerFailed:
    def test_retry_under_max(self) -> None:
        action = determine_next(
            CrowType.FIXER, CrowStatus.FAILED, None, 2,
        )
        assert isinstance(action, AssignCrow)
        assert action.crow_type == CrowType.FIXER

    def test_max_retries_fails_mvi(self) -> None:
        action = determine_next(
            CrowType.FIXER, CrowStatus.FAILED, None, 3,
        )
        assert isinstance(action, FailMVI)


class TestEdgeCases:
    def test_unexpected_status_returns_no_action(self) -> None:
        action = determine_next(
            CrowType.PLANNER, CrowStatus.PENDING, None, 0,
        )
        assert isinstance(action, NoAction)

    def test_reviewer_none_outcome_assigns_fixer(self) -> None:
        action = determine_next(
            CrowType.REVIEWER, CrowStatus.COMPLETED, None, 0,
        )
        assert isinstance(action, AssignCrow)
        assert action.crow_type == CrowType.FIXER
