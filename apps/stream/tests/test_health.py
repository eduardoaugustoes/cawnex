"""Tests for the health endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from stream.app import create_app


def test_health_returns_200() -> None:
    app = create_app()
    client = TestClient(app)
    resp = client.get("/_health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
