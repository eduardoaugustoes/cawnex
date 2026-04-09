"""Tests for council data models."""

from council.enums import AdvisorType, DecisionAction, VoteType
from council.models import AdvisorCost, AdvisorVote, CouncilDecision, VotingRound


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


class TestAdvisorCost:
    def test_zero(self) -> None:
        cost = AdvisorCost.zero()
        assert cost.tokens_in == 0
        assert cost.tokens_out == 0
        assert cost.total_tokens == 0

    def test_addition(self) -> None:
        a = AdvisorCost(tokens_in=100, tokens_out=50, duration_ms=200)
        b = AdvisorCost(tokens_in=200, tokens_out=100, duration_ms=300)
        c = a + b
        assert c.tokens_in == 300
        assert c.tokens_out == 150
        assert c.duration_ms == 500

    def test_to_dict(self) -> None:
        cost = AdvisorCost(tokens_in=1000, tokens_out=500, duration_ms=350)
        d = cost.to_dict()
        assert d == {"tokens_in": 1000, "tokens_out": 500, "duration_ms": 350}

    def test_total_tokens(self) -> None:
        cost = AdvisorCost(tokens_in=800, tokens_out=200, duration_ms=100)
        assert cost.total_tokens == 1000


class TestVoteCostIntegration:
    def test_vote_includes_cost_in_dict(self) -> None:
        vote = AdvisorVote(
            advisor=AdvisorType.SECURITY,
            vote=VoteType.APPROVE,
            scores={},
            reasoning="OK",
            confidence=0.9,
            cost=AdvisorCost(tokens_in=500, tokens_out=200, duration_ms=150),
        )
        d = vote.to_dict()
        assert "cost" in d
        assert d["cost"]["tokens_in"] == 500

    def test_vote_omits_cost_when_zero(self) -> None:
        vote = AdvisorVote(
            advisor=AdvisorType.QUALITY,
            vote=VoteType.APPROVE,
            scores={},
            reasoning="OK",
            confidence=0.8,
        )
        d = vote.to_dict()
        assert "cost" not in d

    def test_round_aggregates_cost(self) -> None:
        votes = [
            AdvisorVote(
                advisor=AdvisorType.SECURITY,
                vote=VoteType.APPROVE,
                scores={},
                reasoning="OK",
                confidence=0.9,
                cost=AdvisorCost(tokens_in=500, tokens_out=200, duration_ms=150),
            ),
            AdvisorVote(
                advisor=AdvisorType.QUALITY,
                vote=VoteType.APPROVE,
                scores={},
                reasoning="OK",
                confidence=0.8,
                cost=AdvisorCost(tokens_in=600, tokens_out=300, duration_ms=200),
            ),
        ]
        rnd = VotingRound(round_number=1, votes=votes)
        total = rnd.total_cost
        assert total.tokens_in == 1100
        assert total.tokens_out == 500
        assert total.duration_ms == 350

    def test_round_dict_includes_cost(self) -> None:
        votes = [
            AdvisorVote(
                advisor=AdvisorType.SECURITY,
                vote=VoteType.APPROVE,
                scores={},
                reasoning="OK",
                confidence=0.9,
                cost=AdvisorCost(tokens_in=500, tokens_out=200, duration_ms=150),
            ),
        ]
        rnd = VotingRound(round_number=1, votes=votes)
        d = rnd.to_dict()
        assert "cost" in d
        assert d["cost"]["tokens_in"] == 500


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
