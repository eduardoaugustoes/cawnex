"""Tests for waves routes — lifecycle management."""

from typing import Any, Dict
from unittest.mock import Mock, patch

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


# --- Create Wave ---


@patch("src.routes.waves.boto3")
@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table", "EVENTS_TABLE_NAME": ""})
def test_create_wave_from_backlog_mvis(
    mock_db_boto3: Mock, mock_waves_boto3: Mock
) -> None:
    """POST /waves creates wave with multiple MVIs from backlog."""
    mock_table = Mock()
    mock_db_boto3.resource.return_value.Table.return_value = mock_table

    # get_item returns project
    mock_table.get_item.return_value = {
        "Item": {
            "PK": "T#tenant-abc",
            "SK": "P#proj-001",
            "repo": "github.com/org/repo",
        }
    }

    # get_project_item returns backlog MVIs
    def query_side_effect(**kwargs: Any) -> Dict[str, Any]:
        return {"Items": []}

    mock_table.query.return_value = {"Items": []}

    # Simulate get_project_item for backlog
    call_count = {"n": 0}
    original_get = mock_table.get_item

    def get_side_effect(**kwargs: Any) -> Dict[str, Any]:
        key = kwargs.get("Key", {})
        sk = key.get("SK", "")
        if "BACKLOG#goal#" in sk:
            return {
                "Item": {
                    "PK": "T#tenant-abc#P#proj-001",
                    "SK": sk,
                    "mvis": [
                        {
                            "id": "mvi-1",
                            "name": "Setup API",
                            "description": "Build REST API",
                            "acceptance_criteria": "Tests pass",
                        },
                        {
                            "id": "mvi-2",
                            "name": "Setup UI",
                            "description": "Build SwiftUI",
                            "acceptance_criteria": "Renders",
                        },
                    ],
                }
            }
        return {
            "Item": {
                "PK": "T#tenant-abc",
                "SK": "P#proj-001",
                "repo": "github.com/org/repo",
            }
        }

    mock_table.get_item.side_effect = get_side_effect
    mock_table.update_item.return_value = {"Attributes": {}}

    client = _make_client(_make_tenant())
    response = client.post(
        "/projects/proj-001/waves",
        json={
            "directive": "Build the WhatsApp channel",
            "goal_id": "g1",
            "mvi_ids": ["mvi-1", "mvi-2"],
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert "wave_id" in data
    assert data["status"] == "planning"
    assert len(data["mvis"]) == 2
    assert data["mvis"][0]["name"] == "Setup API"
    assert data["mvis"][1]["name"] == "Setup UI"


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table", "EVENTS_TABLE_NAME": ""})
def test_create_wave_mvi_not_found_returns_400(mock_boto3: Mock) -> None:
    """POST /waves returns 400 when MVI ID not in backlog."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    def get_side_effect(**kwargs: Any) -> Dict[str, Any]:
        key = kwargs.get("Key", {})
        sk = key.get("SK", "")
        if "BACKLOG#goal#" in sk:
            return {"Item": {"PK": "pk", "SK": sk, "mvis": [{"id": "existing"}]}}
        return {"Item": {"PK": "T#t", "SK": "P#p", "repo": "r"}}

    mock_table.get_item.side_effect = get_side_effect

    client = _make_client(_make_tenant())
    response = client.post(
        "/projects/proj-001/waves",
        json={"directive": "Test", "goal_id": "g1", "mvi_ids": ["nonexistent"]},
    )

    assert response.status_code == 400
    assert "nonexistent" in response.json()["detail"]


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table", "EVENTS_TABLE_NAME": ""})
def test_create_wave_legacy_single_mvi(mock_boto3: Mock) -> None:
    """POST /waves without goal_id creates single ad-hoc MVI (backward compat)."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table
    mock_table.get_item.return_value = {
        "Item": {"PK": "T#t", "SK": "P#p", "repo": "github.com/org/repo"}
    }

    client = _make_client(_make_tenant())
    response = client.post(
        "/projects/proj-001/waves",
        json={"directive": "Add login feature"},
    )

    assert response.status_code == 201
    data = response.json()
    assert len(data["mvis"]) == 1
    assert data["mvis"][0]["name"] == "Add login feature"


# --- List Waves ---


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_list_waves_returns_sorted(mock_boto3: Mock) -> None:
    """GET /waves returns waves sorted by created_at desc."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    mock_table.query.return_value = {
        "Items": [
            {
                "SK": "S#w001",
                "level": "wave",
                "status": "executing",
                "human_directive": "First",
                "created_at": "2026-03-15T10:00:00Z",
            },
            {"SK": "S#w001#mdev", "level": "murder", "status": "queued"},
            {
                "SK": "S#w002",
                "level": "wave",
                "status": "planning",
                "human_directive": "Second",
                "created_at": "2026-03-16T10:00:00Z",
            },
        ]
    }

    client = _make_client(_make_tenant())
    response = client.get("/projects/proj-001/waves")

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2
    assert data["waves"][0]["wave_id"] == "w002"  # newest first
    assert data["waves"][1]["wave_id"] == "w001"


# --- Activate Wave ---


@patch("src.routes.waves.boto3")
@patch("src.db.client.boto3")
@patch.dict(
    "os.environ",
    {
        "TABLE_NAME": "test-table",
        "EVENTS_TABLE_NAME": "test-events",
        "ECS_CLUSTER_NAME": "cawnex-dev",
        "ECS_SERVICE_NAME": "cawnex-worker-dev",
    },
)
def test_activate_wave_queues_mvis(mock_db_boto3: Mock, mock_waves_boto3: Mock) -> None:
    """POST /waves/{wid}/activate transitions to executing and queues MVIs."""
    mock_table = Mock()
    mock_db_boto3.resource.return_value.Table.return_value = mock_table

    # Wave in planning status
    def get_side_effect(**kwargs: Any) -> Dict[str, Any]:
        return {"Item": {"SK": "S#w001", "level": "wave", "status": "planning"}}

    mock_table.get_item.side_effect = get_side_effect

    # MVIs to queue
    mock_table.query.return_value = {
        "Items": [
            {"SK": "S#w001#m01", "level": "murder", "status": "draft"},
            {"SK": "S#w001#m02", "level": "murder", "status": "draft"},
        ]
    }
    mock_table.update_item.return_value = {"Attributes": {}}

    # Mock events table + ECS
    mock_events_table = Mock()
    mock_ecs = Mock()
    mock_waves_boto3.resource.return_value.Table.return_value = mock_events_table
    mock_waves_boto3.client.return_value = mock_ecs

    client = _make_client(_make_tenant())
    response = client.post("/projects/proj-001/waves/w001/activate")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "executing"
    assert data["mvis_queued"] == 2

    # Verify ECS scale-up was called
    mock_ecs.update_service.assert_called_once()


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_activate_wave_wrong_status_returns_409(mock_boto3: Mock) -> None:
    """POST /waves/{wid}/activate returns 409 for non-activatable status."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table
    mock_table.get_item.return_value = {
        "Item": {"SK": "S#w001", "level": "wave", "status": "executing"}
    }

    client = _make_client(_make_tenant())
    response = client.post("/projects/proj-001/waves/w001/activate")

    assert response.status_code == 409


# --- Pause Wave ---


@patch("src.routes.waves.boto3")
@patch("src.db.client.boto3")
@patch.dict(
    "os.environ", {"TABLE_NAME": "test-table", "EVENTS_TABLE_NAME": "test-events"}
)
def test_pause_wave(mock_db_boto3: Mock, mock_waves_boto3: Mock) -> None:
    """POST /waves/{wid}/pause transitions executing to paused."""
    mock_table = Mock()
    mock_db_boto3.resource.return_value.Table.return_value = mock_table
    mock_table.get_item.return_value = {
        "Item": {"SK": "S#w001", "level": "wave", "status": "executing"}
    }
    mock_table.update_item.return_value = {"Attributes": {}}

    mock_events_table = Mock()
    mock_waves_boto3.resource.return_value.Table.return_value = mock_events_table

    client = _make_client(_make_tenant())
    response = client.post("/projects/proj-001/waves/w001/pause")

    assert response.status_code == 200
    assert response.json()["status"] == "paused"


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_pause_wave_not_executing_returns_409(mock_boto3: Mock) -> None:
    """POST /waves/{wid}/pause returns 409 if not executing."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table
    mock_table.get_item.return_value = {
        "Item": {"SK": "S#w001", "level": "wave", "status": "planning"}
    }

    client = _make_client(_make_tenant())
    response = client.post("/projects/proj-001/waves/w001/pause")

    assert response.status_code == 409


# --- Cancel Wave ---


@patch("src.routes.waves.boto3")
@patch("src.db.client.boto3")
@patch.dict(
    "os.environ", {"TABLE_NAME": "test-table", "EVENTS_TABLE_NAME": "test-events"}
)
def test_cancel_wave_cancels_mvis(mock_db_boto3: Mock, mock_waves_boto3: Mock) -> None:
    """POST /waves/{wid}/cancel cancels wave and all non-terminal MVIs."""
    mock_table = Mock()
    mock_db_boto3.resource.return_value.Table.return_value = mock_table
    mock_table.get_item.return_value = {
        "Item": {"SK": "S#w001", "level": "wave", "status": "executing"}
    }
    mock_table.query.return_value = {
        "Items": [
            {"SK": "S#w001#m01", "level": "murder", "status": "executing"},
            {"SK": "S#w001#m02", "level": "murder", "status": "shipped"},
        ]
    }
    mock_table.update_item.return_value = {"Attributes": {}}

    mock_events_table = Mock()
    mock_waves_boto3.resource.return_value.Table.return_value = mock_events_table

    client = _make_client(_make_tenant())
    response = client.post("/projects/proj-001/waves/w001/cancel")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "cancelled"
    assert data["mvis_cancelled"] == 1  # only executing one, shipped is terminal


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_cancel_wave_already_cancelled_returns_409(mock_boto3: Mock) -> None:
    """POST /waves/{wid}/cancel returns 409 for terminal wave."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table
    mock_table.get_item.return_value = {
        "Item": {"SK": "S#w001", "level": "wave", "status": "cancelled"}
    }

    client = _make_client(_make_tenant())
    response = client.post("/projects/proj-001/waves/w001/cancel")

    assert response.status_code == 409


# --- Get Wave Events ---


@patch("src.routes.waves.boto3")
@patch("src.db.client.boto3")
@patch.dict(
    "os.environ", {"TABLE_NAME": "test-table", "EVENTS_TABLE_NAME": "test-events"}
)
def test_get_events_paginated(mock_db_boto3: Mock, mock_waves_boto3: Mock) -> None:
    """GET /waves/{wid}/events returns events from events table."""
    mock_table = Mock()
    mock_db_boto3.resource.return_value.Table.return_value = mock_table

    mock_events_table = Mock()
    mock_waves_boto3.resource.return_value.Table.return_value = mock_events_table
    mock_events_table.query.return_value = {
        "Items": [
            {
                "PK": "T#tenant-abc#P#proj-001#W#w001",
                "SK": "2026-03-16T10:00:00Z#wave_activated",
                "event_type": "wave_activated",
                "message": "Wave activated",
                "color": "blue",
                "timestamp": "2026-03-16T10:00:00Z",
            },
        ],
    }

    client = _make_client(_make_tenant())
    response = client.get("/projects/proj-001/waves/w001/events")

    assert response.status_code == 200
    data = response.json()
    assert len(data["events"]) == 1
    assert data["events"][0]["event_type"] == "wave_activated"


# --- Get Wave Detail ---


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_get_wave_includes_human_tasks(mock_boto3: Mock) -> None:
    """GET /waves/{wid} separates human tasks from crow tasks."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table
    mock_table.query.return_value = {
        "Items": [
            {"SK": "S#w001", "level": "wave", "status": "executing"},
            {"SK": "S#w001#mdev", "level": "murder", "status": "queued"},
            {
                "SK": "S#w001#mdev#cr_plan_01",
                "level": "crow",
                "status": "completed",
                "crow_type": "planner",
            },
            {
                "SK": "S#w001#mdev#ht_esim",
                "level": "crow",
                "task_type": "human",
                "status": "notified",
            },
        ]
    }

    client = _make_client(_make_tenant())
    response = client.get("/projects/proj-001/waves/w001")

    assert response.status_code == 200
    data = response.json()
    assert len(data["crows"]) == 1
    assert len(data["human_tasks"]) == 1
    assert data["human_tasks"][0]["task_type"] == "human"
