"""Tests for human task routes."""

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


def _make_human_task(
    human_task_id: str = "ht_esim",
    status: str = "notified",
    **overrides: Any,
) -> Dict[str, Any]:
    base = {
        "PK": "T#tenant-abc#P#proj-001",
        "SK": f"S#w001#mdev#{human_task_id}",
        "id": human_task_id,
        "level": "crow",
        "task_type": "human",
        "human_task_subtype": "physical_action",
        "status": status,
        "ask": "Purchase an e-SIM number",
        "instructions": "Buy a dedicated phone number for WhatsApp Business.",
        "input_schema": {
            "phone_number": {
                "type": "string",
                "pattern": r"^\+[1-9]\d{1,14}$",
                "pattern_hint": "E.164 format",
                "required": True,
            },
            "carrier": {
                "type": "string",
                "required": False,
            },
        },
        "blocks": ["S#w001#mdev#cr_impl_01"],
        "created_at": "2026-03-16T10:00:00Z",
        "entityType": "Snapshot",
    }
    base.update(overrides)
    return base


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Any:
    yield
    app.dependency_overrides.clear()


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_list_human_tasks(mock_boto3: Mock) -> None:
    """GET /projects/{pid}/human-tasks returns grouped tasks."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    mock_table.query.return_value = {
        "Items": [
            _make_human_task("ht_esim", "notified"),
            _make_human_task("ht_token", "completed"),
            {
                "PK": "T#tenant-abc#P#proj-001",
                "SK": "S#w001#mdev#cr_impl_01",
                "level": "crow",
                "status": "pending",
            },
        ]
    }

    client = _make_client(_make_tenant())
    response = client.get("/projects/proj-001/human-tasks")

    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 2
    assert data["pending_count"] == 1
    assert "notified" in data["tasks"]
    assert "completed" in data["tasks"]


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_get_human_task_detail(mock_boto3: Mock) -> None:
    """GET /projects/{pid}/human-tasks/{htid} returns full task detail."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    mock_table.query.return_value = {"Items": [_make_human_task()]}

    client = _make_client(_make_tenant())
    response = client.get("/projects/proj-001/human-tasks/ht_esim")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "ht_esim"
    assert data["ask"] == "Purchase an e-SIM number"
    assert "phone_number" in data["input_schema"]


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_get_human_task_not_found(mock_boto3: Mock) -> None:
    """GET returns 404 when human task not found."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table
    mock_table.query.return_value = {"Items": []}

    client = _make_client(_make_tenant())
    response = client.get("/projects/proj-001/human-tasks/nonexistent")

    assert response.status_code == 404


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_respond_with_valid_input(mock_boto3: Mock) -> None:
    """POST respond accepts valid input and completes task (no verification)."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    mock_table.query.return_value = {"Items": [_make_human_task()]}
    mock_table.update_item.return_value = {"Attributes": {}}

    client = _make_client(_make_tenant())
    response = client.post(
        "/projects/proj-001/human-tasks/ht_esim/respond",
        json={"response": {"phone_number": "+5511999999999", "carrier": "Claro"}},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_respond_with_invalid_input(mock_boto3: Mock) -> None:
    """POST respond returns 400 with field-level errors for invalid input."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    mock_table.query.return_value = {"Items": [_make_human_task()]}

    client = _make_client(_make_tenant())
    response = client.post(
        "/projects/proj-001/human-tasks/ht_esim/respond",
        json={"response": {"phone_number": "not-a-phone"}},
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "errors" in detail


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_respond_with_steer_only(mock_boto3: Mock) -> None:
    """POST respond with steer only skips input validation."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    mock_table.query.return_value = {"Items": [_make_human_task()]}
    mock_table.update_item.return_value = {"Attributes": {}}

    client = _make_client(_make_tenant())
    response = client.post(
        "/projects/proj-001/human-tasks/ht_esim/respond",
        json={"steer": "Use Twilio instead of Meta direct API"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_respond_with_input_and_steer(mock_boto3: Mock) -> None:
    """POST respond with both input and steer validates input and stores both."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    mock_table.query.return_value = {"Items": [_make_human_task()]}
    mock_table.update_item.return_value = {"Attributes": {}}

    client = _make_client(_make_tenant())
    response = client.post(
        "/projects/proj-001/human-tasks/ht_esim/respond",
        json={
            "response": {"phone_number": "+5511999999999"},
            "steer": "This is a prepaid number",
        },
    )

    assert response.status_code == 200


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_respond_neither_provided(mock_boto3: Mock) -> None:
    """POST respond with neither response nor steer returns 400."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    client = _make_client(_make_tenant())
    response = client.post(
        "/projects/proj-001/human-tasks/ht_esim/respond",
        json={},
    )

    assert response.status_code == 400


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_respond_with_verification_sets_responded(mock_boto3: Mock) -> None:
    """POST respond to task with verification sets status to 'responded', not 'completed'."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    task = _make_human_task(
        verification={
            "type": "crow_check",
            "instructions": "Verify DNS record",
            "max_retries": 3,
        }
    )
    mock_table.query.return_value = {"Items": [task]}
    mock_table.update_item.return_value = {"Attributes": {}}

    client = _make_client(_make_tenant())
    response = client.post(
        "/projects/proj-001/human-tasks/ht_esim/respond",
        json={"response": {"phone_number": "+5511999999999"}},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "responded"


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_respond_to_completed_task_returns_409(mock_boto3: Mock) -> None:
    """POST respond to already-completed task returns 409."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    mock_table.query.return_value = {"Items": [_make_human_task(status="completed")]}

    client = _make_client(_make_tenant())
    response = client.post(
        "/projects/proj-001/human-tasks/ht_esim/respond",
        json={"response": {"phone_number": "+5511999999999"}},
    )

    assert response.status_code == 409


@patch("src.routes.human_tasks.boto3")
@patch("src.db.client.boto3")
@patch.dict(
    "os.environ", {"TABLE_NAME": "test-table", "ASSETS_BUCKET_NAME": "test-bucket"}
)
def test_upload_url_success(mock_db_boto3: Mock, mock_route_boto3: Mock) -> None:
    """POST upload-url generates presigned URL for valid file field."""
    mock_table = Mock()
    mock_db_boto3.resource.return_value.Table.return_value = mock_table

    task = _make_human_task(
        input_schema={
            "logo": {
                "type": "file",
                "accept": ["image/png"],
                "required": True,
            },
        }
    )
    mock_table.query.return_value = {"Items": [task]}

    mock_s3 = Mock()
    mock_route_boto3.client.return_value = mock_s3
    mock_s3.generate_presigned_url.return_value = "https://s3.example.com/presigned"

    client = _make_client(_make_tenant())
    response = client.post(
        "/projects/proj-001/human-tasks/ht_esim/upload-url",
        json={"field": "logo", "filename": "logo.png", "content_type": "image/png"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["upload_url"] == "https://s3.example.com/presigned"
    assert "asset_key" in data
    assert data["expires_in"] == 300


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_upload_url_wrong_content_type(mock_boto3: Mock) -> None:
    """POST upload-url returns 400 for content type not in accept list."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    task = _make_human_task(
        input_schema={
            "logo": {"type": "file", "accept": ["image/png"], "required": True},
        }
    )
    mock_table.query.return_value = {"Items": [task]}

    client = _make_client(_make_tenant())
    response = client.post(
        "/projects/proj-001/human-tasks/ht_esim/upload-url",
        json={
            "field": "logo",
            "filename": "doc.pdf",
            "content_type": "application/pdf",
        },
    )

    assert response.status_code == 400


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_upload_url_non_file_field(mock_boto3: Mock) -> None:
    """POST upload-url returns 400 for non-file field."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    mock_table.query.return_value = {"Items": [_make_human_task()]}

    client = _make_client(_make_tenant())
    response = client.post(
        "/projects/proj-001/human-tasks/ht_esim/upload-url",
        json={
            "field": "phone_number",
            "filename": "file.txt",
            "content_type": "text/plain",
        },
    )

    assert response.status_code == 400


@patch("src.db.client.boto3")
@patch.dict("os.environ", {"TABLE_NAME": "test-table"})
def test_respond_routes_secrets_to_vault(mock_boto3: Mock) -> None:
    """POST respond routes secret fields to vault, stores vault_ref in response."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    task = _make_human_task(
        input_schema={
            "token": {"type": "secret", "required": True},
        }
    )
    mock_table.query.return_value = {"Items": [task]}
    mock_table.update_item.return_value = {"Attributes": {}}

    client = _make_client(_make_tenant())
    response = client.post(
        "/projects/proj-001/human-tasks/ht_esim/respond",
        json={"response": {"token": "EAAGm0secret123"}},
    )

    assert response.status_code == 200
    # Verify vault write was called
    put_calls = [c for c in mock_table.put_item.call_args_list if "VAULT" in str(c)]
    assert len(put_calls) == 1


@patch("src.db.client.boto3")
@patch.dict(
    "os.environ", {"TABLE_NAME": "test-table", "ASSETS_BUCKET_NAME": "test-bucket"}
)
def test_respond_with_file_triggers_post_processing(mock_boto3: Mock) -> None:
    """POST respond writes PROCESS# record for file fields with post_processing."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    task = _make_human_task(
        input_schema={
            "document": {
                "type": "file",
                "accept": ["application/pdf"],
                "required": True,
                "post_processing": "extract_text",
            },
        },
        post_processing="none",
    )
    mock_table.query.return_value = {"Items": [task]}
    mock_table.update_item.return_value = {"Attributes": {}}

    client = _make_client(_make_tenant())
    response = client.post(
        "/projects/proj-001/human-tasks/ht_esim/respond",
        json={
            "response": {
                "document": {
                    "asset_key": "T/tenant-abc/P/proj-001/assets/ht_esim/formula.pdf",
                    "content_type": "application/pdf",
                },
            },
        },
    )

    assert response.status_code == 200

    # Verify PROCESS# record was written
    process_calls = [
        c for c in mock_table.put_item.call_args_list if "PROCESS#" in str(c)
    ]
    assert len(process_calls) == 1
    process_item = process_calls[0][1]["Item"]
    assert process_item["SK"].startswith("PROCESS#ht_esim#document")
    assert process_item["processing"] == "extract_text"
    assert process_item["status"] == "pending"
    assert "s3://test-bucket/" in process_item["source"]


@patch("src.db.client.boto3")
@patch.dict(
    "os.environ", {"TABLE_NAME": "test-table", "ASSETS_BUCKET_NAME": "test-bucket"}
)
def test_respond_with_file_no_post_processing_skips_process_record(
    mock_boto3: Mock,
) -> None:
    """POST respond does NOT write PROCESS# record when post_processing is 'none'."""
    mock_table = Mock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    task = _make_human_task(
        input_schema={
            "logo": {
                "type": "file",
                "accept": ["image/png"],
                "required": True,
            },
        },
    )
    mock_table.query.return_value = {"Items": [task]}
    mock_table.update_item.return_value = {"Attributes": {}}

    client = _make_client(_make_tenant())
    response = client.post(
        "/projects/proj-001/human-tasks/ht_esim/respond",
        json={
            "response": {
                "logo": {
                    "asset_key": "T/tenant-abc/P/proj-001/assets/ht_esim/logo.png",
                    "content_type": "image/png",
                },
            },
        },
    )

    assert response.status_code == 200

    # No PROCESS# record should be written
    process_calls = [
        c for c in mock_table.put_item.call_args_list if "PROCESS#" in str(c)
    ]
    assert len(process_calls) == 0
