"""Billing usage route — credits, costs, ROI aggregation.

Aggregates spend across the tenant's projects by walking each project's
crow snapshots. Returns a CreditsData-shaped payload for iOS.

Per the design spec, this is v1 — some fields are placeholders:

* `balance` is null. No user-level balance is modeled yet; iOS renders
  "Setup required" for the top-up section.
* `breakdown_period` is hardcoded to "All time" until a date-range
  selector is added. Real period filtering would need a GSI or
  per-month rollup.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.auth.dependencies import get_tenant
from src.auth.tenant import TenantContext
from src.db.client import TenantDB

router = APIRouter(prefix="/billing", tags=["billing"])

# Crow-name → role label for the iOS CrowCost.role field.
_CROW_ROLE_LABELS: dict[str, str] = {
    "planner": "Planning & Scoping",
    "implementer": "Code Generation",
    "reviewer": "Review & QA",
    "fixer": "Fix & Iterate",
}

# Default human hourly rate used to compute ROI. Matches the task endpoint
# so both surfaces report a consistent multiplier.
DEFAULT_HOURLY_RATE_USD = Decimal("50")

# Micros per dollar — credit fields in DDB are microdollars.
MICROS_PER_DOLLAR = 1_000_000


# ---- response models -------------------------------------------------------


class ROISummary(BaseModel):
    """Top-of-screen ROI block on iOS Credits."""

    roi_multiplier: int
    human_equiv_saved: Decimal
    credits_spent: Decimal
    ai_minutes: int
    human_hours: int


class CreditBalance(BaseModel):
    """Top-up status. v1 placeholder — fields are nullable."""

    remaining: Decimal | None = None
    total: Decimal | None = None


class ProjectBudget(BaseModel):
    """One row of the per-project spend table."""

    id: str
    project_name: str
    spent: Decimal
    total: Decimal


class CostBreakdownEntry(BaseModel):
    """One row of the cost breakdown — currently keyed by project."""

    id: str
    project_name: str
    amount: Decimal
    task_count: int


class CrowCost(BaseModel):
    """One row of the per-crow cost block."""

    id: str
    crow_name: str
    role: str
    amount: Decimal


class CreditsDataResponse(BaseModel):
    """Aggregated billing view matching iOS CreditsData."""

    roi: ROISummary
    balance: CreditBalance
    project_budgets: list[ProjectBudget]
    cost_breakdown: list[CostBreakdownEntry]
    crow_costs: list[CrowCost]
    breakdown_period: str


# ---- aggregation helpers ---------------------------------------------------


def _micros_to_usd(micros: int) -> Decimal:
    if micros <= 0:
        return Decimal("0.00")
    return (Decimal(micros) / Decimal(MICROS_PER_DOLLAR)).quantize(Decimal("0.01"))


def _list_projects(db: TenantDB) -> list[dict[str, Any]]:
    """Tenant's ProjectEntry rows."""
    return db.query(sk_prefix="P#")


def _list_crow_snapshots(db: TenantDB, project_id: str) -> list[dict[str, Any]]:
    """All crow snapshots in a project. Pattern S#{wave}#{mvi}#{crow}."""
    rows = db.query_project(project_id=project_id, sk_prefix="S#")
    # Crow snapshots have 3 '#'-separated segments after 'S#' (wave/mvi/crow)
    return [r for r in rows if (r.get("SK") or "").count("#") >= 3]


def _crow_total_minutes(crows: list[dict[str, Any]]) -> int:
    total_ms = sum(int((c.get("cost") or {}).get("duration_ms", 0) or 0) for c in crows)
    if total_ms <= 0:
        return 0
    return max(1, round(total_ms / 60_000))


def _human_hours_for_project(db: TenantDB, project_id: str) -> int:
    """Sum planner-task estimated_hours across all planner crows in project.

    This is the "human equivalent" denominator for ROI. Quietly returns 0
    if no planner outcomes exist.
    """
    planners = db.query_project(project_id=project_id, sk_prefix="S#")
    total_hours = 0.0
    for p in planners:
        if "cr_plan" not in (p.get("SK") or ""):
            continue
        outcome = p.get("outcome") or {}
        for task in outcome.get("tasks") or []:
            try:
                total_hours += float(task.get("estimated_hours", 0) or 0)
            except (TypeError, ValueError):
                continue
    return int(total_hours)


# ---- route -----------------------------------------------------------------


@router.get("/usage", response_model=CreditsDataResponse)
async def get_billing_usage(
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> CreditsDataResponse:
    """Aggregate billing data across the tenant's projects.

    Per project: walk the crow snapshots, sum cost.credits + cost.duration_ms,
    bucket by crow_type. Compute ROI = humanHours × DEFAULT_HOURLY_RATE_USD
    / creditsSpent across all projects.
    """
    db = TenantDB(tenant)

    project_budgets: list[ProjectBudget] = []
    cost_breakdown: list[CostBreakdownEntry] = []
    crow_micros_by_type: dict[str, int] = {}

    grand_total_micros = 0
    grand_total_minutes = 0
    grand_total_human_hours = 0

    for project in _list_projects(db):
        project_id = project.get("project_id") or _project_id_from_sk(project)
        if not project_id:
            continue
        project_name = project.get("name", project_id)

        crows = _list_crow_snapshots(db, project_id)
        project_micros = 0
        task_count = 0
        for crow in crows:
            cost = crow.get("cost") or {}
            micros = int(cost.get("credits", 0) or 0)
            project_micros += micros
            crow_type = (crow.get("crow_type") or "unknown").lower()
            crow_micros_by_type[crow_type] = (
                crow_micros_by_type.get(crow_type, 0) + micros
            )
            outcome = crow.get("outcome") or {}
            task_count += len(outcome.get("files_changed") or [])

        project_minutes = _crow_total_minutes(crows)
        grand_total_minutes += project_minutes
        grand_total_micros += project_micros
        grand_total_human_hours += _human_hours_for_project(db, project_id)

        if project_micros == 0 and not crows:
            # Skip projects with zero activity to keep iOS lists clean.
            continue

        project_budget_total = _micros_to_usd(
            int((project.get("budget_limit") or 0)) or project_micros * 2
        )
        project_budgets.append(
            ProjectBudget(
                id=project_id,
                project_name=project_name,
                spent=_micros_to_usd(project_micros),
                total=project_budget_total,
            )
        )
        cost_breakdown.append(
            CostBreakdownEntry(
                id=f"cb-{project_id}",
                project_name=project_name,
                amount=_micros_to_usd(project_micros),
                task_count=task_count,
            )
        )

    # Per-crow-type costs
    crow_costs: list[CrowCost] = []
    for ctype, micros in sorted(crow_micros_by_type.items()):
        crow_costs.append(
            CrowCost(
                id=f"cc-{ctype}",
                crow_name=ctype.capitalize(),
                role=_CROW_ROLE_LABELS.get(ctype, "Other"),
                amount=_micros_to_usd(micros),
            )
        )

    # ROI calc
    credits_spent_usd = _micros_to_usd(grand_total_micros)
    human_equiv_saved = (
        Decimal(grand_total_human_hours) * DEFAULT_HOURLY_RATE_USD
    ).quantize(Decimal("0.01"))
    roi_multiplier = (
        int(human_equiv_saved / credits_spent_usd) if credits_spent_usd > 0 else 0
    )

    return CreditsDataResponse(
        roi=ROISummary(
            roi_multiplier=roi_multiplier,
            human_equiv_saved=human_equiv_saved,
            credits_spent=credits_spent_usd,
            ai_minutes=grand_total_minutes,
            human_hours=grand_total_human_hours,
        ),
        balance=CreditBalance(remaining=None, total=None),
        project_budgets=project_budgets,
        cost_breakdown=cost_breakdown,
        crow_costs=crow_costs,
        breakdown_period="All time",
    )


def _project_id_from_sk(project: dict[str, Any]) -> str | None:
    """Fallback: extract project_id from the SK if `project_id` field is missing."""
    sk = project.get("SK", "")
    if isinstance(sk, str) and sk.startswith("P#"):
        return sk[2:]
    return None
