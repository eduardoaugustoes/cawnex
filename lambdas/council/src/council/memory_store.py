"""DynamoDB-backed memory store for advisor evolution.

Reuses the MEM# SK pattern from Murder's MemoryStore.
Advisor memories stored at: MEM#advisor#{advisor_type}
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from council._blackboard import Blackboard
from council.enums import AdvisorType

MAX_ADVISOR_TOKENS = 2000


def _token_estimate(content: str) -> int:
    return len(content) // 4


class CouncilMemoryStore:
    def __init__(self, blackboard: Blackboard) -> None:
        self._blackboard = blackboard

    def read_advisor_memory(
        self, tenant: str, project: str, advisor: AdvisorType
    ) -> str:
        """Read an advisor's evolving memory. Returns empty string if none."""
        pk = f"T#{tenant}#P#{project}"
        sk = f"MEM#advisor#{advisor.value}"
        item = self._blackboard.read(pk, sk)
        if not item:
            return ""
        return item.get("content", "")

    def write_advisor_memory(
        self, tenant: str, project: str, advisor: AdvisorType, content: str
    ) -> None:
        """Write/overwrite an advisor's memory."""
        pk = f"T#{tenant}#P#{project}"
        sk = f"MEM#advisor#{advisor.value}"
        item: dict[str, Any] = {
            "PK": pk,
            "SK": sk,
            "content": content,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "token_estimate": _token_estimate(content),
            "entityType": "Memory",
        }
        self._blackboard.write_item(item)

    def append_advisor_learning(
        self, tenant: str, project: str, advisor: AdvisorType, learning: str
    ) -> str:
        """Append a learning to an advisor's memory. Prunes if over budget.

        Returns the updated memory content.
        """
        existing = self.read_advisor_memory(tenant, project, advisor)

        if existing:
            updated = f"{existing}\n- {learning}"
        else:
            updated = f"# {advisor.value.title()} Advisor Learnings\n\n- {learning}"

        # Prune if over token budget
        if _token_estimate(updated) > MAX_ADVISOR_TOKENS:
            updated = _prune_memory(updated)

        self.write_advisor_memory(tenant, project, advisor, updated)
        return updated

    def read_all_advisor_memories(
        self, tenant: str, project: str
    ) -> dict[str, str]:
        """Read all advisor memories for a project."""
        pk = f"T#{tenant}#P#{project}"
        items = self._blackboard.query(pk, "MEM#advisor#")
        result: dict[str, str] = {}
        for item in items:
            parts = item["SK"].split("#")
            if len(parts) >= 3:
                advisor_type = parts[2]
                result[advisor_type] = item.get("content", "")
        return result

    def read_org_standards(self, tenant: str) -> str:
        """Read org-level standards (shared across all projects).

        Stored at PK=T#{tenant}, SK=MEM#org#standards.
        """
        pk = f"T#{tenant}"
        sk = "MEM#org#standards"
        item = self._blackboard.read(pk, sk)
        if not item:
            return ""
        return item.get("content", "")

    def read_project_context(self, tenant: str, project: str) -> str:
        """Read all project-level memories concatenated.

        Includes wave reflections, conventions, and other project memories.
        """
        pk = f"T#{tenant}#P#{project}"
        items = self._blackboard.query(pk, "MEM#project#")
        sections: list[str] = []
        for item in items:
            topic = item["SK"].split("#")[-1]
            content = item.get("content", "")
            if content:
                sections.append(f"## {topic.replace('_', ' ').title()}\n{content}")
        return "\n\n".join(sections)


def _prune_memory(content: str) -> str:
    """Prune memory to stay within token budget.

    Strategy: keep the header and the most recent learnings.
    Drop the oldest entries (at the top of the list).
    """
    lines = content.split("\n")

    # Separate header from learnings
    header_lines: list[str] = []
    learning_lines: list[str] = []
    in_learnings = False

    for line in lines:
        if line.startswith("- "):
            in_learnings = True
        if in_learnings:
            learning_lines.append(line)
        else:
            header_lines.append(line)

    if not learning_lines:
        return content

    # Keep dropping oldest learnings until under budget
    header = "\n".join(header_lines)
    while learning_lines and _token_estimate(
        header + "\n" + "\n".join(learning_lines)
    ) > MAX_ADVISOR_TOKENS:
        learning_lines.pop(0)

    if not learning_lines:
        return header

    return header + "\n" + "\n".join(learning_lines)
