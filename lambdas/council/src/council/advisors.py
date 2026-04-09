"""Advisor prompt building, parallel execution, and response parsing."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from council.config import ANTHROPIC_MODEL
from council.enums import AdvisorType, VoteType
from council.models import AdvisorCost, AdvisorVote

_PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts" / "advisors"


def build_advisor_prompt(
    advisor: AdvisorType,
    decision_context: dict[str, Any],
    advisor_memory: str = "",
    org_standards: str = "",
    project_context: str = "",
) -> dict[str, str]:
    """Build system + user prompt for an advisor.

    5-layer prompt structure:
    1. Advisor identity and role (static, from prompts/advisors/{type}.md)
    2. Org standards (shared across projects, rarely changes)
    3. Project context (project memories, wave reflections)
    4. Advisor memory (evolving learnings from past sessions)
    5. Decision context (unique per session, in user message)
    """
    # Layer 1: Advisor identity
    prompt_path = _PROMPTS_DIR / f"{advisor.value}.md"
    system = (
        prompt_path.read_text()
        if prompt_path.exists()
        else f"You are the {advisor.value} advisor."
    )

    # Layer 2: Org standards
    if org_standards:
        system = (
            f"{system}\n\n"
            f"## Organization Standards\n"
            f"{org_standards}"
        )

    # Layer 3: Project context
    if project_context:
        system = (
            f"{system}\n\n"
            f"## Project Context\n"
            f"{project_context}"
        )

    # Layer 4: Advisor's evolving memory
    if advisor_memory:
        system = (
            f"{system}\n\n"
            f"## Your Memory (learnings from previous sessions)\n"
            f"{advisor_memory}"
        )

    # Layer 5: Decision context (in user message)
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
    advisor_memory: str = "",
    org_standards: str = "",
    project_context: str = "",
) -> AdvisorVote:
    """Call a single advisor via the Anthropic API."""
    from council._claude_client import call_claude

    prompt = build_advisor_prompt(
        advisor,
        decision_context,
        advisor_memory=advisor_memory,
        org_standards=org_standards,
        project_context=project_context,
    )
    result = call_claude(
        system=prompt["system"],
        user=prompt["user"],
        model=ANTHROPIC_MODEL,
        max_tokens=1024,
    )
    vote = parse_advisor_response(advisor, result.content)
    vote.cost = AdvisorCost(
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        duration_ms=result.duration_ms,
    )
    return vote


def run_all_advisors(
    decision_context: dict[str, Any],
    advisors: list[AdvisorType] | None = None,
    advisor_memories: dict[str, str] | None = None,
    org_standards: str = "",
    project_context: str = "",
) -> list[AdvisorVote]:
    """Run all advisors in parallel and return their votes.

    advisor_memories: optional dict mapping advisor type name to memory content.
    org_standards: shared org-level standards (Layer 2).
    project_context: project memories and reflections (Layer 3).
    """
    if advisors is None:
        advisors = list(AdvisorType)
    if advisor_memories is None:
        advisor_memories = {}

    votes: list[AdvisorVote] = []
    with ThreadPoolExecutor(max_workers=len(advisors)) as executor:
        futures = {
            executor.submit(
                _call_advisor,
                advisor,
                decision_context,
                advisor_memories.get(advisor.value, ""),
                org_standards,
                project_context,
            ): advisor
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
