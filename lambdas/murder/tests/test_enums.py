"""Tests for enums — status values and valid transitions."""

import pytest

from murder.enums import (
    AdvisorType,
    BehaviorState,
    CrowStatus,
    CrowType,
    EventColor,
    EventType,
    MVIStatus,
    SnapshotLevel,
    VoteType,
    WaveStatus,
)


class TestWaveStatus:
    def test_all_wave_statuses_exist(self) -> None:
        expected = {
            "planning",
            "proposed",
            "revised",
            "approved",
            "rejected",
            "executing",
            "paused",
            "review",
            "steered",
            "delivered",
            "cancelled",
        }
        actual = {s.value for s in WaveStatus}
        assert actual == expected

    def test_terminal_states(self) -> None:
        assert WaveStatus.DELIVERED.is_terminal()
        assert WaveStatus.CANCELLED.is_terminal()
        assert not WaveStatus.EXECUTING.is_terminal()
        assert not WaveStatus.PLANNING.is_terminal()

    def test_valid_transitions(self) -> None:
        assert WaveStatus.PLANNING.can_transition_to(WaveStatus.PROPOSED)
        assert WaveStatus.PLANNING.can_transition_to(WaveStatus.CANCELLED)
        assert WaveStatus.PROPOSED.can_transition_to(WaveStatus.APPROVED)
        assert WaveStatus.PROPOSED.can_transition_to(WaveStatus.REVISED)
        assert WaveStatus.PROPOSED.can_transition_to(WaveStatus.REJECTED)
        assert WaveStatus.APPROVED.can_transition_to(WaveStatus.EXECUTING)
        assert WaveStatus.EXECUTING.can_transition_to(WaveStatus.REVIEW)
        assert WaveStatus.EXECUTING.can_transition_to(WaveStatus.PAUSED)
        assert WaveStatus.EXECUTING.can_transition_to(WaveStatus.STEERED)
        assert WaveStatus.EXECUTING.can_transition_to(WaveStatus.CANCELLED)
        assert WaveStatus.PAUSED.can_transition_to(WaveStatus.EXECUTING)
        assert WaveStatus.PAUSED.can_transition_to(WaveStatus.STEERED)
        assert WaveStatus.PAUSED.can_transition_to(WaveStatus.CANCELLED)
        assert WaveStatus.STEERED.can_transition_to(WaveStatus.EXECUTING)
        assert WaveStatus.STEERED.can_transition_to(WaveStatus.PROPOSED)
        assert WaveStatus.REVIEW.can_transition_to(WaveStatus.DELIVERED)
        assert WaveStatus.REVIEW.can_transition_to(WaveStatus.STEERED)
        assert WaveStatus.REVISED.can_transition_to(WaveStatus.PROPOSED)
        assert WaveStatus.REVISED.can_transition_to(WaveStatus.CANCELLED)
        assert WaveStatus.REJECTED.can_transition_to(WaveStatus.PLANNING)

    def test_invalid_transitions(self) -> None:
        assert not WaveStatus.PLANNING.can_transition_to(WaveStatus.EXECUTING)
        assert not WaveStatus.DELIVERED.can_transition_to(WaveStatus.PLANNING)
        assert not WaveStatus.CANCELLED.can_transition_to(WaveStatus.PLANNING)
        assert not WaveStatus.APPROVED.can_transition_to(WaveStatus.PLANNING)


class TestMVIStatus:
    def test_all_mvi_statuses_exist(self) -> None:
        expected = {
            "draft",
            "refined",
            "queued",
            "executing",
            "failed",
            "ready_to_ship",
            "rejected",
            "shipped",
            "cancelled",
        }
        actual = {s.value for s in MVIStatus}
        assert actual == expected

    def test_terminal_states(self) -> None:
        assert MVIStatus.SHIPPED.is_terminal()
        assert MVIStatus.CANCELLED.is_terminal()
        assert not MVIStatus.EXECUTING.is_terminal()

    def test_valid_transitions(self) -> None:
        assert MVIStatus.DRAFT.can_transition_to(MVIStatus.REFINED)
        assert MVIStatus.REFINED.can_transition_to(MVIStatus.QUEUED)
        assert MVIStatus.QUEUED.can_transition_to(MVIStatus.EXECUTING)
        assert MVIStatus.EXECUTING.can_transition_to(MVIStatus.READY_TO_SHIP)
        assert MVIStatus.EXECUTING.can_transition_to(MVIStatus.FAILED)
        assert MVIStatus.READY_TO_SHIP.can_transition_to(MVIStatus.SHIPPED)
        assert MVIStatus.READY_TO_SHIP.can_transition_to(MVIStatus.REJECTED)
        assert MVIStatus.FAILED.can_transition_to(MVIStatus.QUEUED)
        assert MVIStatus.REJECTED.can_transition_to(MVIStatus.QUEUED)
        assert MVIStatus.REJECTED.can_transition_to(MVIStatus.CANCELLED)

    def test_invalid_transitions(self) -> None:
        assert not MVIStatus.DRAFT.can_transition_to(MVIStatus.EXECUTING)
        assert not MVIStatus.SHIPPED.can_transition_to(MVIStatus.DRAFT)


class TestCrowStatus:
    def test_all_crow_statuses_exist(self) -> None:
        expected = {"pending", "running", "completed", "failed"}
        actual = {s.value for s in CrowStatus}
        assert actual == expected

    def test_valid_transitions(self) -> None:
        assert CrowStatus.PENDING.can_transition_to(CrowStatus.RUNNING)
        assert CrowStatus.RUNNING.can_transition_to(CrowStatus.COMPLETED)
        assert CrowStatus.RUNNING.can_transition_to(CrowStatus.FAILED)

    def test_invalid_transitions(self) -> None:
        assert not CrowStatus.PENDING.can_transition_to(CrowStatus.COMPLETED)
        assert not CrowStatus.COMPLETED.can_transition_to(CrowStatus.RUNNING)
        assert not CrowStatus.FAILED.can_transition_to(CrowStatus.RUNNING)


class TestCrowType:
    def test_all_crow_types_exist(self) -> None:
        expected = {"planner", "implementer", "reviewer", "fixer"}
        actual = {t.value for t in CrowType}
        assert actual == expected

    def test_max_retries(self) -> None:
        assert CrowType.PLANNER.max_retries == 1
        assert CrowType.IMPLEMENTER.max_retries == 3
        assert CrowType.REVIEWER.max_retries == 2
        assert CrowType.FIXER.max_retries == 3


class TestBehaviorState:
    def test_all_behavior_states_exist(self) -> None:
        expected = {"assigned", "working", "landed", "error", "blocked"}
        actual = {s.value for s in BehaviorState}
        assert actual == expected


class TestSnapshotLevel:
    def test_all_levels_exist(self) -> None:
        expected = {"root", "wave", "council", "murder", "crow"}
        actual = {l.value for l in SnapshotLevel}
        assert actual == expected


class TestVoteType:
    def test_all_vote_types_exist(self) -> None:
        expected = {"approve", "approve_with_condition", "abstain", "block"}
        actual = {v.value for v in VoteType}
        assert actual == expected

    def test_blocking_votes(self) -> None:
        assert VoteType.BLOCK.is_blocking()
        assert not VoteType.APPROVE.is_blocking()
        assert not VoteType.APPROVE_WITH_CONDITION.is_blocking()
        assert not VoteType.ABSTAIN.is_blocking()


class TestAdvisorType:
    def test_all_advisor_types_exist(self) -> None:
        expected = {
            "security",
            "quality",
            "performance",
            "market",
            "maturity",
            "clarity",
        }
        actual = {a.value for a in AdvisorType}
        assert actual == expected

    def test_veto_power(self) -> None:
        assert AdvisorType.SECURITY.has_veto()
        assert AdvisorType.CLARITY.has_veto()
        assert not AdvisorType.QUALITY.has_veto()
        assert not AdvisorType.PERFORMANCE.has_veto()
        assert not AdvisorType.MARKET.has_veto()
        assert not AdvisorType.MATURITY.has_veto()


class TestEventType:
    def test_all_event_types_exist(self) -> None:
        expected = {
            "crow_assigned",
            "crow_completed",
            "crow_failed",
            "mvi_ready",
            "mvi_shipped",
            "wave_started",
            "wave_delivered",
            "budget_warning",
            "budget_exceeded",
        }
        actual = {e.value for e in EventType}
        assert actual == expected


class TestEventColor:
    def test_all_event_colors_exist(self) -> None:
        expected = {"green", "red", "purple", "yellow", "blue"}
        actual = {c.value for c in EventColor}
        assert actual == expected
