"""Wave creation and activation for the Monarch Lambda."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key as DKey

from monarch.config import ECS_CLUSTER_NAME, ECS_SERVICE_NAME
from monarch.events import emit_event


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _short_id() -> str:
    return uuid.uuid4().hex[:8]


def _wave_id() -> str:
    return f"w{int(time.time() * 1000)}"


def _find_first_goal_mvis(
    table: Any,
    pk: str,
    milestones_data: list[dict[str, Any]],
) -> tuple[str | None, list[str]]:
    """Return (goal_id, mvi_ids) for the first goal that has MVIs."""
    for milestone in milestones_data:
        for goal in milestone.get("goals", []):
            goal_id = str(goal.get("id", ""))
            resp = table.get_item(Key={"PK": pk, "SK": f"BACKLOG#goal#{goal_id}#mvis"})
            backlog = resp.get("Item")
            if backlog and backlog.get("mvis"):
                mvi_ids = [str(m["id"]) for m in backlog["mvis"]]
                return goal_id, mvi_ids
    return None, []


def _write_mvi_snapshot(
    table: Any,
    pk: str,
    wave_id: str,
    mvi_id: str,
    backlog_mvi: dict[str, Any],
    repo: str,
    now: str,
) -> dict[str, Any]:
    branch = f"cawnex/{wave_id}-{mvi_id}"
    entry: dict[str, Any] = {
        "id": mvi_id,
        "name": str(backlog_mvi.get("name", mvi_id)),
        "description": str(backlog_mvi.get("description", "")),
        "acceptance_criteria": str(backlog_mvi.get("acceptance_criteria", "")),
        "repo": repo,
        "branch": branch,
    }
    table.put_item(
        Item={
            "PK": pk,
            "SK": f"S#{wave_id}#m{mvi_id}",
            "level": "murder",
            "status": "draft",
            "name": entry["name"],
            "description": entry["description"],
            "acceptance_criteria": entry["acceptance_criteria"],
            "tasks_done": 0,
            "tasks_total": 0,
            "can_ship": False,
            "merge_checklist": [],
            "cost": {"tokens_in": 0, "tokens_out": 0, "credits": 0, "duration_ms": 0},
            "repo": repo,
            "branch": branch,
            "created_at": now,
            "entityType": "Snapshot",
        }
    )
    return entry


def _write_backlog_mvi_snapshots(
    table: Any,
    pk: str,
    wave_id: str,
    goal_id: str,
    mvi_ids: list[str],
    repo: str,
    now: str,
) -> list[dict[str, Any]]:
    resp = table.get_item(Key={"PK": pk, "SK": f"BACKLOG#goal#{goal_id}#mvis"})
    backlog = resp.get("Item")
    backlog_mvis: list[dict[str, Any]] = backlog.get("mvis", []) if backlog else []
    backlog_by_id = {str(m["id"]): m for m in backlog_mvis}

    wave_entries: list[dict[str, Any]] = []
    for mvi_id in mvi_ids:
        entry = _write_mvi_snapshot(
            table, pk, wave_id, mvi_id, backlog_by_id.get(mvi_id, {}), repo, now
        )
        wave_entries.append(entry)

    for mvi in backlog_mvis:
        if str(mvi["id"]) in mvi_ids:
            mvi["wave_id"] = wave_id
            mvi["wave_status"] = "draft"

    table.update_item(
        Key={"PK": pk, "SK": f"BACKLOG#goal#{goal_id}#mvis"},
        UpdateExpression="SET #mvis = :mvis",
        ExpressionAttributeNames={"#mvis": "mvis"},
        ExpressionAttributeValues={":mvis": backlog_mvis},
    )
    return wave_entries


def _write_fallback_mvi_snapshot(
    table: Any,
    pk: str,
    wave_id: str,
    directive: str,
    repo: str,
    now: str,
) -> list[dict[str, Any]]:
    mvi_id = wave_id
    branch = f"cawnex/{wave_id}-{mvi_id}"
    table.put_item(
        Item={
            "PK": pk,
            "SK": f"S#{wave_id}#m{mvi_id}",
            "level": "murder",
            "status": "draft",
            "name": directive,
            "description": "",
            "acceptance_criteria": "",
            "tasks_done": 0,
            "tasks_total": 0,
            "can_ship": False,
            "merge_checklist": [],
            "cost": {"tokens_in": 0, "tokens_out": 0, "credits": 0, "duration_ms": 0},
            "repo": repo,
            "branch": branch,
            "created_at": now,
            "entityType": "Snapshot",
        }
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


def _scale_ecs(desired_count: int) -> None:
    if not ECS_CLUSTER_NAME or not ECS_SERVICE_NAME:
        return
    try:
        ecs = boto3.client("ecs")
        ecs.update_service(
            cluster=ECS_CLUSTER_NAME,
            service=ECS_SERVICE_NAME,
            desiredCount=desired_count,
        )
    except Exception:
        pass


def create_and_activate_wave(
    table: Any,
    events_table: Any,
    tenant_id: str,
    project_id: str,
    pk: str,
    plan: dict[str, Any],
    milestones_data: list[dict[str, Any]],
) -> str:
    """Create a wave for the first goal's MVIs and activate it. Returns wave_id."""
    now = _now_iso()
    wave_id = _wave_id()
    repo: str = str(plan.get("repo", ""))

    goal_id, mvi_ids = _find_first_goal_mvis(table, pk, milestones_data)

    if goal_id and mvi_ids:
        mvis_wave_data = _write_backlog_mvi_snapshots(
            table, pk, wave_id, goal_id, mvi_ids, repo, now
        )
    else:
        directive = str(plan.get("description", "Initial wave"))
        mvis_wave_data = _write_fallback_mvi_snapshot(
            table, pk, wave_id, directive, repo, now
        )

    table.put_item(
        Item={
            "PK": pk,
            "SK": f"S#{wave_id}",
            "level": "wave",
            "status": "planning",
            "human_directive": str(plan.get("description", "Autopilot launch")),
            "progress": {
                "mvis_total": len(mvis_wave_data),
                "mvis_shipped": 0,
                "tasks_done": 0,
                "tasks_total": 0,
            },
            "budget": {"spent": 0, "limit": 20_000_000},
            "created_at": now,
            "entityType": "Snapshot",
        }
    )

    # Transition wave to executing
    table.update_item(
        Key={"PK": pk, "SK": f"S#{wave_id}"},
        UpdateExpression="SET #s = :s, #aa = :aa",
        ExpressionAttributeNames={"#s": "status", "#aa": "activated_at"},
        ExpressionAttributeValues={":s": "executing", ":aa": now},
    )

    # Queue all MVI snapshots
    resp = table.query(
        KeyConditionExpression=DKey("PK").eq(pk)
        & DKey("SK").begins_with(f"S#{wave_id}#m")
    )
    for item in resp.get("Items", []):
        if item.get("level") == "murder" and item.get("status") in ("draft", "refined"):
            table.update_item(
                Key={"PK": pk, "SK": str(item["SK"])},
                UpdateExpression="SET #s = :s",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":s": "queued"},
            )

    mvis_count = len(mvis_wave_data)
    emit_event(
        events_table,
        tenant_id,
        project_id,
        "wave_activated",
        f"Wave activated via Monarch — {mvis_count} MVIs queued",
        "blue",
    )
    emit_event(
        events_table,
        tenant_id,
        project_id,
        "worker_warming",
        "Execution engine warming up (~30s)",
        "yellow",
    )
    _scale_ecs(1)

    return wave_id
