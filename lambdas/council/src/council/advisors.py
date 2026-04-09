"""Advisor prompt building, parallel execution, and response parsing."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from council.config import ANTHROPIC_MODEL
from council.enums import AdvisorType, VoteType
from council.models import AdvisorVote

_PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts" / "advisors"


def build_advisor_prompt(
    advisor: AdvisorType,
    decision_context: dict[str, Any],
) -> dict[str, str]:
    """Build system + user prompt for an advisor."""
    prompt_path = _PROMPTS_DIR / f"{advisor.value}.md"
    system = (
        prompt_path.read_text()
        if prompt_path.exists()
        else f"You are the {advisor.value} advisor."
    )

    user = json.dumps(decision_context, indent=2, default=str)

    return {"system": system, "user": user}


def parse_advisor_response(advisor: AdvisorType, raw: str) -> AdvisorVote:
    """Parse an advisor's JSON response into an AdvisorVote."""
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1]) if len(lines) > 2 else cleaned

        data = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        return AdvisorVote(
            advisor=advisor,
            vote=VoteType.ABSTAIN,
            scores={},
            reasoning=f"Failed to parse response: {raw[:200]}",
            confidence=0.0,
        )

    vote_str = data.get("vote", "abstain").lower()
    try:
        vote = VoteType(vote_str)
    except ValueError:
        vote = VoteType.ABSTAIN

    return AdvisorVote(
        advisor=advisor,
        vote=vote,
        scores=data.get("scores", {}),
        reasoning=data.get("reasoning", ""),
        confidence=float(data.get("confidence", 0.5)),
        blockers=data.get("blockers", []),
        condition=data.get("condition", ""),
        suggested_crows=data.get("suggested_crows", []),
        changed_from=data.get("changed_from", ""),
    )


def _call_advisor(
    advisor: AdvisorType,
    decision_context: dict[str, Any],
) -> AdvisorVote:
    """Call a single advisor via the Anthropic API."""
    from council._claude_client import call_claude

    prompt = build_advisor_prompt(advisor, decision_context)
    result = call_claude(
        system=prompt["system"],
        user=prompt["user"],
        model=ANTHROPIC_MODEL,
        max_tokens=1024,
    )
    return parse_advisor_response(advisor, result.content)


def run_all_advisors(
    decision_context: dict[str, Any],
    advisors: list[AdvisorType] | None = None,
) -> list[AdvisorVote]:
    """Run all advisors in parallel and return their votes."""
    if advisors is None:
        advisors = list(AdvisorType)

    votes: list[AdvisorVote] = []
    with ThreadPoolExecutor(max_workers=len(advisors)) as executor:
        futures = {
            executor.submit(_call_advisor, advisor, decision_context): advisor
            for advisor in advisors
        }
        for future in as_completed(futures):
            advisor = futures[future]
            try:
                votes.append(future.result())
            except Exception as e:
                votes.append(
                    AdvisorVote(
                        advisor=advisor,
                        vote=VoteType.ABSTAIN,
                        scores={},
                        reasoning=f"Advisor call failed: {e}",
                        confidence=0.0,
                    )
                )

    return votes
