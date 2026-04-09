"""Monarch synthesis — deterministic decision-making from advisor votes."""

from __future__ import annotations

from council.enums import DecisionAction, VoteType
from council.models import CouncilDecision, VotingRound


def synthesize_round(
    voting_round: VotingRound,
    round_number: int,
    max_rounds: int,
) -> CouncilDecision:
    """Synthesize a decision from a voting round's results.

    Rules:
    1. Veto (Security/Clarity BLOCK) -> reject on final round, reject earlier
    2. All approve/approve_with_condition/abstain -> approve (with conditions)
    3. Mixed votes without veto -> approve if majority positive by confidence
    """
    if voting_round.has_veto:
        return _handle_veto(voting_round, round_number, max_rounds)

    return _handle_no_veto(voting_round)


def _handle_veto(
    voting_round: VotingRound,
    round_number: int,
    max_rounds: int,
) -> CouncilDecision:
    veto_advisors = voting_round.veto_advisors
    veto_votes = [v for v in voting_round.votes if v.is_veto]
    all_blockers: list[str] = []
    for v in veto_votes:
        all_blockers.extend(v.blockers)

    flagged_mvis: list[dict[str, str]] = []
    for v in veto_votes:
        for blocker in v.blockers:
            flagged_mvis.append(
                {
                    "advisor": v.advisor.value,
                    "concern": blocker,
                }
            )

    dissent = {
        v.advisor.value: v.reasoning
        for v in voting_round.votes
        if v.vote in (VoteType.APPROVE, VoteType.APPROVE_WITH_CONDITION)
    }

    advisor_names = ", ".join(a.value for a in veto_advisors)
    blocker_text = "; ".join(all_blockers)

    if round_number >= max_rounds:
        return CouncilDecision(
            action=DecisionAction.REJECT,
            reasoning=(
                f"Veto by {advisor_names} after {round_number} rounds: {blocker_text}"
            ),
            confidence=max(v.confidence for v in veto_votes),
            flagged_mvis=flagged_mvis,
            dissent_record=dissent,
        )

    return CouncilDecision(
        action=DecisionAction.REJECT,
        reasoning=f"Veto by {advisor_names}: {blocker_text}",
        confidence=max(v.confidence for v in veto_votes),
        flagged_mvis=flagged_mvis,
        dissent_record=dissent,
    )


def _handle_no_veto(voting_round: VotingRound) -> CouncilDecision:
    non_abstain = [v for v in voting_round.votes if v.vote != VoteType.ABSTAIN]
    if not non_abstain:
        return CouncilDecision(
            action=DecisionAction.ESCALATE,
            reasoning="All advisors abstained — insufficient context",
            confidence=0.0,
        )

    conditions = [v.condition for v in non_abstain if v.condition]

    approvals = [
        v
        for v in non_abstain
        if v.vote in (VoteType.APPROVE, VoteType.APPROVE_WITH_CONDITION)
    ]

    dissent = {
        v.advisor.value: v.reasoning
        for v in non_abstain
        if v.vote == VoteType.BLOCK
    }

    avg_confidence = (
        sum(v.confidence for v in approvals) / len(approvals) if approvals else 0.0
    )

    if len(approvals) == len(non_abstain):
        action = (
            DecisionAction.APPROVE_WITH_CONDITIONS
            if conditions
            else DecisionAction.APPROVE
        )
        return CouncilDecision(
            action=action,
            reasoning=(
                "Consensus reached"
                + (f" with {len(conditions)} condition(s)" if conditions else "")
            ),
            confidence=avg_confidence,
            conditions=conditions,
            dissent_record=dissent,
        )

    # Majority by confidence-weighted scoring
    weighted_approve = sum(v.confidence for v in approvals)
    weighted_total = sum(v.confidence for v in non_abstain)
    approval_ratio = weighted_approve / weighted_total if weighted_total > 0 else 0

    if approval_ratio >= 0.6:
        action = (
            DecisionAction.APPROVE_WITH_CONDITIONS
            if conditions
            else DecisionAction.APPROVE
        )
        return CouncilDecision(
            action=action,
            reasoning=(
                f"Majority approval ({approval_ratio:.0%} confidence-weighted)"
            ),
            confidence=avg_confidence,
            conditions=conditions,
            dissent_record=dissent,
        )

    return CouncilDecision(
        action=DecisionAction.ESCALATE,
        reasoning=(
            f"No clear majority ({approval_ratio:.0%} approval by confidence)"
        ),
        confidence=avg_confidence,
        dissent_record=dissent,
    )
