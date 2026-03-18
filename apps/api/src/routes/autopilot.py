"""Autopilot chat endpoint — stateful project creation via natural language.

Monarch (the AI planner) guides the founder through 2-4 targeted questions,
proposes a structured plan, and executes the full project setup on launch.

Phases:
  gathering  — collecting requirements via conversation
  proposed   — plan proposed, user can refine before launching
  executing  — plan being written to DynamoDB (synchronous, <10s)
  complete   — project + wave ready, returns IDs
"""

import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.auth.dependencies import get_tenant
from src.auth.tenant import TenantContext
from src.claude.client import DEFAULT_MODEL, chat
from src.db.client import TenantDB

router = APIRouter(prefix="/projects/autopilot", tags=["autopilot"])

_SESSION_TTL_SECONDS = 3600  # 1 hour
_WRITER_SYSTEM = "You are a technical writer. Output clean, well-structured content."

_MONARCH_SYSTEM = """\
You are Monarch, the AI project planner for Cawnex. The user wants to create \
a new software project.

Your job:
1. Ask 2-4 targeted questions to understand what they want to build. Only ask \
what you can't infer.
2. Once you have enough context, propose a structured plan.

When proposing a plan, output it as a JSON code block with this exact structure:
```json
{
  "project_name": "...",
  "description": "...",
  "repo": "new",
  "tech_stack": "...",
  "milestones": [
    {
      "name": "...",
      "description": "...",
      "goals": [
        {
          "name": "...",
          "description": "...",
          "mvis": [
            {
              "name": "...",
              "description": "...",
              "acceptance_criteria": "...",
              "estimated_hours": 4
            }
          ]
        }
      ]
    }
  ]
}
```

Rules:
- Each MVI must be ≤ 8 hours of human equivalent work
- Be concise in questions — the user is a busy founder
- Propose 1-2 milestones max for the first plan
- Each milestone should have 2-4 goals
- Each goal should have 1-3 MVIs
"""

_DOC_PROMPTS: Dict[str, str] = {
    "vision": (
        "Generate a concise product vision document for: {description}. "
        "Include these sections: Problem Statement, Target User, "
        "Core Value Proposition, Key Differentiators, Success Metrics, Non-Goals. "
        "Return only the document content, no preamble."
    ),
    "architecture": (
        "Generate a technical architecture document for: {description}. "
        "Tech stack: {tech_stack}. "
        "Include these sections: System Overview, High-Level Components, "
        "Data Flow, Technology Decisions. "
        "Return only the document content, no preamble."
    ),
    "glossary": (
        "Generate a glossary for: {description}. "
        "Include these sections: Domain Terms, Technical Terms. "
        "Return only the document content, no preamble."
    ),
    "design": (
        "Generate a design brief for: {description}. "
        "Include these sections: API Design, Error Handling. "
        "Return only the document content, no preamble."
    ),
}


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class AutopilotChatRequest(BaseModel):
    """Request body for the autopilot chat endpoint."""

    session_id: str = ""
    message: str = ""
    action: str = "message"  # "message" or "launch"


class AutopilotChatResponse(BaseModel):
    """Response from the autopilot chat endpoint."""

    session_id: str
    phase: str  # gathering | proposed | executing | complete
    reply: str
    plan: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, str]] = None


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_session_id() -> str:
    return uuid.uuid4().hex


def _short_id() -> str:
    return uuid.uuid4().hex[:8]


def _load_session(
    db: TenantDB, session_id: str
) -> Optional[Dict[str, Any]]:  # pragma: no cover
    return db.get_item(sk=f"AUTOPILOT#{session_id}")


def _save_session(db: TenantDB, session: Dict[str, Any]) -> None:  # pragma: no cover
    db.put_item(
        sk=f"AUTOPILOT#{session['session_id']}",
        **{k: v for k, v in session.items() if k != "SK"},
    )


def _new_session(session_id: str, tenant_id: str) -> Dict[str, Any]:
    now = _now_iso()
    return {
        "session_id": session_id,
        "tenant_id": tenant_id,
        "phase": "gathering",
        "messages": [],
        "plan": None,
        "created_at": now,
        "updated_at": now,
        "expires_at": int(time.time()) + _SESSION_TTL_SECONDS,
    }


def _resolve_session(  # pragma: no cover
    db: TenantDB, body_session_id: str, tenant_id: str
) -> tuple[str, Dict[str, Any]]:
    """Return (session_id, session) — creates a new session if no id given."""
    session_id = body_session_id.strip()
    if session_id:
        session = _load_session(db, session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found or expired")
        return session_id, session
    session_id = _new_session_id()
    return session_id, _new_session(session_id, tenant_id)


# ---------------------------------------------------------------------------
# Plan extraction
# ---------------------------------------------------------------------------


def _extract_plan(text: str) -> Optional[Dict[str, Any]]:
    """Parse the first ```json ... ``` block from Claude's reply.

    Returns the parsed dict if it contains required keys, else None.
    """
    match = re.search(r"```json\s*([\s\S]+?)\s*```", text)
    if not match:
        return None
    try:
        data: Dict[str, Any] = json.loads(match.group(1))
    except (json.JSONDecodeError, ValueError):
        return None

    required = {"project_name", "description", "milestones"}
    if not required.issubset(data.keys()):
        return None

    return data


# ---------------------------------------------------------------------------
# Execution helpers — write to DynamoDB directly
# ---------------------------------------------------------------------------


def _create_project(db: TenantDB, plan: Dict[str, Any]) -> str:  # pragma: no cover
    """Create project list entry and root snapshot. Returns project_id."""
    name: str = str(plan.get("project_name", "untitled"))
    description: str = str(plan.get("description", ""))
    repo: str = str(plan.get("repo", ""))
    tech_stack: str = str(plan.get("tech_stack", ""))

    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40]
    ts_suffix = hex(int(time.time() * 1000))[-4:]
    rand_suffix = hex(int.from_bytes(os.urandom(1), "big"))[-2:]
    project_id = f"{slug}-{ts_suffix}{rand_suffix}"

    now = _now_iso()
    one_liner = description[:120]

    db.put_item(
        sk=f"P#{project_id}",
        project_id=project_id,
        name=name,
        one_liner=one_liner,
        repo=repo,
        murders=["dev"],
        status="draft",
        created_at=now,
        updated_at=now,
        entityType="ProjectEntry",
    )

    db.put_project_item(
        project_id=project_id,
        sk="S#",
        level="root",
        name=name,
        one_liner=one_liner,
        description=description,
        tech_stack=tech_stack,
        murders=["dev"],
        status="draft",
        repo=repo or None,
        repo_status="ready" if repo and repo != "new" else "pending",
        created_at=now,
        updated_at=now,
        entityType="Snapshot",
    )

    return project_id


def _generate_and_save_documents(  # pragma: no cover
    db: TenantDB, project_id: str, plan: Dict[str, Any]
) -> None:
    """Call Claude for each document type and persist the result."""
    description: str = str(plan.get("description", ""))
    tech_stack: str = str(plan.get("tech_stack", ""))
    now = _now_iso()

    for doc_type, prompt_template in _DOC_PROMPTS.items():
        prompt = prompt_template.format(description=description, tech_stack=tech_stack)
        try:
            result = chat(
                system=_WRITER_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
                model=DEFAULT_MODEL,
                max_tokens=2048,
            )
            content = result.content
        except Exception:
            content = f"Document generation pending for {doc_type}."

        db.put_project_item(
            project_id=project_id,
            sk=f"DOC#{doc_type}",
            entityType="Document",
            doc_type=doc_type,
            status="complete",
            sections=_parse_sections(doc_type, content),
            created_at=now,
            updated_at=now,
        )


def _parse_sections(doc_type: str, content: str) -> List[Dict[str, str]]:
    """Split document content by ## headings into section dicts."""
    lines = content.split("\n")
    sections: List[Dict[str, str]] = []
    current_title = doc_type.capitalize()
    current_lines: List[str] = []

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

    return (
        sections
        if sections
        else [
            {
                "id": _short_id(),
                "title": doc_type.capitalize(),
                "content": content.strip(),
                "status": "complete",
            }
        ]
    )


def _build_mvi_record(pmvi: Dict[str, Any]) -> Dict[str, Any]:
    """Build a single MVI DynamoDB record from plan input."""
    hours = min(float(pmvi.get("estimated_hours", 4)), 8.0)
    return {
        "id": _short_id(),
        "name": str(pmvi.get("name", "MVI")),
        "description": str(pmvi.get("description", "")),
        "acceptance_criteria": str(pmvi.get("acceptance_criteria", "")),
        "estimated_hours": Decimal(str(hours)),
        "status": "planned",
    }


def _save_goal_mvis(  # pragma: no cover
    db: TenantDB, project_id: str, goal_id: str, plan_goal: Dict[str, Any], now: str
) -> List[Dict[str, Any]]:
    """Persist MVIs for one goal. Returns the saved MVI dicts."""
    mvis_data = [_build_mvi_record(pmvi) for pmvi in plan_goal.get("mvis", [])]
    total_hours = sum(float(m["estimated_hours"]) for m in mvis_data)
    db.put_project_item(
        project_id=project_id,
        sk=f"BACKLOG#goal#{goal_id}#mvis",
        entityType="GoalMVIs",
        goal_id=goal_id,
        mvis=mvis_data,
        count=len(mvis_data),
        total_estimated_hours=Decimal(str(total_hours)),
        created_at=now,
        updated_at=now,
    )
    return mvis_data


def _save_milestones_and_mvis(  # pragma: no cover
    db: TenantDB, project_id: str, plan: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Persist milestones + goals from plan. Returns enriched milestone dicts."""
    now = _now_iso()
    plan_milestones: List[Dict[str, Any]] = plan.get("milestones", [])
    milestones_data: List[Dict[str, Any]] = []

    for pm in plan_milestones:
        milestone_id = _short_id()
        goals_data: List[Dict[str, Any]] = []

        for pg in pm.get("goals", []):
            goal_id = _short_id()
            _save_goal_mvis(db, project_id, goal_id, pg, now)
            goals_data.append(
                {
                    "id": goal_id,
                    "name": str(pg.get("name", "Goal")),
                    "description": str(pg.get("description", "")),
                    "status": "planned",
                }
            )

        milestones_data.append(
            {
                "id": milestone_id,
                "name": str(pm.get("name", "Milestone")),
                "description": str(pm.get("description", "")),
                "status": "planned",
                "goals": goals_data,
            }
        )

    db.put_project_item(
        project_id=project_id,
        sk="BACKLOG#milestones",
        entityType="Backlog",
        milestones=milestones_data,
        count=len(milestones_data),
        created_at=now,
        updated_at=now,
    )

    return milestones_data


def _find_first_goal_mvis(  # pragma: no cover
    db: TenantDB, project_id: str, milestones_data: List[Dict[str, Any]]
) -> tuple[Optional[str], List[str]]:
    """Return (goal_id, mvi_ids) for the first goal that has MVIs, else (None, [])."""
    for milestone in milestones_data:
        for goal in milestone.get("goals", []):
            goal_id = str(goal.get("id", ""))
            backlog = db.get_project_item(
                project_id=project_id,
                sk=f"BACKLOG#goal#{goal_id}#mvis",
            )
            if backlog and backlog.get("mvis"):
                mvi_ids = [str(m["id"]) for m in backlog["mvis"]]
                return goal_id, mvi_ids
    return None, []


def _write_mvi_snapshot(  # pragma: no cover
    db: TenantDB,
    project_id: str,
    wave_id: str,
    mvi_id: str,
    backlog_mvi: Dict[str, Any],
    repo: str,
    now: str,
) -> Dict[str, Any]:
    """Write a single MVI snapshot for a wave. Returns the wave MVI entry."""
    branch = f"cawnex/{wave_id}-{mvi_id}"
    entry: Dict[str, Any] = {
        "id": mvi_id,
        "name": str(backlog_mvi.get("name", mvi_id)),
        "description": str(backlog_mvi.get("description", "")),
        "acceptance_criteria": str(backlog_mvi.get("acceptance_criteria", "")),
        "repo": repo,
        "branch": branch,
    }
    db.put_project_item(
        project_id=project_id,
        sk=f"S#{wave_id}#m{mvi_id}",
        level="murder",
        status="draft",
        name=entry["name"],
        description=entry["description"],
        acceptance_criteria=entry["acceptance_criteria"],
        tasks_done=0,
        tasks_total=0,
        can_ship=False,
        merge_checklist=[],
        cost={"tokens_in": 0, "tokens_out": 0, "credits": 0, "duration_ms": 0},
        repo=repo,
        branch=branch,
        created_at=now,
        entityType="Snapshot",
    )
    return entry


def _write_backlog_mvi_snapshots(  # pragma: no cover
    db: TenantDB,
    project_id: str,
    wave_id: str,
    goal_id: str,
    mvi_ids: List[str],
    repo: str,
    now: str,
) -> List[Dict[str, Any]]:
    """Write wave snapshots for all backlog MVIs and annotate them with wave_id."""
    backlog = db.get_project_item(
        project_id=project_id,
        sk=f"BACKLOG#goal#{goal_id}#mvis",
    )
    backlog_mvis: List[Dict[str, Any]] = backlog.get("mvis", []) if backlog else []
    backlog_by_id = {str(m["id"]): m for m in backlog_mvis}

    wave_entries: List[Dict[str, Any]] = []
    for mvi_id in mvi_ids:
        entry = _write_mvi_snapshot(
            db, project_id, wave_id, mvi_id, backlog_by_id.get(mvi_id, {}), repo, now
        )
        wave_entries.append(entry)

    for mvi in backlog_mvis:
        if str(mvi["id"]) in mvi_ids:
            mvi["wave_id"] = wave_id
            mvi["wave_status"] = "draft"
    db.update_project_item(
        project_id=project_id,
        sk=f"BACKLOG#goal#{goal_id}#mvis",
        updates={"mvis": backlog_mvis},
    )
    return wave_entries


def _write_fallback_mvi_snapshot(  # pragma: no cover
    db: TenantDB,
    project_id: str,
    wave_id: str,
    directive: str,
    repo: str,
    now: str,
) -> List[Dict[str, Any]]:
    """Write a single ad-hoc MVI snapshot when no backlog goal is available."""
    mvi_id = wave_id
    branch = f"cawnex/{wave_id}-{mvi_id}"
    db.put_project_item(
        project_id=project_id,
        sk=f"S#{wave_id}#m{mvi_id}",
        level="murder",
        status="draft",
        name=directive,
        description="",
        acceptance_criteria="",
        tasks_done=0,
        tasks_total=0,
        can_ship=False,
        merge_checklist=[],
        cost={"tokens_in": 0, "tokens_out": 0, "credits": 0, "duration_ms": 0},
        repo=repo,
        branch=branch,
        created_at=now,
        entityType="Snapshot",
    )
    return [
        {
            "id": mvi_id,
            "name": directive,
            "description": "",
            "acceptance_criteria": "",
            "repo": repo,
            "branch": branch,
        }
    ]


def _activate_wave(  # pragma: no cover
    db: TenantDB,
    tenant: TenantContext,
    project_id: str,
    wave_id: str,
    mvis_count: int,
    now: str,
) -> None:
    """Transition wave to executing, queue MVI snapshots, emit events, scale ECS."""
    from src.routes.waves import _scale_ecs, _write_event

    db.update_project_item(
        project_id=project_id,
        sk=f"S#{wave_id}",
        updates={"status": "executing", "activated_at": now},
    )

    items = db.query_project(project_id=project_id, sk_prefix=f"S#{wave_id}#m")
    for item in items:
        if item.get("level") == "murder" and item.get("status") in ("draft", "refined"):
            db.update_project_item(
                project_id=project_id,
                sk=str(item["SK"]),
                updates={"status": "queued"},
            )

    _write_event(
        tenant.tenant_id,
        project_id,
        wave_id,
        "wave_activated",
        f"Wave activated via Autopilot — {mvis_count} MVIs queued",
        "blue",
    )
    _write_event(
        tenant.tenant_id,
        project_id,
        wave_id,
        "worker_warming",
        "Execution engine warming up (~30s)",
        "yellow",
    )
    _scale_ecs(1)


def _create_and_activate_first_wave(  # pragma: no cover
    db: TenantDB,
    tenant: TenantContext,
    project_id: str,
    plan: Dict[str, Any],
    milestones_data: List[Dict[str, Any]],
) -> str:
    """Create a wave for the first goal's MVIs and activate it. Returns wave_id."""
    now = _now_iso()
    wave_id = f"w{int(time.time() * 1000)}"
    repo: str = str(plan.get("repo", ""))

    goal_id, mvi_ids = _find_first_goal_mvis(db, project_id, milestones_data)

    if goal_id and mvi_ids:
        mvis_wave_data = _write_backlog_mvi_snapshots(
            db, project_id, wave_id, goal_id, mvi_ids, repo, now
        )
    else:
        directive = str(plan.get("description", "Initial wave"))
        mvis_wave_data = _write_fallback_mvi_snapshot(
            db, project_id, wave_id, directive, repo, now
        )

    db.put_project_item(
        project_id=project_id,
        sk=f"S#{wave_id}",
        level="wave",
        status="planning",
        human_directive=str(plan.get("description", "Autopilot launch")),
        progress={
            "mvis_total": len(mvis_wave_data),
            "mvis_shipped": 0,
            "tasks_done": 0,
            "tasks_total": 0,
        },
        budget={"spent": 0, "limit": 20_000_000},
        created_at=now,
        entityType="Snapshot",
    )

    _activate_wave(db, tenant, project_id, wave_id, len(mvis_wave_data), now)
    return wave_id


# ---------------------------------------------------------------------------
# Route action handlers
# ---------------------------------------------------------------------------


def _handle_launch(  # pragma: no cover
    db: TenantDB,
    tenant: TenantContext,
    session_id: str,
    session: Dict[str, Any],
    phase: str,
    plan: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Create project and queue async Monarch task. Returns immediately."""
    if phase not in ("proposed", "gathering"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot launch from phase '{phase}'",
        )
    if not plan:
        raise HTTPException(
            status_code=400,
            detail="No plan available. Continue the conversation first.",
        )

    project_id = _create_project(db, plan)
    now = _now_iso()
    db.put_project_item(
        project_id=project_id,
        sk="MONARCH#task",
        entityType="MonarchTask",
        status="pending",
        plan=plan,
        tenant_id=tenant.tenant_id,
        created_at=now,
        updated_at=now,
    )

    session["phase"] = "executing"
    session["updated_at"] = now
    _save_session(db, session)

    return {
        "session_id": session_id,
        "phase": "executing",
        "reply": (
            f"Your project **{plan.get('project_name', 'project')}** is being set up. "
            "Monarch is generating documents, planning your backlog, "
            "and launching the first wave."
        ),
        "plan": plan,
        "result": {"project_id": project_id},
    }


def _build_system_prompt(phase: str, plan: Optional[Dict[str, Any]]) -> str:
    """Return the system prompt, appending current plan context when proposed."""
    if phase == "proposed" and plan:
        plan_json = json.dumps(plan, indent=2)
        return (
            _MONARCH_SYSTEM + f"\n\nCurrent proposed plan:\n```json\n{plan_json}\n```\n"
            "If the user requests changes, output an updated plan JSON block."
        )
    return _MONARCH_SYSTEM


def _handle_message(  # pragma: no cover
    db: TenantDB,
    session_id: str,
    session: Dict[str, Any],
    phase: str,
    plan: Optional[Dict[str, Any]],
    messages: List[Dict[str, Any]],
    user_message: str,
) -> Dict[str, Any]:
    """Process a user message through Claude and return updated response."""
    if not user_message.strip():
        raise HTTPException(status_code=400, detail="message is required")

    messages.append({"role": "user", "content": user_message.strip()})
    claude_messages = [{"role": m["role"], "content": m["content"]} for m in messages]

    try:
        result = chat(
            system=_build_system_prompt(phase, plan),
            messages=claude_messages,  # type: ignore[arg-type]
            model=DEFAULT_MODEL,
            max_tokens=2048,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Claude API error: {str(e)}")

    reply = result.content
    messages.append({"role": "assistant", "content": reply})

    detected_plan = _extract_plan(reply)
    if detected_plan:
        plan = detected_plan
        phase = "proposed"

    session["phase"] = phase
    session["messages"] = messages
    session["plan"] = plan
    session["updated_at"] = _now_iso()
    _save_session(db, session)

    return {
        "session_id": session_id,
        "phase": phase,
        "reply": reply,
        "plan": plan,
        "result": None,
    }


# ---------------------------------------------------------------------------
# Route handler
# ---------------------------------------------------------------------------


@router.post("/chat", response_model=AutopilotChatResponse)
async def autopilot_chat(  # pragma: no cover
    body: AutopilotChatRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> Dict[str, Any]:
    """Stateful autopilot chat for project creation via natural language.

    On first call (no session_id), creates a new session.
    Drives through gathering → proposed → complete phases.
    On action=launch, executes the full project setup synchronously.
    """
    db = TenantDB(tenant)
    session_id, session = _resolve_session(db, body.session_id, tenant.tenant_id)

    phase: str = str(session.get("phase", "gathering"))
    messages: List[Dict[str, Any]] = list(session.get("messages", []))
    plan: Optional[Dict[str, Any]] = session.get("plan")

    if body.action == "launch":
        return _handle_launch(db, tenant, session_id, session, phase, plan)

    return _handle_message(db, session_id, session, phase, plan, messages, body.message)
