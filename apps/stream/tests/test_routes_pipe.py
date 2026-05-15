"""Tests for the EventBridge Pipe ingestion endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from stream.app import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_pipe_rejects_missing_secret(client: TestClient) -> None:
    resp = client.post("/_pipe", json=[])
    assert resp.status_code == 401


def test_pipe_rejects_wrong_secret(client: TestClient) -> None:
    resp = client.post(
        "/_pipe",
        json=[],
        headers={"X-Pipe-Secret": "wrong"},
    )
    assert resp.status_code == 401


def test_pipe_accepts_empty_batch(client: TestClient) -> None:
    resp = client.post(
        "/_pipe",
        json=[],
        headers={"X-Pipe-Secret": "test-pipe-secret"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"published": 0}


def test_pipe_publishes_to_registry(client: TestClient) -> None:
    record = {
        "PK": "T#tenant-abc#P#p1#W#w1",
        "SK": "2026-05-15T19:14:12Z#crow_assigned",
        "event_type": "crow_assigned",
        "message": "Implementer assigned",
        "color": "blue",
        "timestamp": "2026-05-15T19:14:12Z",
        "wave_id": "w1",
        "mvi_id": "m1",
    }
    resp = client.post(
        "/_pipe",
        json=[record],
        headers={"X-Pipe-Secret": "test-pipe-secret"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"published": 1}


def test_pipe_skips_record_with_missing_pk(client: TestClient) -> None:
    bad = {"SK": "no_pk", "event_type": "x"}
    resp = client.post(
        "/_pipe",
        json=[bad],
        headers={"X-Pipe-Secret": "test-pipe-secret"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"published": 0}
