"""Project maturity stage inference based on project signals."""

from __future__ import annotations

from typing import Any

# Thresholds for maturity stage transitions
# mvp -> growth: project has shipped enough to prove viability
# growth -> scale: project is stable with good quality signals
# scale -> mature: project is production-hardened
_THRESHOLDS = {
    "growth": {
        "waves_delivered": 3,
        "mvis_shipped": 8,
    },
    "scale": {
        "waves_delivered": 8,
        "mvis_shipped": 25,
        "min_avg_coverage": 70.0,
    },
    "mature": {
        "waves_delivered": 15,
        "mvis_shipped": 50,
        "min_avg_coverage": 80.0,
        "max_rejection_rate": 0.1,
    },
}

_STAGE_ORDER = ["mvp", "growth", "scale", "mature"]


def assess_maturity(
    current_stage: str,
    waves_delivered: int,
    mvis_shipped: int,
    avg_coverage: float | None = None,
    council_rejection_rate: float | None = None,
) -> str:
    """Determine the project maturity stage based on signals.

    Only advances one stage at a time. Never regresses.
    Returns the new stage (may be same as current).
    """
    current_idx = _STAGE_ORDER.index(current_stage) if current_stage in _STAGE_ORDER else 0
    next_idx = current_idx + 1

    if next_idx >= len(_STAGE_ORDER):
        return current_stage  # already at max

    next_stage = _STAGE_ORDER[next_idx]
    thresholds = _THRESHOLDS.get(next_stage, {})

    # Check all required thresholds
    if waves_delivered < thresholds.get("waves_delivered", 0):
        return current_stage

    if mvis_shipped < thresholds.get("mvis_shipped", 0):
        return current_stage

    min_coverage = thresholds.get("min_avg_coverage")
    if min_coverage is not None and avg_coverage is not None:
        if avg_coverage < min_coverage:
            return current_stage

    max_rejection = thresholds.get("max_rejection_rate")
    if max_rejection is not None and council_rejection_rate is not None:
        if council_rejection_rate > max_rejection:
            return current_stage

    return next_stage


def gather_project_signals(
    table: Any,
    pk: str,
) -> dict[str, Any]:
    """Query DynamoDB for project maturity signals."""
    from boto3.dynamodb.conditions import Key

    # Count delivered waves
    wave_items = table.query(
        KeyConditionExpression=Key("PK").eq(pk) & Key("SK").begins_with("S#w"),
    ).get("Items", [])

    waves = [w for w in wave_items if w.get("level") == "wave"]
    waves_delivered = sum(1 for w in waves if w.get("status") == "delivered")

    # Count shipped MVIs across all waves
    all_items = table.query(
        KeyConditionExpression=Key("PK").eq(pk) & Key("SK").begins_with("S#"),
    ).get("Items", [])

    mvis = [m for m in all_items if m.get("level") == "murder"]
    mvis_shipped = sum(1 for m in mvis if m.get("status") == "shipped")

    # Average coverage from deterministic checks
    coverages: list[float] = []
    for mvi in mvis:
        checks = mvi.get("deterministic_checks", {})
        details = checks.get("details", [])
        for detail in details:
            if detail.get("name") == "coverage_no_drop" and "%" in detail.get("detail", ""):
                # Parse "80.0% -> 82.0%" format
                parts = detail["detail"].split("->")
                if len(parts) == 2:
                    try:
                        after = float(parts[1].strip().rstrip("%"))
                        coverages.append(after)
                    except ValueError:
                        pass

    avg_coverage = sum(coverages) / len(coverages) if coverages else None

    # Council rejection rate
    council_items = table.query(
        KeyConditionExpression=Key("PK").eq(pk) & Key("SK").begins_with("COUNCIL#"),
    ).get("Items", [])

    completed_councils = [c for c in council_items if c.get("status") == "completed"]
    rejections = sum(
        1
        for c in completed_councils
        if c.get("decision", {}).get("action") == "reject"
    )
    rejection_rate = (
        rejections / len(completed_councils) if completed_councils else 0.0
    )

    return {
        "waves_delivered": waves_delivered,
        "mvis_shipped": mvis_shipped,
        "avg_coverage": avg_coverage,
        "council_rejection_rate": rejection_rate,
    }
