"""Shared pytest fixtures for the stream service."""

from __future__ import annotations

from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def stub_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Provide deterministic env for unit tests — overridden per-test as needed."""
    monkeypatch.setenv("TABLE_NAME", "cawnex-test")
    monkeypatch.setenv("EVENTS_TABLE_NAME", "cawnex-events-test")
    monkeypatch.setenv("USER_POOL_ID", "us-east-1_TESTPOOL")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("PIPE_SECRET", "test-pipe-secret")
    monkeypatch.setenv("ALLOWED_AUDIENCES", "test-client-id")
    yield
