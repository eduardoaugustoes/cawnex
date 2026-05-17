"""Tests for post-session reflection — learning extraction."""

from council.enums import AdvisorType, CouncilStatus, DecisionAction, VoteType
from council.models import AdvisorVote, CouncilDecision, VotingRound
from council.orchestrator import CouncilSessionResult
from council.reflection import extract_learnings


def _vote(
    advisor: AdvisorType,
    vote: VoteType,
    confidence: float = 0.8,
    blockers: list[str] | None = None,
    condition: str = "",
    reasoning: str = "",
) -> AdvisorVote:
    return AdvisorVote(
        advisor=advisor,
        vote=vote,
        scores={},
        reasoning=reasoning or f"{advisor.value} {vote.value}",
        confidence=confidence,
        blockers=blockers or [],
        condition=condition,
    )


class TestExtractLearnings:
    def test_consensus_no_learnings_for_simple_approve(self) -> None:
        result = CouncilSessionResult(
            rounds=[
                VotingRound(
                    round_number=1,
                    votes=[
                        _vote(AdvisorType.SECURITY, VoteType.APPROVE, 0.7),
                        _vote(AdvisorType.ARCHITECTURE, VoteType.APPROVE, 0.6),
                    ],
                )
            ],
            decision=CouncilDecision(
                action=DecisionAction.APPROVE,
                reasoning="Consensus",
                confidence=0.65,
            ),
            status=CouncilStatus.COMPLETED,
        )

        learnings = extract_learnings(result)

        # Low confidence approvals don't generate learnings
        assert len(learnings) == 0

    def test_veto_resolved_generates_learning(self) -> None:
        result = CouncilSessionResult(
            rounds=[
                VotingRound(
                    round_number=1,
                    votes=[
                        _vote(
                            AdvisorType.SECURITY,
                            VoteType.BLOCK,
                            0.9,
                            blockers=["No rate limiting"],
                        ),
                        _vote(AdvisorType.ARCHITECTURE, VoteType.APPROVE, 0.8),
                    ],
                ),
                VotingRound(
                    round_number=2,
                    votes=[
                        _vote(
                            AdvisorType.SECURITY,
                            VoteType.APPROVE_WITH_CONDITION,
                            0.78,
                            condition="Rate limiting must ship first",
                        ),
                    ],
                ),
            ],
            decision=CouncilDecision(
                action=DecisionAction.APPROVE_WITH_CONDITIONS,
                reasoning="Resolved",
                confidence=0.78,
                conditions=["Rate limiting must ship first"],
            ),
            status=CouncilStatus.COMPLETED,
        )

        learnings = extract_learnings(result)

        assert AdvisorType.SECURITY in learnings
        sec_learnings = learnings[AdvisorType.SECURITY]
        assert any("constraint" in l.lower() or "resolved" in l.lower() for l in sec_learnings)

    def test_veto_held_through_rejection(self) -> None:
        result = CouncilSessionResult(
            rounds=[
                VotingRound(
                    round_number=1,
                    votes=[
                        _vote(
                            AdvisorType.SECURITY,
                            VoteType.BLOCK,
                            0.9,
                            blockers=["Critical vulnerability"],
                        ),
                    ],
                ),
                VotingRound(
                    round_number=2,
                    votes=[
                        _vote(
                            AdvisorType.SECURITY,
                            VoteType.BLOCK,
                            0.95,
                            blockers=["Still critical"],
                        ),
                    ],
                ),
            ],
            decision=CouncilDecision(
                action=DecisionAction.REJECT,
                reasoning="Security veto held",
                confidence=0.95,
            ),
            status=CouncilStatus.COMPLETED,
        )

        learnings = extract_learnings(result)

        assert AdvisorType.SECURITY in learnings
        assert any("validated" in l.lower() or "confirmed" in l.lower() for l in learnings[AdvisorType.SECURITY])

    def test_dissent_overridden(self) -> None:
        result = CouncilSessionResult(
            rounds=[
                VotingRound(
                    round_number=1,
                    votes=[
                        _vote(
                            AdvisorType.ARCHITECTURE,
                            VoteType.BLOCK,
                            0.7,
                            reasoning="Test coverage too low",
                        ),
                        _vote(AdvisorType.SECURITY, VoteType.APPROVE, 0.9),
                        _vote(AdvisorType.COST, VoteType.APPROVE, 0.85),
                        _vote(AdvisorType.PERFORMANCE, VoteType.APPROVE, 0.8),
                        _vote(AdvisorType.UX, VoteType.APPROVE, 0.75),
                        _vote(AdvisorType.CLARITY, VoteType.APPROVE, 0.8),
                    ],
                )
            ],
            decision=CouncilDecision(
                action=DecisionAction.APPROVE,
                reasoning="Majority approved",
                confidence=0.82,
            ),
            status=CouncilStatus.COMPLETED,
        )

        learnings = extract_learnings(result)

        # Quality blocked but was overridden — should learn this
        assert AdvisorType.ARCHITECTURE in learnings
        assert any("overridden" in l.lower() for l in learnings[AdvisorType.ARCHITECTURE])

    def test_max_three_learnings_per_advisor(self) -> None:
        # Edge case: advisor has many triggers — should cap at 3
        result = CouncilSessionResult(
            rounds=[
                VotingRound(
                    round_number=1,
                    votes=[
                        _vote(
                            AdvisorType.SECURITY,
                            VoteType.BLOCK,
                            0.9,
                            blockers=["Issue 1"],
                            condition="Cond 1",
                            reasoning="Long reasoning",
                        ),
                    ],
                ),
                VotingRound(
                    round_number=2,
                    votes=[
                        _vote(
                            AdvisorType.SECURITY,
                            VoteType.APPROVE_WITH_CONDITION,
                            0.85,
                            condition="Cond 2",
                        ),
                    ],
                ),
            ],
            decision=CouncilDecision(
                action=DecisionAction.APPROVE_WITH_CONDITIONS,
                reasoning="Resolved",
                confidence=0.85,
                conditions=["Cond 2"],
            ),
            status=CouncilStatus.COMPLETED,
        )

        learnings = extract_learnings(result)

        if AdvisorType.SECURITY in learnings:
            assert len(learnings[AdvisorType.SECURITY]) <= 3

    def test_empty_rounds_returns_empty(self) -> None:
        result = CouncilSessionResult(
            rounds=[],
            decision=CouncilDecision(
                action=DecisionAction.ESCALATE,
                reasoning="No data",
                confidence=0.0,
            ),
            status=CouncilStatus.COMPLETED,
        )

        learnings = extract_learnings(result)
        assert learnings == {}
