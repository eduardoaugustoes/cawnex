"""Lambda entry point — DynamoDB Stream -> Murder reactor.

Deserializes stream records, filters for relevant events,
and routes to the appropriate reactor function.
"""

from __future__ import annotations

from typing import Any

import boto3

from murder.blackboard import Blackboard
from murder.config import EVENTS_TABLE_NAME, TABLE_NAME
from murder.logging import StructuredLogger
from murder.reactor import (
    react_to_crow_completion,
    react_to_human_task_completed,
    react_to_mvi_queued,
)
from murder.stream import deserialize_stream_record


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, int]:
    """Process DynamoDB Stream events."""
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(TABLE_NAME)
    events_table = dynamodb.Table(EVENTS_TABLE_NAME) if EVENTS_TABLE_NAME else None
    blackboard = Blackboard(table, events_table=events_table)
    logger = StructuredLogger("murder-handler")

    processed = 0
    skipped = 0

    for record in event.get("Records", []):
        event_name = record.get("eventName", "")
        if event_name not in ("INSERT", "MODIFY"):
            skipped += 1
            continue

        new_image = record.get("dynamodb", {}).get("NewImage")
        if not new_image:
            skipped += 1
            continue

        item = deserialize_stream_record(new_image)

        old_image = record.get("dynamodb", {}).get("OldImage")
        old_item = deserialize_stream_record(old_image) if old_image else {}

        if _should_skip(item, old_item):
            skipped += 1
            continue

        level = item.get("level", "")
        status = item.get("status", "")

        task_type = item.get("task_type", "")

        try:
            if level == "crow" and task_type == "human" and status == "completed":
                react_to_human_task_completed(blackboard, item, logger)
                processed += 1
            elif level == "crow" and status in ("completed", "failed"):
                react_to_crow_completion(blackboard, item, logger)
                processed += 1
            elif level == "murder" and status == "queued":
                react_to_mvi_queued(blackboard, item, logger)
                processed += 1
            else:
                skipped += 1
        except Exception:
            logger.error(
                "record_processing_failed",
                level=level,
                status=status,
                pk=item.get("PK", ""),
            )
            raise

    return {"processed": processed, "skipped": skipped}


def _should_skip(new_item: dict[str, Any], old_item: dict[str, Any]) -> bool:
    """Guard against duplicate processing on stream retries.

    If old and new status are the same, this is a non-status update
    (or a stream retry) — skip to prevent re-triggering.
    """
    if not old_item:
        return False
    return new_item.get("status") == old_item.get("status")
