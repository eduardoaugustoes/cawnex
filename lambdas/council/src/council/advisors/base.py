"""Base advisor: tool-use loop wrapper with cap-handling."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from council.claude_client import run_tool_use_loop
from council.enums import AdvisorType, VoteType
from council.models import AdvisorCost, AdvisorVote, CitedEvidence, ToolCall
from council.tools.palette import execute_tool, get_palette

CALL_CAP = 15
WALL_CLOCK_SECONDS = 180

_PROMPT_DIR = Path(__file__).parent / "prompts"


def _load_prompt(advisor: AdvisorType) -> str:
    path = _PROMPT_DIR / f"{advisor.value}.md"
    if not path.exists():
        return f"You are the {advisor.value} advisor. Investigate and submit_vote."
    return path.read_text()


def _vote_from_result(advisor: AdvisorType, result: Any) -> AdvisorVote:
    """Convert a ToolUseResult into an AdvisorVote."""
    cost = AdvisorCost(
        tokens_in=int(result.tokens_consumed * 0.7),
        tokens_out=int(result.tokens_consumed * 0.3),
        duration_ms=0,
    )
    trace = [
        ToolCall(
            tool_name=e["tool_name"],
            args=e["args"],
            result_summary=e["result_summary"],
            duration_ms=e["duration_ms"],
            error=e.get("error"),
        )
        for e in result.trace_entries
    ]

    if result.terminated_by == "submit_vote" and result.final_vote:
        v = result.final_vote
        vote_str = v.get("vote", "abstain")
        vote_type = {
            "approve": VoteType.APPROVE,
            "approve_with_condition": VoteType.APPROVE_WITH_CONDITION,
            "abstain": VoteType.ABSTAIN,
            "block": VoteType.BLOCK,
        }.get(vote_str, VoteType.ABSTAIN)
        evidence = [
            CitedEvidence(
                file_path=e.get("file_path", ""),
                line_range=tuple(e["line_range"]) if e.get("line_range") else None,
                pr_number=e.get("pr_number"),
                reason=e.get("reason", ""),
            )
            for e in v.get("cited_evidence", [])
        ]
        return AdvisorVote(
            advisor=advisor,
            vote=vote_type,
            scores={},
            reasoning=v.get("reasoning", ""),
            confidence=float(v.get("confidence", 0.5)),
            blockers=v.get("blockers", []),
            condition=v.get("condition", ""),
            cost=cost,
            investigation_trace=trace,
            cited_evidence=evidence,
        )

    reasoning = (
        f"investigation incomplete: terminated by {result.terminated_by} "
        f"after {result.tool_calls_made} tool calls (cap={CALL_CAP})"
    )
    return AdvisorVote(
        advisor=advisor,
        vote=VoteType.ABSTAIN,
        scores={},
        reasoning=reasoning,
        confidence=0.0,
        blockers=[reasoning] if "cap" in result.terminated_by else [],
        cost=cost,
        investigation_trace=trace,
    )


async def run_advisor(
    advisor: AdvisorType,
    packet: dict[str, Any],
    context: dict[str, Any],
) -> AdvisorVote:
    """Run a single advisor's investigation + vote."""
    system_prompt = _load_prompt(advisor)
    user_message = json.dumps(packet)
    tools = get_palette(advisor)

    def tool_executor(name: str, args: dict[str, Any]) -> dict[str, Any]:
        return execute_tool(
            advisor=advisor, tool_name=name, args=args, context=context
        )

    result = await run_tool_use_loop(
        system_prompt=system_prompt,
        user_message=user_message,
        tools=tools,
        max_tool_calls=CALL_CAP,
        wall_clock_seconds=WALL_CLOCK_SECONDS,
        tool_executor=tool_executor,
    )

    return _vote_from_result(advisor=advisor, result=result)
