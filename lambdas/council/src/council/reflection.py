"""Post-session reflection — extract learnings from council votes.

Deterministic extraction (no LLM needed): analyzes vote patterns,
veto resolutions, and disagreements to produce learnings per advisor.
"""

from __future__ import annotations

from council.enums import AdvisorType, DecisionAction, VoteType
from council.models import AdvisorVote, VotingRound
from council.orchestrator import CouncilSessionResult


def extract_learnings(
    result: CouncilSessionResult,
) -> dict[AdvisorType, list[str]]:
    """Extract 0-3 learnings per advisor from a completed council session.

    Learnings are generated from:
    1. Vetoes that were resolved (advisor changed vote after debate)
    2. Vetoes that held (advisor's concern validated by final rejection)
    3. High-confidence advisors whose vote aligned with the final decision
    4. Dissent that was overridden (learning about what the project prioritizes)
    """
    learnings: dict[AdvisorType, list[str]] = {}

    if len(result.rounds) == 0:
        return learnings

    # Track vote changes across rounds
    vote_history = _build_vote_history(result.rounds)
    final_action = result.decision.action

    for advisor, history in vote_history.items():
        advisor_learnings: list[str] = []

        # Learning 1: Veto that was resolved via debate
        if _changed_from_block(history):
            last_vote = history[-1]
            if last_vote.condition:
                advisor_learnings.append(
                    f"Veto resolved with constraint: {last_vote.condition}"
                )
            else:
                advisor_learnings.append(
                    "Initial block resolved after debate — concern was addressed"
                )

        # Learning 2: Veto that held through to rejection
        if _held_block(history) and final_action == DecisionAction.REJECT:
            first_vote = history[0]
            blockers = "; ".join(first_vote.blockers) if first_vote.blockers else first_vote.reasoning
            advisor_learnings.append(
                f"Block validated — rejection confirmed: {blockers[:100]}"
            )

        # Learning 3: High-confidence approval that aligned with final decision
        if (
            final_action
            in (DecisionAction.APPROVE, DecisionAction.APPROVE_WITH_CONDITIONS)
            and history[-1].vote
            in (VoteType.APPROVE, VoteType.APPROVE_WITH_CONDITION)
            and history[-1].confidence >= 0.8
        ):
            if history[-1].condition:
                advisor_learnings.append(
                    f"Condition accepted: {history[-1].condition[:100]}"
                )

        # Learning 4: Dissent overridden
        if (
            history[-1].vote == VoteType.BLOCK
            and final_action
            in (DecisionAction.APPROVE, DecisionAction.APPROVE_WITH_CONDITIONS)
        ):
            advisor_learnings.append(
                f"Block overridden by majority — project prioritized shipping: {history[-1].reasoning[:100]}"
            )

        # Cap at 3 learnings per advisor
        if advisor_learnings:
            learnings[advisor] = advisor_learnings[:3]

    return learnings


def _build_vote_history(
    rounds: list[VotingRound],
) -> dict[AdvisorType, list[AdvisorVote]]:
    """Build a per-advisor history of votes across rounds."""
    history: dict[AdvisorType, list[AdvisorVote]] = {}
    for rnd in rounds:
        for vote in rnd.votes:
            history.setdefault(vote.advisor, []).append(vote)
    return history


def _changed_from_block(history: list[AdvisorVote]) -> bool:
    """Did this advisor start with BLOCK and later change?"""
    if len(history) < 2:
        return False
    return (
        history[0].vote == VoteType.BLOCK
        and history[-1].vote != VoteType.BLOCK
    )


def _held_block(history: list[AdvisorVote]) -> bool:
    """Did this advisor BLOCK and maintain it through all rounds?"""
    return all(v.vote == VoteType.BLOCK for v in history)
