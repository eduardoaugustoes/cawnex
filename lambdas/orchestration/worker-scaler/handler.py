"""Service scaler Lambda — auto scale-down for idle Worker AND Council services.

Runs every 15 minutes via EventBridge. For each managed service:
  - Worker: scale to 0 when no DISPATCH#pending crows exist.
  - Council: scale to 0 when no pending COUNCIL# rows exist.

Scale-UP is handled out-of-band: API for Worker (on wave activation), Murder
reactor for Council (after writing a COUNCIL# row in react_to_integration_complete).
"""

from __future__ import annotations

import os
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

TABLE_NAME = os.environ.get("TABLE_NAME", "cawnex")
ECS_CLUSTER_NAME = os.environ.get("ECS_CLUSTER_NAME", "")
ECS_SERVICE_NAME = os.environ.get("ECS_SERVICE_NAME", "")
COUNCIL_SERVICE_NAME = os.environ.get("COUNCIL_SERVICE_NAME", "")


def _scale_down_if_idle(
    ecs: Any,
    service_name: str,
    is_idle: bool,
) -> dict[str, Any]:
    if not service_name:
        return {"service": "", "action": "skipped", "reason": "no service configured"}
    services = ecs.describe_services(
        cluster=ECS_CLUSTER_NAME,
        services=[service_name],
    )
    if not services.get("services"):
        return {"service": service_name, "action": "skipped", "reason": "not found"}
    current_desired = services["services"][0].get("desiredCount", 0)
    if current_desired == 0:
        return {"service": service_name, "action": "already_scaled_down"}
    if not is_idle:
        return {"service": service_name, "action": "kept_running"}
    ecs.update_service(
        cluster=ECS_CLUSTER_NAME,
        service=service_name,
        desiredCount=0,
    )
    return {
        "service": service_name,
        "action": "scaled_down",
        "from": current_desired,
        "to": 0,
    }


def _worker_idle(table: Any) -> bool:
    response = table.query(
        IndexName="GSI1",
        KeyConditionExpression=Key("GSI1PK").eq("DISPATCH#pending"),
        Limit=1,
    )
    return len(response.get("Items", [])) == 0


def _council_idle(table: Any) -> bool:
    """Council is idle when no COUNCIL# row has status=pending or running."""
    response = table.scan(
        FilterExpression="begins_with(SK, :sk) AND (#s = :p OR #s = :r)",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":sk": "COUNCIL#",
            ":p": "pending",
            ":r": "running",
        },
        Limit=1,
    )
    return len(response.get("Items", [])) == 0


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Scale down idle services. Returns per-service result."""
    if not ECS_CLUSTER_NAME:
        return {"action": "skipped", "reason": "ECS_CLUSTER_NAME missing"}

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(TABLE_NAME)
    ecs = boto3.client("ecs")

    results = [
        _scale_down_if_idle(ecs, ECS_SERVICE_NAME, _worker_idle(table)),
        _scale_down_if_idle(ecs, COUNCIL_SERVICE_NAME, _council_idle(table)),
    ]
    return {"results": results}
