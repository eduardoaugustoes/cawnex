"""Tests for the reactor — core orchestration with DynamoDB Local.

All money values are integer microdollars (1 USD = 1_000_000).
"""

from typing import Any

import pytest

from murder.blackboard import Blackboard
from murder.config import MICROS_PER_DOLLAR, WAVE_BUDGET_LIMIT
from murder.enums import CrowStatus, CrowType, MVIStatus, WaveStatus
from murder.keys import build_pk, build_sk
from murder.logging import StructuredLogger
from murder.models import Cost, CrowSnapshot, MVISnapshot, WaveBudget, WaveSnapshot
from murder.reactor import (
    react_to_crow_completion,
    react_to_mvi_queued,
    react_to_mvi_terminal,
)


def _seed_wave(
    blackboard: Blackboard,
    tenant: str = "t1",
    project: str = "p1",
    wave_id: str = "w01",
    budget_spent: int = 0,
    budget_limit: int = WAVE_BUDGET_LIMIT,
) -> WaveSnapshot:
    wave = WaveSnapshot(
        tenant=tenant,
        project=project,
        wave_id=wave_id,
        status=WaveStatus.EXECUTING,
        human_directive="Build auth system",
        budget=WaveBudget(spent=budget_spent, limit=budget_limit),
    )
    blackboard.write_item(wave.to_item())
    return wave


def _seed_mvi(
    blackboard: Blackboard,
    tenant: str = "t1",
    project: str = "p1",
    wave_id: str = "w01",
    mvi_id: str = "01",
    status: MVIStatus = MVIStatus.QUEUED,
) -> MVISnapshot:
    mvi = MVISnapshot(
        tenant=tenant,
        project=project,
        wave_id=wave_id,
        mvi_id=mvi_id,
        name="Auth MVI",
        status=status,
        repo="owner/repo",
        branch="feat/auth",
        description="Implement JWT authentication",
    )
    blackboard.write_item(mvi.to_item())
    return mvi


def _seed_crow(
    blackboard: Blackboard,
    tenant: str = "t1",
    project: str = "p1",
    wave_id: str = "w01",
    mvi_id: str = "01",
    crow_id: str = "cr_plan_01",
    crow_type: CrowType = CrowType.PLANNER,
    status: CrowStatus = CrowStatus.COMPLETED,
    outcome: dict | None = None,
    retry_count: int = 0,
    cost: Cost | None = None,
) -> CrowSnapshot:
    crow = CrowSnapshot(
        tenant=tenant,
        project=project,
        wave_id=wave_id,
        mvi_id=mvi_id,
        crow_id=crow_id,
        crow_type=crow_type,
        status=status,
        instructions="test instructions",
        repo="owner/repo",
        branch="feat/auth",
        budget_remaining=WAVE_BUDGET_LIMIT,
        retry_count=retry_count,
        outcome=outcome,
        cost=cost or Cost.zero(),
    )
    blackboard.write_item(crow.to_item())
    return crow


@pytest.fixture
def blackboard(dynamodb_table, events_table):  # type: ignore[no-untyped-def]
    return Blackboard(dynamodb_table, events_table=events_table)


@pytest.fixture
def logger() -> StructuredLogger:
    return StructuredLogger("test-reactor", tenant="t1", project="p1")


class TestReactToMVIQueued:
    def test_assigns_planner_crow(
        self, blackboard: Blackboard, logger: StructuredLogger
    ) -> None:
        _seed_wave(blackboard)
        mvi = _seed_mvi(blackboard)
        mvi_item = blackboard.read(mvi.pk, mvi.sk)
        assert mvi_item is not None

        react_to_mvi_queued(blackboard, mvi_item, logger)

        pk = build_pk("t1", "p1")
        crows = blackboard.query(pk, "S#w01#m01#cr_")
        assert len(crows) == 1
        assert crows[0]["crow_type"] == "planner"
        assert crows[0]["status"] == "pending"

    def test_transitions_mvi_to_executing(
        self, blackboard: Blackboard, logger: StructuredLogger
    ) -> None:
        _seed_wave(blackboard)
        mvi = _seed_mvi(blackboard)
        mvi_item = blackboard.read(mvi.pk, mvi.sk)
        assert mvi_item is not None

        react_to_mvi_queued(blackboard, mvi_item, logger)

        updated = blackboard.read(mvi.pk, mvi.sk)
        assert updated is not None
        assert updated["status"] == "executing"

    def test_budget_exceeded_fails_mvi(
        self, blackboard: Blackboard, logger: StructuredLogger
    ) -> None:
        _seed_wave(
            blackboard,
            budget_spent=21 * MICROS_PER_DOLLAR,
            budget_limit=20 * MICROS_PER_DOLLAR,
        )
        mvi = _seed_mvi(blackboard)
        mvi_item = blackboard.read(mvi.pk, mvi.sk)
        assert mvi_item is not None

        react_to_mvi_queued(blackboard, mvi_item, logger)

        updated = blackboard.read(mvi.pk, mvi.sk)
        assert updated is not None
        assert updated["status"] == "failed"

    def test_writes_crow_assigned_event(
        self, blackboard: Blackboard, events_table: Any, logger: StructuredLogger,
    ) -> None:
        _seed_wave(blackboard)
        mvi = _seed_mvi(blackboard)
        mvi_item = blackboard.read(mvi.pk, mvi.sk)
        assert mvi_item is not None

        react_to_mvi_queued(blackboard, mvi_item, logger)

        # Events now written to events table with PK=T#t#P#p#W#w
        from boto3.dynamodb.conditions import Key
        events_pk = "T#t1#P#p1#W#w01"
        response = events_table.query(
            KeyConditionExpression=Key("PK").eq(events_pk),
        )
        events = response.get("Items", [])
        assert len(events) >= 1
        assert events[0]["event_type"] == "crow_assigned"


class TestReactToCrowCompletion:
    def test_planner_completed_assigns_implementer(
        self, blackboard: Blackboard, logger: StructuredLogger
    ) -> None:
        _seed_wave(blackboard)
        _seed_mvi(blackboard, status=MVIStatus.EXECUTING)
        crow = _seed_crow(
            blackboard,
            outcome={"tasks": [{"name": "t1", "description": "do stuff"}]},
        )
        crow_item = blackboard.read(crow.pk, crow.sk)
        assert crow_item is not None

        react_to_crow_completion(blackboard, crow_item, logger)

        pk = build_pk("t1", "p1")
        crows = blackboard.query(pk, "S#w01#m01#cr_")
        types = [c["crow_type"] for c in crows]
        assert "implementer" in types

    def test_implementer_completed_assigns_reviewer(
        self, blackboard: Blackboard, logger: StructuredLogger
    ) -> None:
        _seed_wave(blackboard)
        _seed_mvi(blackboard, status=MVIStatus.EXECUTING)
        crow = _seed_crow(
            blackboard,
            crow_id="cr_impl_01",
            crow_type=CrowType.IMPLEMENTER,
        )
        crow_item = blackboard.read(crow.pk, crow.sk)
        assert crow_item is not None

        react_to_crow_completion(blackboard, crow_item, logger)

        pk = build_pk("t1", "p1")
        crows = blackboard.query(pk, "S#w01#m01#cr_")
        types = [c["crow_type"] for c in crows]
        assert "reviewer" in types

    def test_reviewer_approved_marks_mvi_ready(
        self, blackboard: Blackboard, logger: StructuredLogger
    ) -> None:
        _seed_wave(blackboard)
        _seed_mvi(blackboard, status=MVIStatus.EXECUTING)
        crow = _seed_crow(
            blackboard,
            crow_id="cr_rev_01",
            crow_type=CrowType.REVIEWER,
            outcome={"approved": True},
        )
        crow_item = blackboard.read(crow.pk, crow.sk)
        assert crow_item is not None

        react_to_crow_completion(blackboard, crow_item, logger)

        pk = build_pk("t1", "p1")
        mvi_sk = build_sk(wave_id="w01", mvi_id="01")
        updated = blackboard.read(pk, mvi_sk)
        assert updated is not None
        assert updated["status"] == "ready_to_ship"
        assert updated["can_ship"] is True

    def test_reviewer_rejected_assigns_fixer(
        self, blackboard: Blackboard, logger: StructuredLogger
    ) -> None:
        _seed_wave(blackboard)
        _seed_mvi(blackboard, status=MVIStatus.EXECUTING)
        crow = _seed_crow(
            blackboard,
            crow_id="cr_rev_01",
            crow_type=CrowType.REVIEWER,
            outcome={"approved": False, "issues": ["bug"]},
        )
        crow_item = blackboard.read(crow.pk, crow.sk)
        assert crow_item is not None

        react_to_crow_completion(blackboard, crow_item, logger)

        pk = build_pk("t1", "p1")
        crows = blackboard.query(pk, "S#w01#m01#cr_")
        types = [c["crow_type"] for c in crows]
        assert "fixer" in types

    def test_fixer_completed_assigns_reviewer(
        self, blackboard: Blackboard, logger: StructuredLogger
    ) -> None:
        _seed_wave(blackboard)
        _seed_mvi(blackboard, status=MVIStatus.EXECUTING)
        crow = _seed_crow(
            blackboard,
            crow_id="cr_fix_01",
            crow_type=CrowType.FIXER,
        )
        crow_item = blackboard.read(crow.pk, crow.sk)
        assert crow_item is not None

        react_to_crow_completion(blackboard, crow_item, logger)

        pk = build_pk("t1", "p1")
        crows = blackboard.query(pk, "S#w01#m01#cr_")
        types = [c["crow_type"] for c in crows]
        assert "reviewer" in types

    def test_implementer_failed_retries(
        self, blackboard: Blackboard, logger: StructuredLogger
    ) -> None:
        _seed_wave(blackboard)
        _seed_mvi(blackboard, status=MVIStatus.EXECUTING)
        crow = _seed_crow(
            blackboard,
            crow_id="cr_impl_01",
            crow_type=CrowType.IMPLEMENTER,
            status=CrowStatus.FAILED,
            retry_count=1,
        )
        crow_item = blackboard.read(crow.pk, crow.sk)
        assert crow_item is not None

        react_to_crow_completion(blackboard, crow_item, logger)

        pk = build_pk("t1", "p1")
        crows = blackboard.query(pk, "S#w01#m01#cr_")
        new_crows = [c for c in crows if c["SK"] != crow.sk]
        assert len(new_crows) == 1
        assert new_crows[0]["crow_type"] == "implementer"
        assert new_crows[0]["retry_count"] == 2

    def test_implementer_max_retries_fails_mvi(
        self, blackboard: Blackboard, logger: StructuredLogger
    ) -> None:
        _seed_wave(blackboard)
        _seed_mvi(blackboard, status=MVIStatus.EXECUTING)
        crow = _seed_crow(
            blackboard,
            crow_id="cr_impl_01",
            crow_type=CrowType.IMPLEMENTER,
            status=CrowStatus.FAILED,
            retry_count=3,
        )
        crow_item = blackboard.read(crow.pk, crow.sk)
        assert crow_item is not None

        react_to_crow_completion(blackboard, crow_item, logger)

        pk = build_pk("t1", "p1")
        mvi_sk = build_sk(wave_id="w01", mvi_id="01")
        updated = blackboard.read(pk, mvi_sk)
        assert updated is not None
        assert updated["status"] == "failed"

    def test_crow_completion_increments_wave_budget_spent(
        self, blackboard: Blackboard, logger: StructuredLogger
    ) -> None:
        _seed_wave(blackboard)
        _seed_mvi(blackboard, status=MVIStatus.EXECUTING)
        crow = _seed_crow(
            blackboard,
            outcome={"tasks": [{"name": "t1"}]},
            cost=Cost(tokens_in=1000, tokens_out=500, credits=10_500, duration_ms=5000),
        )
        crow_item = blackboard.read(crow.pk, crow.sk)
        assert crow_item is not None

        react_to_crow_completion(blackboard, crow_item, logger)

        pk = build_pk("t1", "p1")
        wave = blackboard.read(pk, build_sk(wave_id="w01"))
        assert wave is not None
        assert int(wave["budget"]["spent"]) == 10_500

    def test_reviewer_instructions_include_planner_tasks(
        self, blackboard: Blackboard, logger: StructuredLogger
    ) -> None:
        _seed_wave(blackboard)
        _seed_mvi(blackboard, status=MVIStatus.EXECUTING)
        _seed_crow(
            blackboard,
            crow_id="cr_plan_01",
            crow_type=CrowType.PLANNER,
            outcome={"tasks": [{"name": "add endpoint"}, {"name": "add test"}]},
        )
        impl_crow = _seed_crow(
            blackboard,
            crow_id="cr_impl_02",
            crow_type=CrowType.IMPLEMENTER,
            status=CrowStatus.COMPLETED,
        )
        impl_item = blackboard.read(impl_crow.pk, impl_crow.sk)
        assert impl_item is not None

        react_to_crow_completion(blackboard, impl_item, logger)

        pk = build_pk("t1", "p1")
        crows = blackboard.query(pk, "S#w01#m01#cr_")
        rev_crows = [c for c in crows if c["crow_type"] == "reviewer"]
        assert len(rev_crows) == 1
        instructions = rev_crows[0]["instructions"]
        assert "add endpoint" in instructions
        assert "add test" in instructions
        assert "Planned tasks" in instructions

    def test_fixer_receives_fix_history(
        self, blackboard: Blackboard, logger: StructuredLogger
    ) -> None:
        """Second fixer assignment includes history from the first reviewer/fixer cycle."""
        _seed_wave(blackboard)
        _seed_mvi(blackboard, status=MVIStatus.EXECUTING)

        # First reviewer: rejected with issues
        _seed_crow(
            blackboard,
            crow_id="cr_rev_01",
            crow_type=CrowType.REVIEWER,
            status=CrowStatus.COMPLETED,
            outcome={
                "approved": False,
                "issues": ["missing null check", "no test coverage"],
            },
        )

        # First fixer: completed with a summary and files changed
        _seed_crow(
            blackboard,
            crow_id="cr_fix_02",
            crow_type=CrowType.FIXER,
            status=CrowStatus.COMPLETED,
            outcome={
                "summary": "Added null guard in handler, wrote unit test",
                "files_changed": ["src/handler.py", "tests/test_handler.py"],
            },
        )

        # Second reviewer: rejected again (this is the triggering crow)
        second_reviewer = _seed_crow(
            blackboard,
            crow_id="cr_rev_03",
            crow_type=CrowType.REVIEWER,
            status=CrowStatus.COMPLETED,
            outcome={
                "approved": False,
                "issues": ["test coverage still insufficient"],
            },
        )
        reviewer_item = blackboard.read(second_reviewer.pk, second_reviewer.sk)
        assert reviewer_item is not None

        react_to_crow_completion(blackboard, reviewer_item, logger)

        pk = build_pk("t1", "p1")
        crows = blackboard.query(pk, "S#w01#m01#cr_")
        fixer_crows = [c for c in crows if c["crow_type"] == "fixer" and c["status"] == "pending"]
        assert len(fixer_crows) == 1

        instructions = fixer_crows[0]["instructions"]
        assert "Previous Fix Attempts" in instructions
        assert "missing null check" in instructions
        assert "Added null guard in handler" in instructions
        assert "src/handler.py" in instructions
        assert "Attempt 1" in instructions

    def test_first_fixer_has_no_history(
        self, blackboard: Blackboard, logger: StructuredLogger
    ) -> None:
        """First fixer assignment has no history section."""
        _seed_wave(blackboard)
        _seed_mvi(blackboard, status=MVIStatus.EXECUTING)

        reviewer = _seed_crow(
            blackboard,
            crow_id="cr_rev_01",
            crow_type=CrowType.REVIEWER,
            status=CrowStatus.COMPLETED,
            outcome={"approved": False, "issues": ["bug"]},
        )
        reviewer_item = blackboard.read(reviewer.pk, reviewer.sk)
        assert reviewer_item is not None

        react_to_crow_completion(blackboard, reviewer_item, logger)

        pk = build_pk("t1", "p1")
        crows = blackboard.query(pk, "S#w01#m01#cr_")
        fixer_crows = [c for c in crows if c["crow_type"] == "fixer"]
        assert len(fixer_crows) == 1
        assert "Previous Fix Attempts" not in fixer_crows[0]["instructions"]

    def test_full_pipeline_planner_to_ready(
        self, blackboard: Blackboard, logger: StructuredLogger
    ) -> None:
        """End-to-end: planner -> implementer -> reviewer(approved) -> MVI ready."""
        _seed_wave(blackboard)
        _seed_mvi(blackboard, status=MVIStatus.EXECUTING)

        # Step 1: planner completed
        planner = _seed_crow(
            blackboard,
            outcome={"tasks": [{"name": "add login"}]},
        )
        planner_item = blackboard.read(planner.pk, planner.sk)
        assert planner_item is not None
        react_to_crow_completion(blackboard, planner_item, logger)

        # Step 2: implementer completed
        pk = build_pk("t1", "p1")
        crows = blackboard.query(pk, "S#w01#m01#cr_")
        impl_items = [c for c in crows if c["crow_type"] == "implementer"]
        assert len(impl_items) == 1
        impl_item = impl_items[0]
        blackboard.update(
            pk, impl_item["SK"],
            {"status": "completed", "outcome": {}},
        )
        updated_impl = blackboard.read(pk, impl_item["SK"])
        assert updated_impl is not None
        react_to_crow_completion(blackboard, updated_impl, logger)

        # Step 3: reviewer approved
        crows = blackboard.query(pk, "S#w01#m01#cr_")
        rev_items = [c for c in crows if c["crow_type"] == "reviewer"]
        assert len(rev_items) == 1
        rev_item = rev_items[0]
        blackboard.update(
            pk, rev_item["SK"],
            {"status": "completed", "outcome": {"approved": True}},
        )
        updated_rev = blackboard.read(pk, rev_item["SK"])
        assert updated_rev is not None
        react_to_crow_completion(blackboard, updated_rev, logger)

        # Verify MVI is ready to ship
        mvi_sk = build_sk(wave_id="w01", mvi_id="01")
        mvi = blackboard.read(pk, mvi_sk)
        assert mvi is not None
        assert mvi["status"] == "ready_to_ship"
        assert mvi["can_ship"] is True
        # Task counts propagated from planner outcome onto the MVI so iOS
        # merge-readiness gauge can render "1/1 tasks completed".
        assert int(mvi.get("tasks_total", 0)) == 1
        assert int(mvi.get("tasks_done", 0)) == 1

    def test_planner_outcome_populates_mvi_task_count(
        self, blackboard: Blackboard, logger: StructuredLogger
    ) -> None:
        """Planner completion writes tasks_total onto the MVI snapshot.

        Without this, iOS shows '0/0 tasks completed' on the merge-readiness
        gauge even after the MVI ships, because the Murder loop never
        propagates the planner's task count from its outcome onto the MVI.
        """
        _seed_wave(blackboard)
        _seed_mvi(blackboard, status=MVIStatus.EXECUTING)

        planner = _seed_crow(
            blackboard,
            outcome={
                "tasks": [
                    {"name": "task one"},
                    {"name": "task two"},
                    {"name": "task three"},
                ]
            },
        )
        planner_item = blackboard.read(planner.pk, planner.sk)
        assert planner_item is not None
        react_to_crow_completion(blackboard, planner_item, logger)

        pk = build_pk("t1", "p1")
        mvi_sk = build_sk(wave_id="w01", mvi_id="01")
        mvi = blackboard.read(pk, mvi_sk)
        assert mvi is not None
        assert int(mvi.get("tasks_total", 0)) == 3
        # tasks_done stays at 0 until the implementer finishes and the MVI
        # transitions to ready_to_ship.
        assert int(mvi.get("tasks_done", 0)) == 0

    def test_reviewer_rejects_after_max_fix_cycles_fails_mvi(
        self, blackboard: Blackboard, logger: StructuredLogger
    ) -> None:
        """After FIX_CYCLE_LIMIT completed fixers, a rejecting reviewer fails the MVI."""
        _seed_wave(blackboard)
        _seed_mvi(blackboard, status=MVIStatus.EXECUTING)

        # Two completed fixers already exist
        _seed_crow(
            blackboard,
            crow_id="cr_fix_01",
            crow_type=CrowType.FIXER,
            status=CrowStatus.COMPLETED,
            outcome={"summary": "first fix", "files_changed": [], "issues_addressed": []},
        )
        _seed_crow(
            blackboard,
            crow_id="cr_fix_02",
            crow_type=CrowType.FIXER,
            status=CrowStatus.COMPLETED,
            outcome={"summary": "second fix", "files_changed": [], "issues_addressed": []},
        )

        # Reviewer still rejects (triggering crow)
        reviewer = _seed_crow(
            blackboard,
            crow_id="cr_rev_03",
            crow_type=CrowType.REVIEWER,
            status=CrowStatus.COMPLETED,
            outcome={"blocking_issues": ["still broken"], "approved": False},
        )
        reviewer_item = blackboard.read(reviewer.pk, reviewer.sk)
        assert reviewer_item is not None

        react_to_crow_completion(blackboard, reviewer_item, logger)

        pk = build_pk("t1", "p1")
        mvi_sk = build_sk(wave_id="w01", mvi_id="01")
        mvi = blackboard.read(pk, mvi_sk)
        assert mvi is not None
        assert mvi["status"] == "failed"

        # No new fixer should have been assigned
        crows = blackboard.query(pk, "S#w01#m01#cr_")
        fixer_pending = [c for c in crows if c["crow_type"] == "fixer" and c["status"] == "pending"]
        assert len(fixer_pending) == 0

    def test_reviewer_rejects_within_fix_limit_assigns_fixer(
        self, blackboard: Blackboard, logger: StructuredLogger
    ) -> None:
        """When fix_count < FIX_CYCLE_LIMIT, a rejecting reviewer still assigns another fixer."""
        _seed_wave(blackboard)
        _seed_mvi(blackboard, status=MVIStatus.EXECUTING)

        # Only one completed fixer exists (limit is 2)
        _seed_crow(
            blackboard,
            crow_id="cr_fix_01",
            crow_type=CrowType.FIXER,
            status=CrowStatus.COMPLETED,
            outcome={"summary": "first fix", "files_changed": [], "issues_addressed": []},
        )

        reviewer = _seed_crow(
            blackboard,
            crow_id="cr_rev_02",
            crow_type=CrowType.REVIEWER,
            status=CrowStatus.COMPLETED,
            outcome={"blocking_issues": ["still broken"], "approved": False},
        )
        reviewer_item = blackboard.read(reviewer.pk, reviewer.sk)
        assert reviewer_item is not None

        react_to_crow_completion(blackboard, reviewer_item, logger)

        pk = build_pk("t1", "p1")
        crows = blackboard.query(pk, "S#w01#m01#cr_")
        fixer_pending = [c for c in crows if c["crow_type"] == "fixer" and c["status"] == "pending"]
        assert len(fixer_pending) == 1

    def test_fix_history_built_with_blocking_issues_field(
        self, blackboard: Blackboard, logger: StructuredLogger
    ) -> None:
        """Fix history uses blocking_issues field when present in reviewer outcome."""
        _seed_wave(blackboard)
        _seed_mvi(blackboard, status=MVIStatus.EXECUTING)

        # Reviewer using new blocking_issues field (no approved field)
        _seed_crow(
            blackboard,
            crow_id="cr_rev_01",
            crow_type=CrowType.REVIEWER,
            status=CrowStatus.COMPLETED,
            outcome={
                "blocking_issues": ["SQL injection at db.py:42"],
                "non_blocking_issues": ["rename x to y"],
                "issues": ["SQL injection at db.py:42", "rename x to y"],
            },
        )

        # Fixer completed
        _seed_crow(
            blackboard,
            crow_id="cr_fix_02",
            crow_type=CrowType.FIXER,
            status=CrowStatus.COMPLETED,
            outcome={
                "summary": "Fixed SQL injection",
                "files_changed": ["src/db.py"],
                "issues_addressed": ["SQL injection"],
            },
        )

        # Second reviewer rejects again
        second_reviewer = _seed_crow(
            blackboard,
            crow_id="cr_rev_03",
            crow_type=CrowType.REVIEWER,
            status=CrowStatus.COMPLETED,
            outcome={"blocking_issues": ["still broken"], "approved": False},
        )
        reviewer_item = blackboard.read(second_reviewer.pk, second_reviewer.sk)
        assert reviewer_item is not None

        react_to_crow_completion(blackboard, reviewer_item, logger)

        pk = build_pk("t1", "p1")
        crows = blackboard.query(pk, "S#w01#m01#cr_")
        fixer_pending = [c for c in crows if c["crow_type"] == "fixer" and c["status"] == "pending"]
        assert len(fixer_pending) == 1

        instructions = fixer_pending[0]["instructions"]
        assert "Previous Fix Attempts" in instructions
        assert "SQL injection at db.py:42" in instructions
        assert "Fixed SQL injection" in instructions

    def test_reviewer_after_fixer_includes_fixer_context(
        self, blackboard: Blackboard, logger: StructuredLogger
    ) -> None:
        """Reviewer assigned after fixer receives the fixer's outcome as context."""
        _seed_wave(blackboard)
        _seed_mvi(blackboard, status=MVIStatus.EXECUTING)

        fixer = _seed_crow(
            blackboard,
            crow_id="cr_fix_01",
            crow_type=CrowType.FIXER,
            status=CrowStatus.COMPLETED,
            outcome={
                "summary": "Added null guard",
                "files_changed": ["src/handler.py"],
                "issues_addressed": ["null pointer exception"],
            },
        )
        fixer_item = blackboard.read(fixer.pk, fixer.sk)
        assert fixer_item is not None

        react_to_crow_completion(blackboard, fixer_item, logger)

        pk = build_pk("t1", "p1")
        crows = blackboard.query(pk, "S#w01#m01#cr_")
        reviewer_pending = [c for c in crows if c["crow_type"] == "reviewer" and c["status"] == "pending"]
        assert len(reviewer_pending) == 1

        instructions = reviewer_pending[0]["instructions"]
        assert "Recent Fixes Applied" in instructions
        assert "Added null guard" in instructions
        assert "src/handler.py" in instructions


class TestReactToMVITerminal:
    """Tests for the MVI shipped/rejected → wave delivered transition.

    Triggered by the iOS PR Review screen calling Approve & Merge or
    Reject. After the API updates the MVI snapshot, the DDB Stream
    dispatches into react_to_mvi_terminal, which checks if the wave can
    now leave REVIEW → DELIVERED.
    """

    def test_shipped_mvi_transitions_wave_to_delivered_when_only_mvi(
        self, blackboard: Blackboard, logger: StructuredLogger
    ) -> None:
        """Single-MVI wave: shipping the only MVI delivers the wave."""
        wave = WaveSnapshot(
            tenant="t1",
            project="p1",
            wave_id="w01",
            status=WaveStatus.REVIEW,  # wave already moved past executing
            human_directive="x",
            budget=WaveBudget(spent=0, limit=WAVE_BUDGET_LIMIT),
        )
        blackboard.write_item(wave.to_item())
        _seed_mvi(blackboard, status=MVIStatus.SHIPPED)

        mvi_sk = build_sk(wave_id="w01", mvi_id="01")
        mvi_item = blackboard.read(build_pk("t1", "p1"), mvi_sk)
        assert mvi_item is not None
        react_to_mvi_terminal(blackboard, mvi_item, logger)

        wave_after = blackboard.read(build_pk("t1", "p1"), build_sk(wave_id="w01"))
        assert wave_after is not None
        assert wave_after["status"] == "delivered"

    def test_shipped_mvi_does_not_deliver_when_sibling_still_ready(
        self, blackboard: Blackboard, logger: StructuredLogger
    ) -> None:
        """Wave stays in REVIEW if another MVI is still ready_to_ship."""
        wave = WaveSnapshot(
            tenant="t1",
            project="p1",
            wave_id="w01",
            status=WaveStatus.REVIEW,
            human_directive="x",
            budget=WaveBudget(spent=0, limit=WAVE_BUDGET_LIMIT),
        )
        blackboard.write_item(wave.to_item())
        _seed_mvi(blackboard, mvi_id="01", status=MVIStatus.SHIPPED)
        _seed_mvi(blackboard, mvi_id="02", status=MVIStatus.READY_TO_SHIP)

        mvi_sk = build_sk(wave_id="w01", mvi_id="01")
        mvi_item = blackboard.read(build_pk("t1", "p1"), mvi_sk)
        assert mvi_item is not None
        react_to_mvi_terminal(blackboard, mvi_item, logger)

        wave_after = blackboard.read(build_pk("t1", "p1"), build_sk(wave_id="w01"))
        assert wave_after is not None
        assert wave_after["status"] == "review"

    def test_rejected_mvi_also_counts_as_terminal(
        self, blackboard: Blackboard, logger: StructuredLogger
    ) -> None:
        """A rejected MVI is a final disposition — wave can still deliver."""
        wave = WaveSnapshot(
            tenant="t1",
            project="p1",
            wave_id="w01",
            status=WaveStatus.REVIEW,
            human_directive="x",
            budget=WaveBudget(spent=0, limit=WAVE_BUDGET_LIMIT),
        )
        blackboard.write_item(wave.to_item())
        _seed_mvi(blackboard, mvi_id="01", status=MVIStatus.SHIPPED)
        _seed_mvi(blackboard, mvi_id="02", status=MVIStatus.REJECTED)

        mvi_sk = build_sk(wave_id="w01", mvi_id="02")
        mvi_item = blackboard.read(build_pk("t1", "p1"), mvi_sk)
        assert mvi_item is not None
        react_to_mvi_terminal(blackboard, mvi_item, logger)

        wave_after = blackboard.read(build_pk("t1", "p1"), build_sk(wave_id="w01"))
        assert wave_after is not None
        assert wave_after["status"] == "delivered"

    def test_terminal_mvi_with_no_wave_is_noop(
        self, blackboard: Blackboard, logger: StructuredLogger
    ) -> None:
        """If the wave snapshot is missing, the reactor exits cleanly."""
        _seed_mvi(blackboard, status=MVIStatus.SHIPPED)
        mvi_sk = build_sk(wave_id="w01", mvi_id="01")
        mvi_item = blackboard.read(build_pk("t1", "p1"), mvi_sk)
        assert mvi_item is not None
        # No wave seeded; this should not raise.
        react_to_mvi_terminal(blackboard, mvi_item, logger)

    def test_terminal_mvi_does_not_advance_wave_if_already_delivered(
        self, blackboard: Blackboard, logger: StructuredLogger
    ) -> None:
        """Idempotency — re-dispatching on an already-delivered wave is a noop."""
        wave = WaveSnapshot(
            tenant="t1",
            project="p1",
            wave_id="w01",
            status=WaveStatus.DELIVERED,
            human_directive="x",
            budget=WaveBudget(spent=0, limit=WAVE_BUDGET_LIMIT),
        )
        blackboard.write_item(wave.to_item())
        _seed_mvi(blackboard, status=MVIStatus.SHIPPED)

        mvi_sk = build_sk(wave_id="w01", mvi_id="01")
        mvi_item = blackboard.read(build_pk("t1", "p1"), mvi_sk)
        assert mvi_item is not None
        react_to_mvi_terminal(blackboard, mvi_item, logger)

        wave_after = blackboard.read(build_pk("t1", "p1"), build_sk(wave_id="w01"))
        assert wave_after is not None
        assert wave_after["status"] == "delivered"


class TestHandleWaveReviewReady:
    def test_all_mvis_ready_writes_integrator_task_and_transitions_wave(
        self, blackboard: Blackboard, logger: StructuredLogger
    ) -> None:
        blackboard.write_item(
            {
                "PK": "P#p1",
                "SK": "S#w1",
                "level": "wave",
                "status": "review",
                "wave_id": "w1",
            }
        )
        blackboard.write_item(
            {
                "PK": "P#p1",
                "SK": "S#w1#m_1",
                "level": "murder",
                "status": "ready_to_ship",
                "pr_number": 42,
                "mvi_id": "_1",
            }
        )
        blackboard.write_item(
            {
                "PK": "P#p1",
                "SK": "S#w1#m_2",
                "level": "murder",
                "status": "ready_to_ship",
                "pr_number": 43,
                "mvi_id": "_2",
            }
        )

        from murder.reactor import _maybe_start_integrator

        _maybe_start_integrator(
            blackboard=blackboard,
            pk="P#p1",
            wave_id="w1",
            logger=logger,
        )

        wave = blackboard.read("P#p1", "S#w1")
        assert wave is not None
        assert wave["status"] == "integrating"

        task = blackboard.read("P#p1", "S#w1/integrator-task")
        assert task is not None
        assert task["crow_kind"] == "integrator"
        assert task["pr_to_mvi"] == {"42": "_1", "43": "_2"}

    def test_not_all_mvis_ready_does_nothing(
        self, blackboard: Blackboard, logger: StructuredLogger
    ) -> None:
        blackboard.write_item(
            {
                "PK": "P#p1",
                "SK": "S#w2",
                "level": "wave",
                "status": "review",
                "wave_id": "w2",
            }
        )
        blackboard.write_item(
            {
                "PK": "P#p1",
                "SK": "S#w2#m_1",
                "level": "murder",
                "status": "ready_to_ship",
                "pr_number": 42,
                "mvi_id": "_1",
            }
        )
        blackboard.write_item(
            {
                "PK": "P#p1",
                "SK": "S#w2#m_2",
                "level": "murder",
                "status": "executing",
                "mvi_id": "_2",
            }
        )

        from murder.reactor import _maybe_start_integrator

        _maybe_start_integrator(
            blackboard=blackboard,
            pk="P#p1",
            wave_id="w2",
            logger=logger,
        )

        wave = blackboard.read("P#p1", "S#w2")
        assert wave is not None
        assert wave["status"] == "review"
        assert blackboard.read("P#p1", "S#w2/integrator-task") is None


class TestHandleIntegrationComplete:
    def test_ready_for_council_writes_council_task_and_transitions_wave(
        self, blackboard: Blackboard, logger: StructuredLogger
    ) -> None:
        blackboard.write_item(
            {
                "PK": "P#p1",
                "SK": "S#w1",
                "level": "wave",
                "status": "integrating",
                "wave_id": "w1",
                "auto_mode": "on",
            }
        )

        findings = {
            "PK": "P#p1",
            "SK": "INTEGRATION#w1",
            "wave_id": "w1",
            "overall": "ready_for_council",
            "merge_status": "ok",
            "rework_reasons": [],
        }

        from murder.reactor import react_to_integration_complete

        react_to_integration_complete(
            blackboard=blackboard,
            findings=findings,
            logger=logger,
        )

        wave = blackboard.read("P#p1", "S#w1")
        assert wave is not None
        assert wave["status"] == "under_council_review"

        sessions = blackboard.query("P#p1", "COUNCIL#")
        assert len(sessions) == 1
        assert sessions[0]["status"] == "pending"
        assert sessions[0]["wave_id"] == "w1"
        assert sessions[0]["integration_sk"] == "INTEGRATION#w1"

    def test_needs_rework_dispatches_fixers_per_affected_mvi(
        self, blackboard: Blackboard, logger: StructuredLogger
    ) -> None:
        blackboard.write_item(
            {
                "PK": "P#p1",
                "SK": "S#w1",
                "level": "wave",
                "status": "integrating",
                "wave_id": "w1",
            }
        )
        blackboard.write_item(
            {
                "PK": "P#p1",
                "SK": "S#w1#m_1",
                "level": "murder",
                "status": "ready_to_ship",
                "mvi_id": "_1",
            }
        )
        blackboard.write_item(
            {
                "PK": "P#p1",
                "SK": "S#w1#m_2",
                "level": "murder",
                "status": "ready_to_ship",
                "mvi_id": "_2",
            }
        )

        findings = {
            "PK": "P#p1",
            "SK": "INTEGRATION#w1",
            "wave_id": "w1",
            "overall": "needs_rework",
            "merge_status": "conflict",
            "rework_reasons": [
                "merge conflict between PR #42 and PR #43 (1 files)"
            ],
            "merge_conflicts": [
                {
                    "pr_a": 42,
                    "pr_b": 43,
                    "mvi_a": "_1",
                    "mvi_b": "_2",
                    "files": ["foo.py"],
                    "hunks": [],
                }
            ],
        }

        from murder.reactor import react_to_integration_complete

        react_to_integration_complete(
            blackboard=blackboard,
            findings=findings,
            logger=logger,
        )

        wave = blackboard.read("P#p1", "S#w1")
        assert wave is not None
        assert wave["status"] == "executing"

        mvi_1 = blackboard.read("P#p1", "S#w1#m_1")
        mvi_2 = blackboard.read("P#p1", "S#w1#m_2")
        assert mvi_1 is not None and mvi_1["status"] == "executing"
        assert mvi_2 is not None and mvi_2["status"] == "executing"


class TestHandleCouncilComplete:
    def test_council_completed_transitions_wave_to_under_human_review(
        self, blackboard: Blackboard, logger: StructuredLogger
    ) -> None:
        blackboard.write_item(
            {
                "PK": "P#p1",
                "SK": "S#w1",
                "level": "wave",
                "status": "under_council_review",
                "wave_id": "w1",
            }
        )
        session = {
            "PK": "P#p1",
            "SK": "COUNCIL#wr_w1_xyz",
            "status": "completed",
            "wave_id": "w1",
            "decision": {"action": "approve"},
        }
        from murder.reactor import react_to_council_complete

        react_to_council_complete(
            blackboard=blackboard,
            session=session,
            logger=logger,
        )
        wave = blackboard.read("P#p1", "S#w1")
        assert wave is not None
        assert wave["status"] == "under_human_review"
