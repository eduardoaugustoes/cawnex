"""Council Lambda handler — DynamoDB Stream entry point."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import boto3

from council._blackboard import Blackboard
from council.actions import execute_decision, execute_planning_decision
from council.config import EVENTS_TABLE_NAME, TABLE_NAME
from council.memory_store import CouncilMemoryStore
from council.orchestrator import run_council_session
from council.reflection import extract_learnings

logger = logging.getLogger("council")
logger.setLevel(logging.INFO)


def _deserialize(item: dict[str, Any]) -> dict[str, Any]:
    """Convert DynamoDB Stream format to plain dict."""
    result: dict[str, Any] = {}
    for key, val in item.items():
        if "S" in val:
            result[key] = val["S"]
        elif "N" in val:
            result[key] = val["N"]
        elif "BOOL" in val:
            result[key] = val["BOOL"]
        elif "NULL" in val:
            result[key] = None
        elif "M" in val:
            result[key] = _deserialize(val["M"])
        elif "L" in val:
            result[key] = [
                (
                    _deserialize({"_": v})["_"]
                    if isinstance(v, dict)
                    and any(k in v for k in ("S", "N", "BOOL", "NULL", "M", "L"))
                    else v
                )
                for v in val["L"]
            ]
    return result


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, int]:
    processed = 0
    skipped = 0

    for record in event.get("Records", []):
        if record.get("eventName") != "INSERT":
            skipped += 1
            continue

        new_image = record.get("dynamodb", {}).get("NewImage")
        if not new_image:
            skipped += 1
            continue

        item = _deserialize(new_image)

        if item.get("status") != "pending":
            skipped += 1
            continue

        try:
            _process_council_task(item)
            processed += 1
        except Exception:
            logger.exception("Council task failed: %s", item.get("SK"))
            skipped += 1

    return {"processed": processed, "skipped": skipped}


def _extract_tenant_project(pk: str) -> tuple[str, str]:
    """Extract tenant and project from PK format T#{tenant}#P#{project}."""
    parts = pk.split("#")
    return parts[1], parts[3]


def _process_council_task(item: dict[str, Any]) -> None:
    """Run the full council session and execute the decision."""
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(TABLE_NAME)
    events_table = dynamodb.Table(EVENTS_TABLE_NAME) if EVENTS_TABLE_NAME else table
    blackboard = Blackboard(table, events_table=events_table)

    pk = item["PK"]
    sk = item["SK"]
    wave_id = item.get("wave_id", "")
    session_id = sk.replace("COUNCIL#", "")
    auto_mode = item.get("auto_mode", "auto")
    context = item.get("context", {})
    session_type = item.get("type", "wave_review")
    tenant, project = _extract_tenant_project(pk)

    # Mark as voting
    blackboard.update(pk, sk, {"status": "voting"})

    # Load all memory layers for advisors
    memory_store = CouncilMemoryStore(blackboard)
    advisor_memories = memory_store.read_all_advisor_memories(tenant, project)
    org_standards = memory_store.read_org_standards(tenant)
    project_context = memory_store.read_project_context(tenant, project)

    # Run the council session with full 5-layer prompt context
    result = run_council_session(
        decision_context=context,
        advisor_memories=advisor_memories,
        org_standards=org_standards,
        project_context=project_context,
    )

    # Save full council session with cost tracking
    session_cost = result.total_cost
    blackboard.update(
        pk,
        sk,
        {
            "status": result.status.value,
            "rounds": [r.to_dict() for r in result.rounds],
            "decision": result.decision.to_dict(),
            "cost": session_cost.to_dict(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    # Post-session reflection: extract learnings and update advisor memories
    learnings = extract_learnings(result)
    for advisor_type, advisor_learnings in learnings.items():
        for learning in advisor_learnings:
            memory_store.append_advisor_learning(
                tenant, project, advisor_type, learning
            )

    # Execute the decision based on session type
    if session_type == "wave_planning":
        execute_planning_decision(
            blackboard=blackboard,
            pk=pk,
            session_id=session_id,
            decision=result.decision,
            context=context,
        )
    else:
        execute_decision(
            blackboard=blackboard,
            pk=pk,
            wave_id=wave_id,
            session_id=session_id,
            decision=result.decision,
            auto_mode=auto_mode,
        )
