"""Post-execution reflection: extract learnings from crow outcomes and persist to memory.

After each crow completes, 0-2 concrete learnings are extracted and appended
to the agent's specialization memory in DynamoDB. This accumulated memory is
then injected into future crow instructions by the reactor.

The core question this module answers: does accumulated agent memory improve outcomes?
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from murder.memory_store import MemoryStore

MAX_MEMORY_TOKENS = 500  # ~2000 chars, conservative for MVP


def extract_learnings(
    crow_type: str, outcome: dict[str, Any], status: str
) -> list[str]:
    """Extract 0-2 concrete learnings from a crow's outcome. Pure function, no I/O."""
    learnings: list[str] = []

    if status != "completed":
        error = outcome.get("error", "unknown")
        learnings.append(f"[FAILURE] {crow_type} failed: {error}")
        return learnings

    if crow_type == "reviewer":
        approved = outcome.get("approved", False)
        blocking = outcome.get("blocking_issues", [])
        if not approved and blocking:
            for issue in blocking[:2]:
                learnings.append(f"[REVIEW] Blocking issue found: {issue}")
        elif approved:
            suggestions = outcome.get(
                "non_blocking_issues", outcome.get("suggestions", [])
            )
            if suggestions:
                learnings.append(
                    f"[QUALITY] Approved with suggestions: "
                    f"{'; '.join(str(s) for s in suggestions[:3])}"
                )

    elif crow_type == "fixer":
        issues_addressed = outcome.get("issues_addressed", [])
        files_changed = outcome.get("files_changed", [])
        if issues_addressed:
            learnings.append(
                f"[FIX] Fixed: {'; '.join(str(i) for i in issues_addressed[:2])} "
                f"in {', '.join(files_changed[:3])}"
            )

    elif crow_type == "implementer":
        files_changed = outcome.get("files_changed", [])
        summary = outcome.get("summary", "")
        if files_changed and summary:
            learnings.append(
                f"[IMPL] {summary[:150]} — files: {', '.join(files_changed[:5])}"
            )

    elif crow_type == "planner":
        tasks = outcome.get("tasks", [])
        if tasks:
            task_names = [t.get("name", "?") for t in tasks[:5]]
            learnings.append(f"[PLAN] Decomposed into: {', '.join(task_names)}")

    return learnings


def append_learnings(
    existing_content: str,
    new_learnings: list[str],
    max_tokens: int = MAX_MEMORY_TOKENS,
) -> str:
    """Append learnings to existing memory content, pruning oldest if over budget.

    Returns updated memory content string.
    """
    if not new_learnings:
        return existing_content

    lines = (
        [l for l in existing_content.strip().split("\n") if l.strip()]
        if existing_content
        else []
    )

    for learning in new_learnings:
        lines.append(f"- {learning}")

    content = "\n".join(lines)
    while len(content) // 4 > max_tokens and len(lines) > 1:
        lines.pop(0)
        content = "\n".join(lines)

    return content


def reflect_on_crow(
    memory_store: MemoryStore,
    tenant: str,
    project: str,
    crow_type: str,
    outcome: dict[str, Any],
    status: str,
) -> list[str]:
    """Full reflection cycle: extract learnings, append to agent memory, return learnings.

    This is the entry point called after each crow completion.
    """
    learnings = extract_learnings(crow_type, outcome, status)
    if not learnings:
        return []

    memory_key = f"agent#{crow_type}"
    existing = memory_store.read_memory(tenant, project, memory_key)
    updated = append_learnings(existing, learnings)
    memory_store.write_memory(tenant, project, memory_key, updated)

    return learnings
