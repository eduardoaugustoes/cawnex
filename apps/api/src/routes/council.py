"""Council routes — human overrides for supervised auto mode."""

import uuid
from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.auth.dependencies import get_tenant
from src.auth.tenant import TenantContext
from src.db.client import TenantDB

router = APIRouter(prefix="/projects/{project_id}/council", tags=["council"])

VALID_OVERRIDE_ACTIONS = {
    "override_block",
    "request_round",
    "add_constraint",
    "dismiss_advisor",
    "force_decision",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _short_id() -> str:
    return uuid.uuid4().hex[:8]


class OverrideRequest(BaseModel):
    """Human override for a council session."""

    action: str
    reason: str
    advisor_overridden: str = ""
    constraint: str = ""
    question: str = ""
    wave_plan: List[str] = Field(default_factory=list)


class OverrideResponse(BaseModel):
    """Response after applying an override."""

    status: str
    override_action: str
    session_id: str


@router.post("/{session_id}/override", response_model=OverrideResponse)
async def apply_council_override(
    project_id: str,
    session_id: str,
    body: OverrideRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> Dict[str, Any]:
    """Apply a human override to a council session.

    The override is written to the council session record and a new
    COUNCIL#override task is created for the Council Lambda to process.
    """
    if body.action not in VALID_OVERRIDE_ACTIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid override action. Must be one of: "
                f"{', '.join(sorted(VALID_OVERRIDE_ACTIONS))}"
            ),
        )

    db = TenantDB(tenant)

    # Verify the council session exists
    council_sk = f"COUNCIL#{session_id}"
    session = db.get_project_item(project_id, council_sk)
    if not session:
        raise HTTPException(status_code=404, detail="Council session not found")

    # Verify session is in a state that accepts overrides (escalated or completed)
    session_status = session.get("status", "")
    if session_status not in ("completed", "failed"):
        raise HTTPException(
            status_code=409,
            detail=(
                f"Session status is '{session_status}', "
                "overrides require 'completed' or 'failed'"
            ),
        )

    # Build the override record
    override_record: Dict[str, Any] = {
        "action": body.action,
        "reason": body.reason,
        "timestamp": _now_iso(),
    }
    if body.advisor_overridden:
        override_record["advisor_overridden"] = body.advisor_overridden
    if body.constraint:
        override_record["constraint"] = body.constraint
    if body.question:
        override_record["question"] = body.question
    if body.wave_plan:
        override_record["wave_plan"] = body.wave_plan

    # Append override to the session record
    existing_overrides = session.get("human_overrides", [])
    existing_overrides.append(override_record)
    db.update_project_item(
        project_id, council_sk, {"human_overrides": existing_overrides}
    )

    # Write a COUNCIL#override task for the Council Lambda to process
    override_task_id = f"override_{session_id}_{_short_id()}"
    wave_id = session.get("wave_id", "")
    db.put_project_item(
        project_id,
        sk=f"COUNCIL#{override_task_id}",
        level="council",
        status="pending",
        type="override",
        original_session_id=session_id,
        wave_id=wave_id,
        auto_mode=session.get("auto_mode", "supervised"),
        override=override_record,
        context=session.get("context", {}),
        entityType="Snapshot",
        created_at=_now_iso(),
    )

    return {
        "status": "override_submitted",
        "override_action": body.action,
        "session_id": session_id,
    }
