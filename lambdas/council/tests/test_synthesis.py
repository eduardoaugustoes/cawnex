"""Tests for Monarch synthesis — the decision-making core."""

from council.enums import AdvisorType, DecisionAction, VoteType
from council.models import AdvisorVote, VotingRound
from council.synthesis import synthesize_round


def _vote(
    advisor: AdvisorType,
    vote: VoteType,
    confidence: float = 0.8,
    blockers: list[str] | None = None,
    condition: str = "",
) -> AdvisorVote:
    return AdvisorVote(
        advisor=advisor,
        vote=vote,
        scores={},
        reasoning=f"{advisor.value} says {vote.value}",
        confidence=confidence,
        blockers=blockers or [],
        condition=condition,
    )


class TestSynthesizeRound:
    def test_consensus_approves(self) -> None:
        rnd = VotingRound(
            round_number=1,
            votes=[
                _vote(AdvisorType.SECURITY, VoteType.APPROVE, 0.9),
                _vote(AdvisorType.QUALITY, VoteType.APPROVE, 0.8),
                _vote(AdvisorType.PERFORMANCE, VoteType.APPROVE, 0.7),
                _vote(AdvisorType.MARKET, VoteType.APPROVE, 0.85),
                _vote(AdvisorType.MATURITY, VoteType.APPROVE, 0.75),
                _vote(AdvisorType.CLARITY, VoteType.APPROVE, 0.8),
            ],
        )
        decision = synthesize_round(rnd, round_number=1, max_rounds=3)
        assert decision.action == DecisionAction.APPROVE

    def test_security_veto_triggers_reject(self) -> None:
        rnd = VotingRound(
            round_number=1,
            votes=[
                _vote(
                    AdvisorType.SECURITY,
                    VoteType.BLOCK,
                    0.9,
                    blockers=["No rate limiting"],
                ),
                _vote(AdvisorType.QUALITY, VoteType.APPROVE, 0.8),
                _vote(AdvisorType.PERFORMANCE, VoteType.APPROVE, 0.7),
                _vote(AdvisorType.MARKET, VoteType.APPROVE, 0.85),
                _vote(AdvisorType.MATURITY, VoteType.APPROVE, 0.75),
                _vote(AdvisorType.CLARITY, VoteType.APPROVE, 0.8),
            ],
        )
        decision = synthesize_round(rnd, round_number=1, max_rounds=3)
        assert decision.action in (DecisionAction.REJECT, DecisionAction.ESCALATE)

    def test_final_round_veto_rejects(self) -> None:
        rnd = VotingRound(
            round_number=3,
            votes=[
                _vote(
                    AdvisorType.SECURITY,
                    VoteType.BLOCK,
                    0.9,
                    blockers=["Still blocked"],
                ),
                _vote(AdvisorType.CLARITY, VoteType.APPROVE, 0.8),
            ],
        )
        decision = synthesize_round(rnd, round_number=3, max_rounds=3)
        assert decision.action == DecisionAction.REJECT

    def test_conditions_collected(self) -> None:
        rnd = VotingRound(
            round_number=1,
            votes=[
                _vote(
                    AdvisorType.SECURITY,
                    VoteType.APPROVE_WITH_CONDITION,
                    0.9,
                    condition="Add rate limiting",
                ),
                _vote(AdvisorType.QUALITY, VoteType.APPROVE, 0.8),
                _vote(AdvisorType.PERFORMANCE, VoteType.APPROVE, 0.7),
                _vote(AdvisorType.MARKET, VoteType.APPROVE, 0.85),
                _vote(AdvisorType.MATURITY, VoteType.APPROVE, 0.75),
                _vote(AdvisorType.CLARITY, VoteType.APPROVE, 0.8),
            ],
        )
        decision = synthesize_round(rnd, round_number=1, max_rounds=3)
        assert decision.action == DecisionAction.APPROVE_WITH_CONDITIONS
        assert "Add rate limiting" in decision.conditions

    def test_abstain_votes_excluded_from_consensus(self) -> None:
        rnd = VotingRound(
            round_number=1,
            votes=[
                _vote(AdvisorType.SECURITY, VoteType.APPROVE, 0.9),
                _vote(AdvisorType.QUALITY, VoteType.ABSTAIN, 0.3),
                _vote(AdvisorType.PERFORMANCE, VoteType.ABSTAIN, 0.2),
                _vote(AdvisorType.MARKET, VoteType.APPROVE, 0.85),
                _vote(AdvisorType.MATURITY, VoteType.ABSTAIN, 0.1),
                _vote(AdvisorType.CLARITY, VoteType.APPROVE, 0.8),
            ],
        )
        decision = synthesize_round(rnd, round_number=1, max_rounds=3)
        assert decision.action == DecisionAction.APPROVE
