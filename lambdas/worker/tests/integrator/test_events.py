"""Tests for the loud-failure event helper."""

from unittest.mock import MagicMock

from worker.integrator.events import emit_pipeline_error


def test_emit_pipeline_error_writes_to_events_table_and_logs() -> None:
    blackboard = MagicMock()
    emit_pipeline_error(
        blackboard=blackboard,
        project_id="p1",
        wave_id="w1",
        phase="integrator-fetch",
        error_class="WorktreeError",
        error_message="fetch failed for PR #42",
        traceback_head="Traceback...\n  ...",
        retry_count=2,
        final=True,
    )
    assert blackboard.write_event.called
    args = blackboard.write_event.call_args
    # write_event takes a positional arg (matches the production Blackboard
    # signature used by the worker — earlier kwarg form crashed on the live
    # Blackboard which expects positional only).
    event_item = args.args[0]
    assert event_item["event_type"] == "council_pipeline_error"
    assert event_item["phase"] == "integrator-fetch"
    assert event_item["final"] is True
    assert event_item["wave_id"] == "w1"
    assert event_item["PK"] == "P#p1"
    assert event_item["retry_count"] == 2
