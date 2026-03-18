"""DynamoDB Stream record deserialization."""

from __future__ import annotations

from typing import Any


def deserialize_stream_record(item: dict[str, Any]) -> dict[str, Any]:
    """Convert DynamoDB Stream format to plain dict."""
    result: dict[str, Any] = {}
    for key, val in item.items():
        if "S" in val:
            result[key] = val["S"]
        elif "N" in val:
            result[key] = val["N"]
        elif "BOOL" in val:
            result[key] = val["BOOL"]
        elif "NULL" in val:
            result[key] = None
        elif "M" in val:
            result[key] = deserialize_stream_record(val["M"])
        elif "L" in val:
            result[key] = [
                deserialize_stream_record({"_": v})["_"] if isinstance(v, dict) else v
                for v in val["L"]
            ]
    return result
