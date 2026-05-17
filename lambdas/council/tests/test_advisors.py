"""Tests for advisor prompt building and response parsing."""

import json

from council.advisors_legacy import build_advisor_prompt, parse_advisor_response
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
            AdvisorType.ARCHITECTURE,
            decision_context={"ask": "Review wave", "mvis": ["mvi_01"]},
        )
        assert "mvi_01" in prompt["user"]

    def test_includes_advisor_memory_in_system(self) -> None:
        prompt = build_advisor_prompt(
            AdvisorType.SECURITY,
            decision_context={"ask": "Review wave"},
            advisor_memory="- Auth endpoints need rate limiting\n- CORS must be explicit",
        )
        assert "Your Memory" in prompt["system"]
        assert "rate limiting" in prompt["system"]
        assert "CORS" in prompt["system"]

    def test_no_memory_section_when_empty(self) -> None:
        prompt = build_advisor_prompt(
            AdvisorType.SECURITY,
            decision_context={"ask": "Review wave"},
            advisor_memory="",
        )
        assert "Your Memory" not in prompt["system"]

    def test_full_5_layer_prompt(self) -> None:
        prompt = build_advisor_prompt(
            AdvisorType.SECURITY,
            decision_context={"ask": "Review wave"},
            advisor_memory="- Rate limiting learned from Wave 3",
            org_standards="All APIs must use JWT auth. No wildcard CORS.",
            project_context="## Conventions\nFastAPI + DynamoDB\n\n## Wave Reflections\n- Wave w01 shipped",
        )
        system = prompt["system"]
        # Layer 1: identity
        assert "Security Advisor" in system
        # Layer 2: org standards
        assert "Organization Standards" in system
        assert "JWT auth" in system
        # Layer 3: project context
        assert "Project Context" in system
        assert "FastAPI" in system
        # Layer 4: advisor memory
        assert "Your Memory" in system
        assert "Rate limiting" in system
        # Verify ordering: Layer 1 before 2 before 3 before 4
        idx_identity = system.index("Security Advisor")
        idx_org = system.index("Organization Standards")
        idx_project = system.index("Project Context")
        idx_memory = system.index("Your Memory")
        assert idx_identity < idx_org < idx_project < idx_memory

    def test_layers_omitted_when_empty(self) -> None:
        prompt = build_advisor_prompt(
            AdvisorType.ARCHITECTURE,
            decision_context={"ask": "Review"},
            advisor_memory="",
            org_standards="",
            project_context="",
        )
        system = prompt["system"]
        assert "Organization Standards" not in system
        assert "Project Context" not in system
        assert "Your Memory" not in system


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
        vote = parse_advisor_response(AdvisorType.ARCHITECTURE, "not json at all")
        assert vote.vote == VoteType.ABSTAIN
        assert vote.confidence == 0.0
