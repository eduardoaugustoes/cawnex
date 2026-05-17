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
class ToolCall:
    tool_name: str
    args: dict[str, Any]
    result_summary: str
    duration_ms: int
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "tool_name": self.tool_name,
            "args": self.args,
            "result_summary": self.result_summary,
            "duration_ms": self.duration_ms,
        }
        if self.error:
            d["error"] = self.error
        return d


@dataclass
class CitedEvidence:
    file_path: str
    line_range: tuple[int, int] | None = None
    pr_number: int | None = None
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"file_path": self.file_path, "reason": self.reason}
        if self.line_range:
            d["line_range"] = list(self.line_range)
        if self.pr_number is not None:
            d["pr_number"] = self.pr_number
        return d


@dataclass
class AdvisorCost:
    tokens_in: int = 0
    tokens_out: int = 0
    duration_ms: int = 0

    @property
    def total_tokens(self) -> int:
        return self.tokens_in + self.tokens_out

    def __add__(self, other: AdvisorCost) -> AdvisorCost:
        return AdvisorCost(
            tokens_in=self.tokens_in + other.tokens_in,
            tokens_out=self.tokens_out + other.tokens_out,
            duration_ms=self.duration_ms + other.duration_ms,
        )

    def to_dict(self) -> dict[str, int]:
        return {
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "duration_ms": self.duration_ms,
        }

    @classmethod
    def zero(cls) -> AdvisorCost:
        return cls()


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
    cost: AdvisorCost = field(default_factory=AdvisorCost.zero)
    investigation_trace: list[ToolCall] = field(default_factory=list)
    cited_evidence: list[CitedEvidence] = field(default_factory=list)

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
        if self.cost.total_tokens > 0:
            d["cost"] = self.cost.to_dict()
        if self.investigation_trace:
            d["investigation_trace"] = [t.to_dict() for t in self.investigation_trace]
        if self.cited_evidence:
            d["cited_evidence"] = [c.to_dict() for c in self.cited_evidence]
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

    @property
    def total_cost(self) -> AdvisorCost:
        result = AdvisorCost.zero()
        for v in self.votes:
            result = result + v.cost
        return result

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
        cost = self.total_cost
        if cost.total_tokens > 0:
            d["cost"] = cost.to_dict()
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
