"""Monarch agent — core project setup orchestration chain."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import boto3

from monarch.config import DOC_PROMPTS, EVENTS_TABLE_NAME, TABLE_NAME
from monarch.documents import generate_document
from monarch.events import emit_event
from monarch.planner import save_milestones_and_mvis
from monarch.wave_launcher import create_and_activate_wave

log = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_tenant(pk: str) -> str:
    """Extract tenant_id from PK format T#{tenant}#P#{project}."""
    parts = pk.split("#")
    return parts[1]


def _extract_project(pk: str) -> str:
    """Extract project_id from PK format T#{tenant}#P#{project}."""
    parts = pk.split("#")
    return parts[3]


def _update_monarch_status(
    table: Any,
    pk: str,
    sk: str,
    status: str,
    wave_id: str | None = None,
    error: str | None = None,
) -> None:
    updates: dict[str, Any] = {"status": status, "updated_at": _now_iso()}
    if wave_id:
        updates["wave_id"] = wave_id
    if error:
        updates["error"] = error

    expr_parts = [f"#{k.replace('-', '_')} = :{k.replace('-', '_')}" for k in updates]
    names = {f"#{k.replace('-', '_')}": k for k in updates}
    values = {f":{k.replace('-', '_')}": v for k, v in updates.items()}

    table.update_item(
        Key={"PK": pk, "SK": sk},
        UpdateExpression="SET " + ", ".join(expr_parts),
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
    )


def run_monarch(task_item: dict[str, Any]) -> None:
    """Execute the full project setup chain."""
    pk: str = str(task_item["PK"])
    sk: str = str(task_item["SK"])
    tenant_id = _extract_tenant(pk)
    project_id = _extract_project(pk)
    plan: dict[str, Any] = task_item.get("plan", {})
    if isinstance(plan, str):
        plan = json.loads(plan)

    log.info(
        json.dumps(
            {
                "event": "monarch_start",
                "tenant_id": tenant_id,
                "project_id": project_id,
            }
        )
    )

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(TABLE_NAME)
    events_table = dynamodb.Table(EVENTS_TABLE_NAME) if EVENTS_TABLE_NAME else table

    try:
        _update_monarch_status(table, pk, sk, "executing")

        # Phase 1: Generate documents
        for doc_type in DOC_PROMPTS:
            emit_event(
                events_table,
                tenant_id,
                project_id,
                "monarch_progress",
                f"Generating {doc_type} document...",
                "purple",
            )
            generate_document(table, pk, project_id, plan, doc_type)
            emit_event(
                events_table,
                tenant_id,
                project_id,
                "monarch_progress",
                f"{doc_type.capitalize()} document complete",
                "green",
            )

        # Phase 2: Save milestones, goals, MVIs
        emit_event(
            events_table,
            tenant_id,
            project_id,
            "monarch_progress",
            "Planning milestones and goals...",
            "purple",
        )
        milestones_data = save_milestones_and_mvis(table, pk, plan)
        emit_event(
            events_table,
            tenant_id,
            project_id,
            "monarch_progress",
            "Backlog ready",
            "green",
        )

        # Phase 3: Create and activate first wave
        emit_event(
            events_table,
            tenant_id,
            project_id,
            "monarch_progress",
            "Launching first wave...",
            "purple",
        )
        wave_id = create_and_activate_wave(
            table,
            events_table,
            tenant_id,
            project_id,
            pk,
            plan,
            milestones_data,
        )
        emit_event(
            events_table,
            tenant_id,
            project_id,
            "monarch_complete",
            f"Monarch complete — wave {wave_id} executing",
            "green",
        )

        _update_monarch_status(table, pk, sk, "complete", wave_id=wave_id)

        log.info(
            json.dumps(
                {
                    "event": "monarch_complete",
                    "tenant_id": tenant_id,
                    "project_id": project_id,
                    "wave_id": wave_id,
                }
            )
        )

    except Exception as exc:
        error_msg = str(exc)
        log.error(
            json.dumps(
                {
                    "event": "monarch_failed",
                    "tenant_id": tenant_id,
                    "project_id": project_id,
                    "error": error_msg,
                }
            )
        )
        _update_monarch_status(table, pk, sk, "failed", error=error_msg)
        emit_event(
            events_table,
            tenant_id,
            project_id,
            "monarch_error",
            f"Monarch failed: {error_msg}",
            "red",
        )
