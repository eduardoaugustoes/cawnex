"""Memory injection — synthesize completed crow outcomes into system prompt."""

from __future__ import annotations

MAX_MEMORY_BULLETS = 10


def synthesize_memory(entries: list[dict]) -> str:
    """Turn pre-extracted crow summaries into a memory block (~300-500 tokens).

    Each entry: {"crow_type": str, "summary": str, ...optional fields}.
    Returns markdown suitable for appending to system prompt.
    """
    if not entries:
        return ""

    bullets: list[str] = []
    for entry in entries[:MAX_MEMORY_BULLETS]:
        crow_type = entry.get("crow_type", "unknown")
        summary = entry.get("summary", "")

        if crow_type == "planner":
            tasks = entry.get("tasks", [])
            context_files = entry.get("context_files", [])
            task_names = [t.get("name", "?") for t in tasks] if isinstance(tasks, list) else []
            bullets.append(
                f"Planner: planned {len(task_names)} tasks ({', '.join(task_names[:5])}). "
                f"Key files: {', '.join(context_files[:5]) if context_files else 'none identified'}"
            )

        elif crow_type == "implementer":
            files_changed = entry.get("files_changed", [])
            commit_msg = entry.get("commit_message", "")
            bullets.append(
                f"Implementer: changed {len(files_changed)} files "
                f"({', '.join(files_changed[:5])}). Commit: {commit_msg}"
            )

        elif crow_type == "reviewer":
            approved = entry.get("approved", False)
            if approved:
                bullets.append(f"Reviewer: approved. {summary[:200]}")
            else:
                issues = entry.get("issues", [])
                suggestions = entry.get("suggestions", [])
                bullets.append(
                    f"Reviewer: rejected with {len(issues)} issues. "
                    f"Issues: {'; '.join(str(i)[:100] for i in issues[:3])}. "
                    f"Suggestions: {'; '.join(str(s)[:100] for s in suggestions[:3])}"
                )

        elif crow_type == "fixer":
            files_changed = entry.get("files_changed", [])
            issues_addressed = entry.get("issues_addressed", [])
            bullets.append(
                f"Fixer: addressed {len(issues_addressed)} issues, "
                f"changed {len(files_changed)} files ({', '.join(files_changed[:5])})"
            )

        else:
            if summary:
                bullets.append(f"{crow_type}: {summary[:200]}")

    if not bullets:
        return ""

    return "## Project Memory\n" + "\n".join(f"- {b}" for b in bullets)


def inject_memory(system_prompt: str, memory_block: str) -> str:
    """Append memory block to system prompt. No-op if memory_block is empty."""
    if not memory_block:
        return system_prompt
    return f"{system_prompt}\n\n{memory_block}"
