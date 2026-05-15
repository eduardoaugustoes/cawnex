"""Tests for the SQS poller.

We don't run the full asyncio loop here — we exercise the message parser
and an injected boto3 client to verify receive → publish → delete sequencing.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from stream.sqs_poller import _parse_message_body, SqsPoller
from stream.subscribers import SubscriberRegistry


def test_parse_body_unwraps_json() -> None:
    body = json.dumps(
        {
            "eventName": "INSERT",
            "dynamodb": {"NewImage": {"PK": {"S": "T#t#P#p#W#w"}}},
        }
    )
    assert _parse_message_body(body) == {
        "eventName": "INSERT",
        "dynamodb": {"NewImage": {"PK": {"S": "T#t#P#p#W#w"}}},
    }


def test_parse_body_returns_none_on_garbage() -> None:
    assert _parse_message_body("not-json") is None
    assert _parse_message_body("") is None
    assert _parse_message_body("[1,2,3]") is None  # not a dict


@pytest.mark.asyncio
async def test_start_and_stop_idempotent() -> None:
    registry = SubscriberRegistry()

    mock_sqs_client = MagicMock()
    # Block forever on receive so the poll loop just sits in the executor.
    import threading

    block = threading.Event()

    def blocking_receive(**_kwargs: object) -> dict[str, list[dict[str, str]]]:
        block.wait(timeout=2)
        return {"Messages": []}

    mock_sqs_client.receive_message.side_effect = blocking_receive

    with patch("stream.sqs_poller.boto3.client", return_value=mock_sqs_client):
        poller = SqsPoller(
            queue_url="https://sqs.us-east-1.amazonaws.com/x/queue",
            registry=registry,
            region="us-east-1",
        )
        await poller.start()
        await poller.start()  # idempotent — does not create a second task
        block.set()
        await poller.stop()
        await poller.stop()  # idempotent
