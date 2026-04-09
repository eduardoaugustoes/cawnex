"""Data models for council sessions, votes, and decisions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from council.enums import (
    AdvisorType,
    DecisionAction,
    VoteType,
    VETO_ADVISORS,
)


@dataclass
class AdvisorVote:
    advisor: AdvisorType
    vote: VoteType
    scores: dict[str, int]
    reasoning: str
    confidence: float
    blockers: list[str] = field(default_factory=list)
    condition: str = ""
    suggested_crows: list[str] = field(default_factory=list)
    changed_from: str = ""

    @property
    def is_veto(self) -> bool:
        return self.advisor in VETO_ADVISORS and self.vote == VoteType.BLOCK

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "advisor": self.advisor.value,
            "vote": self.vote.value,
            "scores": self.scores,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
        }
        if self.blockers:
            d["blockers"] = self.blockers
        if self.condition:
            d["condition"] = self.condition
        if self.suggested_crows:
            d["suggested_crows"] = self.suggested_crows
        if self.changed_from:
            d["changed_from"] = self.changed_from
        return d


@dataclass
class VotingRound:
    round_number: int
    votes: list[AdvisorVote]
    question: str = ""

    @property
    def has_veto(self) -> bool:
        return any(v.is_veto for v in self.votes)

    @property
    def veto_advisors(self) -> list[AdvisorType]:
        return [v.advisor for v in self.votes if v.is_veto]

    @property
    def consensus(self) -> bool:
        non_abstain = [v for v in self.votes if v.vote != VoteType.ABSTAIN]
        if not non_abstain:
            return False
        return all(
            v.vote in (VoteType.APPROVE, VoteType.APPROVE_WITH_CONDITION)
            for v in non_abstain
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "round": self.round_number,
            "votes": [v.to_dict() for v in self.votes],
            "consensus": self.consensus,
        }
        if self.question:
            d["question"] = self.question
        if self.has_veto:
            d["blocker"] = ",".join(a.value for a in self.veto_advisors)
        return d


@dataclass
class CouncilDecision:
    action: DecisionAction
    reasoning: str
    confidence: float
    wave_plan: list[str] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)
    flagged_mvis: list[dict[str, Any]] = field(default_factory=list)
    dissent_record: dict[str, str] = field(default_factory=dict)
    ordering_constraints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "action": self.action.value,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
        }
        if self.wave_plan:
            d["wave_plan"] = self.wave_plan
        if self.conditions:
            d["conditions"] = self.conditions
        if self.flagged_mvis:
            d["flagged_mvis"] = self.flagged_mvis
        if self.dissent_record:
            d["dissent_record"] = self.dissent_record
        if self.ordering_constraints:
            d["ordering_constraints"] = self.ordering_constraints
        return d
