"""Tests for the reactor — core orchestration with DynamoDB Local.

All money values are integer microdollars (1 USD = 1_000_000).
"""

import pytest

from murder.blackboard import Blackboard
from murder.config import MICROS_PER_DOLLAR, WAVE_BUDGET_LIMIT
from murder.enums import CrowStatus, CrowType, MVIStatus, WaveStatus
from murder.keys import build_pk, build_sk
from murder.logging import StructuredLogger
from murder.models import Cost, CrowSnapshot, MVISnapshot, WaveBudget, WaveSnapshot
from murder.reactor import react_to_crow_completion, react_to_mvi_queued


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
def blackboard(dynamodb_table):  # type: ignore[no-untyped-def]
    return Blackboard(dynamodb_table)


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
        self, blackboard: Blackboard, logger: StructuredLogger
    ) -> None:
        _seed_wave(blackboard)
        mvi = _seed_mvi(blackboard)
        mvi_item = blackboard.read(mvi.pk, mvi.sk)
        assert mvi_item is not None

        react_to_mvi_queued(blackboard, mvi_item, logger)

        pk = build_pk("t1", "p1")
        events = blackboard.query(pk, "EVT#w01")
        assert len(events) >= 1
        assert events[0]["type"] == "crow_assigned"


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
