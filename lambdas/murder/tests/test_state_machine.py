"""Tests for the deterministic state machine."""

from murder.enums import CrowStatus, CrowType
from murder.state_machine import (
    AssignCrow,
    FailMVI,
    MarkMVIReady,
    NoAction,
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
    def test_assigns_reviewer_for_re_review(self) -> None:
        action = determine_next(
            CrowType.FIXER, CrowStatus.COMPLETED, {}, 0,
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
