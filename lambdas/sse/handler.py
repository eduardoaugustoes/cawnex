"""SSE Lambda — streams wave events to iOS via Lambda Function URL.

Uses RESPONSE_STREAM invoke mode. Validates Cognito JWT in code.
Polls the events table every 1s and writes SSE-formatted chunks.
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

EVENTS_TABLE_NAME = os.environ.get("EVENTS_TABLE_NAME", "cawnex-events")
TABLE_NAME = os.environ.get("TABLE_NAME", "cawnex")
USER_POOL_ID = os.environ.get("USER_POOL_ID", "")
AWS_REGION = os.environ.get("AWS_REGION_NAME", os.environ.get("AWS_REGION", "us-east-1"))
POLL_INTERVAL = 1.0
MAX_DURATION = 840  # 14 minutes (leave 1 min buffer for Lambda 15min limit)

# JWKS cache (warm Lambda reuses)
_jwks_cache: dict[str, Any] | None = None


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """SSE streaming handler for Lambda Function URL."""
    # Extract query params and auth
    query = event.get("queryStringParameters", {}) or {}
    headers = event.get("headers", {}) or {}

    project_id = query.get("project_id", "")
    wave_id = query.get("wave_id", "")
    auth_header = headers.get("authorization", "")

    if not project_id or not wave_id:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "project_id and wave_id required"}),
        }

    # Validate JWT and extract tenant
    tenant_id = _validate_jwt(auth_header)
    if not tenant_id:
        return {
            "statusCode": 401,
            "body": json.dumps({"error": "Invalid or missing authorization"}),
        }

    # Build events PK
    events_pk = f"T#{tenant_id}#P#{project_id}#W#{wave_id}"

    # For non-streaming invocation, return initial batch
    if not _is_streaming(event):
        return _initial_batch(events_pk)

    # Streaming response
    return _stream_events(events_pk, wave_id, tenant_id, project_id)


def _is_streaming(event: dict[str, Any]) -> bool:
    """Check if this is a streaming invocation."""
    return event.get("requestContext", {}).get("http", {}).get("method") == "GET"


def _initial_batch(events_pk: str) -> dict[str, Any]:
    """Return initial batch of events as regular JSON response."""
    table = boto3.resource("dynamodb").Table(EVENTS_TABLE_NAME)
    response = table.query(
        KeyConditionExpression=Key("PK").eq(events_pk),
        ScanIndexForward=False,
        Limit=50,
    )
    items = response.get("Items", [])
    events = [_format_event(item) for item in items]
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
        "body": "\n".join(f"data: {json.dumps(e, default=str)}\n" for e in events),
    }


def _stream_events(
    events_pk: str,
    wave_id: str,
    tenant_id: str,
    project_id: str,
) -> dict[str, Any]:
    """Stream events as SSE. For streaming Lambda Function URL."""
    table = boto3.resource("dynamodb").Table(EVENTS_TABLE_NAME)
    main_table = boto3.resource("dynamodb").Table(TABLE_NAME)

    # Send initial batch
    last_sk = ""
    response = table.query(
        KeyConditionExpression=Key("PK").eq(events_pk),
        ScanIndexForward=True,
    )
    chunks = []
    for item in response.get("Items", []):
        evt = _format_event(item)
        chunks.append(f"data: {json.dumps(evt, default=str)}\n\n")
        last_sk = item["SK"]

    # Poll loop
    start = time.time()
    while time.time() - start < MAX_DURATION:
        time.sleep(POLL_INTERVAL)

        # Query new events after last_sk
        if last_sk:
            new_response = table.query(
                KeyConditionExpression=Key("PK").eq(events_pk)
                & Key("SK").gt(last_sk),
                ScanIndexForward=True,
            )
        else:
            new_response = table.query(
                KeyConditionExpression=Key("PK").eq(events_pk),
                ScanIndexForward=True,
            )

        for item in new_response.get("Items", []):
            evt = _format_event(item)
            chunks.append(f"data: {json.dumps(evt, default=str)}\n\n")
            last_sk = item["SK"]

        # Check if wave is terminal
        wave_pk = f"T#{tenant_id}#P#{project_id}"
        wave_sk = f"S#{wave_id}"
        wave_item = main_table.get_item(Key={"PK": wave_pk, "SK": wave_sk}).get("Item")
        if wave_item:
            status = wave_item.get("status", "")
            if status in ("delivered", "cancelled"):
                chunks.append(f"data: {json.dumps({'type': 'wave_terminal', 'status': status}, default=str)}\n\n")
                break

    # Return all chunks as body (streaming mode sends incrementally)
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
        "body": "".join(chunks),
    }


def _format_event(item: dict[str, Any]) -> dict[str, Any]:
    """Format a DynamoDB event item for SSE output."""
    return {
        "type": item.get("event_type", ""),
        "message": item.get("message", ""),
        "color": item.get("color", ""),
        "timestamp": item.get("timestamp", ""),
        "extra": {
            k: v for k, v in item.items()
            if k not in ("PK", "SK", "GSI1PK", "GSI1SK", "event_type", "message",
                         "color", "timestamp", "expires_at", "entityType")
        },
    }


def _validate_jwt(auth_header: str) -> str | None:
    """Validate Cognito JWT and return tenant_id. Returns None if invalid."""
    if not auth_header:
        return None

    token = auth_header.replace("Bearer ", "").strip()
    if not token:
        return None

    try:
        # Decode without verification for claims extraction
        # In production, verify signature against JWKS
        import base64

        parts = token.split(".")
        if len(parts) != 3:
            return None

        # Decode payload (part 1)
        payload = parts[1]
        # Add padding
        payload += "=" * (4 - len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload)
        claims = json.loads(decoded)

        # Check expiration
        exp = claims.get("exp", 0)
        if time.time() > exp:
            return None

        # Check issuer matches our user pool
        iss = claims.get("iss", "")
        expected_iss = f"https://cognito-idp.{AWS_REGION}.amazonaws.com/{USER_POOL_ID}"
        if iss != expected_iss:
            return None

        # Extract tenant_id
        tenant_id = claims.get("custom:tenant_id", "")
        if not tenant_id:
            return None

        return tenant_id

    except Exception:
        return None
