"""Task detail route.

Tasks are not standalone DDB entities — they live as elements of the
planner crow's `outcome.tasks` array. A task is identified by the composite
key `{wave_id}:{mvi_id}:{task_index}`. This route resolves that composite
back into the planner outcome, looks up the indexed task, and enriches
with the implementer crow's metadata + PR + cost when available.

Fields the iOS TaskDetail model expects that we don't track per-task yet
(implementationSteps, acceptanceCriteria) are returned as empty arrays —
iOS renders placeholders.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.auth.dependencies import get_tenant
from src.auth.tenant import TenantContext
from src.db.client import TenantDB

router = APIRouter(prefix="/projects/{project_id}/tasks", tags=["tasks"])


# ---- response models -------------------------------------------------------


class ImplementationStep(BaseModel):
    """One step of an implementer's work (placeholder until per-task tracking lands)."""

    id: str
    text: str
    completed: bool


class AcceptanceCriterion(BaseModel):
    """One acceptance criterion (placeholder until per-criterion tracking lands)."""

    id: str
    text: str
    passed: bool


class TaskPR(BaseModel):
    """PR metadata surfaced on the task detail view."""

    number: str
    title: str
    branch: str
    status: str
    lines_added: int
    lines_removed: int
    files_changed: int
    coverage: int


class AssignedCrow(BaseModel):
    """Which crow worked this task (derived from implementer snapshot)."""

    name: str
    role: str
    model: str
    behavior_state: str
    execution_minutes: int
    files_changed: int


class TaskDetailResponse(BaseModel):
    """API response shape matching iOS TaskDetail."""

    id: str
    name: str
    status: str
    description: str
    breadcrumb: str
    human_estimate: str
    ai_cost: Decimal
    roi: int
    assigned_crow: AssignedCrow
    implementation_steps: list[ImplementationStep]
    acceptance_criteria: list[AcceptanceCriterion]
    pr: TaskPR | None = None


# ---- helpers ---------------------------------------------------------------


def _parse_task_id(task_id: str) -> tuple[str, str, int]:
    """Parse composite `{wave_id}:{mvi_id}:{task_index}`.

    Raises HTTPException(400) if the shape is wrong.
    """
    parts = task_id.split(":")
    if len(parts) != 3:
        raise HTTPException(
            status_code=400,
            detail=(
                "task_id must be 'wave_id:mvi_id:task_index' " f"(got {task_id!r})"
            ),
        )
    try:
        idx = int(parts[2])
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"task_index must be an integer (got {parts[2]!r})",
        )
    return parts[0], parts[1], idx


def _find_planner_outcome(
    db: TenantDB, project_id: str, wave_id: str, mvi_id: str
) -> dict[str, Any] | None:
    """Locate the most recent completed planner crow for this MVI.

    Planner crows have ids matching `cr_plan_*`. We query all crow snapshots
    under the MVI and pick the planner. If none exist (e.g. wave is still
    warming), return None.
    """
    sk_prefix = f"S#{wave_id}#m{mvi_id}#cr_plan"
    rows = db.query_project(project_id=project_id, sk_prefix=sk_prefix)
    completed = [r for r in rows if r.get("status") == "completed"]
    if not completed:
        return None
    # Newest first if multiple
    completed.sort(key=lambda r: r.get("completed_at", ""), reverse=True)
    return completed[0]


def _find_implementer_for_task(
    db: TenantDB,
    project_id: str,
    wave_id: str,
    mvi_id: str,
) -> dict[str, Any] | None:
    """Most recent completed implementer crow for the MVI, if any."""
    sk_prefix = f"S#{wave_id}#m{mvi_id}#cr_impl"
    rows = db.query_project(project_id=project_id, sk_prefix=sk_prefix)
    completed = [r for r in rows if r.get("status") == "completed"]
    if not completed:
        return None
    completed.sort(key=lambda r: r.get("completed_at", ""), reverse=True)
    return completed[0]


def _crow_files_changed(crow: dict[str, Any]) -> int:
    """Count of files the crow's outcome touched."""
    outcome = crow.get("outcome") or {}
    files = outcome.get("files_changed") or []
    if isinstance(files, list):
        return len(files)
    return 0


def _human_hours_to_estimate_label(hours_raw: Any) -> str:
    """Map planner's estimated_hours (int|str) to a UI-friendly label."""
    try:
        hours = float(hours_raw)
    except (TypeError, ValueError):
        return "—"
    if hours <= 0:
        return "—"
    if hours < 1:
        return f"~{int(hours * 60)} min"
    if hours == int(hours):
        return f"~{int(hours)} hrs"
    return f"~{hours:.1f} hrs"


def _build_breadcrumb(wave_id: str, mvi_id: str, mvi_name: str, task_index: int) -> str:
    return f"MVI {mvi_name} › Task {task_index + 1}"


def _build_assigned_crow(
    impl_crow: dict[str, Any] | None, task: dict[str, Any]
) -> AssignedCrow:
    """Derive the AssignedCrow block.

    Falls back to defaults if no implementer has run yet.
    """
    if impl_crow is None:
        return AssignedCrow(
            name="Implementer",
            role="implementer",
            model="—",
            behavior_state="idle",
            execution_minutes=0,
            files_changed=0,
        )
    cost = impl_crow.get("cost") or {}
    duration_ms = int(cost.get("duration_ms", 0) or 0)
    exec_minutes = max(1, round(duration_ms / 60_000)) if duration_ms > 0 else 0
    return AssignedCrow(
        name="Implementer",
        role=impl_crow.get("crow_type", "implementer"),
        model=impl_crow.get("model", "—"),
        behavior_state=impl_crow.get("behavior_state", "landed"),
        execution_minutes=exec_minutes,
        files_changed=_crow_files_changed(impl_crow),
    )


def _prorate_cost(impl_crow: dict[str, Any] | None, task_count: int) -> Decimal:
    """Approximate per-task AI cost = implementer total / task count.

    Honest about imprecision — implementer cost is per-crow, not per-task.
    iOS surface should label this as approximate.
    """
    if impl_crow is None or task_count <= 0:
        return Decimal("0")
    cost = impl_crow.get("cost") or {}
    credits = int(cost.get("credits", 0) or 0)
    # credits are microdollars; convert to USD then split
    micros_per_dollar = 1_000_000
    if credits == 0:
        return Decimal("0")
    usd_total = Decimal(credits) / Decimal(micros_per_dollar)
    return (usd_total / Decimal(task_count)).quantize(Decimal("0.01"))


def _compute_roi(human_hours_raw: Any, ai_cost_usd: Decimal) -> int:
    """ROI = (human hours × default rate) / ai_cost. Returns multiplier int.

    Uses a $50/hr default (mid-level dev). If ai_cost is zero, returns 0
    to signal "no execution yet" rather than infinity.
    """
    try:
        hours = float(human_hours_raw)
    except (TypeError, ValueError):
        return 0
    if hours <= 0 or ai_cost_usd <= 0:
        return 0
    DEFAULT_RATE = Decimal("50")
    human_cost = Decimal(str(hours)) * DEFAULT_RATE
    return int(human_cost / ai_cost_usd)


def _task_status(impl_crow: dict[str, Any] | None) -> str:
    """Derive task status from whether the implementer landed work.

    With current data model, all tasks in an MVI share the implementer's
    status — we don't track per-task progress. This is honest about that
    limitation; iOS shows the implementer-level status for each task row.
    """
    if impl_crow is None:
        return "pending"
    status = impl_crow.get("status", "pending")
    return str(status) if status is not None else "pending"


def _maybe_pr_stub(impl_crow: dict[str, Any] | None) -> TaskPR | None:
    """Return a minimal PR stub when the implementer has a pr.number.

    The full PR (title, line counts, status, coverage) is the PR endpoint's
    job — phase 1.2. This phase just surfaces "yes there is a PR" so iOS
    can link out.
    """
    if impl_crow is None:
        return None
    pr = impl_crow.get("pr") or {}
    number = pr.get("number")
    if not number:
        return None
    return TaskPR(
        number=f"PR #{number}",
        title="",
        branch=impl_crow.get("branch", ""),
        status="open",
        lines_added=0,
        lines_removed=0,
        files_changed=_crow_files_changed(impl_crow),
        coverage=0,
    )


# ---- route -----------------------------------------------------------------


@router.get("/{task_id}", response_model=TaskDetailResponse)
async def get_task_detail(
    project_id: str,
    task_id: str,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> TaskDetailResponse:
    """Resolve a planner-produced task by composite id and return its detail.

    task_id format: `{wave_id}:{mvi_id}:{task_index}`.

    Sources data from:
      - Planner crow outcome (task name, description, estimated_hours)
      - Implementer crow snapshot (cost, model, files_changed, PR)
      - MVI snapshot (name for breadcrumb)

    Returns empty arrays for implementation_steps and acceptance_criteria —
    iOS renders placeholders for those sections.
    """
    wave_id, mvi_id, task_index = _parse_task_id(task_id)
    db = TenantDB(tenant)

    planner = _find_planner_outcome(db, project_id, wave_id, mvi_id)
    if planner is None:
        raise HTTPException(
            status_code=404,
            detail=f"No completed planner found for wave {wave_id} mvi {mvi_id}",
        )

    tasks = (planner.get("outcome") or {}).get("tasks") or []
    if not isinstance(tasks, list) or task_index < 0 or task_index >= len(tasks):
        raise HTTPException(
            status_code=404,
            detail=(
                f"task_index {task_index} out of range "
                f"(planner has {len(tasks) if isinstance(tasks, list) else 0} tasks)"
            ),
        )

    task = tasks[task_index]
    impl_crow = _find_implementer_for_task(db, project_id, wave_id, mvi_id)

    mvi_sk = f"S#{wave_id}#m{mvi_id}"
    mvi = db.get_project_item(project_id=project_id, sk=mvi_sk) or {}
    mvi_name = mvi.get("name", mvi_id)

    return TaskDetailResponse(
        id=task_id,
        name=task.get("name", "Untitled task"),
        status=_task_status(impl_crow),
        description=task.get("description", ""),
        breadcrumb=_build_breadcrumb(wave_id, mvi_id, mvi_name, task_index),
        human_estimate=_human_hours_to_estimate_label(task.get("estimated_hours")),
        ai_cost=_prorate_cost(impl_crow, len(tasks)),
        roi=_compute_roi(
            task.get("estimated_hours"),
            _prorate_cost(impl_crow, len(tasks)),
        ),
        assigned_crow=_build_assigned_crow(impl_crow, task),
        implementation_steps=[],
        acceptance_criteria=[],
        pr=_maybe_pr_stub(impl_crow),
    )
