"""Human override processing for supervised mode.

Overrides allow the founder to intervene when the council escalates:
- override_block: Override a veto advisor's block
- request_round: Trigger a targeted debate round with a specific question
- add_constraint: Approve with an additional constraint
- dismiss_advisor: Remove an advisor's vote from consideration
- force_decision: Skip council entirely, provide the wave plan directly
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from council._blackboard import Blackboard
from council.actions import execute_decision, execute_planning_decision
from council.enums import AdvisorType, DecisionAction, VoteType
from council.models import AdvisorCost, AdvisorVote, CouncilDecision, VotingRound
from council.synthesis import synthesize_round


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dynamo_safe(obj: Any) -> Any:
    """Convert floats to Decimal for DynamoDB compatibility."""
    return json.loads(json.dumps(obj), parse_float=Decimal)


@dataclass
class HumanOverride:
    action: str  # override_block, request_round, add_constraint, dismiss_advisor, force_decision
    reason: str
    advisor_overridden: str = ""
    constraint: str = ""
    question: str = ""
    wave_plan: list[str] | None = None
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = _now_iso()

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "action": self.action,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }
        if self.advisor_overridden:
            d["advisor_overridden"] = self.advisor_overridden
        if self.constraint:
            d["constraint"] = self.constraint
        if self.question:
            d["question"] = self.question
        if self.wave_plan:
            d["wave_plan"] = self.wave_plan
        return d


def apply_override(
    blackboard: Blackboard,
    pk: str,
    session_sk: str,
    wave_id: str,
    override: HumanOverride,
    session_type: str = "wave_review",
    context: dict[str, Any] | None = None,
) -> CouncilDecision:
    """Apply a human override to a council session and return the resulting decision.

    Reads the existing session, applies the override, saves the override record,
    and returns the decision to be executed.
    """
    session = blackboard.read(pk, session_sk)
    if not session:
        raise ValueError(f"Council session not found: {session_sk}")

    existing_rounds = session.get("rounds", [])

    if override.action == "force_decision":
        decision = _apply_force_decision(override)
    elif override.action == "override_block":
        decision = _apply_override_block(override, existing_rounds)
    elif override.action == "add_constraint":
        decision = _apply_add_constraint(override, existing_rounds)
    elif override.action == "dismiss_advisor":
        decision = _apply_dismiss_advisor(override, existing_rounds)
    elif override.action == "request_round":
        # request_round doesn't produce a decision — it's handled separately
        # by writing a new council task with the question
        decision = CouncilDecision(
            action=DecisionAction.ESCALATE,
            reasoning=f"Human requested additional round: {override.question}",
            confidence=0.0,
        )
    else:
        raise ValueError(f"Unknown override action: {override.action}")

    # Save override record on the session
    overrides = session.get("human_overrides", [])
    overrides.append(override.to_dict())
    blackboard.update(
        pk,
        session_sk,
        {
            "human_overrides": overrides,
            "decision": _dynamo_safe(decision.to_dict()),
            "override_applied_at": _now_iso(),
        },
    )

    return decision


def _apply_force_decision(override: HumanOverride) -> CouncilDecision:
    """Human provides the wave plan directly, bypassing council."""
    return CouncilDecision(
        action=DecisionAction.APPROVE,
        reasoning=f"Human override (force_decision): {override.reason}",
        confidence=1.0,
        wave_plan=override.wave_plan or [],
    )


def _apply_override_block(
    override: HumanOverride,
    existing_rounds: list[dict[str, Any]],
) -> CouncilDecision:
    """Override a specific advisor's BLOCK vote — re-synthesize without it."""
    advisor_name = override.advisor_overridden.lower()

    # Rebuild the last round's votes, changing the blocked advisor to APPROVE
    if not existing_rounds:
        return CouncilDecision(
            action=DecisionAction.APPROVE,
            reasoning=f"Human override (override_block): {override.reason}",
            confidence=1.0,
        )

    last_round = existing_rounds[-1]
    rebuilt_votes: list[AdvisorVote] = []
    for vote_dict in last_round.get("votes", []):
        advisor_str = vote_dict.get("advisor", "")
        try:
            advisor = AdvisorType(advisor_str)
        except ValueError:
            continue

        if advisor_str == advisor_name and vote_dict.get("vote") == "block":
            # Override the block to approve_with_condition
            rebuilt_votes.append(
                AdvisorVote(
                    advisor=advisor,
                    vote=VoteType.APPROVE_WITH_CONDITION,
                    scores=vote_dict.get("scores", {}),
                    reasoning=f"OVERRIDDEN by human: {override.reason}",
                    confidence=float(vote_dict.get("confidence", 0.5)),
                    condition=f"Human accepted risk: {override.reason}",
                )
            )
        else:
            rebuilt_votes.append(
                AdvisorVote(
                    advisor=advisor,
                    vote=VoteType(vote_dict.get("vote", "abstain")),
                    scores=vote_dict.get("scores", {}),
                    reasoning=vote_dict.get("reasoning", ""),
                    confidence=float(vote_dict.get("confidence", 0.5)),
                    blockers=vote_dict.get("blockers", []),
                    condition=vote_dict.get("condition", ""),
                )
            )

    if not rebuilt_votes:
        return CouncilDecision(
            action=DecisionAction.APPROVE,
            reasoning=f"Human override (override_block): {override.reason}",
            confidence=1.0,
        )

    rebuilt_round = VotingRound(
        round_number=last_round.get("round", 1) + 1,
        votes=rebuilt_votes,
    )
    return synthesize_round(rebuilt_round, round_number=99, max_rounds=99)


def _apply_add_constraint(
    override: HumanOverride,
    existing_rounds: list[dict[str, Any]],
) -> CouncilDecision:
    """Approve with an additional human-specified constraint."""
    return CouncilDecision(
        action=DecisionAction.APPROVE_WITH_CONDITIONS,
        reasoning=f"Human override (add_constraint): {override.reason}",
        confidence=1.0,
        conditions=[override.constraint],
    )


def _apply_dismiss_advisor(
    override: HumanOverride,
    existing_rounds: list[dict[str, Any]],
) -> CouncilDecision:
    """Remove an advisor's vote and re-synthesize."""
    advisor_name = override.advisor_overridden.lower()

    if not existing_rounds:
        return CouncilDecision(
            action=DecisionAction.APPROVE,
            reasoning=f"Human override (dismiss_advisor): {override.reason}",
            confidence=1.0,
        )

    last_round = existing_rounds[-1]
    filtered_votes: list[AdvisorVote] = []
    for vote_dict in last_round.get("votes", []):
        if vote_dict.get("advisor") == advisor_name:
            continue  # dismissed
        try:
            advisor = AdvisorType(vote_dict.get("advisor", ""))
        except ValueError:
            continue
        filtered_votes.append(
            AdvisorVote(
                advisor=advisor,
                vote=VoteType(vote_dict.get("vote", "abstain")),
                scores=vote_dict.get("scores", {}),
                reasoning=vote_dict.get("reasoning", ""),
                confidence=float(vote_dict.get("confidence", 0.5)),
                blockers=vote_dict.get("blockers", []),
                condition=vote_dict.get("condition", ""),
            )
        )

    if not filtered_votes:
        return CouncilDecision(
            action=DecisionAction.APPROVE,
            reasoning=f"Human override (dismiss_advisor): all advisors dismissed",
            confidence=1.0,
        )

    rebuilt_round = VotingRound(
        round_number=last_round.get("round", 1) + 1,
        votes=filtered_votes,
    )
    return synthesize_round(rebuilt_round, round_number=99, max_rounds=99)
