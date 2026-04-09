"""Tests for advisor prompt building and response parsing."""

import json

from council.advisors import build_advisor_prompt, parse_advisor_response
from council.enums import AdvisorType, VoteType


class TestBuildAdvisorPrompt:
    def test_includes_advisor_identity(self) -> None:
        prompt = build_advisor_prompt(
            AdvisorType.SECURITY,
            decision_context={"ask": "Review wave output"},
        )
        assert "Security Advisor" in prompt["system"]

    def test_includes_decision_context(self) -> None:
        prompt = build_advisor_prompt(
            AdvisorType.QUALITY,
            decision_context={"ask": "Review wave", "mvis": ["mvi_01"]},
        )
        assert "mvi_01" in prompt["user"]


class TestParseAdvisorResponse:
    def test_valid_json_response(self) -> None:
        raw = json.dumps(
            {
                "vote": "approve",
                "scores": {"mvi_01": 8},
                "reasoning": "Looks good",
                "confidence": 0.85,
            }
        )
        vote = parse_advisor_response(AdvisorType.SECURITY, raw)
        assert vote.advisor == AdvisorType.SECURITY
        assert vote.vote == VoteType.APPROVE
        assert vote.confidence == 0.85

    def test_block_with_blockers(self) -> None:
        raw = json.dumps(
            {
                "vote": "block",
                "scores": {"mvi_01": 2},
                "reasoning": "No rate limiting",
                "confidence": 0.9,
                "blockers": ["No rate limiting on auth"],
            }
        )
        vote = parse_advisor_response(AdvisorType.SECURITY, raw)
        assert vote.vote == VoteType.BLOCK
        assert len(vote.blockers) == 1

    def test_malformed_json_returns_abstain(self) -> None:
        vote = parse_advisor_response(AdvisorType.QUALITY, "not json at all")
        assert vote.vote == VoteType.ABSTAIN
        assert vote.confidence == 0.0
