"""Document generation for the Monarch Lambda."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from monarch.claude_client import call_claude
from monarch.config import DOC_PROMPTS, MAX_DOC_TOKENS, WRITER_SYSTEM


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _short_id() -> str:
    return uuid.uuid4().hex[:8]


def _parse_sections(doc_type: str, content: str) -> list[dict[str, str]]:
    """Split document content by ## headings into section dicts."""
    lines = content.split("\n")
    sections: list[dict[str, str]] = []
    current_title = doc_type.capitalize()
    current_lines: list[str] = []

    for line in lines:
        if line.startswith("## "):
            if current_lines:
                sections.append(
                    {
                        "id": _short_id(),
                        "title": current_title,
                        "content": "\n".join(current_lines).strip(),
                        "status": "complete",
                    }
                )
                current_lines = []
            current_title = line[3:].strip()
        else:
            current_lines.append(line)

    if current_lines:
        sections.append(
            {
                "id": _short_id(),
                "title": current_title,
                "content": "\n".join(current_lines).strip(),
                "status": "complete",
            }
        )

    if not sections:
        return [
            {
                "id": _short_id(),
                "title": doc_type.capitalize(),
                "content": content.strip(),
                "status": "complete",
            }
        ]

    return sections


def generate_document(
    table: Any,
    pk: str,
    project_id: str,
    plan: dict[str, Any],
    doc_type: str,
) -> None:
    """Generate one document via Claude and persist it to DynamoDB."""
    description = str(plan.get("description", ""))
    tech_stack = str(plan.get("tech_stack", ""))
    prompt_template = DOC_PROMPTS[doc_type]
    prompt = prompt_template.format(description=description, tech_stack=tech_stack)

    try:
        result = call_claude(
            system=WRITER_SYSTEM,
            user=prompt,
            max_tokens=MAX_DOC_TOKENS,
        )
        content = result.content
    except Exception:
        content = f"Document generation pending for {doc_type}."

    now = _now_iso()
    table.put_item(
        Item={
            "PK": pk,
            "SK": f"DOC#{doc_type}",
            "entityType": "Document",
            "doc_type": doc_type,
            "status": "complete",
            "sections": _parse_sections(doc_type, content),
            "created_at": now,
            "updated_at": now,
        }
    )
