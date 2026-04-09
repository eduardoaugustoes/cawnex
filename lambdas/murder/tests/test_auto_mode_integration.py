"""Integration test: auto mode wave completion -> council trigger."""

from decimal import Decimal

import pytest

from murder.blackboard import Blackboard
from murder.enums import CrowStatus, CrowType, MVIStatus, WaveStatus
from murder.keys import build_pk, build_sk
from murder.logging import StructuredLogger
from murder.models import Cost, CrowSnapshot, MVISnapshot, WaveBudget, WaveSnapshot
from murder.reactor import react_to_crow_completion


@pytest.fixture
def blackboard(dynamodb_table, events_table):  # type: ignore[no-untyped-def]
    return Blackboard(dynamodb_table, events_table=events_table)


@pytest.fixture
def logger() -> StructuredLogger:
    return StructuredLogger("test-auto-mode", tenant="t1", project="p1")


class TestAutoModeFullChain:
    def test_reviewer_approve_triggers_council_in_auto_mode(
        self, blackboard: Blackboard, logger: StructuredLogger
    ) -> None:
        pk = build_pk("t1", "p1")

        # Seed project root with auto_mode
        blackboard.write_item(
            {
                "PK": pk,
                "SK": "S#",
                "level": "root",
                "auto_mode": "auto",
                "maturity_stage": "mvp",
                "entityType": "Snapshot",
            }
        )

        # Seed wave
        wave = WaveSnapshot(
            tenant="t1",
            project="p1",
            wave_id="w01",
            status=WaveStatus.EXECUTING,
            human_directive="Build auth",
        )
        blackboard.write_item(wave.to_item())

        # Seed single MVI (executing)
        mvi = MVISnapshot(
            tenant="t1",
            project="p1",
            wave_id="w01",
            mvi_id="01",
            name="Auth MVI",
            status=MVIStatus.EXECUTING,
            repo="owner/repo",
            branch="feat/auth",
        )
        blackboard.write_item(mvi.to_item())

        # Seed implementer crow (completed with test results)
        impl = CrowSnapshot(
            tenant="t1",
            project="p1",
            wave_id="w01",
            mvi_id="01",
            crow_id="cr_impl_01",
            crow_type=CrowType.IMPLEMENTER,
            status=CrowStatus.COMPLETED,
            instructions="implement auth",
            repo="owner/repo",
            branch="feat/auth",
            budget_remaining=20_000_000,
            outcome={
                "test_results": {"exit_code": 0, "summary": "10 passed"},
                "lint_results": {"exit_code": 0, "summary": "clean"},
                "coverage_delta": {"before": Decimal("80.0"), "after": Decimal("82.0")},
            },
        )
        blackboard.write_item(impl.to_item())

        # Seed reviewer crow (completed, approved)
        reviewer = CrowSnapshot(
            tenant="t1",
            project="p1",
            wave_id="w01",
            mvi_id="01",
            crow_id="cr_review_01",
            crow_type=CrowType.REVIEWER,
            status=CrowStatus.COMPLETED,
            instructions="review auth",
            repo="owner/repo",
            branch="feat/auth",
            budget_remaining=20_000_000,
            outcome={"approved": True, "blocking_issues": []},
        )
        blackboard.write_item(reviewer.to_item())

        # Trigger the chain
        reviewer_item = blackboard.read(reviewer.pk, reviewer.sk)
        assert reviewer_item is not None
        react_to_crow_completion(blackboard, reviewer_item, logger)

        # Verify: MVI is ready_to_ship with deterministic checks
        mvi_item = blackboard.read(pk, build_sk(wave_id="w01", mvi_id="01"))
        assert mvi_item is not None
        assert mvi_item["status"] == "ready_to_ship"
        assert "deterministic_checks" in mvi_item

        # Verify: wave transitioned to review
        wave_item = blackboard.read(pk, build_sk(wave_id="w01"))
        assert wave_item is not None
        assert wave_item["status"] == "review"

        # Verify: COUNCIL# task was written
        council_items = blackboard.query(pk, "COUNCIL#")
        assert len(council_items) == 1
        assert council_items[0]["type"] == "wave_review"
        assert council_items[0]["status"] == "pending"
        assert council_items[0]["wave_id"] == "w01"

    def test_no_council_trigger_when_auto_mode_off(
        self, blackboard: Blackboard, logger: StructuredLogger
    ) -> None:
        pk = build_pk("t1", "p1")

        # Project root with auto_mode OFF
        blackboard.write_item(
            {
                "PK": pk,
                "SK": "S#",
                "level": "root",
                "auto_mode": "off",
                "entityType": "Snapshot",
            }
        )

        wave = WaveSnapshot(
            tenant="t1",
            project="p1",
            wave_id="w02",
            status=WaveStatus.EXECUTING,
            human_directive="Build auth",
        )
        blackboard.write_item(wave.to_item())

        mvi = MVISnapshot(
            tenant="t1",
            project="p1",
            wave_id="w02",
            mvi_id="01",
            name="Auth MVI",
            status=MVIStatus.EXECUTING,
            repo="owner/repo",
            branch="feat/auth",
        )
        blackboard.write_item(mvi.to_item())

        impl = CrowSnapshot(
            tenant="t1",
            project="p1",
            wave_id="w02",
            mvi_id="01",
            crow_id="cr_impl_01",
            crow_type=CrowType.IMPLEMENTER,
            status=CrowStatus.COMPLETED,
            instructions="implement",
            repo="owner/repo",
            branch="feat/auth",
            budget_remaining=20_000_000,
            outcome={"test_results": {"exit_code": 0, "summary": "ok"}},
        )
        blackboard.write_item(impl.to_item())

        reviewer = CrowSnapshot(
            tenant="t1",
            project="p1",
            wave_id="w02",
            mvi_id="01",
            crow_id="cr_review_01",
            crow_type=CrowType.REVIEWER,
            status=CrowStatus.COMPLETED,
            instructions="review",
            repo="owner/repo",
            branch="feat/auth",
            budget_remaining=20_000_000,
            outcome={"approved": True, "blocking_issues": []},
        )
        blackboard.write_item(reviewer.to_item())

        reviewer_item = blackboard.read(reviewer.pk, reviewer.sk)
        assert reviewer_item is not None
        react_to_crow_completion(blackboard, reviewer_item, logger)

        # Wave should be in review but NO council task
        wave_item = blackboard.read(pk, build_sk(wave_id="w02"))
        assert wave_item is not None
        assert wave_item["status"] == "review"

        council_items = blackboard.query(pk, "COUNCIL#")
        assert len(council_items) == 0
