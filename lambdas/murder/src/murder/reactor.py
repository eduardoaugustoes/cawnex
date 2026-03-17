"""Core orchestration — read state, decide, write next crow.

Two entry points:
- react_to_mvi_queued: initial trigger, assigns planner
- react_to_crow_completion: main loop, chains crow pipeline
"""

from __future__ import annotations

from typing import Any

from murder.blackboard import Blackboard
from murder.config import EVENT_TTL_DAYS
from murder.context_builder import (
    build_instructions,
    build_planner_instructions,
    build_planner_split_instructions,
)
from murder.contracts import (
    validate_crow_assignment,
    validate_human_task,
    validate_mvi_ready_to_ship,
)
from murder.cost import check_wave_budget
from murder.enums import (
    CrowStatus,
    CrowType,
    HumanTaskStatus,
    HumanTaskSubtype,
    MVIStatus,
    WaveStatus,
)
from murder.events import (
    build_budget_exceeded_event,
    build_crow_assigned_event,
    build_human_task_completed_event,
    build_human_task_created_event,
    build_mvi_ready_event,
    build_task_blocked_event,
    build_task_unblocked_event,
)
from murder.keys import build_pk, build_sk
from murder.logging import StructuredLogger
from murder.memory_store import MemoryStore
from murder.models import (
    Cost,
    CrowSnapshot,
    HumanTaskSnapshot,
    WaveBudget,
    WaveSnapshot,
)
from murder.reflection import reflect_on_crow
from murder.state_machine import (
    AssignCrow,
    CreateHumanTasks,
    FailMVI,
    MarkMVIReady,
    NoAction,
    SplitRequired,
    determine_next,
)
from murder.vault_client import has_secret, list_required_secrets


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
    blackboard.write_event(evt.to_events_item(EVENT_TTL_DAYS))

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

    split_count = _count_completed_planners(blackboard, pk, wave_id, mvi_id)
    fix_count = _count_completed_fixers(blackboard, pk, wave_id, mvi_id)
    action = determine_next(crow_type, crow_status, outcome, retry_count, split_count, fix_count)

    if isinstance(action, AssignCrow):
        _handle_assign(
            blackboard, pk, tenant, project, wave_id, mvi_id,
            action, crow_type, retry_count, outcome, logger,
        )
    elif isinstance(action, CreateHumanTasks):
        _handle_create_human_tasks(
            blackboard, pk, tenant, project, wave_id, mvi_id, action, outcome, logger,
        )
    elif isinstance(action, SplitRequired):
        _handle_split_required(
            blackboard, pk, tenant, project, wave_id, mvi_id, action, logger,
        )
    elif isinstance(action, MarkMVIReady):
        _handle_mvi_ready(blackboard, pk, tenant, project, wave_id, mvi_id, logger)
    elif isinstance(action, FailMVI):
        _handle_fail_mvi(blackboard, pk, wave_id, mvi_id, action.reason, logger)
    elif isinstance(action, NoAction):
        logger.event("no_action", reason=action.reason, mvi_id=mvi_id)

    # Post-execution reflection: extract learnings and update agent memory
    memory_store = MemoryStore(blackboard)
    learnings = reflect_on_crow(
        memory_store, tenant, project, crow_type.value, outcome or {}, crow_status.value
    )
    if learnings:
        logger.event("reflection_stored", crow_type=crow_type.value, learnings=len(learnings))


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
    fixer_outcome = None
    if action.crow_type == CrowType.REVIEWER:
        planner_outcome = _find_planner_outcome(blackboard, pk, wave_id, mvi_id)
        # When assigning reviewer after a fixer, pass what the fixer changed
        if previous_type == CrowType.FIXER:
            fixer_outcome = previous_outcome

    # For fixer, build history of previous fix cycles so it avoids repeating failed approaches
    fix_history = None
    if action.crow_type == CrowType.FIXER:
        fix_history = _find_fix_history(blackboard, pk, wave_id, mvi_id)

    instructions = build_instructions(
        action.crow_type, previous_outcome, mvi_item.get("description", ""),
        planner_outcome=planner_outcome,
        fix_history=fix_history,
        iteration=retry_count + 1,
        fixer_outcome=fixer_outcome,
    )

    # Check for required secrets — if missing, create human task and block
    required_secrets = list_required_secrets(instructions)
    missing_secrets = [
        s for s in required_secrets
        if not has_secret(blackboard, tenant, project, s)
    ]
    if missing_secrets:
        for secret_name in missing_secrets:
            _create_human_task(
                blackboard, tenant, project, wave_id, mvi_id,
                task_def={
                    "id": f"ht_secret_{secret_name}",
                    "task_type": "human",
                    "human_task_subtype": "provide_secret",
                    "ask": f"Provide secret: {secret_name}",
                    "instructions": f"This task requires the secret '{secret_name}'. Please provide it in the vault.",
                    "input_schema": {
                        secret_name: {
                            "type": "secret",
                            "label": secret_name,
                            "required": True,
                        },
                    },
                },
                logger=logger,
            )
        # Mark that we're blocked — don't dispatch the crow
        evt = build_task_blocked_event(
            tenant, project, wave_id,
            crow_id=f"next_{action.crow_type.value}",
            blocker_ref=f"secrets:{','.join(missing_secrets)}",
            reason=f"Missing secrets: {', '.join(missing_secrets)}",
        )
        blackboard.write_event(evt.to_events_item(EVENT_TTL_DAYS))
        logger.event(
            "crow_blocked_on_secrets",
            secrets=missing_secrets,
            mvi_id=mvi_id,
        )
        return

    # Inject agent specialization memory so the crow benefits from past learnings
    memory_store = MemoryStore(blackboard)
    agent_memory = memory_store.read_memory(
        tenant, project, f"agent#{action.crow_type.value}"
    )
    if agent_memory:
        instructions = (
            f"{instructions}\n\n"
            f"## Agent Memory (learnings from previous executions)\n{agent_memory}"
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
    blackboard.write_event(evt.to_events_item(EVENT_TTL_DAYS))

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
    blackboard.write_event(evt.to_events_item(EVENT_TTL_DAYS))

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


def _handle_split_required(
    blackboard: Blackboard,
    pk: str,
    tenant: str,
    project: str,
    wave_id: str,
    mvi_id: str,
    action: SplitRequired,
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

    instructions = build_planner_split_instructions(
        action.oversized_tasks,
        wave.human_directive,
        mvi_item.get("description", ""),
    )

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
        tenant, project, wave_id, CrowType.PLANNER, action.reason
    )
    blackboard.write_event(evt.to_events_item(EVENT_TTL_DAYS))

    logger.event("planner_split_assigned", crow_id=crow_id, mvi_id=mvi_id)


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
    blackboard.write_event(evt.to_events_item(EVENT_TTL_DAYS))

    logger.event("budget_exceeded", mvi_id=mvi_id, spent=budget.spent, limit=budget.limit)


# --- Human task handling ---

def react_to_human_task_completed(
    blackboard: Blackboard,
    ht_item: dict[str, Any],
    logger: StructuredLogger,
) -> None:
    """Triggered when a human task transitions to completed.

    Performs staleness guards, then unblocks dependent crow tasks.
    """
    tenant = _extract_tenant(ht_item["PK"])
    project = _extract_project(ht_item["PK"])
    sk = ht_item["SK"]
    sk_parts = sk.split("#")
    wave_id = sk_parts[1]
    mvi_id = sk_parts[2][1:]  # strip leading 'm'
    human_task_id = ht_item.get("id", sk_parts[3])

    pk = build_pk(tenant, project)

    # Staleness guard 1: wave must be executing or paused
    wave_item = blackboard.read(pk, build_sk(wave_id=wave_id))
    if not wave_item:
        logger.event("stale_unblock", reason="wave_not_found", wave_id=wave_id)
        return
    wave = WaveSnapshot.from_item(wave_item)
    if wave.status not in (WaveStatus.EXECUTING, WaveStatus.PAUSED):
        logger.event(
            "stale_unblock",
            reason=f"wave is {wave.status.value}",
            wave_id=wave_id,
        )
        return

    # Staleness guard 2: MVI must be in active state
    mvi_sk = build_sk(wave_id=wave_id, mvi_id=mvi_id)
    mvi_item = blackboard.read(pk, mvi_sk)
    if not mvi_item:
        logger.event("stale_unblock", reason="mvi_not_found", mvi_id=mvi_id)
        return
    mvi_status = mvi_item.get("status", "")
    if mvi_status not in ("executing", "queued", "blocked"):
        logger.event(
            "stale_unblock",
            reason=f"MVI is {mvi_status}",
            mvi_id=mvi_id,
        )
        return

    # Staleness guard 3: budget
    if wave.budget.is_exceeded:
        logger.event(
            "stale_unblock",
            reason="budget exhausted",
            wave_id=wave_id,
        )
        return

    # Write completion event
    evt = build_human_task_completed_event(
        tenant, project, wave_id, human_task_id,
        ht_item.get("ask", ""),
    )
    blackboard.write_event(evt.to_events_item(EVENT_TTL_DAYS))

    # Find blocked tasks that reference this human task
    blocks = ht_item.get("blocks", [])
    steer = ht_item.get("steer")

    _check_and_unblock(
        blackboard, tenant, project, wave_id, mvi_id,
        human_task_id, blocks, steer, mvi_item, wave, logger,
    )

    logger.event(
        "human_task_completed",
        human_task_id=human_task_id,
        blocks_count=len(blocks),
    )


def _handle_create_human_tasks(
    blackboard: Blackboard,
    pk: str,
    tenant: str,
    project: str,
    wave_id: str,
    mvi_id: str,
    action: CreateHumanTasks,
    planner_outcome: dict[str, Any] | None,
    logger: StructuredLogger,
) -> None:
    """Create human task snapshots and dispatch non-blocked crow tasks."""
    # Create human task snapshots
    human_task_ids = []
    for task_def in action.human_tasks:
        ht_id = _create_human_task(
            blackboard, tenant, project, wave_id, mvi_id, task_def, logger,
        )
        human_task_ids.append(ht_id)

    # Dispatch non-blocked crow tasks (implementer)
    if action.crow_tasks:
        # There are crow tasks that can proceed without waiting for human tasks
        crow_action = AssignCrow(CrowType.IMPLEMENTER, reason="planner completed — dispatching non-blocked tasks")
        _handle_assign(
            blackboard, pk, tenant, project, wave_id, mvi_id,
            crow_action, CrowType.PLANNER, 0, planner_outcome, logger,
        )
    else:
        logger.event(
            "all_tasks_human",
            mvi_id=mvi_id,
            human_task_count=len(human_task_ids),
        )


def _create_human_task(
    blackboard: Blackboard,
    tenant: str,
    project: str,
    wave_id: str,
    mvi_id: str,
    task_def: dict[str, Any],
    logger: StructuredLogger,
) -> str:
    """Write a HumanTaskSnapshot and notification event. Returns the task ID."""
    human_task_id = task_def.get("id", f"ht_{wave_id}_{mvi_id}_{len(task_def)}")
    subtype_str = task_def.get("human_task_subtype", "fill_content")
    subtype = HumanTaskSubtype(subtype_str)

    ht = HumanTaskSnapshot(
        tenant=tenant,
        project=project,
        wave_id=wave_id,
        mvi_id=mvi_id,
        human_task_id=human_task_id,
        subtype=subtype,
        status=HumanTaskStatus.NOTIFIED,
        ask=task_def.get("ask", ""),
        instructions=task_def.get("instructions", ""),
        input_schema=task_def.get("input_schema", {}),
        verification=task_def.get("verification"),
        blocks=task_def.get("blocks", []),
        estimated_human_hours=float(task_def.get("estimated_human_hours", 0)),
        deadline_hint=task_def.get("deadline_hint", ""),
    )

    item = ht.to_item()
    validate_human_task(item)
    blackboard.write_item(item)

    evt = build_human_task_created_event(
        tenant, project, wave_id, human_task_id, subtype,
        task_def.get("ask", ""),
    )
    blackboard.write_event(evt.to_events_item(EVENT_TTL_DAYS))

    logger.event("human_task_created", human_task_id=human_task_id, subtype=subtype_str)
    return human_task_id


def _check_and_unblock(
    blackboard: Blackboard,
    tenant: str,
    project: str,
    wave_id: str,
    mvi_id: str,
    resolved_ref: str,
    blocked_sks: list[str],
    steer: str | None,
    mvi_item: dict[str, Any],
    wave: WaveSnapshot,
    logger: StructuredLogger,
) -> None:
    """Find blocked tasks referencing the resolved blocker and dispatch new crows."""
    pk = build_pk(tenant, project)

    for blocked_sk in blocked_sks:
        # Read the blocked crow's snapshot
        blocked_item = blackboard.read(pk, blocked_sk)
        if not blocked_item:
            continue

        # Build instructions with human guidance
        original_instructions = blocked_item.get("instructions", "")
        if steer:
            instructions = f"{original_instructions}\n\n## Human Guidance\n{steer}"
        else:
            instructions = original_instructions

        # Carry forward existing PR if present
        existing_outcome = blocked_item.get("outcome", {})
        existing_pr = existing_outcome.get("pr") if existing_outcome else None

        # Create new crow to resume the work
        crow_type_str = blocked_item.get("crow_type", "implementer")
        crow_type = CrowType(crow_type_str)
        crow_id = _next_crow_id(blackboard, pk, wave_id, mvi_id, crow_type)

        crow = CrowSnapshot(
            tenant=tenant,
            project=project,
            wave_id=wave_id,
            mvi_id=mvi_id,
            crow_id=crow_id,
            crow_type=crow_type,
            status=CrowStatus.PENDING,
            instructions=instructions,
            repo=mvi_item.get("repo", ""),
            branch=mvi_item.get("branch", ""),
            budget_remaining=wave.budget.remaining,
        )

        crow_item = crow.to_item()
        if existing_pr:
            crow_item["existing_pr"] = existing_pr

        validate_crow_assignment(crow_item)
        blackboard.write_item(crow_item)

        evt = build_task_unblocked_event(
            tenant, project, wave_id, crow_id, resolved_ref,
        )
        blackboard.write_event(evt.to_events_item(EVENT_TTL_DAYS))

        evt2 = build_crow_assigned_event(
            tenant, project, wave_id, crow_type, f"unblocked by {resolved_ref}",
        )
        blackboard.write_event(evt2.to_events_item(EVENT_TTL_DAYS))

        logger.event(
            "crow_unblocked",
            crow_id=crow_id,
            unblocked_by=resolved_ref,
        )


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


# --- Planner helpers ---

def _count_completed_planners(
    blackboard: Blackboard,
    pk: str,
    wave_id: str,
    mvi_id: str,
) -> int:
    """Count how many planner crows have completed for this MVI."""
    crow_prefix = f"S#{wave_id}#m{mvi_id}#cr_"
    crows = blackboard.query(pk, crow_prefix)
    return sum(
        1 for c in crows
        if c.get("crow_type") == "planner" and c.get("status") == "completed"
    )


def _count_completed_fixers(
    blackboard: Blackboard,
    pk: str,
    wave_id: str,
    mvi_id: str,
) -> int:
    """Count how many fixer crows have completed for this MVI."""
    crow_prefix = f"S#{wave_id}#m{mvi_id}#cr_"
    crows = blackboard.query(pk, crow_prefix)
    return sum(
        1 for c in crows
        if c.get("crow_type") == "fixer" and c.get("status") == "completed"
    )


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


# --- Fix history lookup ---

def _find_fix_history(
    blackboard: Blackboard,
    pk: str,
    wave_id: str,
    mvi_id: str,
) -> list[dict[str, Any]]:
    """Return completed (reviewer_rejected, fixer_completed) pairs chronologically.

    Walks all crows sorted by sequence number extracted from crow_id
    (e.g. cr_rev_03 -> 3). Sorting by SK string would mis-order crows
    because type abbreviations (fix, rev) sort alphabetically, not by
    insertion order. For each reviewer rejection followed by a completed
    fixer, records one history entry. The triggering reviewer is excluded
    because it is not yet written back as completed when this runs.
    """
    crow_prefix = f"S#{wave_id}#m{mvi_id}#cr_"
    crows = blackboard.query(pk, crow_prefix)

    def _seq(crow: dict[str, Any]) -> int:
        sk = crow.get("SK", "")
        crow_id_part = sk.rsplit("#", 1)[-1]
        seq_part = crow_id_part.rsplit("_", 1)[-1]
        try:
            return int(seq_part)
        except ValueError:
            return 0

    crows_sorted = sorted(crows, key=_seq)

    history: list[dict[str, Any]] = []
    iteration = 0
    i = 0
    while i < len(crows_sorted) - 1:
        current = crows_sorted[i]
        nxt = crows_sorted[i + 1]
        outcome_dict = current.get("outcome", {}) if isinstance(current.get("outcome"), dict) else {}
        if "blocking_issues" in outcome_dict:
            _reviewer_rejected_flag = len(outcome_dict["blocking_issues"]) > 0
        else:
            _reviewer_rejected_flag = not outcome_dict.get("approved", True)
        reviewer_rejected = (
            current.get("crow_type") == "reviewer"
            and current.get("status") == "completed"
            and isinstance(current.get("outcome"), dict)
            and _reviewer_rejected_flag
        )
        fixer_completed = (
            nxt.get("crow_type") == "fixer"
            and nxt.get("status") == "completed"
        )
        if reviewer_rejected and fixer_completed:
            iteration += 1
            reviewer_outcome = current.get("outcome", {})
            fixer_outcome_hist = nxt.get("outcome", {})
            if "blocking_issues" in reviewer_outcome:
                reviewer_issues = reviewer_outcome.get("blocking_issues", [])
            else:
                reviewer_issues = reviewer_outcome.get("issues", [])
            history.append({
                "iteration": iteration,
                "reviewer_issues": reviewer_issues,
                "fixer_summary": fixer_outcome_hist.get("summary", ""),
                "fixer_files_changed": fixer_outcome_hist.get("files_changed", []),
            })
            i += 2
        else:
            i += 1

    return history


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
