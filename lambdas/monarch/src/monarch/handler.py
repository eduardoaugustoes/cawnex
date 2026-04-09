"""Lambda entry point — DynamoDB Stream -> Monarch orchestrator.

Filters INSERT events where SK begins with MONARCH# and status is pending,
then runs the full project setup chain.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from monarch.agent import run_monarch
from monarch.continuation import run_monarch_continuation, run_monarch_wave_launch
from monarch.stream import deserialize_stream_record

log = logging.getLogger(__name__)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, int]:
    """Process DynamoDB Stream events."""
    processed = 0
    skipped = 0

    for record in event.get("Records", []):
        if record.get("eventName") != "INSERT":
            skipped += 1
            continue

        new_image = record.get("dynamodb", {}).get("NewImage")
        if not new_image:
            skipped += 1
            continue

        item = deserialize_stream_record(new_image)
        sk = str(item.get("SK", ""))

        if not sk.startswith("MONARCH#"):
            skipped += 1
            continue

        if item.get("status") != "pending":
            skipped += 1
            continue

        try:
            mode = item.get("mode", "")
            if mode == "continuation":
                run_monarch_continuation(item)
            elif mode == "wave_launch":
                run_monarch_wave_launch(item)
            else:
                run_monarch(item)
            processed += 1
        except Exception as exc:
            log.error(
                json.dumps(
                    {
                        "event": "handler_error",
                        "pk": item.get("PK", ""),
                        "sk": sk,
                        "error": str(exc),
                    }
                )
            )
            raise

    return {"processed": processed, "skipped": skipped}
