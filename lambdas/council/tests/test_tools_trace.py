"""Tests for the TraceBuilder."""

from council.tools.trace import TraceBuilder


def test_trace_builder_records_tool_calls() -> None:
    builder = TraceBuilder()
    builder.record(
        tool_name="read_file",
        args={"path": "foo.py"},
        result_summary="def foo()...",
        duration_ms=10,
    )
    builder.record(
        tool_name="grep",
        args={"pattern": "tenant_id"},
        result_summary="3 matches",
        duration_ms=20,
    )
    trace = builder.build()
    assert len(trace) == 2
    assert trace[0].tool_name == "read_file"
    assert trace[1].duration_ms == 20


def test_trace_builder_records_errors() -> None:
    builder = TraceBuilder()
    builder.record(
        tool_name="read_file",
        args={"path": "missing.py"},
        result_summary="",
        duration_ms=5,
        error="file_not_found",
    )
    trace = builder.build()
    assert trace[0].error == "file_not_found"
