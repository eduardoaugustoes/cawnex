"""Core orchestration — read state, decide, write next crow.

Two entry points:
- react_to_mvi_queued: initial trigger, assigns planner
- react_to_crow_completion: main loop, chains crow pipeline
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from murder.blackboard import Blackboard
from murder.checks import run_deterministic_checks
from murder.config import EVENT_TTL_DAYS, WAVE_BUDGET_LIMIT
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

    # Persist task count from planner outcome onto the MVI so the iOS Wave
    # Execution and MVI Detail screens can render the merge-readiness gauge
    # accurately. Without this, tasks_total stays at 0 from MVI seeding and
    # iOS shows "0/0 tasks completed" even when the implementer succeeded.
    if previous_type == CrowType.PLANNER and previous_outcome:
        planner_task_count = len(previous_outcome.get("tasks", []) or [])
        if planner_task_count > 0 and int(mvi_item.get("tasks_total", 0) or 0) == 0:
            blackboard.update(pk, mvi_sk, {"tasks_total": planner_task_count})
            mvi_item["tasks_total"] = planner_task_count

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

    # Run deterministic checks against the implementer's outcome
    impl_crows = [c for c in crow_items if c.get("crow_type") == "implementer"]
    impl_outcome = impl_crows[-1].get("outcome", {}) if impl_crows else {}
    mvi_item = blackboard.read(pk, mvi_sk)
    mvi_name = (mvi_item or {}).get("name", mvi_id)
    check_results = run_deterministic_checks(impl_outcome or {}, mvi_item or {})

    checks_summary = {
        "passed": [r.name for r in check_results if r.passed],
        "failed": [r.name for r in check_results if not r.passed and r.is_hard_block],
        "warnings": [
            r.name for r in check_results if not r.passed and not r.is_hard_block
        ],
        "details": [r.to_dict() for r in check_results],
        "run_at": datetime.now(timezone.utc).isoformat(),
    }

    # Bundled-PR mode: when the MVI is ready to ship, every task the
    # planner emitted has landed in the same implementer PR. Mark them
    # all complete so the iOS merge-readiness gauge shows the right
    # state. (If we move to per-task PRs later, this needs to count
    # actually-completed tasks instead.)
    tasks_total_count = int((mvi_item or {}).get("tasks_total", 0) or 0)

    updates: dict[str, Any] = {
        "status": MVIStatus.READY_TO_SHIP.value,
        "can_ship": True,
        "merge_checklist": merge_checklist,
        "cost": total_cost.to_dict(),
        "deterministic_checks": checks_summary,
        "tasks_done": tasks_total_count,
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

    # Check if all MVIs in the wave are terminal — transition wave to review
    _maybe_transition_wave(blackboard, pk, wave_id, logger)

    # If wave reached review with all MVIs ready_to_ship, kick off the Integrator.
    _maybe_start_integrator(blackboard, pk, wave_id, logger)


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

    _maybe_transition_wave(blackboard, pk, wave_id, logger)


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


# --- Wave steering (council rejection) ---


def react_to_wave_steered(
    blackboard: Blackboard,
    wave_item: dict[str, Any],
    logger: StructuredLogger,
) -> None:
    """Handle council rejection: re-execute flagged MVIs with fixer crows."""
    pk = wave_item["PK"]
    sk = wave_item["SK"]
    wave_id = sk.replace("S#", "")
    tenant = _extract_tenant(pk)
    project = _extract_project(pk)

    council_feedback = wave_item.get("council_feedback", {})
    flagged_mvis = council_feedback.get("flagged_mvis", [])
    reasoning = council_feedback.get("reasoning", "Council rejected wave")

    # Group concerns by MVI
    mvi_concerns: dict[str, list[str]] = {}
    for flagged in flagged_mvis:
        mvi_id = flagged.get("mvi_id", "")
        concern = flagged.get("concern", "")
        advisor = flagged.get("advisor", "")
        if mvi_id:
            mvi_concerns.setdefault(mvi_id, []).append(
                f"[{advisor}] {concern}" if advisor else concern
            )

    # Transition each flagged MVI back to executing and assign fixer crow
    for mvi_id, concerns in mvi_concerns.items():
        mvi_sk = build_sk(wave_id=wave_id, mvi_id=mvi_id)
        mvi_item = blackboard.read(pk, mvi_sk)
        if not mvi_item:
            logger.error("steered_mvi_not_found", mvi_id=mvi_id)
            continue

        # Transition MVI back to executing
        blackboard.update(pk, mvi_sk, {"status": MVIStatus.EXECUTING.value})

        # Build fixer instructions from council feedback
        concerns_text = "\n".join(f"- {c}" for c in concerns)
        instructions = (
            f"## Council Review Feedback\n\n"
            f"The council rejected this MVI's output. Fix the following issues:\n\n"
            f"{concerns_text}\n\n"
            f"## Overall Reasoning\n{reasoning}\n\n"
            f"## MVI Context\n{mvi_item.get('description', '')}"
        )

        # Read wave for budget
        wave_sk = build_sk(wave_id=wave_id)
        wave_read = blackboard.read(pk, wave_sk)
        budget_remaining = WAVE_BUDGET_LIMIT
        if wave_read and "budget" in wave_read:
            budget_data = wave_read["budget"]
            budget_remaining = int(budget_data.get("limit", WAVE_BUDGET_LIMIT)) - int(
                budget_data.get("spent", 0)
            )

        crow_id = _next_crow_id(
            blackboard, pk, wave_id, mvi_id, CrowType.FIXER
        )
        crow = CrowSnapshot(
            tenant=tenant,
            project=project,
            wave_id=wave_id,
            mvi_id=mvi_id,
            crow_id=crow_id,
            crow_type=CrowType.FIXER,
            status=CrowStatus.PENDING,
            instructions=instructions,
            repo=mvi_item.get("repo", ""),
            branch=mvi_item.get("branch", ""),
            budget_remaining=budget_remaining,
        )
        blackboard.write_item(crow.to_item())
        logger.event(
            "council_fixer_assigned",
            mvi_id=mvi_id,
            crow_id=crow_id,
            concerns=len(concerns),
        )

    # Transition wave back to executing
    blackboard.update(pk, build_sk(wave_id=wave_id), {
        "status": WaveStatus.EXECUTING.value,
    })
    logger.event(
        "wave_steered_to_executing",
        wave_id=wave_id,
        flagged_mvis=len(mvi_concerns),
    )


# --- Wave lifecycle ---

def _maybe_transition_wave(
    blackboard: Blackboard,
    pk: str,
    wave_id: str,
    logger: StructuredLogger,
) -> None:
    """If all MVIs in the wave are terminal, transition wave to review."""
    mvi_prefix = f"S#{wave_id}#m"
    mvi_items = blackboard.query(pk, mvi_prefix)

    # Only look at MVI-level items (not crows or human tasks)
    mvis = [m for m in mvi_items if m.get("level") == "murder"]
    if not mvis:
        return

    terminal_statuses = {"ready_to_ship", "shipped", "failed"}
    all_terminal = all(m.get("status") in terminal_statuses for m in mvis)
    if not all_terminal:
        return

    wave_sk = build_sk(wave_id=wave_id)
    wave_item = blackboard.read(pk, wave_sk)
    if not wave_item or wave_item.get("status") != WaveStatus.EXECUTING.value:
        return

    any_ready = any(m.get("status") == "ready_to_ship" for m in mvis)
    new_status = WaveStatus.REVIEW.value if any_ready else WaveStatus.CANCELLED.value

    blackboard.update(pk, wave_sk, {"status": new_status})
    logger.event(
        "wave_transitioned",
        wave_id=wave_id,
        new_status=new_status,
        mvi_count=len(mvis),
    )

    # Auto mode: trigger council review if enabled
    if new_status == WaveStatus.REVIEW.value:
        _trigger_council_review(blackboard, pk, wave_id, mvis, wave_item, logger)


def _maybe_transition_review_to_delivered(
    blackboard: Blackboard,
    pk: str,
    wave_id: str,
    logger: StructuredLogger,
) -> None:
    """If every MVI in this wave is in a post-review terminal state, deliver the wave.

    Triggered after an MVI transitions to `shipped` or `rejected` (from
    the founder approving or rejecting via the iOS PR actions). The wave
    is allowed to leave REVIEW only when all of its MVIs have a definite
    final disposition — not when some are still in `ready_to_ship`.

    Terminal-after-review statuses: shipped, rejected, failed, cancelled.
    (`ready_to_ship` is intentionally NOT terminal here — that's the
    pre-review staging state. The user hasn't acted on it yet.)
    """
    mvi_prefix = f"S#{wave_id}#m"
    mvi_items = blackboard.query(pk, mvi_prefix)
    mvis = [m for m in mvi_items if m.get("level") == "murder"]
    if not mvis:
        return

    post_review_terminal = {"shipped", "rejected", "failed", "cancelled"}
    all_terminal = all(m.get("status") in post_review_terminal for m in mvis)
    if not all_terminal:
        return

    wave_sk = build_sk(wave_id=wave_id)
    wave_item = blackboard.read(pk, wave_sk)
    if not wave_item or wave_item.get("status") != WaveStatus.REVIEW.value:
        return

    # REVIEW → DELIVERED is the only forward transition from review per
    # enums._WAVE_TRANSITIONS. "Delivered" here means "the wave finished
    # the review gate" — it doesn't require all MVIs to be shipped, just
    # that every MVI got a final disposition (shipped or rejected).
    blackboard.update(pk, wave_sk, {"status": WaveStatus.DELIVERED.value})
    logger.event(
        "wave_delivered",
        wave_id=wave_id,
        mvi_count=len(mvis),
        shipped_count=sum(1 for m in mvis if m.get("status") == "shipped"),
        rejected_count=sum(1 for m in mvis if m.get("status") == "rejected"),
    )


def react_to_mvi_terminal(
    blackboard: Blackboard,
    mvi_item: dict[str, Any],
    logger: StructuredLogger,
) -> None:
    """Dispatched when an MVI transitions to shipped/rejected/cancelled.

    These transitions are user-driven (founder hitting Approve & Merge
    or Reject in the iOS PR Review screen) — they're not produced by
    crow completions. The dispatcher in handler.py routes here when
    level=murder and status is a post-review terminal.

    The only follow-up action is to check whether the wave can now
    transition REVIEW → DELIVERED.
    """
    pk = mvi_item.get("PK", "")
    sk = mvi_item.get("SK", "")
    if not pk or not sk:
        return
    wave_id = _extract_wave_id(sk)
    _maybe_transition_review_to_delivered(blackboard, pk, wave_id, logger)


def _trigger_council_review(
    blackboard: Blackboard,
    pk: str,
    wave_id: str,
    mvis: list[dict[str, Any]],
    wave_item: dict[str, Any],
    logger: StructuredLogger,
) -> None:
    """Write COUNCIL# task if auto_mode is enabled."""
    root = blackboard.read(pk, "S#")
    auto_mode = root.get("auto_mode", "off") if root else "off"
    if auto_mode == "off":
        return

    session_id = f"wr_{wave_id}_{uuid.uuid4().hex[:8]}"

    mvi_check_results = []
    for mvi in mvis:
        mvi_id = mvi.get("mvi_id", mvi["SK"].split("#m")[-1].split("#")[0])
        mvi_check_results.append(
            {
                "mvi_id": mvi_id,
                "status": mvi.get("status"),
                "name": mvi.get("name", ""),
                "deterministic_checks": mvi.get("deterministic_checks", {}),
            }
        )

    council_item: dict[str, Any] = {
        "PK": pk,
        "SK": f"COUNCIL#{session_id}",
        "level": "council",
        "status": "pending",
        "type": "wave_review",
        "wave_id": wave_id,
        "auto_mode": auto_mode,
        "context": {
            "wave_summary": {
                "wave_id": wave_id,
                "human_directive": wave_item.get("human_directive", ""),
                "budget": wave_item.get("budget", {}),
                "progress": wave_item.get("progress", {}),
            },
            "mvi_check_results": mvi_check_results,
            "project_maturity": root.get("maturity_stage", "mvp"),
        },
        "entityType": "Snapshot",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    blackboard.write_item(council_item)
    logger.event(
        "council_review_triggered",
        wave_id=wave_id,
        session_id=session_id,
        auto_mode=auto_mode,
    )


def react_to_integration_complete(
    blackboard: Blackboard,
    findings: dict[str, Any],
    logger: StructuredLogger,
) -> None:
    """Route on IntegratorFindings.overall: ready_for_council or needs_rework."""
    pk = findings["PK"]
    wave_id = findings["wave_id"]
    overall = findings["overall"]
    wave_sk = build_sk(wave_id=wave_id)

    if overall == "ready_for_council":
        blackboard.update(
            pk, wave_sk, {"status": WaveStatus.UNDER_COUNCIL_REVIEW.value}
        )

        session_id = f"wr_{wave_id}_{uuid.uuid4().hex[:8]}"
        blackboard.write_item(
            {
                "PK": pk,
                "SK": f"COUNCIL#{session_id}",
                "level": "council",
                "status": "pending",
                "type": "wave_review",
                "wave_id": wave_id,
                "integration_sk": findings["SK"],
                "auto_mode": "off",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "entityType": "CouncilSession",
            }
        )

        logger.event(
            "council_session_created",
            wave_id=wave_id,
            session_id=session_id,
        )
        return

    if overall == "needs_rework":
        blackboard.update(pk, wave_sk, {"status": WaveStatus.EXECUTING.value})

        affected_mvi_ids: set[str] = set()
        for conflict in findings.get("merge_conflicts", []) or []:
            if conflict.get("mvi_a"):
                affected_mvi_ids.add(conflict["mvi_a"])
            if conflict.get("mvi_b"):
                affected_mvi_ids.add(conflict["mvi_b"])

        for mvi_id in affected_mvi_ids:
            mvi_sk = build_sk(wave_id=wave_id, mvi_id=mvi_id)
            blackboard.update(
                pk,
                mvi_sk,
                {
                    "status": MVIStatus.EXECUTING.value,
                    "rework_reason": "merge conflict",
                },
            )

        logger.event(
            "wave_needs_rework",
            wave_id=wave_id,
            affected_mvi_count=len(affected_mvi_ids),
            reasons=findings.get("rework_reasons", []),
        )
        return

    logger.event(
        "integration_complete_unknown_overall",
        wave_id=wave_id,
        overall=overall,
    )


def _maybe_start_integrator(
    blackboard: Blackboard,
    pk: str,
    wave_id: str,
    logger: StructuredLogger,
) -> None:
    """If all MVIs in the wave are ready_to_ship, transition wave to integrating
    and write an integrator task for the Worker.

    Safe to call repeatedly: bails out if the wave is not in REVIEW, if any MVI
    is not ready, or if no PR numbers are recorded.
    """
    wave_sk = build_sk(wave_id=wave_id)
    wave_item = blackboard.read(pk, wave_sk)
    if not wave_item or wave_item.get("status") != WaveStatus.REVIEW.value:
        return

    mvi_prefix = f"S#{wave_id}#m"
    mvis = [
        m
        for m in blackboard.query(pk, mvi_prefix)
        if m.get("level") == "murder"
    ]
    if not mvis:
        return

    not_ready = [m for m in mvis if m.get("status") != MVIStatus.READY_TO_SHIP.value]
    if not_ready:
        return

    pr_to_mvi: dict[str, str] = {}
    for mvi in mvis:
        pr_number = mvi.get("pr_number")
        mvi_id = mvi.get("mvi_id") or mvi["SK"].split("#m")[-1].split("#")[0]
        if pr_number is not None:
            pr_to_mvi[str(pr_number)] = mvi_id

    if not pr_to_mvi:
        return

    blackboard.update(pk, wave_sk, {"status": WaveStatus.INTEGRATING.value})

    project = blackboard.read(pk, "META")
    repo_path = (
        project.get("repo_path", "") if project else ""
    ) or f"/mnt/repos{pk.replace('P#', '/T/')}/repo"

    blackboard.write_item(
        {
            "PK": pk,
            "SK": f"S#{wave_id}/integrator-task",
            "level": "wave",
            "entityType": "CrowTask",
            "crow_kind": "integrator",
            "wave_id": wave_id,
            "project_id": pk.replace("P#", ""),
            "repo_path": repo_path,
            "pr_to_mvi": pr_to_mvi,
            "status": "pending",
            "GSI1PK": "DISPATCH#pending",
            "GSI1SK": f"{datetime.now(timezone.utc).isoformat()}#integrator#{wave_id}",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    logger.event(
        "integrator_dispatched",
        wave_id=wave_id,
        pr_count=len(pr_to_mvi),
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
