"""Council handler — Lambda DDB-stream entry point AND Fargate poll-once entry.

The Lambda path (`lambda_handler`) is the legacy entry; Task 29 will remove it.
The Fargate path (`process_pending_session`) is invoked by apps/council/main.py
and processes one pending COUNCIL# row end-to-end.
"""

from __future__ import annotations

import json
import logging
import os
import traceback
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import boto3

from council._blackboard import Blackboard
from council.actions import execute_decision, execute_planning_decision
from council.config import EVENTS_TABLE_NAME, TABLE_NAME
from council.enums import AdvisorType
from council.memory_store import CouncilMemoryStore
from council.orchestrator import run_council_session, run_council_session_async
from council.overrides import HumanOverride, apply_override
from council.reflection import extract_learnings

logger = logging.getLogger("council")
logger.setLevel(logging.INFO)


def _dynamo_safe(obj: Any) -> Any:
    """Convert floats to Decimal for DynamoDB compatibility."""
    return json.loads(json.dumps(obj), parse_float=Decimal)


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
    """Route council tasks: voting sessions or human overrides."""
    session_type = item.get("type", "wave_review")

    if session_type == "override":
        _process_override(item)
    else:
        _process_voting_session(item)


def _process_voting_session(item: dict[str, Any]) -> None:
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
            "decision": _dynamo_safe(result.decision.to_dict()),
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


def _process_override(item: dict[str, Any]) -> None:
    """Apply a human override and execute the resulting decision."""
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(TABLE_NAME)
    events_table = dynamodb.Table(EVENTS_TABLE_NAME) if EVENTS_TABLE_NAME else table
    blackboard = Blackboard(table, events_table=events_table)

    pk = item["PK"]
    sk = item["SK"]
    wave_id = item.get("wave_id", "")
    auto_mode = item.get("auto_mode", "supervised")
    context = item.get("context", {})
    override_data = item.get("override", {})
    original_session_id = item.get("original_session_id", "")

    # Mark override task as processing
    blackboard.update(pk, sk, {"status": "processing"})

    # Build the override object
    override = HumanOverride(
        action=override_data.get("action", ""),
        reason=override_data.get("reason", ""),
        advisor_overridden=override_data.get("advisor_overridden", ""),
        constraint=override_data.get("constraint", ""),
        question=override_data.get("question", ""),
        wave_plan=override_data.get("wave_plan"),
        timestamp=override_data.get("timestamp", ""),
    )

    # Apply override to the original session
    original_sk = f"COUNCIL#{original_session_id}"
    original_session = blackboard.read(pk, original_sk)
    session_type = original_session.get("type", "wave_review") if original_session else "wave_review"

    decision = apply_override(
        blackboard=blackboard,
        pk=pk,
        session_sk=original_sk,
        wave_id=wave_id,
        override=override,
        session_type=session_type,
        context=context,
    )

    # Mark override task as completed
    blackboard.update(
        pk,
        sk,
        {
            "status": "completed",
            "decision": _dynamo_safe(decision.to_dict()),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    # Execute the decision (unless it's a request_round — that needs a new session)
    if override.action == "request_round":
        # Write a new council task with the human's question
        import uuid

        new_session_id = f"hr_{uuid.uuid4().hex[:8]}"
        blackboard.write_item(
            {
                "PK": pk,
                "SK": f"COUNCIL#{new_session_id}",
                "level": "council",
                "status": "pending",
                "type": session_type,
                "wave_id": wave_id,
                "auto_mode": auto_mode,
                "context": {
                    **context,
                    "human_question": override.question,
                    "previous_session": original_session_id,
                },
                "entityType": "Snapshot",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    elif session_type == "wave_planning":
        execute_planning_decision(
            blackboard=blackboard,
            pk=pk,
            session_id=original_session_id,
            decision=decision,
            context=context,
        )
    else:
        execute_decision(
            blackboard=blackboard,
            pk=pk,
            wave_id=wave_id,
            session_id=original_session_id,
            decision=decision,
            auto_mode=auto_mode,
        )


# ---------------------------------------------------------------------------
# Fargate path: process one pending COUNCIL# session end-to-end.
# ---------------------------------------------------------------------------

_fargate_logger = logging.getLogger("council.handler.fargate")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit_pipeline_error(
    blackboard: Any,
    project_id: str,
    session_id: str,
    wave_id: str,
    phase: str,
    error_class: str,
    error_message: str,
    traceback_head: str = "",
    final: bool = False,
) -> None:
    now = _now()
    blackboard.write_event(
        {
            "PK": f"P#{project_id}",
            "SK": f"E#{now}#{session_id[-8:]}",
            "event_type": "council_pipeline_error",
            "phase": phase,
            "error_class": error_class,
            "error_message": error_message[:1000],
            "traceback_head": traceback_head[:1000],
            "wave_id": wave_id,
            "session_id": session_id,
            "final": final,
            "created_at": now,
        }
    )
    _fargate_logger.error(
        json.dumps(
            {
                "event": "council_pipeline_error",
                "phase": phase,
                "wave_id": wave_id,
                "session_id": session_id,
                "error_class": error_class,
                "final": final,
            }
        )
    )


async def process_pending_session(
    blackboard: Any,
    project_id: str,
    session_sk: str,
) -> None:
    """Process one pending Council session: load packet, run advisors, write decision."""
    pk = f"P#{project_id}"
    session = blackboard.read(pk, session_sk)
    if not session or session.get("status") != "pending":
        return

    session_id = session_sk.replace("COUNCIL#", "")
    wave_id = session.get("wave_id", "")

    blackboard.update(pk, session_sk, {"status": "running", "started_at": _now()})

    findings = blackboard.read(pk, session.get("integration_sk", ""))
    if not findings:
        _emit_pipeline_error(
            blackboard=blackboard,
            project_id=project_id,
            session_id=session_id,
            wave_id=wave_id,
            phase="council-load-findings",
            error_class="MissingFindings",
            error_message=(
                f"no INTEGRATION row at {session.get('integration_sk', '')}"
            ),
            final=True,
        )
        blackboard.update(
            pk, session_sk, {"status": "errored", "completed_at": _now()}
        )
        return

    packet = {
        "wave_id": wave_id,
        "project_id": project_id,
        "integration_findings": findings,
        "pr_numbers": findings.get("pr_numbers", []),
    }
    context = {
        "repo_path": os.environ.get("REPO_PATH", "/mnt/repos/T/dev-tenant/repo"),
        "repo": os.environ.get("GITHUB_REPO", ""),
        "github_token": os.environ.get("GITHUB_TOKEN", ""),
        "worktree_paths": {
            int(k): v for k, v in (findings.get("worktree_paths") or {}).items()
        },
        "integration_path": findings.get("integration_worktree", ""),
    }

    pipeline_errors = 0
    try:
        result = await run_council_session_async(packet=packet, context=context)
    except Exception as e:  # noqa: BLE001 -- loud-fail catch with pipeline_error emission
        _emit_pipeline_error(
            blackboard=blackboard,
            project_id=project_id,
            session_id=session_id,
            wave_id=wave_id,
            phase="council-orchestrator",
            error_class=type(e).__name__,
            error_message=str(e),
            traceback_head=traceback.format_exc()[:1000],
            final=True,
        )
        blackboard.update(
            pk, session_sk, {"status": "errored", "completed_at": _now()}
        )
        return

    try:
        learnings = extract_learnings(result)
        memory_store = CouncilMemoryStore(blackboard)
        tenant, project = _safe_extract_tenant_project(pk, project_id)
        for advisor_type, advisor_learnings in learnings.items():
            for learning in advisor_learnings:
                memory_store.append_advisor_learning(
                    tenant, project, advisor_type, learning
                )
    except Exception as e:  # noqa: BLE001 -- reflection failures are non-fatal but loud
        _emit_pipeline_error(
            blackboard=blackboard,
            project_id=project_id,
            session_id=session_id,
            wave_id=wave_id,
            phase="council-reflection",
            error_class=type(e).__name__,
            error_message=str(e),
            traceback_head=traceback.format_exc()[:1000],
            final=False,
        )
        pipeline_errors += 1

    pipeline_health = "degraded" if pipeline_errors >= 2 else "ok"
    blackboard.update(
        pk,
        session_sk,
        {
            "status": "completed",
            "completed_at": _now(),
            "decision": _dynamo_safe(result.decision.to_dict()),
            "rounds": _dynamo_safe([r.to_dict() for r in result.rounds]),
            "cost": result.total_cost.to_dict(),
            "pipeline_health": pipeline_health,
        },
    )

    blackboard.write_event(
        {
            "PK": pk,
            "SK": f"E#{_now()}#{session_id[-8:]}",
            "event_type": "council_decision",
            "wave_id": wave_id,
            "session_id": session_id,
            "decision_action": result.decision.action.value,
            "confidence": result.decision.confidence,
            "pipeline_health": pipeline_health,
            "created_at": _now(),
        }
    )


def _safe_extract_tenant_project(pk: str, project_id: str) -> tuple[str, str]:
    """Map PK to (tenant, project) for memory-store calls.

    Stage 4 PKs are `P#{project_id}` (single-tenant); for now route memory under
    a synthetic tenant slot so the existing CouncilMemoryStore API works
    unchanged.
    """
    if pk.startswith("T#") and "#P#" in pk:
        return _extract_tenant_project(pk)
    return ("default", project_id)
