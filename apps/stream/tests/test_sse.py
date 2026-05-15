"""Tests for SSE frame encoding."""

from __future__ import annotations

from stream.sse import KEEPALIVE_COMMENT, encode_event


def test_encode_event_minimal() -> None:
    out = encode_event(
        event_id="1747332779#crow_assigned",
        event_name="wave_event",
        data={"event_type": "crow_assigned", "wave_id": "w1"},
    )
    assert out == (
        "id: 1747332779#crow_assigned\n"
        "event: wave_event\n"
        'data: {"event_type": "crow_assigned", "wave_id": "w1"}\n'
        "\n"
    )


def test_encode_event_escapes_newlines_in_data() -> None:
    out = encode_event(
        event_id="2",
        event_name="wave_event",
        data={"message": "line1\nline2"},
    )
    data_line = out.split("data: ", 1)[1].split("\n\n")[0]
    assert "\nline2" not in data_line


def test_encode_event_omits_id_when_none() -> None:
    out = encode_event(event_id=None, event_name="wave_event", data={"ok": True})
    assert "id:" not in out
    assert "event: wave_event\n" in out


def test_keepalive_is_comment_line() -> None:
    assert KEEPALIVE_COMMENT.startswith(":")
    assert KEEPALIVE_COMMENT.endswith("\n\n")
