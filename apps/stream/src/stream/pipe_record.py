"""Parse pipe records into (wave_id, SSE-frame-data) tuples.

Two shapes are accepted:

1. **Flat record** (manual /_pipe injection, used by tests and ops):
   {"PK": "T#t#P#p#W#w", "SK": "...", "event_type": "...", "message": "...", ...}

2. **DDB Streams record via EventBridge Pipe** — when DynamoDB Streams
   feeds into an EventBridge Pipe targeted at SQS, each message body is
   a single stream record with NewImage in DDB AttributeValue format:
   {
     "eventName": "INSERT",
     "dynamodb": {
       "Keys": {"PK": {"S": "..."}, "SK": {"S": "..."}},
       "NewImage": {
         "PK": {"S": "T#t#P#p#W#w"},
         "SK": {"S": "..."},
         "event_type": {"S": "crow_assigned"},
         "message": {"S": "..."},
         "timestamp": {"S": "..."},
         "mvi_id": {"S": "m1"}
       }
     }
   }

We unwrap both shapes into the same downstream tuple.
"""

from __future__ import annotations

import re
from typing import Any

_PK_PATTERN = re.compile(r"^T#(?P<tenant>[^#]+)#P#(?P<project>[^#]+)#W#(?P<wave>[^#]+)$")


def wave_id_from_pk(pk: str) -> str | None:
    match = _PK_PATTERN.match(pk)
    return match.group("wave") if match else None


def _unwrap_attribute_value(attr: Any) -> Any:
    """Convert a single DDB AttributeValue dict to a Python value."""
    if not isinstance(attr, dict) or len(attr) != 1:
        return None
    (type_key, value), = attr.items()
    if type_key == "S":
        return value
    if type_key == "N":
        try:
            return int(value) if "." not in value else float(value)
        except (ValueError, TypeError):
            return value
    if type_key == "BOOL":
        return bool(value)
    if type_key == "NULL":
        return None
    if type_key == "L":
        return [_unwrap_attribute_value(v) for v in value]
    if type_key == "M":
        return {k: _unwrap_attribute_value(v) for k, v in value.items()}
    return value


def _unwrap_streams_image(image: dict[str, Any]) -> dict[str, Any]:
    """Convert {key: {"S": val}, ...} → {key: val, ...}."""
    return {key: _unwrap_attribute_value(attr) for key, attr in image.items()}


def normalize_record(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Return a flat event dict regardless of input shape, or None if unparseable.

    Always returns at least PK; other fields may be absent.
    """
    # Shape 2: DDB Streams via EventBridge Pipe (nested under "dynamodb").
    if "dynamodb" in raw and isinstance(raw["dynamodb"], dict):
        # Pipes can emit MODIFY/REMOVE too; we only broadcast INSERTs.
        if raw.get("eventName") not in (None, "INSERT"):
            return None
        new_image = raw["dynamodb"].get("NewImage")
        if not isinstance(new_image, dict):
            return None
        return _unwrap_streams_image(new_image)

    # Shape 1: flat record.
    if "PK" in raw:
        return raw

    return None
