"""Wave reflection — analyze delivered wave and extract project learnings.

Runs after each wave delivery in continuation mode. Deterministic analysis
(no LLM needed): examines MVI outcomes, costs, check failures, and council
feedback to produce actionable learnings for project memory.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from boto3.dynamodb.conditions import Key

MAX_PROJECT_MEMORY_TOKENS = 4000


def _token_estimate(content: str) -> int:
    return len(content) // 4


def reflect_on_wave(
    table: Any,
    pk: str,
    delivered_wave_id: str,
    council_decision: dict[str, Any],
) -> list[str]:
    """Analyze a delivered wave and return project-level learnings.

    Examines:
    - MVI outcomes (shipped vs failed, reasons)
    - Costs (total, per-MVI averages)
    - Deterministic check patterns (recurring failures)
    - Council feedback (what advisors flagged)

    Returns 0-5 learnings as strings.
    """
    learnings: list[str] = []

    # Query all items in the wave
    wave_prefix = f"S#{delivered_wave_id}#"
    items = table.query(
        KeyConditionExpression=Key("PK").eq(pk)
        & Key("SK").begins_with(wave_prefix),
    ).get("Items", [])

    mvis = [i for i in items if i.get("level") == "murder"]
    crows = [i for i in items if i.get("level") == "crow"]

    if not mvis:
        return learnings

    # --- MVI outcome analysis ---
    shipped = [m for m in mvis if m.get("status") == "shipped"]
    ready = [m for m in mvis if m.get("status") == "ready_to_ship"]
    failed = [m for m in mvis if m.get("status") == "failed"]

    shipped_count = len(shipped) + len(ready)  # ready_to_ship counts as success
    failed_count = len(failed)
    total = len(mvis)

    if failed_count > 0:
        fail_names = [m.get("name", m.get("mvi_id", "?")) for m in failed]
        learnings.append(
            f"Wave {delivered_wave_id}: {failed_count}/{total} MVIs failed — {', '.join(fail_names[:3])}"
        )

    if shipped_count == total:
        learnings.append(
            f"Wave {delivered_wave_id}: all {total} MVIs shipped successfully"
        )

    # --- Cost analysis ---
    total_credits = 0
    for crow in crows:
        cost = crow.get("cost", {})
        if isinstance(cost, dict):
            total_credits += int(cost.get("credits", 0))

    if total_credits > 0 and shipped_count > 0:
        avg_credits = total_credits // shipped_count
        learnings.append(
            f"Wave cost: {total_credits} credits total, ~{avg_credits} per MVI"
        )

    # --- Deterministic check patterns ---
    check_failures: dict[str, int] = {}
    for mvi in mvis:
        checks = mvi.get("deterministic_checks", {})
        for name in checks.get("failed", []):
            check_failures[name] = check_failures.get(name, 0) + 1
        for name in checks.get("warnings", []):
            check_failures[name] = check_failures.get(name, 0) + 1

    if check_failures:
        top_failures = sorted(check_failures.items(), key=lambda x: -x[1])[:3]
        failure_text = ", ".join(f"{name} ({count}x)" for name, count in top_failures)
        learnings.append(f"Recurring check issues: {failure_text}")

    # --- Council feedback analysis ---
    dissent = council_decision.get("dissent_record", {})
    conditions = council_decision.get("conditions", [])

    if conditions:
        learnings.append(
            f"Council conditions applied: {'; '.join(c[:80] for c in conditions[:2])}"
        )

    if dissent:
        dissent_summary = "; ".join(
            f"{advisor}: {reason[:60]}" for advisor, reason in list(dissent.items())[:2]
        )
        learnings.append(f"Dissenting views: {dissent_summary}")

    # --- Fixer cycle analysis ---
    fixer_crows = [c for c in crows if c.get("crow_type") == "fixer"]
    if len(fixer_crows) > 2:
        learnings.append(
            f"High fixer activity: {len(fixer_crows)} fixer cycles — review quality may need attention"
        )

    return learnings[:5]


def save_wave_reflection(
    table: Any,
    pk: str,
    learnings: list[str],
) -> None:
    """Append wave learnings to project memory."""
    if not learnings:
        return

    sk = "MEM#project#wave_reflections"
    existing_item = table.get_item(Key={"PK": pk, "SK": sk}).get("Item")
    existing = existing_item.get("content", "") if existing_item else ""

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    new_entries = "\n".join(f"- [{timestamp}] {l}" for l in learnings)

    if existing:
        updated = f"{existing}\n{new_entries}"
    else:
        updated = f"# Wave Reflection Log\n\n{new_entries}"

    # Prune if over token budget
    if _token_estimate(updated) > MAX_PROJECT_MEMORY_TOKENS:
        updated = _prune_reflections(updated)

    table.put_item(
        Item={
            "PK": pk,
            "SK": sk,
            "content": updated,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "token_estimate": _token_estimate(updated),
            "entityType": "Memory",
        }
    )


def _prune_reflections(content: str) -> str:
    """Drop oldest reflection entries to stay within token budget."""
    lines = content.split("\n")

    header_lines: list[str] = []
    entry_lines: list[str] = []
    in_entries = False

    for line in lines:
        if line.startswith("- ["):
            in_entries = True
        if in_entries:
            entry_lines.append(line)
        else:
            header_lines.append(line)

    header = "\n".join(header_lines)
    while entry_lines and _token_estimate(
        header + "\n" + "\n".join(entry_lines)
    ) > MAX_PROJECT_MEMORY_TOKENS:
        entry_lines.pop(0)

    if not entry_lines:
        return header

    return header + "\n" + "\n".join(entry_lines)
