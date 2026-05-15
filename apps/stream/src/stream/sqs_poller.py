"""SQS poller — background task that drains the EventBridge Pipe target queue.

EventBridge Pipes can't POST directly to HTTP. So the production path is:

    DDB Streams → EventBridge Pipe → SQS queue → this poller → SubscriberRegistry

Messages on the queue are DDB Streams records (EventName, dynamodb.NewImage, …)
wrapped one-per-message by the Pipe. We long-poll, batch up to 10 at a time,
hand them to `publish_records`, and delete on success.

Failures: if `publish_records` raises (it shouldn't — it only fan-outs in
memory), we leave the message on the queue and SQS retries via visibility
timeout. Records that fail to parse return `None` from `record_to_frame`
and are silently deleted (we don't want them re-driven forever).
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import boto3

from stream.routes_pipe import publish_records
from stream.subscribers import SubscriberRegistry

log = logging.getLogger(__name__)


# SQS long-poll wait. 20s is the max and dramatically cheaper than short polling.
LONG_POLL_WAIT_SEC = 20
MAX_MESSAGES_PER_RECEIVE = 10


class SqsPoller:
    """Owns the receive→publish→delete loop for one SQS queue."""

    def __init__(
        self,
        *,
        queue_url: str,
        registry: SubscriberRegistry,
        region: str,
    ) -> None:
        self._queue_url = queue_url
        self._registry = registry
        self._client = boto3.client("sqs", region_name=region)
        self._task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()

    async def start(self) -> None:
        """Spawn the poll loop in the background. Idempotent."""
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run(), name="sqs-poller")

    async def stop(self) -> None:
        """Signal the loop to exit and wait for it. Idempotent."""
        if self._task is None:
            return
        self._stopping.set()
        try:
            await asyncio.wait_for(self._task, timeout=LONG_POLL_WAIT_SEC + 5)
        except asyncio.TimeoutError:
            self._task.cancel()
        self._task = None

    async def _run(self) -> None:
        """Long-poll forever, exit cleanly on stop()."""
        loop = asyncio.get_running_loop()
        log.info("sqs poller starting queue=%s", self._queue_url)
        while not self._stopping.is_set():
            try:
                resp = await loop.run_in_executor(None, self._receive)
            except Exception:  # noqa: BLE001 — keep looping; AWS hiccups are normal
                log.exception("sqs receive failed")
                await asyncio.sleep(2)
                continue

            messages = resp.get("Messages", [])
            if not messages:
                continue

            records = []
            receipts = []
            for msg in messages:
                receipts.append(msg["ReceiptHandle"])
                body = msg.get("Body", "")
                parsed = _parse_message_body(body)
                if parsed is not None:
                    records.append(parsed)

            if records:
                try:
                    published = await publish_records(self._registry, records)
                    log.info(
                        "sqs poll batch=%d records=%d published=%d",
                        len(messages),
                        len(records),
                        published,
                    )
                except Exception:  # noqa: BLE001
                    log.exception("publish_records raised — leaving messages on queue")
                    continue  # do not delete; let SQS redrive

            await loop.run_in_executor(None, self._delete_batch, receipts)
        log.info("sqs poller stopped")

    def _receive(self) -> dict[str, Any]:
        return self._client.receive_message(
            QueueUrl=self._queue_url,
            MaxNumberOfMessages=MAX_MESSAGES_PER_RECEIVE,
            WaitTimeSeconds=LONG_POLL_WAIT_SEC,
        )

    def _delete_batch(self, receipts: list[str]) -> None:
        if not receipts:
            return
        entries = [{"Id": str(i), "ReceiptHandle": r} for i, r in enumerate(receipts)]
        self._client.delete_message_batch(QueueUrl=self._queue_url, Entries=entries)


def _parse_message_body(body: str) -> dict[str, Any] | None:
    """SQS messages are JSON strings. Returns dict or None."""
    if not body:
        return None
    try:
        parsed = json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return None
    if isinstance(parsed, dict):
        return parsed
    return None
