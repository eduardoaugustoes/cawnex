"""Scheduled checker Lambda — queries CHECK records and dispatches verification crows."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key


TABLE_NAME = os.environ.get("TABLE_NAME", "cawnex")
QUEUE_URL = os.environ.get("QUEUE_URL", "")


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Query CHECK records with ttl <= now and dispatch verification tasks."""
    table = boto3.resource("dynamodb").Table(TABLE_NAME)
    sqs = boto3.client("sqs")

    now = datetime.now(timezone.utc).isoformat()
    processed = 0
    skipped = 0

    # Scan for CHECK records — in production, use a GSI for efficiency
    response = table.scan(
        FilterExpression="begins_with(SK, :prefix) AND #ttl <= :now",
        ExpressionAttributeNames={"#ttl": "ttl"},
        ExpressionAttributeValues={
            ":prefix": "CHECK#",
            ":now": now,
        },
    )

    for item in response.get("Items", []):
        human_task_id = item.get("human_task_id", "")
        retry_count = int(item.get("retry_count", 0))
        max_retries = int(item.get("max_retries", 3))

        if retry_count >= max_retries:
            # Max retries exceeded — update check record, skip dispatch
            table.update_item(
                Key={"PK": item["PK"], "SK": item["SK"]},
                UpdateExpression="SET #s = :s",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":s": "max_retries_exceeded"},
            )
            skipped += 1
            continue

        # Increment retry count
        table.update_item(
            Key={"PK": item["PK"], "SK": item["SK"]},
            UpdateExpression="SET retry_count = retry_count + :one",
            ExpressionAttributeValues={":one": 1},
        )

        # Dispatch verification task via SQS
        if QUEUE_URL:
            sqs.send_message(
                QueueUrl=QUEUE_URL,
                MessageBody=json.dumps({
                    "type": "verification_check",
                    "pk": item["PK"],
                    "human_task_id": human_task_id,
                    "check_type": item.get("check_type", "crow_check"),
                    "instructions": item.get("instructions", ""),
                    "required_secrets": item.get("required_secrets", []),
                }),
            )

        processed += 1

    return {"processed": processed, "skipped": skipped}
