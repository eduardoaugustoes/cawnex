"""Tests for wave steering — council rejection triggers fixer crows."""

from decimal import Decimal

import pytest

from murder.blackboard import Blackboard
from murder.config import WAVE_BUDGET_LIMIT
from murder.enums import CrowStatus, CrowType, MVIStatus, WaveStatus
from murder.keys import build_pk, build_sk
from murder.logging import StructuredLogger
from murder.models import MVISnapshot, WaveBudget, WaveSnapshot
from murder.reactor import react_to_wave_steered


@pytest.fixture
def blackboard(dynamodb_table, events_table):  # type: ignore[no-untyped-def]
    return Blackboard(dynamodb_table, events_table=events_table)


@pytest.fixture
def logger() -> StructuredLogger:
    return StructuredLogger("test-steering", tenant="t1", project="p1")


def _seed_steered_wave(
    blackboard: Blackboard,
    wave_id: str = "w01",
    flagged_mvis: list | None = None,
) -> None:
    pk = build_pk("t1", "p1")

    # Project root
    blackboard.write_item(
        {
            "PK": pk,
            "SK": "S#",
            "level": "root",
            "auto_mode": "auto",
            "entityType": "Snapshot",
        }
    )

    # Wave in steered state with council feedback
    wave = WaveSnapshot(
        tenant="t1",
        project="p1",
        wave_id=wave_id,
        status=WaveStatus.STEERED,
        human_directive="Build auth",
    )
    item = wave.to_item()
    item["council_feedback"] = {
        "flagged_mvis": flagged_mvis
        or [
            {
                "mvi_id": "01",
                "advisor": "security",
                "concern": "No rate limiting on auth endpoint",
            }
        ],
        "reasoning": "Security veto: missing rate limiting",
    }
    blackboard.write_item(item)

    # MVI that was ready_to_ship but got flagged
    mvi = MVISnapshot(
        tenant="t1",
        project="p1",
        wave_id=wave_id,
        mvi_id="01",
        name="Auth MVI",
        status=MVIStatus.READY_TO_SHIP,
        repo="owner/repo",
        branch="feat/auth",
        description="Implement JWT authentication",
    )
    blackboard.write_item(mvi.to_item())


class TestReactToWaveSteered:
    def test_transitions_wave_to_executing(
        self, blackboard: Blackboard, logger: StructuredLogger
    ) -> None:
        _seed_steered_wave(blackboard)
        pk = build_pk("t1", "p1")

        wave_item = blackboard.read(pk, build_sk(wave_id="w01"))
        assert wave_item is not None
        react_to_wave_steered(blackboard, wave_item, logger)

        wave = blackboard.read(pk, build_sk(wave_id="w01"))
        assert wave is not None
        assert wave["status"] == "executing"

    def test_transitions_flagged_mvi_to_executing(
        self, blackboard: Blackboard, logger: StructuredLogger
    ) -> None:
        _seed_steered_wave(blackboard)
        pk = build_pk("t1", "p1")

        wave_item = blackboard.read(pk, build_sk(wave_id="w01"))
        assert wave_item is not None
        react_to_wave_steered(blackboard, wave_item, logger)

        mvi = blackboard.read(pk, build_sk(wave_id="w01", mvi_id="01"))
        assert mvi is not None
        assert mvi["status"] == "executing"

    def test_assigns_fixer_crow_with_council_feedback(
        self, blackboard: Blackboard, logger: StructuredLogger
    ) -> None:
        _seed_steered_wave(blackboard)
        pk = build_pk("t1", "p1")

        wave_item = blackboard.read(pk, build_sk(wave_id="w01"))
        assert wave_item is not None
        react_to_wave_steered(blackboard, wave_item, logger)

        # Should have a fixer crow assigned
        crows = blackboard.query(pk, "S#w01#m01#cr_")
        fixer_crows = [c for c in crows if c.get("crow_type") == "fixer"]
        assert len(fixer_crows) == 1
        assert fixer_crows[0]["status"] == "pending"
        # Instructions should contain council feedback
        assert "rate limiting" in fixer_crows[0]["instructions"].lower()

    def test_no_council_feedback_does_nothing(
        self, blackboard: Blackboard, logger: StructuredLogger
    ) -> None:
        pk = build_pk("t1", "p1")
        blackboard.write_item(
            {
                "PK": pk,
                "SK": "S#",
                "level": "root",
                "auto_mode": "auto",
                "entityType": "Snapshot",
            }
        )
        wave = WaveSnapshot(
            tenant="t1",
            project="p1",
            wave_id="w02",
            status=WaveStatus.STEERED,
            human_directive="Build auth",
        )
        blackboard.write_item(wave.to_item())

        wave_item = blackboard.read(pk, build_sk(wave_id="w02"))
        assert wave_item is not None
        react_to_wave_steered(blackboard, wave_item, logger)

        # Wave should still transition to executing even without flagged MVIs
        wave = blackboard.read(pk, build_sk(wave_id="w02"))
        assert wave is not None
        assert wave["status"] == "executing"

    def test_multiple_flagged_mvis(
        self, blackboard: Blackboard, logger: StructuredLogger
    ) -> None:
        pk = build_pk("t1", "p1")
        blackboard.write_item(
            {
                "PK": pk,
                "SK": "S#",
                "level": "root",
                "auto_mode": "auto",
                "entityType": "Snapshot",
            }
        )

        flagged = [
            {"mvi_id": "01", "advisor": "security", "concern": "No rate limiting"},
            {"mvi_id": "02", "advisor": "clarity", "concern": "Spec ambiguity"},
        ]
        wave = WaveSnapshot(
            tenant="t1",
            project="p1",
            wave_id="w03",
            status=WaveStatus.STEERED,
            human_directive="Build auth",
        )
        item = wave.to_item()
        item["council_feedback"] = {
            "flagged_mvis": flagged,
            "reasoning": "Multiple issues",
        }
        blackboard.write_item(item)

        for mvi_id in ("01", "02"):
            mvi = MVISnapshot(
                tenant="t1",
                project="p1",
                wave_id="w03",
                mvi_id=mvi_id,
                name=f"MVI {mvi_id}",
                status=MVIStatus.READY_TO_SHIP,
                repo="owner/repo",
                branch=f"feat/{mvi_id}",
            )
            blackboard.write_item(mvi.to_item())

        wave_item = blackboard.read(pk, build_sk(wave_id="w03"))
        assert wave_item is not None
        react_to_wave_steered(blackboard, wave_item, logger)

        # Both MVIs should be executing with fixer crows
        for mvi_id in ("01", "02"):
            mvi = blackboard.read(pk, build_sk(wave_id="w03", mvi_id=mvi_id))
            assert mvi is not None
            assert mvi["status"] == "executing"

            crows = blackboard.query(pk, f"S#w03#m{mvi_id}#cr_")
            fixer_crows = [c for c in crows if c.get("crow_type") == "fixer"]
            assert len(fixer_crows) == 1
