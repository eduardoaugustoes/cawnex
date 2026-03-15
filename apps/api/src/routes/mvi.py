"""MVI routes — ship an MVI."""

from datetime import datetime, timezone
from typing import Annotated, Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.auth.dependencies import get_tenant
from src.auth.tenant import TenantContext
from src.db.client import TenantDB

router = APIRouter(
    prefix="/projects/{project_id}/waves/{wave_id}/mvis",
    tags=["mvis"],
)


class ShipResponse(BaseModel):
    status: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.post("/{mvi_id}/ship", response_model=ShipResponse)
async def ship_mvi(
    project_id: str,
    wave_id: str,
    mvi_id: str,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> Dict[str, Any]:
    """Ship an MVI that is ready to ship.

    Verifies the MVI is in status=ready_to_ship with can_ship=true,
    then transitions it to status=shipped per Contract 5.
    """
    db = TenantDB(tenant)
    sk = f"S#{wave_id}#m{mvi_id}"

    mvi = db.get_project_item(project_id=project_id, sk=sk)
    if mvi is None:
        raise HTTPException(status_code=404, detail="MVI not found")

    if mvi.get("status") != "ready_to_ship":
        raise HTTPException(
            status_code=409,
            detail=f"MVI is not ready to ship (status={mvi.get('status')})",
        )

    if not mvi.get("can_ship", False):
        raise HTTPException(status_code=409, detail="MVI cannot be shipped yet")

    db.update_project_item(
        project_id=project_id,
        sk=sk,
        updates={"status": "shipped", "shipped_at": _now_iso()},
    )

    return {"status": "shipped"}
