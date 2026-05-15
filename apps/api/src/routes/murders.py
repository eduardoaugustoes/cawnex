"""Murders route — static catalog of Murder types + their crow rosters.

Per the design spec, v1 returns a hardcoded catalog. Live state (which
crows are currently building, behavior lines like "2 crows building")
returns placeholder values — building real telemetry needs a separate
rollup pass and is deferred to a later phase. This unblocks the iOS
Murders screen from showing fabricated runtime numbers while keeping
the catalog data trustworthy.

Color, icon, and the marketplace items mirror what the iOS mock used
so the screen renders the same way once the API path is wired.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.auth.dependencies import get_tenant
from src.auth.tenant import TenantContext

router = APIRouter(prefix="/murders", tags=["murders"])


class CrowSummary(BaseModel):
    """One crow in a murder's roster."""

    id: str
    name: str
    is_active: bool


class BehaviorLine(BaseModel):
    """One live-status line shown on the murder card. Placeholder for v1."""

    id: str
    text: str
    tone: str  # "success" | "info" | "warning" | "muted"


class Murder(BaseModel):
    """One murder configuration."""

    id: str
    name: str
    type: str  # MurderType raw value: dev / editorial / infra / data / social
    description: str
    status: str  # "active" | "idle" | "error"
    icon: str
    behavior_lines: list[BehaviorLine]
    crows: list[CrowSummary]
    tasks_done: int
    success_rate: int
    total_cost: Decimal


class MarketplaceMurder(BaseModel):
    """Pre-built murder template in the marketplace."""

    id: str
    name: str
    icon: str
    icon_color: str  # iOS-side maps to CawnexColors
    description: str
    rating: float
    installs: str
    author: str


class MurdersDataResponse(BaseModel):
    """Aggregated murders view matching iOS MurdersData."""

    murders: list[Murder]
    marketplace: list[MarketplaceMurder]


# ---- catalog ---------------------------------------------------------------

_DEFAULT_CATALOG: list[Murder] = [
    Murder(
        id="m-dev",
        name="Dev Murder",
        type="dev",
        description="Software development orchestration",
        status="idle",
        icon="bird.fill",
        behavior_lines=[],
        crows=[
            CrowSummary(id="cr-planner", name="Planner", is_active=False),
            CrowSummary(id="cr-implementer", name="Implementer", is_active=False),
            CrowSummary(id="cr-reviewer", name="Reviewer", is_active=False),
            CrowSummary(id="cr-fixer", name="Fixer", is_active=False),
        ],
        tasks_done=0,
        success_rate=0,
        total_cost=Decimal("0.00"),
    ),
    Murder(
        id="m-editorial",
        name="Editorial Murder",
        type="editorial",
        description="Book & long-form content creation",
        status="idle",
        icon="book.fill",
        behavior_lines=[],
        crows=[
            CrowSummary(id="cr-researcher", name="Researcher", is_active=False),
            CrowSummary(id="cr-writer", name="Writer", is_active=False),
            CrowSummary(id="cr-editor", name="Editor", is_active=False),
            CrowSummary(id="cr-proofreader", name="Proofreader", is_active=False),
        ],
        tasks_done=0,
        success_rate=0,
        total_cost=Decimal("0.00"),
    ),
    Murder(
        id="m-social",
        name="Social Murder",
        type="social",
        description="Social media content & publishing",
        status="idle",
        icon="megaphone.fill",
        behavior_lines=[],
        crows=[
            CrowSummary(id="cr-creator", name="Creator", is_active=False),
            CrowSummary(id="cr-designer", name="Designer", is_active=False),
            CrowSummary(id="cr-scheduler", name="Scheduler", is_active=False),
            CrowSummary(id="cr-analyst", name="Analyst", is_active=False),
        ],
        tasks_done=0,
        success_rate=0,
        total_cost=Decimal("0.00"),
    ),
    Murder(
        id="m-infra",
        name="Infra Murder",
        type="infra",
        description="Cloud infrastructure & operations",
        status="idle",
        icon="server.rack",
        behavior_lines=[],
        crows=[
            CrowSummary(id="cr-architect", name="Architect", is_active=False),
            CrowSummary(id="cr-deployer", name="Deployer", is_active=False),
            CrowSummary(id="cr-monitor", name="Monitor", is_active=False),
        ],
        tasks_done=0,
        success_rate=0,
        total_cost=Decimal("0.00"),
    ),
    Murder(
        id="m-data",
        name="Data Murder",
        type="data",
        description="Data pipelines, analytics, ML",
        status="idle",
        icon="chart.line.uptrend.xyaxis",
        behavior_lines=[],
        crows=[
            CrowSummary(id="cr-ingestor", name="Ingestor", is_active=False),
            CrowSummary(id="cr-transformer", name="Transformer", is_active=False),
            CrowSummary(id="cr-analyst", name="Analyst", is_active=False),
        ],
        tasks_done=0,
        success_rate=0,
        total_cost=Decimal("0.00"),
    ),
]

_DEFAULT_MARKETPLACE: list[MarketplaceMurder] = [
    MarketplaceMurder(
        id="mp-infra",
        name="Infra Murder",
        icon="server.rack",
        icon_color="info",
        description="Pre-built infrastructure orchestration with battle-tested crows.",
        rating=4.7,
        installs="1.2k",
        author="Cawnex Team",
    ),
    MarketplaceMurder(
        id="mp-data",
        name="Data Murder",
        icon="chart.line.uptrend.xyaxis",
        icon_color="primary",
        description="ETL + analytics + ML workflows packaged for quick start.",
        rating=4.5,
        installs="850",
        author="Cawnex Team",
    ),
]


@router.get("", response_model=MurdersDataResponse)
async def get_murders(
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> MurdersDataResponse:
    """Return the static murder catalog + marketplace templates.

    Live state (active crows, behavior lines, per-murder stats) is a
    placeholder. Real rollup will come from aggregating wave/crow snapshots
    by murder type — deferred to a later phase. The catalog itself is
    trustworthy: iOS can rely on `murders[*].crows` and types.
    """
    return MurdersDataResponse(
        murders=_DEFAULT_CATALOG,
        marketplace=_DEFAULT_MARKETPLACE,
    )
