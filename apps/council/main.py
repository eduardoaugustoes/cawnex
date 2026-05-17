"""ECS Fargate entrypoint — polls for pending Council sessions."""

from __future__ import annotations

import asyncio
import logging
import os
import time

import boto3

from council._blackboard import Blackboard
from council.handler import process_pending_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("council-loop")

POLL_INTERVAL_SECONDS = 10


async def poll_once(blackboard: Blackboard) -> int:
    """Find one pending COUNCIL# session and process it. Returns count handled."""
    items = blackboard.scan_pending_council_sessions()
    if not items:
        return 0
    item = items[0]
    project_id = item["PK"].replace("P#", "")
    await process_pending_session(
        blackboard=blackboard,
        project_id=project_id,
        session_sk=item["SK"],
    )
    return 1


def main() -> None:
    logger.info("Council Fargate starting continuous poll loop")
    region = os.environ.get("AWS_REGION", "us-east-1")
    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(os.environ["TABLE_NAME"])
    events_name = os.environ.get("EVENTS_TABLE_NAME")
    events_table = dynamodb.Table(events_name) if events_name else None
    blackboard = Blackboard(table, events_table=events_table)

    while True:
        try:
            processed = asyncio.run(poll_once(blackboard))
            if processed:
                logger.info(f"Poll: processed={processed}")
        except Exception as e:  # noqa: BLE001 -- poll loop must not die on per-iter errors
            logger.error(f"Poll error: {e}", exc_info=True)
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
