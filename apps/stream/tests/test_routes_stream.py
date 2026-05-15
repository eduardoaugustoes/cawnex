"""Tests for the public SSE stream endpoint.

We don't fully exercise the long-running event_generator coroutine here —
TestClient + StreamingResponse + asyncio.wait_for blocks the test loop in
ways that are awkward to mock. The end-to-end behavior is verified by the
live smoke test (Task 12). Here we only verify the auth gate.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from stream.app import create_app


def test_stream_rejects_missing_authorization() -> None:
    app = create_app()
    client = TestClient(app)
    resp = client.get("/projects/p1/waves/w1/stream")
    assert resp.status_code == 401


def test_stream_rejects_invalid_bearer() -> None:
    app = create_app()
    client = TestClient(app)
    resp = client.get(
        "/projects/p1/waves/w1/stream",
        headers={"Authorization": "Bearer not-a-jwt"},
    )
    assert resp.status_code == 401
