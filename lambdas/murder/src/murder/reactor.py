"""Core orchestration — read state, decide, write next crow.

Two entry points:
- react_to_mvi_queued: initial trigger, assigns planner
- react_to_crow_completion: main loop, chains crow pipeline
"""

from __future__ import annotations

from typing import Any

from murder.blackboard import Blackboard
from murder.context_builder import build_instructions, build_planner_instructions
from murder.contracts import validate_crow_assignment, validate_mvi_ready_to_ship
from murder.cost import check_wave_budget
from murder.enums import CrowStatus, CrowType, MVIStatus
from murder.events import (
    build_budget_exceeded_event,
    build_crow_assigned_event,
    build_mvi_ready_event,
)
from murder.keys import build_pk, build_sk
from murder.logging import StructuredLogger
from murder.models import Cost, CrowSnapshot, WaveBudget, WaveSnapshot
from murder.state_machine import (
    AssignCrow,
    FailMVI,
    MarkMVIReady,
    NoAction,
    determine_next,
)


def react_to_mvi_queued(
    blackboard: Blackboard,
    mvi_item: dict[str, Any],
    logger: StructuredLogger,
) -> None:
    """Initial trigger: MVI queued -> assign planner crow."""
    tenant = _extract_tenant(mvi_item["PK"])
    project = _extract_project(mvi_item["PK"])
    wave_id = _extract_wave_id(mvi_item["SK"])
    mvi_id = _extract_mvi_id(mvi_item["SK"])

    pk = build_pk(tenant, project)
    wave_sk = build_sk(wave_id=wave_id)
    wave_item = blackboard.read(pk, wave_sk)
    if not wave_item:
        logger.error("wave_not_found", wave_id=wave_id)
        return

    wave = WaveSnapshot.from_item(wave_item)

    budget_check = check_wave_budget(wave.budget.spent, 0, wave.budget.limit)
    if budget_check.exceeded:
        _fail_mvi_budget(blackboard, pk, wave_id, mvi_id, mvi_item, wave.budget, logger)
        return

    description = mvi_item.get("description", "")
    instructions = build_planner_instructions(wave.human_directive, description)

    crow_id = _next_crow_id(blackboard, pk, wave_id, mvi_id, CrowType.PLANNER)
    crow = CrowSnapshot(
        tenant=tenant,
        project=project,
        wave_id=wave_id,
        mvi_id=mvi_id,
        crow_id=crow_id,
        crow_type=CrowType.PLANNER,
        status=CrowStatus.PENDING,
        instructions=instructions,
        repo=mvi_item.get("repo", ""),
        branch=mvi_item.get("branch", ""),
        budget_remaining=wave.budget.remaining,
    )

    item = crow.to_item()
    validate_crow_assignment(item)
    blackboard.write_item(item)

    evt = build_crow_assigned_event(
        tenant, project, wave_id, CrowType.PLANNER, "plan"
    )
    blackboard.write_item(evt.to_item())

    mvi_sk = build_sk(wave_id=wave_id, mvi_id=mvi_id)
    blackboard.conditional_status_update(
        pk, mvi_sk, MVIStatus.QUEUED.value, MVIStatus.EXECUTING.value
    )

    logger.event("planner_assigned", crow_id=crow_id, mvi_id=mvi_id)


def react_to_crow_completion(
    blackboard: Blackboard,
    crow_item: dict[str, Any],
    logger: StructuredLogger,
) -> None:
    """Main loop: crow completed/failed -> decide next action."""
    crow_type = CrowType(crow_item["crow_type"])
    crow_status = CrowStatus(crow_item["status"])
    outcome = crow_item.get("outcome")
    retry_count = int(crow_item.get("retry_count", 0))

    tenant = _extract_tenant(crow_item["PK"])
    project = _extract_project(crow_item["PK"])
    wave_id = _extract_wave_id(crow_item["SK"])
    mvi_id = _extract_mvi_id(crow_item["SK"])
    pk = build_pk(tenant, project)

    # Update wave budget with this crow's cost
    crow_cost = _extract_crow_cost(crow_item)
    if crow_cost > 0:
        _increment_wave_budget(blackboard, pk, wave_id, crow_cost)

    action = determine_next(crow_type, crow_status, outcome, retry_count)

    if isinstance(action, AssignCrow):
        _handle_assign(
            blackboard, pk, tenant, project, wave_id, mvi_id,
            action, crow_type, retry_count, outcome, logger,
        )
    elif isinstance(action, MarkMVIReady):
        _handle_mvi_ready(blackboard, pk, tenant, project, wave_id, mvi_id, logger)
    elif isinstance(action, FailMVI):
        _handle_fail_mvi(blackboard, pk, wave_id, mvi_id, action.reason, logger)
    elif isinstance(action, NoAction):
        logger.event("no_action", reason=action.reason, mvi_id=mvi_id)


def _handle_assign(
    blackboard: Blackboard,
    pk: str,
    tenant: str,
    project: str,
    wave_id: str,
    mvi_id: str,
    action: AssignCrow,
    previous_type: CrowType,
    previous_retry_count: int,
    previous_outcome: dict[str, Any] | None,
    logger: StructuredLogger,
) -> None:
    wave_item = blackboard.read(pk, build_sk(wave_id=wave_id))
    if not wave_item:
        logger.error("wave_not_found", wave_id=wave_id)
        return
    wave = WaveSnapshot.from_item(wave_item)

    budget_check = check_wave_budget(wave.budget.spent, 0, wave.budget.limit)
    if budget_check.exceeded:
        mvi_sk = build_sk(wave_id=wave_id, mvi_id=mvi_id)
        mvi_item = blackboard.read(pk, mvi_sk)
        _fail_mvi_budget(
            blackboard, pk, wave_id, mvi_id, mvi_item or {}, wave.budget, logger
        )
        return

    mvi_sk = build_sk(wave_id=wave_id, mvi_id=mvi_id)
    mvi_item = blackboard.read(pk, mvi_sk)
    if not mvi_item:
        logger.error("mvi_not_found", mvi_id=mvi_id)
        return

    is_retry = action.crow_type == previous_type
    retry_count = previous_retry_count + 1 if is_retry else 0

    # For reviewer, find the planner outcome so reviewer sees what was planned
    planner_outcome = None
    if action.crow_type == CrowType.REVIEWER:
        planner_outcome = _find_planner_outcome(blackboard, pk, wave_id, mvi_id)

    instructions = build_instructions(
        action.crow_type, previous_outcome, mvi_item.get("description", ""),
        planner_outcome=planner_outcome,
    )

    crow_id = _next_crow_id(blackboard, pk, wave_id, mvi_id, action.crow_type)
    crow = CrowSnapshot(
        tenant=tenant,
        project=project,
        wave_id=wave_id,
        mvi_id=mvi_id,
        crow_id=crow_id,
        crow_type=action.crow_type,
        status=CrowStatus.PENDING,
        instructions=instructions,
        repo=mvi_item.get("repo", ""),
        branch=mvi_item.get("branch", ""),
        budget_remaining=wave.budget.remaining,
        retry_count=retry_count,
    )

    item = crow.to_item()
    validate_crow_assignment(item)
    blackboard.write_item(item)

    evt = build_crow_assigned_event(
        tenant, project, wave_id, action.crow_type, action.reason
    )
    blackboard.write_item(evt.to_item())

    logger.event(
        "crow_assigned",
        crow_id=crow_id,
        crow_type=action.crow_type.value,
        retry_count=retry_count,
    )


def _handle_mvi_ready(
    blackboard: Blackboard,
    pk: str,
    tenant: str,
    project: str,
    wave_id: str,
    mvi_id: str,
    logger: StructuredLogger,
) -> None:
    mvi_sk = build_sk(wave_id=wave_id, mvi_id=mvi_id)

    crow_sk_prefix = f"S#{wave_id}#m{mvi_id}#cr_"
    crow_items = blackboard.query(pk, crow_sk_prefix)

    total_cost = Cost.zero()
    for ci in crow_items:
        if "cost" in ci and isinstance(ci["cost"], dict):
            total_cost = total_cost + Cost.from_dict(ci["cost"])

    merge_checklist = [
        {"check": "all_crows_completed", "passed": True},
        {"check": "reviewer_approved", "passed": True},
        {"check": "cost_tracked", "passed": total_cost.credits >= 0},
    ]

    mvi_item = blackboard.read(pk, mvi_sk)
    mvi_name = (mvi_item or {}).get("name", mvi_id)

    updates: dict[str, Any] = {
        "status": MVIStatus.READY_TO_SHIP.value,
        "can_ship": True,
        "merge_checklist": merge_checklist,
        "cost": total_cost.to_dict(),
    }

    ready_item = {
        "status": MVIStatus.READY_TO_SHIP.value,
        "can_ship": True,
        "merge_checklist": merge_checklist,
    }
    validate_mvi_ready_to_ship(ready_item)

    blackboard.update(pk, mvi_sk, updates)

    evt = build_mvi_ready_event(tenant, project, wave_id, mvi_name)
    blackboard.write_item(evt.to_item())

    logger.event("mvi_ready_to_ship", mvi_id=mvi_id, cost=total_cost.credits)


def _handle_fail_mvi(
    blackboard: Blackboard,
    pk: str,
    wave_id: str,
    mvi_id: str,
    reason: str,
    logger: StructuredLogger,
) -> None:
    mvi_sk = build_sk(wave_id=wave_id, mvi_id=mvi_id)
    blackboard.update(pk, mvi_sk, {"status": MVIStatus.FAILED.value})
    logger.event("mvi_failed", mvi_id=mvi_id, reason=reason)


def _fail_mvi_budget(
    blackboard: Blackboard,
    pk: str,
    wave_id: str,
    mvi_id: str,
    mvi_item: dict[str, Any],
    budget: WaveBudget,
    logger: StructuredLogger,
) -> None:
    tenant = _extract_tenant(pk)
    project = _extract_project(pk)

    mvi_sk = build_sk(wave_id=wave_id, mvi_id=mvi_id)
    blackboard.update(pk, mvi_sk, {"status": MVIStatus.FAILED.value})

    evt = build_budget_exceeded_event(tenant, project, wave_id, budget.spent, budget.limit)
    blackboard.write_item(evt.to_item())

    logger.event("budget_exceeded", mvi_id=mvi_id, spent=budget.spent, limit=budget.limit)


# --- Budget tracking ---

def _extract_crow_cost(crow_item: dict[str, Any]) -> int:
    """Extract credits (microdollars) from a crow item's cost dict."""
    cost_dict = crow_item.get("cost")
    if not cost_dict or not isinstance(cost_dict, dict):
        return 0
    return int(cost_dict.get("credits", 0))


def _increment_wave_budget(
    blackboard: Blackboard,
    pk: str,
    wave_id: str,
    credits: int,
) -> None:
    """Atomically increment wave.budget.spent using DynamoDB ADD expression."""
    wave_sk = build_sk(wave_id=wave_id)
    blackboard.increment_nested(pk, wave_sk, "budget", "spent", credits)


# --- Planner outcome lookup ---

def _find_planner_outcome(
    blackboard: Blackboard,
    pk: str,
    wave_id: str,
    mvi_id: str,
) -> dict[str, Any] | None:
    """Find the most recent completed planner crow's outcome for this MVI."""
    crow_prefix = f"S#{wave_id}#m{mvi_id}#cr_"
    crows = blackboard.query(pk, crow_prefix)
    for crow in reversed(crows):
        if (
            crow.get("crow_type") == "planner"
            and crow.get("status") == "completed"
            and crow.get("outcome")
        ):
            return crow["outcome"]
    return None


# --- Key parsing helpers ---

def _extract_tenant(pk: str) -> str:
    """Extract tenant from PK format T#{tenant}#P#{project}."""
    parts = pk.split("#")
    return parts[1]


def _extract_project(pk: str) -> str:
    parts = pk.split("#")
    return parts[3]


def _extract_wave_id(sk: str) -> str:
    """Extract wave_id from SK format S#{wave_id}#m{mvi_id}[#{crow_id}]."""
    parts = sk.split("#")
    return parts[1]


def _extract_mvi_id(sk: str) -> str:
    """Extract mvi_id from SK format S#{wave_id}#m{mvi_id}[#{crow_id}]."""
    parts = sk.split("#")
    for part in parts:
        if part.startswith("m"):
            return part[1:]
    raise ValueError(f"Cannot extract mvi_id from SK: {sk}")


def _next_crow_id(
    blackboard: Blackboard,
    pk: str,
    wave_id: str,
    mvi_id: str,
    crow_type: CrowType,
) -> str:
    """Generate next crow ID like cr_plan_01, cr_impl_02."""
    abbrev = {
        CrowType.PLANNER: "plan",
        CrowType.IMPLEMENTER: "impl",
        CrowType.REVIEWER: "rev",
        CrowType.FIXER: "fix",
    }[crow_type]

    sk_prefix = f"S#{wave_id}#m{mvi_id}#cr_"
    existing = blackboard.query(pk, sk_prefix)
    next_num = len(existing) + 1
    return f"cr_{abbrev}_{next_num:02d}"
