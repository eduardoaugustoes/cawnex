"""Waves routes — create, activate, pause, cancel, list, events."""

import os
import re
import time
from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List, Optional

import boto3
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.auth.dependencies import get_tenant
from src.auth.tenant import TenantContext
from src.db.client import TenantDB

router = APIRouter(prefix="/projects/{project_id}/waves", tags=["waves"])

_DEFAULT_BUDGET_MICROS = 20_000_000  # $20

# Valid wave status transitions (mirrors murder/enums.py WaveStatus)
_WAVE_TRANSITIONS: Dict[str, set[str]] = {
    "planning": {"approved", "cancelled"},
    "approved": {"executing"},
    "executing": {"review", "paused", "steered", "cancelled"},
    "paused": {"executing", "steered", "cancelled"},
    "steered": {"executing", "proposed"},
    "review": {"delivered", "steered"},
}

_TERMINAL_WAVE_STATUSES = {"delivered", "cancelled"}
_TERMINAL_MVI_STATUSES = {"shipped", "cancelled"}


class CreateWaveRequest(BaseModel):
    """Request body for creating a wave from backlog MVIs."""

    directive: str
    goal_id: str = ""
    mvi_ids: List[str] = []
    budget_micros: int = _DEFAULT_BUDGET_MICROS


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:30]


def _wave_id() -> str:
    return f"w{int(time.time() * 1000)}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_event(
    tenant_id: str,
    project_id: str,
    wave_id: str,
    event_type: str,
    message: str,
    color: str,
    extra: Dict[str, Any] | None = None,
) -> None:
    """Write an event to the events table."""
    events_table_name = os.environ.get("EVENTS_TABLE_NAME", "")
    if not events_table_name:
        return
    table = boto3.resource("dynamodb").Table(events_table_name)
    now = _now_iso()
    ttl_days = 365 if os.environ.get("STAGE") == "prod" else 90
    item: Dict[str, Any] = {
        "PK": f"T#{tenant_id}#P#{project_id}#W#{wave_id}",
        "SK": f"{now}#{event_type}",
        "GSI1PK": f"T#{tenant_id}#P#{project_id}",
        "GSI1SK": now,
        "event_type": event_type,
        "message": message,
        "color": color,
        "timestamp": now,
        "expires_at": int(time.time()) + (ttl_days * 86400),
        "entityType": "Event",
    }
    if extra:
        item["extra"] = extra
    table.put_item(Item=item)


def _scale_ecs(desired_count: int) -> None:
    """Scale ECS worker service."""
    cluster = os.environ.get("ECS_CLUSTER_NAME", "")
    service = os.environ.get("ECS_SERVICE_NAME", "")
    if not cluster or not service:
        return
    try:
        ecs = boto3.client("ecs")
        ecs.update_service(
            cluster=cluster,
            service=service,
            desiredCount=desired_count,
        )
    except Exception:
        pass  # Non-critical — worker may already be running


@router.post("", status_code=201)
async def create_wave(
    project_id: str,
    body: CreateWaveRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> Dict[str, Any]:
    """Create a wave from backlog MVIs or a single ad-hoc directive."""
    db = TenantDB(tenant)

    project = db.get_item(sk=f"P#{project_id}")
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    wave_id = _wave_id()
    now = _now_iso()
    repo = project.get("repo", "")

    mvis_data: List[Dict[str, Any]] = []

    if body.goal_id and body.mvi_ids:
        # Create wave from backlog MVIs
        backlog = db.get_project_item(
            project_id=project_id,
            sk=f"BACKLOG#goal#{body.goal_id}#mvis",
        )
        if not backlog:
            raise HTTPException(status_code=404, detail="Goal backlog not found")

        backlog_mvis = backlog.get("mvis", [])
        backlog_by_id = {m["id"]: m for m in backlog_mvis}

        for mvi_id in body.mvi_ids:
            if mvi_id not in backlog_by_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"MVI '{mvi_id}' not found in goal backlog",
                )

        for mvi_id in body.mvi_ids:
            backlog_mvi = backlog_by_id[mvi_id]
            branch = f"cawnex/{wave_id}-{mvi_id}"
            mvi_data = {
                "id": mvi_id,
                "name": backlog_mvi.get("name", mvi_id),
                "description": backlog_mvi.get("description", ""),
                "acceptance_criteria": backlog_mvi.get("acceptance_criteria", ""),
                "repo": repo,
                "branch": branch,
            }
            mvis_data.append(mvi_data)

            # Write MVI snapshot — goal_id + mvi_id persisted so the Murder
            # reactor can write back to the backlog when this MVI ships,
            # cancels, or is rejected.
            db.put_project_item(
                project_id=project_id,
                sk=f"S#{wave_id}#m{mvi_id}",
                level="murder",
                status="draft",
                name=mvi_data["name"],
                description=mvi_data["description"],
                acceptance_criteria=mvi_data["acceptance_criteria"],
                tasks_done=0,
                tasks_total=0,
                can_ship=False,
                merge_checklist=[],
                cost={"tokens_in": 0, "tokens_out": 0, "credits": 0, "duration_ms": 0},
                repo=repo,
                branch=branch,
                goal_id=body.goal_id,
                mvi_id=mvi_id,
                created_at=now,
                entityType="Snapshot",
            )

        # Annotate backlog MVIs with wave_id (bridge)
        for mvi in backlog_mvis:
            if mvi["id"] in body.mvi_ids:
                mvi["wave_id"] = wave_id
                mvi["wave_status"] = "draft"
        db.update_project_item(
            project_id=project_id,
            sk=f"BACKLOG#goal#{body.goal_id}#mvis",
            updates={"mvis": backlog_mvis},
        )
    else:
        # Legacy: single ad-hoc MVI from directive
        mvi_id = _slug(body.directive) or wave_id
        branch = f"cawnex/{wave_id}-{mvi_id}"
        mvi_data = {
            "id": mvi_id,
            "name": body.directive,
            "description": "",
            "acceptance_criteria": "",
            "repo": repo,
            "branch": branch,
        }
        mvis_data.append(mvi_data)

        db.put_project_item(
            project_id=project_id,
            sk=f"S#{wave_id}#m{mvi_id}",
            level="murder",
            status="draft",
            name=body.directive,
            description="",
            acceptance_criteria="",
            tasks_done=0,
            tasks_total=0,
            can_ship=False,
            merge_checklist=[],
            cost={"tokens_in": 0, "tokens_out": 0, "credits": 0, "duration_ms": 0},
            repo=repo,
            branch=branch,
            created_at=now,
            entityType="Snapshot",
        )

    # Write wave snapshot
    db.put_project_item(
        project_id=project_id,
        sk=f"S#{wave_id}",
        level="wave",
        status="planning",
        human_directive=body.directive,
        progress={
            "mvis_total": len(mvis_data),
            "mvis_shipped": 0,
            "tasks_done": 0,
            "tasks_total": 0,
        },
        budget={"spent": 0, "limit": body.budget_micros},
        created_at=now,
        entityType="Snapshot",
    )

    return {
        "wave_id": wave_id,
        "status": "planning",
        "mvis": mvis_data,
    }


@router.get("")
async def list_waves(
    project_id: str,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> Dict[str, Any]:
    """List all waves for a project, sorted by created_at desc."""
    db = TenantDB(tenant)
    items = db.query_project(project_id=project_id, sk_prefix="S#")

    waves: List[Dict[str, Any]] = []
    for item in items:
        if item.get("level") != "wave":
            continue
        sk = item.get("SK", "")
        wid = sk.replace("S#", "") if sk.startswith("S#") else sk
        waves.append(
            {
                "wave_id": wid,
                "status": item.get("status", ""),
                "directive": item.get("human_directive", ""),
                "progress": item.get("progress", {}),
                "budget": item.get("budget", {}),
                "created_at": item.get("created_at", ""),
            }
        )

    waves.sort(key=lambda w: w.get("created_at", ""), reverse=True)

    return {"waves": waves, "count": len(waves)}


@router.get("/{wave_id}")
async def get_wave(
    project_id: str,
    wave_id: str,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> Dict[str, Any]:
    """Return the wave snapshot and all child snapshots."""
    db = TenantDB(tenant)
    items = db.query_project(project_id=project_id, sk_prefix=f"S#{wave_id}")

    if not items:
        raise HTTPException(status_code=404, detail="Wave not found")

    wave: Optional[Dict[str, Any]] = None
    mvis: List[Dict[str, Any]] = []
    crows: List[Dict[str, Any]] = []
    human_tasks: List[Dict[str, Any]] = []

    for item in items:
        level = item.get("level")
        task_type = item.get("task_type", "")
        if level == "wave":
            wave = item
        elif level == "murder":
            mvis.append(item)
        elif level == "crow" and task_type == "human":
            human_tasks.append(item)
        elif level == "crow":
            crows.append(item)

    return {
        "wave": wave,
        "mvis": mvis,
        "crows": crows,
        "human_tasks": human_tasks,
    }


@router.post("/{wave_id}/activate")
async def activate_wave(
    project_id: str,
    wave_id: str,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> Dict[str, Any]:
    """Activate a wave — transitions to executing and queues MVIs.

    Writes synthetic events for ECS warm-up visibility.
    Scales up ECS worker.
    """
    db = TenantDB(tenant)

    wave_item = db.get_project_item(project_id=project_id, sk=f"S#{wave_id}")
    if not wave_item:
        raise HTTPException(status_code=404, detail="Wave not found")

    current_status = wave_item.get("status", "")
    if current_status in _TERMINAL_WAVE_STATUSES:
        raise HTTPException(status_code=409, detail=f"Wave already {current_status}")

    # Allow activation from planning (skip council for MVP)
    if current_status not in ("planning", "approved", "paused"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot activate wave in status '{current_status}'",
        )

    now = _now_iso()

    # Transition wave to executing
    db.update_project_item(
        project_id=project_id,
        sk=f"S#{wave_id}",
        updates={"status": "executing", "activated_at": now},
    )

    # Queue MVIs — transition draft/refined to queued (triggers Murder via DDB Stream)
    items = db.query_project(project_id=project_id, sk_prefix=f"S#{wave_id}#m")
    queued_count = 0
    for item in items:
        if item.get("level") != "murder":
            continue
        mvi_status = item.get("status", "")
        if mvi_status in ("draft", "refined"):
            db.update_project_item(
                project_id=project_id,
                sk=item["SK"],
                updates={"status": "queued"},
            )
            queued_count += 1

    # Write synthetic events for warm-up visibility
    _write_event(
        tenant.tenant_id,
        project_id,
        wave_id,
        "wave_activated",
        f"Wave activated — {queued_count} MVIs queued for execution",
        "blue",
    )
    _write_event(
        tenant.tenant_id,
        project_id,
        wave_id,
        "worker_warming",
        "Execution engine warming up (~30s)",
        "yellow",
    )

    # Scale up ECS worker
    _scale_ecs(1)

    return {
        "wave_id": wave_id,
        "status": "executing",
        "mvis_queued": queued_count,
    }


@router.post("/{wave_id}/pause")
async def pause_wave(
    project_id: str,
    wave_id: str,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> Dict[str, Any]:
    """Pause a wave — running crows complete but no new ones dispatch."""
    db = TenantDB(tenant)

    wave_item = db.get_project_item(project_id=project_id, sk=f"S#{wave_id}")
    if not wave_item:
        raise HTTPException(status_code=404, detail="Wave not found")

    current_status = wave_item.get("status", "")
    if current_status != "executing":
        raise HTTPException(
            status_code=409,
            detail=f"Cannot pause wave in status '{current_status}'",
        )

    db.update_project_item(
        project_id=project_id,
        sk=f"S#{wave_id}",
        updates={"status": "paused", "paused_at": _now_iso()},
    )

    _write_event(
        tenant.tenant_id,
        project_id,
        wave_id,
        "wave_paused",
        "Wave paused — running crows will complete, no new dispatches",
        "yellow",
    )

    return {"wave_id": wave_id, "status": "paused"}


@router.post("/{wave_id}/cancel")
async def cancel_wave(
    project_id: str,
    wave_id: str,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> Dict[str, Any]:
    """Cancel a wave and all non-terminal MVIs."""
    db = TenantDB(tenant)

    wave_item = db.get_project_item(project_id=project_id, sk=f"S#{wave_id}")
    if not wave_item:
        raise HTTPException(status_code=404, detail="Wave not found")

    current_status = wave_item.get("status", "")
    if current_status in _TERMINAL_WAVE_STATUSES:
        raise HTTPException(status_code=409, detail=f"Wave already {current_status}")

    now = _now_iso()

    # Cancel wave
    db.update_project_item(
        project_id=project_id,
        sk=f"S#{wave_id}",
        updates={"status": "cancelled", "cancelled_at": now},
    )

    # Cancel all non-terminal MVIs
    items = db.query_project(project_id=project_id, sk_prefix=f"S#{wave_id}#m")
    cancelled_count = 0
    for item in items:
        if item.get("level") != "murder":
            continue
        mvi_status = item.get("status", "")
        if mvi_status not in _TERMINAL_MVI_STATUSES:
            db.update_project_item(
                project_id=project_id,
                sk=item["SK"],
                updates={"status": "cancelled"},
            )
            cancelled_count += 1

    _write_event(
        tenant.tenant_id,
        project_id,
        wave_id,
        "wave_cancelled",
        f"Wave cancelled — {cancelled_count} MVIs cancelled",
        "red",
    )

    return {
        "wave_id": wave_id,
        "status": "cancelled",
        "mvis_cancelled": cancelled_count,
    }


def _merge_pr_for_wave(repo: str, pr_number: int) -> Dict[str, Any]:
    """Wrap the existing GitHub PR merge so tests can monkeypatch it.

    Lifted out as a module-level helper so unit tests can replace the
    network call with a stub without going through gh.
    """
    from src.github_mutations import merge_pr

    return merge_pr(repo, pr_number, method="rebase")


@router.post("/{wave_id}/approve")
async def approve_wave(
    project_id: str,
    wave_id: str,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> Dict[str, Any]:
    """Founder-driven wave approval after Council review.

    Wave must be in `under_human_review`. Merges every PR attached to a
    ready_to_ship MVI in the wave, then flips wave status to `delivered`.
    Partial merge failures surface as 502 with status preserved so the
    founder can investigate and retry.
    """
    db = TenantDB(tenant)
    wave_sk = f"S#{wave_id}"
    wave = db.get_project_item(project_id=project_id, sk=wave_sk)
    if not wave:
        raise HTTPException(status_code=404, detail="Wave not found")
    current = wave.get("status", "")
    if current != "under_human_review":
        raise HTTPException(
            status_code=409,
            detail=(
                f"Wave status is '{current}'; approve requires " "'under_human_review'"
            ),
        )

    mvis = db.query_project(project_id=project_id, sk_prefix=f"S#{wave_id}#m")
    targets: List[Dict[str, Any]] = [
        m
        for m in mvis
        if m.get("level") == "murder"
        and m.get("status") == "ready_to_ship"
        and m.get("pr_number") is not None
    ]
    pr_numbers = sorted(int(m["pr_number"]) for m in targets)

    merged: List[int] = []
    for mvi in sorted(targets, key=lambda m: int(m["pr_number"])):
        pr = int(mvi["pr_number"])
        repo = mvi.get("repo", "")
        if not repo:
            raise HTTPException(
                status_code=500,
                detail=f"MVI for PR #{pr} missing repo field",
            )
        try:
            _merge_pr_for_wave(repo=repo, pr_number=pr)
            merged.append(pr)
        except Exception as e:  # noqa: BLE001 -- loud-fail with detail
            raise HTTPException(
                status_code=502,
                detail=(
                    f"Partial merge: succeeded {merged}, failed at PR #{pr}: "
                    f"{type(e).__name__}: {str(e)[:200]}. Wave status unchanged."
                ),
            ) from e

    if merged != pr_numbers:
        raise HTTPException(
            status_code=502,
            detail=(
                f"Partial merge: succeeded {merged}, intended {pr_numbers}. "
                "Wave status unchanged."
            ),
        )

    db.update_project_item(
        project_id=project_id,
        sk=wave_sk,
        updates={"status": "delivered", "delivered_at": _now_iso()},
    )
    return {"status": "delivered", "merged_prs": merged, "wave_id": wave_id}


@router.get("/{wave_id}/events")
async def get_wave_events(
    project_id: str,
    wave_id: str,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
    limit: int = 50,
    after: Optional[str] = None,
) -> Dict[str, Any]:
    """Read events from the events table, paginated."""
    events_table_name = os.environ.get("EVENTS_TABLE_NAME", "")
    if not events_table_name:
        return {"events": [], "next_cursor": None}

    from boto3.dynamodb.conditions import Key

    events_table = boto3.resource("dynamodb").Table(events_table_name)
    events_pk = f"T#{tenant.tenant_id}#P#{project_id}#W#{wave_id}"

    if after:
        response = events_table.query(
            KeyConditionExpression=Key("PK").eq(events_pk) & Key("SK").gt(after),
            ScanIndexForward=False,
            Limit=limit,
        )
    else:
        response = events_table.query(
            KeyConditionExpression=Key("PK").eq(events_pk),
            ScanIndexForward=False,
            Limit=limit,
        )

    items = response.get("Items", [])
    events = [
        {
            "event_type": item.get("event_type", ""),
            "message": item.get("message", ""),
            "color": item.get("color", ""),
            "timestamp": item.get("timestamp", ""),
            "extra": item.get("extra", {}),
        }
        for item in items
    ]

    last_key = response.get("LastEvaluatedKey")
    next_cursor = last_key["SK"] if last_key else None

    return {"events": events, "next_cursor": next_cursor}
