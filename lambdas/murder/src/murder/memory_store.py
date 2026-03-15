"""Persistent agent memory via DynamoDB.

Memory items use the partition key T#{tenant}#P#{project} and sort keys
with prefix MEM# to segregate them from snapshot/event records.

SK patterns:
    MEM#project#conventions  — project-level coding conventions
    MEM#project#mistakes     — anti-patterns observed across executions
    MEM#agent#planner        — planner specialization learnings
    MEM#agent#implementer    — implementer specialization learnings
    MEM#agent#reviewer       — reviewer specialization learnings
    MEM#agent#fixer          — fixer specialization learnings
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from murder.blackboard import Blackboard
from murder.keys import build_pk


class MemoryStore:
    """Read/write agent memory files in DynamoDB."""

    def __init__(self, blackboard: Blackboard) -> None:
        self._blackboard = blackboard

    def read_memory(self, tenant: str, project: str, memory_key: str) -> str:
        """Read a memory file. Returns empty string if not found.

        memory_key: e.g. 'project#conventions', 'agent#implementer'
        """
        pk = build_pk(tenant, project)
        sk = f"MEM#{memory_key}"
        item = self._blackboard.read(pk, sk)
        if not item:
            return ""
        return item.get("content", "")

    def write_memory(
        self, tenant: str, project: str, memory_key: str, content: str
    ) -> None:
        """Write/overwrite a memory file."""
        pk = build_pk(tenant, project)
        sk = f"MEM#{memory_key}"
        item: dict[str, Any] = {
            "PK": pk,
            "SK": sk,
            "content": content,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "token_estimate": len(content) // 4,
            "entityType": "Memory",
        }
        self._blackboard.write_item(item)

    def read_all_agent_memories(
        self, tenant: str, project: str
    ) -> dict[str, str]:
        """Read all agent specialization memories. Returns {crow_type: content}."""
        pk = build_pk(tenant, project)
        items = self._blackboard.query(pk, "MEM#agent#")
        result: dict[str, str] = {}
        for item in items:
            parts = item["SK"].split("#")
            if len(parts) >= 3:
                agent_type = parts[2]
                result[agent_type] = item.get("content", "")
        return result

    def read_project_memory(self, tenant: str, project: str) -> str:
        """Read all project-level memories concatenated."""
        pk = build_pk(tenant, project)
        items = self._blackboard.query(pk, "MEM#project#")
        sections: list[str] = []
        for item in items:
            topic = item["SK"].split("#")[-1]
            content = item.get("content", "")
            if content:
                sections.append(f"## {topic.title()}\n{content}")
        return "\n\n".join(sections)
