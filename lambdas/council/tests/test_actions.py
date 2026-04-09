"""Tests for council post-decision actions."""

import pytest

from council._blackboard import Blackboard
from council.actions import execute_decision, execute_planning_decision
from council.enums import DecisionAction
from council.models import CouncilDecision


@pytest.fixture
def blackboard(dynamodb_table, events_table):  # type: ignore[no-untyped-def]
    return Blackboard(dynamodb_table, events_table=events_table)


class TestExecuteDecision:
    def test_approve_delivers_wave_and_writes_continuation(
        self, blackboard: Blackboard
    ) -> None:
        pk = "T#t1#P#p1"
        wave_id = "w01"

        blackboard.write_item(
            {
                "PK": pk,
                "SK": f"S#{wave_id}",
                "level": "wave",
                "status": "review",
                "human_directive": "Build auth",
                "budget": {"spent": 0, "limit": 20000000},
                "progress": {
                    "mvis_total": 1,
                    "mvis_shipped": 0,
                    "tasks_done": 0,
                    "tasks_total": 0,
                },
            }
        )
        blackboard.write_item(
            {
                "PK": pk,
                "SK": "S#",
                "level": "root",
                "auto_mode": "auto",
                "maturity_stage": "mvp",
            }
        )
        blackboard.write_item(
            {
                "PK": pk,
                "SK": "BACKLOG#milestones",
                "milestones": [{"id": "ms_01", "goals": [{"id": "g_01"}]}],
            }
        )

        decision = CouncilDecision(
            action=DecisionAction.APPROVE,
            reasoning="All clear",
            confidence=0.88,
        )

        execute_decision(
            blackboard=blackboard,
            pk=pk,
            wave_id=wave_id,
            session_id="wr_w01_abc12345",
            decision=decision,
            auto_mode="auto",
        )

        wave = blackboard.read(pk, f"S#{wave_id}")
        assert wave is not None
        assert wave["status"] == "delivered"

        monarch_items = blackboard.query(pk, "MONARCH#continuation")
        assert len(monarch_items) == 1
        assert monarch_items[0]["mode"] == "continuation"
        assert monarch_items[0]["status"] == "pending"
        assert monarch_items[0]["delivered_wave_id"] == wave_id

    def test_reject_steers_wave(self, blackboard: Blackboard) -> None:
        pk = "T#t1#P#p1"
        wave_id = "w01"

        blackboard.write_item(
            {
                "PK": pk,
                "SK": f"S#{wave_id}",
                "level": "wave",
                "status": "review",
            }
        )

        decision = CouncilDecision(
            action=DecisionAction.REJECT,
            reasoning="Security veto",
            confidence=0.9,
            flagged_mvis=[
                {
                    "mvi_id": "01",
                    "advisor": "security",
                    "concern": "No rate limiting",
                }
            ],
        )

        execute_decision(
            blackboard=blackboard,
            pk=pk,
            wave_id=wave_id,
            session_id="wr_w01_abc12345",
            decision=decision,
            auto_mode="auto",
        )

        wave = blackboard.read(pk, f"S#{wave_id}")
        assert wave is not None
        assert wave["status"] == "steered"


class TestExecutePlanningDecision:
    def test_approve_writes_wave_launch_task(self, blackboard: Blackboard) -> None:
        pk = "T#t1#P#p1"

        decision = CouncilDecision(
            action=DecisionAction.APPROVE,
            reasoning="Good plan",
            confidence=0.85,
            wave_plan=["mvi_07", "mvi_08"],
        )

        execute_planning_decision(
            blackboard=blackboard,
            pk=pk,
            session_id="wp_abc12345",
            decision=decision,
            context={"goal_id": "g_03", "human_directive": "Build onboarding"},
        )

        monarch_items = blackboard.query(pk, "MONARCH#wave_launch")
        assert len(monarch_items) == 1
        assert monarch_items[0]["mode"] == "wave_launch"
        assert monarch_items[0]["wave_plan"]["mvi_ids"] == ["mvi_07", "mvi_08"]
