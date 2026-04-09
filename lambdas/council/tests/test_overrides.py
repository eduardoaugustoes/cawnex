"""Tests for human override processing."""

from decimal import Decimal

import pytest

from council._blackboard import Blackboard
from council.enums import AdvisorType, DecisionAction, VoteType
from council.overrides import HumanOverride, apply_override


@pytest.fixture
def blackboard(dynamodb_table, events_table):  # type: ignore[no-untyped-def]
    return Blackboard(dynamodb_table, events_table=events_table)


def _seed_escalated_session(
    blackboard: Blackboard,
    pk: str = "T#t1#P#p1",
    session_id: str = "wr_w01_abc",
) -> None:
    """Seed a council session that has been escalated."""
    blackboard.write_item(
        {
            "PK": pk,
            "SK": f"COUNCIL#{session_id}",
            "level": "council",
            "status": "completed",
            "type": "wave_review",
            "wave_id": "w01",
            "rounds": [
                {
                    "round": 1,
                    "votes": [
                        {
                            "advisor": "security",
                            "vote": "block",
                            "scores": {"mvi_01": 2},
                            "reasoning": "No rate limiting",
                            "confidence": Decimal("0.9"),
                            "blockers": ["No rate limiting"],
                        },
                        {
                            "advisor": "quality",
                            "vote": "approve",
                            "scores": {"mvi_01": 8},
                            "reasoning": "Good tests",
                            "confidence": Decimal("0.8"),
                        },
                        {
                            "advisor": "performance",
                            "vote": "approve",
                            "scores": {"mvi_01": 7},
                            "reasoning": "Fine",
                            "confidence": Decimal("0.7"),
                        },
                        {
                            "advisor": "market",
                            "vote": "approve",
                            "scores": {"mvi_01": 9},
                            "reasoning": "Ship it",
                            "confidence": Decimal("0.85"),
                        },
                        {
                            "advisor": "maturity",
                            "vote": "approve",
                            "scores": {"mvi_01": 6},
                            "reasoning": "OK for MVP",
                            "confidence": Decimal("0.7"),
                        },
                        {
                            "advisor": "clarity",
                            "vote": "approve",
                            "scores": {"mvi_01": 8},
                            "reasoning": "Specs clear",
                            "confidence": Decimal("0.8"),
                        },
                    ],
                    "consensus": False,
                }
            ],
            "decision": {
                "action": "reject",
                "reasoning": "Security veto",
                "confidence": Decimal("0.9"),
            },
        }
    )


class TestOverrideBlock:
    def test_overrides_security_block_to_approve(
        self, blackboard: Blackboard
    ) -> None:
        pk = "T#t1#P#p1"
        _seed_escalated_session(blackboard, pk)

        override = HumanOverride(
            action="override_block",
            reason="Rate limiting will be added in next wave",
            advisor_overridden="security",
        )

        decision = apply_override(
            blackboard, pk, "COUNCIL#wr_w01_abc", "w01", override
        )

        # Should approve since the block is overridden
        assert decision.action in (
            DecisionAction.APPROVE,
            DecisionAction.APPROVE_WITH_CONDITIONS,
        )

    def test_override_saved_on_session(self, blackboard: Blackboard) -> None:
        pk = "T#t1#P#p1"
        _seed_escalated_session(blackboard, pk)

        override = HumanOverride(
            action="override_block",
            reason="Accepted risk",
            advisor_overridden="security",
        )

        apply_override(blackboard, pk, "COUNCIL#wr_w01_abc", "w01", override)

        session = blackboard.read(pk, "COUNCIL#wr_w01_abc")
        assert session is not None
        assert len(session["human_overrides"]) == 1
        assert session["human_overrides"][0]["action"] == "override_block"


class TestForceDecision:
    def test_force_approves_with_wave_plan(
        self, blackboard: Blackboard
    ) -> None:
        pk = "T#t1#P#p1"
        _seed_escalated_session(blackboard, pk)

        override = HumanOverride(
            action="force_decision",
            reason="I know what to build",
            wave_plan=["mvi_auth", "mvi_onboarding"],
        )

        decision = apply_override(
            blackboard, pk, "COUNCIL#wr_w01_abc", "w01", override
        )

        assert decision.action == DecisionAction.APPROVE
        assert decision.wave_plan == ["mvi_auth", "mvi_onboarding"]
        assert decision.confidence == 1.0


class TestAddConstraint:
    def test_approves_with_constraint(self, blackboard: Blackboard) -> None:
        pk = "T#t1#P#p1"
        _seed_escalated_session(blackboard, pk)

        override = HumanOverride(
            action="add_constraint",
            reason="Need webhook verification",
            constraint="Must add Stripe webhook verification before payment goes live",
        )

        decision = apply_override(
            blackboard, pk, "COUNCIL#wr_w01_abc", "w01", override
        )

        assert decision.action == DecisionAction.APPROVE_WITH_CONDITIONS
        assert "Stripe webhook" in decision.conditions[0]


class TestDismissAdvisor:
    def test_dismiss_removes_advisor_and_resynthesizes(
        self, blackboard: Blackboard
    ) -> None:
        pk = "T#t1#P#p1"
        _seed_escalated_session(blackboard, pk)

        override = HumanOverride(
            action="dismiss_advisor",
            reason="Ignore security for this wave",
            advisor_overridden="security",
        )

        decision = apply_override(
            blackboard, pk, "COUNCIL#wr_w01_abc", "w01", override
        )

        # Without security's block, remaining advisors all approve
        assert decision.action in (
            DecisionAction.APPROVE,
            DecisionAction.APPROVE_WITH_CONDITIONS,
        )


class TestRequestRound:
    def test_returns_escalate_for_new_round(
        self, blackboard: Blackboard
    ) -> None:
        pk = "T#t1#P#p1"
        _seed_escalated_session(blackboard, pk)

        override = HumanOverride(
            action="request_round",
            reason="Need more detail",
            question="Can rate limiting be a task within this wave?",
        )

        decision = apply_override(
            blackboard, pk, "COUNCIL#wr_w01_abc", "w01", override
        )

        # request_round doesn't produce a final decision — it triggers a new session
        assert decision.action == DecisionAction.ESCALATE


class TestHumanOverrideModel:
    def test_to_dict(self) -> None:
        override = HumanOverride(
            action="override_block",
            reason="Accepted risk",
            advisor_overridden="security",
            timestamp="2026-04-09T10:00:00Z",
        )
        d = override.to_dict()
        assert d["action"] == "override_block"
        assert d["advisor_overridden"] == "security"
        assert d["reason"] == "Accepted risk"
        assert d["timestamp"] == "2026-04-09T10:00:00Z"

    def test_to_dict_omits_empty_fields(self) -> None:
        override = HumanOverride(
            action="force_decision",
            reason="Ship it",
            wave_plan=["mvi_01"],
        )
        d = override.to_dict()
        assert "advisor_overridden" not in d
        assert "constraint" not in d
        assert "question" not in d
        assert d["wave_plan"] == ["mvi_01"]

    def test_session_not_found_raises(self, blackboard: Blackboard) -> None:
        override = HumanOverride(action="force_decision", reason="test")
        with pytest.raises(ValueError, match="not found"):
            apply_override(
                blackboard, "T#t1#P#p1", "COUNCIL#nonexistent", "w01", override
            )
