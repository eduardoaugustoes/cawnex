"""Council orchestrator — manages voting rounds and round limits."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from council.advisors import run_all_advisors
from council.config import MAX_ROUNDS
from council.enums import AdvisorType, CouncilStatus, DecisionAction, VoteType
from council.models import CouncilDecision, VotingRound
from council.synthesis import synthesize_round


@dataclass
class CouncilSessionResult:
    rounds: list[VotingRound]
    decision: CouncilDecision
    status: CouncilStatus

    def to_dict(self) -> dict[str, Any]:
        return {
            "rounds": [r.to_dict() for r in self.rounds],
            "decision": self.decision.to_dict(),
            "status": self.status.value,
        }


def run_council_session(
    decision_context: dict[str, Any],
    max_rounds: int = MAX_ROUNDS,
    advisor_memories: dict[str, str] | None = None,
    org_standards: str = "",
    project_context: str = "",
) -> CouncilSessionResult:
    """Run a full council session with up to max_rounds of voting."""
    rounds: list[VotingRound] = []

    # Round 1: all advisors, independent assessment
    votes = run_all_advisors(
        decision_context,
        advisor_memories=advisor_memories,
        org_standards=org_standards,
        project_context=project_context,
    )
    round_1 = VotingRound(round_number=1, votes=votes)
    rounds.append(round_1)

    decision = synthesize_round(round_1, round_number=1, max_rounds=max_rounds)

    if decision.action in (
        DecisionAction.APPROVE,
        DecisionAction.APPROVE_WITH_CONDITIONS,
    ):
        return CouncilSessionResult(
            rounds=rounds,
            decision=decision,
            status=CouncilStatus.COMPLETED,
        )

    # Debate rounds (2+): only disagreeing advisors, with full transparency
    for round_num in range(2, max_rounds + 1):
        disagreeing = _get_disagreeing_advisors(rounds[-1])
        if not disagreeing:
            break

        debate_context = {
            **decision_context,
            "previous_rounds": [r.to_dict() for r in rounds],
            "synthesis": decision.to_dict(),
            "specific_question": (
                f"Round {round_num}: Can the concerns be resolved with constraints?"
            ),
        }

        debate_votes = run_all_advisors(
            debate_context,
            advisors=disagreeing,
            advisor_memories=advisor_memories,
            org_standards=org_standards,
            project_context=project_context,
        )
        debate_round = VotingRound(
            round_number=round_num,
            votes=debate_votes,
            question=f"Round {round_num} debate",
        )
        rounds.append(debate_round)

        decision = synthesize_round(
            debate_round, round_number=round_num, max_rounds=max_rounds
        )

        if decision.action in (
            DecisionAction.APPROVE,
            DecisionAction.APPROVE_WITH_CONDITIONS,
        ):
            return CouncilSessionResult(
                rounds=rounds,
                decision=decision,
                status=CouncilStatus.COMPLETED,
            )

    return CouncilSessionResult(
        rounds=rounds,
        decision=decision,
        status=CouncilStatus.COMPLETED,
    )


def _get_disagreeing_advisors(voting_round: VotingRound) -> list[AdvisorType]:
    """Return advisors who blocked or had strong disagreements."""
    return [v.advisor for v in voting_round.votes if v.vote == VoteType.BLOCK]
