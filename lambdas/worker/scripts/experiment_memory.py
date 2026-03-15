"""Extract learnings from completed crows into structured memory markdown."""

from __future__ import annotations

from typing import Any

from murder.blackboard import Blackboard
from murder.keys import build_pk


def extract_memory(
    blackboard: Blackboard,
    tenant: str,
    project: str,
    wave_id: str,
    mvi_id: str,
) -> str:
    """Query completed crows for a wave/MVI and synthesize memory markdown.

    Returns ~300-500 tokens of structured learnings that can be injected
    into the system prompt of a subsequent run.
    """
    pk = build_pk(tenant, project)
    crow_prefix = f"S#{wave_id}#m{mvi_id}#cr_"
    crows = blackboard.query(pk, crow_prefix)

    completed = [c for c in crows if c.get("status") == "completed"]
    if not completed:
        return "No completed crows to learn from."

    bullets: list[str] = []

    for crow in completed:
        crow_type = crow.get("crow_type", "unknown")
        outcome: dict[str, Any] = crow.get("outcome", {})

        if crow_type == "planner":
            tasks = outcome.get("tasks", [])
            task_names = [t.get("name", "?") for t in tasks] if isinstance(tasks, list) else []
            context_files = outcome.get("context_files", [])
            bullets.append(
                f"Planner: planned {len(task_names)} tasks ({', '.join(task_names[:5])}). "
                f"Key files: {', '.join(context_files[:5]) if context_files else 'none identified'}"
            )

        elif crow_type == "implementer":
            files_changed = outcome.get("files_changed", [])
            commit_msg = outcome.get("commit_message", "")
            bullets.append(
                f"Implementer: changed {len(files_changed)} files "
                f"({', '.join(files_changed[:5])}). Commit: {commit_msg}"
            )

        elif crow_type == "reviewer":
            approved = outcome.get("approved", False)
            if approved:
                summary = outcome.get("summary", "")
                bullets.append(f"Reviewer: approved. Summary: {summary[:200]}")
            else:
                issues = outcome.get("issues", [])
                suggestions = outcome.get("suggestions", [])
                bullets.append(
                    f"Reviewer: rejected with {len(issues)} issues. "
                    f"Issues: {'; '.join(str(i)[:100] for i in issues[:3])}. "
                    f"Suggestions: {'; '.join(str(s)[:100] for s in suggestions[:3])}"
                )

        elif crow_type == "fixer":
            files_changed = outcome.get("files_changed", [])
            issues_addressed = outcome.get("issues_addressed", [])
            bullets.append(
                f"Fixer: addressed {len(issues_addressed)} issues, "
                f"changed {len(files_changed)} files ({', '.join(files_changed[:5])})"
            )

    return "## Project Memory\n" + "\n".join(f"- {b}" for b in bullets)
