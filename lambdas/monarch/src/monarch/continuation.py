"""Monarch continuation mode — reflection, maturity check, budget, council planning."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import boto3

from monarch.config import EVENTS_TABLE_NAME, TABLE_NAME
from monarch.events import emit_event
from monarch.maturity import assess_maturity, gather_project_signals
from monarch.reflection import reflect_on_wave, save_wave_reflection
from monarch.wave_launcher import create_and_activate_wave


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _short_id() -> str:
    return uuid.uuid4().hex[:8]


def _get_table() -> Any:
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(TABLE_NAME)


def _get_events_table() -> Any:
    dynamodb = boto3.resource("dynamodb")
    name = EVENTS_TABLE_NAME
    return dynamodb.Table(name) if name else _get_table()


def run_monarch_continuation(task_item: dict[str, Any]) -> None:
    """Continuation mode: reflect, check budget, trigger council planning."""
    table = _get_table()
    events_table = _get_events_table()

    pk = task_item["PK"]
    sk = task_item["SK"]
    parts = pk.split("#")
    tenant_id = parts[1]
    project_id = parts[3]

    _update_status(table, pk, sk, "executing")

    emit_event(
        events_table,
        tenant_id,
        project_id,
        "monarch_continuation",
        "Starting continuation planning",
        "purple",
    )

    backlog_remaining = task_item.get("backlog_remaining", [])

    # Check if backlog is empty — project complete
    if not backlog_remaining:
        _update_status(
            table, pk, sk, "complete", note="Backlog empty — project complete"
        )
        emit_event(
            events_table,
            tenant_id,
            project_id,
            "project_complete",
            "All goals delivered",
            "green",
        )
        return

    # Read project root for settings
    root = table.get_item(Key={"PK": pk, "SK": "S#"}).get("Item", {})

    # Maturity assessment — update stage if warranted
    current_stage = root.get("maturity_stage", "mvp")
    signals = gather_project_signals(table, pk)
    new_stage = assess_maturity(
        current_stage=current_stage,
        waves_delivered=signals["waves_delivered"],
        mvis_shipped=signals["mvis_shipped"],
        avg_coverage=signals.get("avg_coverage"),
        council_rejection_rate=signals.get("council_rejection_rate"),
    )
    if new_stage != current_stage:
        table.update_item(
            Key={"PK": pk, "SK": "S#"},
            UpdateExpression="SET #ms = :ms",
            ExpressionAttributeNames={"#ms": "maturity_stage"},
            ExpressionAttributeValues={":ms": new_stage},
        )
        emit_event(
            events_table,
            tenant_id,
            project_id,
            "maturity_stage_updated",
            f"Project maturity: {current_stage} -> {new_stage}",
            "blue",
        )

    # Reflection — analyze delivered wave and extract project learnings
    delivered_wave_id = task_item.get("delivered_wave_id", "")
    council_decision = task_item.get("council_decision", {})
    if delivered_wave_id:
        learnings = reflect_on_wave(table, pk, delivered_wave_id, council_decision)
        if learnings:
            save_wave_reflection(table, pk, learnings)
            emit_event(
                events_table,
                tenant_id,
                project_id,
                "wave_reflection",
                f"Extracted {len(learnings)} learnings from wave {delivered_wave_id}",
                "purple",
            )

    # Write COUNCIL#wave_planning task
    session_id = f"wp_{_short_id()}"
    council_item: dict[str, Any] = {
        "PK": pk,
        "SK": f"COUNCIL#{session_id}",
        "level": "council",
        "status": "pending",
        "type": "wave_planning",
        "auto_mode": root.get("auto_mode", "auto"),
        "context": {
            "delivered_wave_id": task_item.get("delivered_wave_id", ""),
            "council_feedback": task_item.get("council_decision", {}),
            "backlog_remaining": backlog_remaining,
            "project_maturity": root.get("maturity_stage", "mvp"),
            "human_directive": root.get("human_directive", ""),
        },
        "entityType": "Snapshot",
        "created_at": _now_iso(),
    }
    table.put_item(Item=council_item)

    emit_event(
        events_table,
        tenant_id,
        project_id,
        "council_planning_triggered",
        "Council planning next wave",
        "blue",
    )

    _update_status(
        table, pk, sk, "waiting_council", wave_planning_session=session_id
    )


def run_monarch_wave_launch(task_item: dict[str, Any]) -> None:
    """Wave launch mode: create wave from council-approved plan."""
    table = _get_table()
    events_table = _get_events_table()

    pk = task_item["PK"]
    sk = task_item["SK"]
    parts = pk.split("#")
    tenant_id = parts[1]
    project_id = parts[3]

    _update_status(table, pk, sk, "executing")

    wave_plan = task_item.get("wave_plan", {})
    mvi_ids = wave_plan.get("mvi_ids", [])
    goal_id = wave_plan.get("goal_id", "")

    if not mvi_ids:
        _update_status(table, pk, sk, "failed", error="No MVIs in wave plan")
        return

    root = table.get_item(Key={"PK": pk, "SK": "S#"}).get("Item", {})
    plan = {
        "description": wave_plan.get(
            "human_directive", root.get("human_directive", "")
        ),
        "repo": root.get("repo", ""),
        "milestones": [],
    }

    milestones_data = [{"goals": [{"id": goal_id, "mvis": mvi_ids}]}]

    wave_id = create_and_activate_wave(
        table=table,
        events_table=events_table,
        tenant_id=tenant_id,
        project_id=project_id,
        pk=pk,
        plan=plan,
        milestones_data=milestones_data,
    )

    _update_status(table, pk, sk, "complete", wave_id=wave_id)
    emit_event(
        events_table,
        tenant_id,
        project_id,
        "wave_launched",
        f"Wave {wave_id} launched via auto mode",
        "green",
    )


def _update_status(
    table: Any,
    pk: str,
    sk: str,
    status: str,
    wave_id: str | None = None,
    error: str | None = None,
    note: str | None = None,
    wave_planning_session: str | None = None,
) -> None:
    names: dict[str, str] = {"#s": "status"}
    values: dict[str, Any] = {":s": status}
    expr_parts = ["#s = :s"]

    if wave_id:
        expr_parts.append("#w = :w")
        names["#w"] = "wave_id"
        values[":w"] = wave_id
    if error:
        expr_parts.append("#e = :e")
        names["#e"] = "error"
        values[":e"] = error
    if note:
        expr_parts.append("#n = :n")
        names["#n"] = "note"
        values[":n"] = note
    if wave_planning_session:
        expr_parts.append("#wps = :wps")
        names["#wps"] = "wave_planning_session"
        values[":wps"] = wave_planning_session

    table.update_item(
        Key={"PK": pk, "SK": sk},
        UpdateExpression="SET " + ", ".join(expr_parts),
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
    )
