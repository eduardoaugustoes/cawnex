"""Tests for GET /projects/{project_id}/council/sessions/{session_id}."""

import json
from pathlib import Path
from typing import Any, Dict
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from src.auth.dependencies import get_tenant
from src.auth.tenant import TenantContext
from src.main import app

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> Dict[str, Any]:
    return json.loads((FIXTURES / name).read_text())


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


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_get_completed_session_returns_full_shape(mock_boto3: Mock) -> None:
    """A completed session round-trips with every top-level field present."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table
    fixture = _load_fixture("council_session_completed.json")
    mock_table.get_item.return_value = {"Item": fixture}

    client = _make_client(_make_tenant())
    resp = client.get("/projects/p1/council/sessions/wr_w1_a8f3b2c1")

    assert resp.status_code == 200
    body = resp.json()
    assert body["session_id"] == "wr_w1_a8f3b2c1"
    assert body["wave_id"] == "w1"
    assert body["project_id"] == "p1"
    assert body["status"] == "completed"
    assert body["integration_sk"] == "INTEGRATION#w1"
    assert body["pipeline_health"] == "ok"
    assert body["decision"]["action"] == "approve"
    assert body["decision"]["confidence"] == 0.86
    assert len(body["rounds"]) == 1
    assert len(body["rounds"][0]["votes"]) == 6
    sec_vote = next(v for v in body["rounds"][0]["votes"] if v["advisor"] == "security")
    assert sec_vote["vote"] == "approve"
    assert sec_vote["cited_evidence"][0]["file_path"] == "apps/api/foo.py"
    assert sec_vote["investigation_trace"][0]["tool_name"] == "read_file"


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_get_pending_session_returns_null_decision(mock_boto3: Mock) -> None:
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table
    mock_table.get_item.return_value = {
        "Item": _load_fixture("council_session_pending.json")
    }

    client = _make_client(_make_tenant())
    resp = client.get("/projects/p1/council/sessions/wr_w2_pending01")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "pending"
    assert body["decision"] is None
    assert body["rounds"] == []


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_get_errored_session_includes_degraded_health(mock_boto3: Mock) -> None:
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table
    mock_table.get_item.return_value = {
        "Item": _load_fixture("council_session_errored.json")
    }

    client = _make_client(_make_tenant())
    resp = client.get("/projects/p1/council/sessions/wr_w3_errored01")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "errored"
    assert body["pipeline_health"] == "degraded"
    assert body["decision"] is None


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_get_missing_session_returns_404(mock_boto3: Mock) -> None:
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table
    mock_table.get_item.return_value = {}

    client = _make_client(_make_tenant())
    resp = client.get("/projects/p1/council/sessions/wr_does_not_exist")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()
