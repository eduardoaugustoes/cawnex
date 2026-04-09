"""Post-decision actions — deliver wave, steer wave, write continuation task."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from council._blackboard import Blackboard
from council.enums import DecisionAction
from council.models import CouncilDecision


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _short_id() -> str:
    return uuid.uuid4().hex[:8]


def _dynamo_safe(obj: Any) -> Any:
    """Convert floats to Decimal for DynamoDB compatibility."""
    return json.loads(json.dumps(obj), parse_float=Decimal)


def execute_decision(
    blackboard: Blackboard,
    pk: str,
    wave_id: str,
    session_id: str,
    decision: CouncilDecision,
    auto_mode: str,
) -> None:
    """Execute the council's wave review decision."""
    if decision.action in (
        DecisionAction.APPROVE,
        DecisionAction.APPROVE_WITH_CONDITIONS,
    ):
        _deliver_wave(blackboard, pk, wave_id)
        _write_continuation_task(blackboard, pk, wave_id, decision)
    elif decision.action == DecisionAction.REJECT:
        _steer_wave(blackboard, pk, wave_id, decision)
    elif decision.action == DecisionAction.ESCALATE:
        if auto_mode == "supervised":
            _notify_human(blackboard, pk, wave_id, decision)
        else:
            # In full auto, Monarch makes the final call — treat as approve
            _deliver_wave(blackboard, pk, wave_id)
            _write_continuation_task(blackboard, pk, wave_id, decision)


def execute_planning_decision(
    blackboard: Blackboard,
    pk: str,
    session_id: str,
    decision: CouncilDecision,
    context: dict[str, Any],
) -> None:
    """Execute wave planning decision — write MONARCH#wave_launch task."""
    if decision.action in (
        DecisionAction.APPROVE,
        DecisionAction.APPROVE_WITH_CONDITIONS,
    ):
        launch_id = f"wave_launch_{_short_id()}"
        blackboard.write_item(
            {
                "PK": pk,
                "SK": f"MONARCH#{launch_id}",
                "status": "pending",
                "mode": "wave_launch",
                "wave_plan": _dynamo_safe(
                    {
                        "mvi_ids": decision.wave_plan,
                        "goal_id": context.get("goal_id", ""),
                        "human_directive": context.get("human_directive", ""),
                        "ordering_constraints": decision.ordering_constraints,
                        "conditions": decision.conditions,
                    }
                ),
                "council_session": session_id,
                "created_at": _now_iso(),
                "entityType": "Snapshot",
            }
        )
    elif decision.action == DecisionAction.REJECT:
        blackboard.write_event(
            {
                "PK": pk,
                "SK": f"ESCALATION#{_short_id()}",
                "type": "planning_rejected",
                "decision": _dynamo_safe(decision.to_dict()),
                "created_at": _now_iso(),
                "entityType": "Event",
            }
        )


def _deliver_wave(blackboard: Blackboard, pk: str, wave_id: str) -> None:
    blackboard.update(
        pk,
        f"S#{wave_id}",
        {
            "status": "delivered",
            "delivered_at": _now_iso(),
        },
    )


def _steer_wave(
    blackboard: Blackboard,
    pk: str,
    wave_id: str,
    decision: CouncilDecision,
) -> None:
    blackboard.update(
        pk,
        f"S#{wave_id}",
        {
            "status": "steered",
            "council_feedback": {
                "flagged_mvis": decision.flagged_mvis,
                "reasoning": decision.reasoning,
            },
        },
    )


def _write_continuation_task(
    blackboard: Blackboard,
    pk: str,
    wave_id: str,
    decision: CouncilDecision,
) -> None:
    backlog_item = blackboard.read(pk, "BACKLOG#milestones")
    backlog_remaining = backlog_item.get("milestones", []) if backlog_item else []

    root = blackboard.read(pk, "S#")
    project_memory = root.get("project_memory", "") if root else ""

    continuation_id = f"continuation_{_short_id()}"
    blackboard.write_item(
        {
            "PK": pk,
            "SK": f"MONARCH#{continuation_id}",
            "status": "pending",
            "mode": "continuation",
            "delivered_wave_id": wave_id,
            "council_decision": _dynamo_safe(decision.to_dict()),
            "backlog_remaining": backlog_remaining,
            "project_memory": project_memory,
            "created_at": _now_iso(),
            "entityType": "Snapshot",
        }
    )


def _notify_human(
    blackboard: Blackboard,
    pk: str,
    wave_id: str,
    decision: CouncilDecision,
) -> None:
    """Write a human notification event for escalation in supervised mode."""
    blackboard.write_event(
        {
            "PK": pk,
            "SK": f"ESCALATION#{_short_id()}",
            "type": "council_escalation",
            "wave_id": wave_id,
            "decision": decision.to_dict(),
            "created_at": _now_iso(),
            "entityType": "Event",
        }
    )
