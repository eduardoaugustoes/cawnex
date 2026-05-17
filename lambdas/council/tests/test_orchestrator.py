"""Tests for the council orchestrator — round management."""

from unittest.mock import MagicMock, patch

from council.enums import AdvisorType, DecisionAction, VoteType
from council.models import AdvisorVote
from council.orchestrator import run_council_session


def _make_approve_vote(advisor: AdvisorType) -> AdvisorVote:
    return AdvisorVote(
        advisor=advisor,
        vote=VoteType.APPROVE,
        scores={},
        reasoning="Looks good",
        confidence=0.8,
    )


def _make_all_approve() -> list[AdvisorVote]:
    return [_make_approve_vote(a) for a in AdvisorType]


class TestRunCouncilSession:
    @patch("council.orchestrator.run_all_advisors")
    def test_consensus_in_round_1(self, mock_run: MagicMock) -> None:
        mock_run.return_value = _make_all_approve()

        result = run_council_session(
            decision_context={"ask": "Review wave"},
        )

        assert result.decision.action == DecisionAction.APPROVE
        assert len(result.rounds) == 1
        mock_run.assert_called_once()

    @patch("council.orchestrator.run_all_advisors")
    def test_veto_in_round_1_triggers_round_2(self, mock_run: MagicMock) -> None:
        veto_votes = _make_all_approve()
        veto_votes[0] = AdvisorVote(
            advisor=AdvisorType.SECURITY,
            vote=VoteType.BLOCK,
            scores={},
            reasoning="No rate limiting",
            confidence=0.9,
            blockers=["No rate limiting"],
        )

        resolved_votes = [
            AdvisorVote(
                advisor=AdvisorType.SECURITY,
                vote=VoteType.APPROVE_WITH_CONDITION,
                scores={},
                reasoning="Resolved with constraint",
                confidence=0.78,
                condition="Rate limiting first",
                changed_from="block",
            ),
        ]
        mock_run.side_effect = [veto_votes, resolved_votes]

        result = run_council_session(
            decision_context={"ask": "Review wave"},
        )

        assert len(result.rounds) == 2
        assert mock_run.call_count == 2

    @patch("council.orchestrator.run_all_advisors")
    def test_max_3_rounds(self, mock_run: MagicMock) -> None:
        veto_votes = _make_all_approve()
        veto_votes[0] = AdvisorVote(
            advisor=AdvisorType.SECURITY,
            vote=VoteType.BLOCK,
            scores={},
            reasoning="Still blocked",
            confidence=0.9,
            blockers=["Still blocked"],
        )
        mock_run.side_effect = [veto_votes, [veto_votes[0]], [veto_votes[0]]]

        result = run_council_session(
            decision_context={"ask": "Review wave"},
        )

        assert len(result.rounds) <= 3
        assert result.decision.action == DecisionAction.REJECT


# --- Async orchestrator tests ---

import pytest as _pytest
from unittest.mock import patch as _patch

from council.orchestrator import run_council_session_async


@_pytest.mark.asyncio
async def test_run_council_session_async_calls_all_6_advisors_in_parallel() -> None:
    from council.models import AdvisorVote as _AdvisorVote
    from council.enums import AdvisorType as _AdvisorType, VoteType as _VoteType

    async def fake_advisor(advisor, packet, context):  # type: ignore[no-untyped-def]
        return _AdvisorVote(
            advisor=advisor,
            vote=_VoteType.APPROVE,
            scores={},
            reasoning="ok",
            confidence=0.8,
        )

    with _patch("council.orchestrator.run_advisor", side_effect=fake_advisor):
        result = await run_council_session_async(
            packet={"wave_id": "w1"},
            context={
                "repo_path": "/r",
                "worktree_paths": {},
                "integration_path": "/i",
                "repo": "org/r",
                "github_token": "t",
            },
        )

    assert len(result.rounds[0].votes) == 6
