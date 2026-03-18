"""Milestone, goal, and MVI persistence for the Monarch Lambda."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _short_id() -> str:
    return uuid.uuid4().hex[:8]


def _build_mvi_record(plan_mvi: dict[str, Any]) -> dict[str, Any]:
    hours = min(float(plan_mvi.get("estimated_hours", 4)), 8.0)
    return {
        "id": _short_id(),
        "name": str(plan_mvi.get("name", "MVI")),
        "description": str(plan_mvi.get("description", "")),
        "acceptance_criteria": str(plan_mvi.get("acceptance_criteria", "")),
        "estimated_hours": Decimal(str(hours)),
        "status": "planned",
    }


def _save_goal_mvis(
    table: Any,
    pk: str,
    goal_id: str,
    plan_goal: dict[str, Any],
    now: str,
) -> list[dict[str, Any]]:
    mvis_data = [_build_mvi_record(pmvi) for pmvi in plan_goal.get("mvis", [])]
    total_hours = sum(float(m["estimated_hours"]) for m in mvis_data)
    table.put_item(
        Item={
            "PK": pk,
            "SK": f"BACKLOG#goal#{goal_id}#mvis",
            "entityType": "GoalMVIs",
            "goal_id": goal_id,
            "mvis": mvis_data,
            "count": len(mvis_data),
            "total_estimated_hours": Decimal(str(total_hours)),
            "created_at": now,
            "updated_at": now,
        }
    )
    return mvis_data


def save_milestones_and_mvis(
    table: Any,
    pk: str,
    plan: dict[str, Any],
) -> list[dict[str, Any]]:
    """Persist milestones, goals, and MVIs from plan. Returns enriched milestone dicts."""
    now = _now_iso()
    plan_milestones: list[dict[str, Any]] = plan.get("milestones", [])
    milestones_data: list[dict[str, Any]] = []

    for pm in plan_milestones:
        milestone_id = _short_id()
        goals_data: list[dict[str, Any]] = []

        for pg in pm.get("goals", []):
            goal_id = _short_id()
            _save_goal_mvis(table, pk, goal_id, pg, now)
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

    table.put_item(
        Item={
            "PK": pk,
            "SK": "BACKLOG#milestones",
            "entityType": "Backlog",
            "milestones": milestones_data,
            "count": len(milestones_data),
            "created_at": now,
            "updated_at": now,
        }
    )

    return milestones_data
