"""Tests for the DDB Streams ↔ flat record normalizer."""

from __future__ import annotations

from stream.pipe_record import normalize_record, wave_id_from_pk


def test_flat_record_passes_through() -> None:
    raw = {"PK": "T#t#P#p#W#w", "SK": "x", "event_type": "crow_assigned"}
    assert normalize_record(raw) == raw


def test_streams_insert_unwraps_attribute_values() -> None:
    raw = {
        "eventName": "INSERT",
        "dynamodb": {
            "Keys": {"PK": {"S": "T#t#P#p#W#w"}},
            "NewImage": {
                "PK": {"S": "T#t#P#p#W#w"},
                "SK": {"S": "2026-05-15T21:00:00Z#crow_assigned"},
                "event_type": {"S": "crow_assigned"},
                "message": {"S": "implementer up"},
                "timestamp": {"S": "2026-05-15T21:00:00Z"},
                "mvi_id": {"S": "m1"},
            },
        },
    }
    out = normalize_record(raw)
    assert out is not None
    assert out["PK"] == "T#t#P#p#W#w"
    assert out["event_type"] == "crow_assigned"
    assert out["mvi_id"] == "m1"


def test_streams_modify_event_dropped() -> None:
    raw = {
        "eventName": "MODIFY",
        "dynamodb": {"NewImage": {"PK": {"S": "T#t#P#p#W#w"}}},
    }
    assert normalize_record(raw) is None


def test_streams_remove_event_dropped() -> None:
    raw = {
        "eventName": "REMOVE",
        "dynamodb": {"Keys": {"PK": {"S": "T#t#P#p#W#w"}}},
    }
    assert normalize_record(raw) is None


def test_streams_missing_new_image_returns_none() -> None:
    raw = {"eventName": "INSERT", "dynamodb": {}}
    assert normalize_record(raw) is None


def test_garbage_returns_none() -> None:
    assert normalize_record({}) is None
    assert normalize_record({"random": "stuff"}) is None


def test_attribute_value_numeric_int() -> None:
    raw = {
        "eventName": "INSERT",
        "dynamodb": {
            "NewImage": {
                "PK": {"S": "T#t#P#p#W#w"},
                "count": {"N": "42"},
            }
        },
    }
    out = normalize_record(raw)
    assert out is not None
    assert out["count"] == 42


def test_wave_id_from_pk_parses_correctly() -> None:
    assert wave_id_from_pk("T#tenant-abc#P#proj-1#W#w-1778872378963") == "w-1778872378963"


def test_wave_id_from_pk_returns_none_on_malformed() -> None:
    assert wave_id_from_pk("T#tenant-only") is None
    assert wave_id_from_pk("") is None
    assert wave_id_from_pk("garbage") is None
