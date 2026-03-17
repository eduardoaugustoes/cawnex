"""Worker Scaler Lambda — auto scale-down ECS when no work pending.

Runs every 15 minutes via EventBridge. Checks GSI1 for DISPATCH#pending
crows. If none found, sets ECS desiredCount to 0.
"""

from __future__ import annotations

import os
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

TABLE_NAME = os.environ.get("TABLE_NAME", "cawnex")
ECS_CLUSTER_NAME = os.environ.get("ECS_CLUSTER_NAME", "")
ECS_SERVICE_NAME = os.environ.get("ECS_SERVICE_NAME", "")


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Check for pending work. Scale down ECS if idle."""
    if not ECS_CLUSTER_NAME or not ECS_SERVICE_NAME:
        return {"action": "skipped", "reason": "ECS config missing"}

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(TABLE_NAME)
    ecs = boto3.client("ecs")

    # Check current ECS desired count
    services = ecs.describe_services(
        cluster=ECS_CLUSTER_NAME,
        services=[ECS_SERVICE_NAME],
    )
    if not services.get("services"):
        return {"action": "skipped", "reason": "service not found"}

    service = services["services"][0]
    current_desired = service.get("desiredCount", 0)

    if current_desired == 0:
        return {"action": "already_scaled_down"}

    # Check for pending crows in GSI1
    response = table.query(
        IndexName="GSI1",
        KeyConditionExpression=Key("GSI1PK").eq("DISPATCH#pending"),
        Limit=1,
    )
    pending_count = len(response.get("Items", []))

    if pending_count > 0:
        return {"action": "kept_running", "pending": pending_count}

    # Check for running crows (status=running in main table)
    # Simple heuristic: if no pending, check if any crows are running
    # by scanning recent wave items. For MVP, just check pending is sufficient.

    # Scale down
    ecs.update_service(
        cluster=ECS_CLUSTER_NAME,
        service=ECS_SERVICE_NAME,
        desiredCount=0,
    )

    return {"action": "scaled_down", "from": current_desired, "to": 0}
