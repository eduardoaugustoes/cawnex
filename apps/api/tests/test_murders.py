"""Tests for the murders catalog route."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.auth.dependencies import get_tenant
from src.auth.tenant import TenantContext
from src.main import app


def _make_tenant() -> TenantContext:
    return TenantContext(
        tenant_id="tenant-abc", user_sub="user-001", email="test@example.com"
    )


def _make_client(tenant: TenantContext) -> TestClient:
    app.dependency_overrides[get_tenant] = lambda: tenant
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Any:
    yield
    app.dependency_overrides.clear()


def test_get_murders_returns_full_catalog() -> None:
    client = _make_client(_make_tenant())
    resp = client.get("/murders")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # All 5 murder types in catalog
    types = {m["type"] for m in body["murders"]}
    assert types == {"dev", "editorial", "social", "infra", "data"}

    # Each murder has a crow roster, status, icon, tone, etc.
    for murder in body["murders"]:
        assert murder["id"]
        assert murder["name"]
        assert murder["icon"]
        assert murder["status"] == "idle"  # placeholder per spec
        assert isinstance(murder["crows"], list) and len(murder["crows"]) > 0
        assert all("name" in c and "is_active" in c for c in murder["crows"])
        # Live state is placeholder
        assert murder["tasks_done"] == 0
        assert murder["behavior_lines"] == []

    # Marketplace section populated
    assert len(body["marketplace"]) >= 1
    for item in body["marketplace"]:
        assert item["name"]
        assert item["author"]
