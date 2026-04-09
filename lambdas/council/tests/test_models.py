"""Tests for council data models."""

from council.enums import AdvisorType, DecisionAction, VoteType
from council.models import AdvisorVote, CouncilDecision, VotingRound


class TestAdvisorVote:
    def test_is_veto_security_block(self) -> None:
        vote = AdvisorVote(
            advisor=AdvisorType.SECURITY,
            vote=VoteType.BLOCK,
            scores={"mvi_01": 2},
            reasoning="No rate limiting",
            confidence=0.85,
            blockers=["No rate limiting on auth endpoint"],
        )
        assert vote.is_veto is True

    def test_is_not_veto_quality_block(self) -> None:
        vote = AdvisorVote(
            advisor=AdvisorType.QUALITY,
            vote=VoteType.BLOCK,
            scores={"mvi_01": 3},
            reasoning="Low test coverage",
            confidence=0.7,
        )
        assert vote.is_veto is False

    def test_is_not_veto_security_approve(self) -> None:
        vote = AdvisorVote(
            advisor=AdvisorType.SECURITY,
            vote=VoteType.APPROVE,
            scores={"mvi_01": 8},
            reasoning="Looks good",
            confidence=0.9,
        )
        assert vote.is_veto is False

    def test_to_dict_roundtrip(self) -> None:
        vote = AdvisorVote(
            advisor=AdvisorType.PERFORMANCE,
            vote=VoteType.APPROVE_WITH_CONDITION,
            scores={"mvi_01": 7},
            reasoning="Add index",
            confidence=0.75,
            condition="Must add DB index before shipping",
        )
        d = vote.to_dict()
        assert d["advisor"] == "performance"
        assert d["vote"] == "approve_with_condition"
        assert d["condition"] == "Must add DB index before shipping"


class TestVotingRound:
    def test_has_veto(self) -> None:
        votes = [
            AdvisorVote(
                advisor=AdvisorType.SECURITY,
                vote=VoteType.BLOCK,
                scores={},
                reasoning="Blocked",
                confidence=0.9,
                blockers=["Critical issue"],
            ),
            AdvisorVote(
                advisor=AdvisorType.QUALITY,
                vote=VoteType.APPROVE,
                scores={},
                reasoning="OK",
                confidence=0.8,
            ),
        ]
        rnd = VotingRound(round_number=1, votes=votes)
        assert rnd.has_veto is True
        assert rnd.veto_advisors == [AdvisorType.SECURITY]

    def test_consensus_all_approve(self) -> None:
        votes = [
            AdvisorVote(
                advisor=AdvisorType.SECURITY,
                vote=VoteType.APPROVE,
                scores={},
                reasoning="OK",
                confidence=0.9,
            ),
            AdvisorVote(
                advisor=AdvisorType.CLARITY,
                vote=VoteType.APPROVE,
                scores={},
                reasoning="Clear",
                confidence=0.85,
            ),
        ]
        rnd = VotingRound(round_number=1, votes=votes)
        assert rnd.has_veto is False
        assert rnd.consensus is True


class TestCouncilDecision:
    def test_to_dict(self) -> None:
        decision = CouncilDecision(
            action=DecisionAction.APPROVE,
            reasoning="All advisors agree",
            confidence=0.88,
            wave_plan=["mvi_01", "mvi_02"],
        )
        d = decision.to_dict()
        assert d["action"] == "approve"
        assert d["wave_plan"] == ["mvi_01", "mvi_02"]
