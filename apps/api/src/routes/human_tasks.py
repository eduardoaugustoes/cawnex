"""Human task routes — list, view, respond, upload."""

import os
from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List, Optional

import boto3
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.auth.dependencies import get_tenant
from src.auth.tenant import TenantContext
from src.db.client import TenantDB

router = APIRouter(
    prefix="/projects/{project_id}/human-tasks",
    tags=["human-tasks"],
)


class RespondRequest(BaseModel):
    """Request body for responding to a human task."""

    response: Optional[Dict[str, Any]] = None
    steer: Optional[str] = None


class UploadURLRequest(BaseModel):
    """Request body for requesting a presigned upload URL."""

    field: str
    filename: str
    content_type: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_response_fields(  # noqa: C901
    input_schema: Dict[str, Any],
    response: Dict[str, Any],
) -> List[Dict[str, str]]:
    """Validate response fields against input schema. Returns list of errors."""
    import re

    errors: List[Dict[str, str]] = []

    for field_name, field_def in input_schema.items():
        if not isinstance(field_def, dict):
            continue
        value = response.get(field_name)
        required = field_def.get("required", False)
        field_type = field_def.get("type", "string")

        if value is None or (isinstance(value, str) and value.strip() == ""):
            if required:
                errors.append(
                    {
                        "field": field_name,
                        "message": f"{field_def.get('label', field_name)} is required",
                        "code": "required",
                    }
                )
            continue

        if field_type in ("string", "text", "secret"):
            if not isinstance(value, str):
                errors.append(
                    {
                        "field": field_name,
                        "message": "Must be a string",
                        "code": "type_mismatch",
                    }
                )
                continue
            min_len = field_def.get("minLength")
            max_len = field_def.get("maxLength")
            if min_len and len(value) < min_len:
                errors.append(
                    {
                        "field": field_name,
                        "message": f"Must be at least {min_len} characters",
                        "code": "too_short",
                    }
                )
            if max_len and len(value) > max_len:
                errors.append(
                    {
                        "field": field_name,
                        "message": f"Must be at most {max_len} characters",
                        "code": "too_long",
                    }
                )
            pattern = field_def.get("pattern")
            if pattern and not re.match(pattern, value):
                hint = field_def.get("pattern_hint", f"Must match: {pattern}")
                errors.append(
                    {"field": field_name, "message": hint, "code": "pattern_mismatch"}
                )

        elif field_type == "file":
            if not isinstance(value, dict):
                errors.append(
                    {
                        "field": field_name,
                        "message": "Must be a file reference",
                        "code": "type_mismatch",
                    }
                )
                continue
            if not value.get("asset_key"):
                errors.append(
                    {
                        "field": field_name,
                        "message": "Missing asset_key",
                        "code": "missing_key",
                    }
                )
            accept = field_def.get("accept", [])
            ct = value.get("content_type", "")
            if accept and ct and ct not in accept:
                errors.append(
                    {
                        "field": field_name,
                        "message": f"File type {ct} not accepted",
                        "code": "invalid_content_type",
                    }
                )

        elif field_type == "url":
            if not isinstance(value, str) or not re.match(
                r"^https?://[^\s/$.?#].[^\s]*$", value, re.IGNORECASE
            ):
                errors.append(
                    {
                        "field": field_name,
                        "message": "Must be a valid URL",
                        "code": "invalid_url",
                    }
                )

        elif field_type == "email":
            if not isinstance(value, str) or not re.match(
                r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", value
            ):
                errors.append(
                    {
                        "field": field_name,
                        "message": "Must be a valid email",
                        "code": "invalid_email",
                    }
                )

        elif field_type == "color":
            if not isinstance(value, str) or not re.match(r"^#[0-9A-Fa-f]{6}$", value):
                errors.append(
                    {
                        "field": field_name,
                        "message": "Must be hex color (#RRGGBB)",
                        "code": "invalid_color",
                    }
                )

        elif field_type == "enum":
            options = field_def.get("options", [])
            valid = {o["value"] if isinstance(o, dict) else o for o in options}
            if value not in valid:
                errors.append(
                    {
                        "field": field_name,
                        "message": f"Must be one of: {', '.join(sorted(valid))}",
                        "code": "invalid_option",
                    }
                )

        elif field_type == "boolean":
            if not isinstance(value, bool):
                errors.append(
                    {
                        "field": field_name,
                        "message": "Must be a boolean",
                        "code": "type_mismatch",
                    }
                )

        elif field_type == "number":
            if not isinstance(value, (int, float)):
                errors.append(
                    {
                        "field": field_name,
                        "message": "Must be a number",
                        "code": "type_mismatch",
                    }
                )
                continue
            if field_def.get("min") is not None and value < field_def["min"]:
                errors.append(
                    {
                        "field": field_name,
                        "message": f"Must be >= {field_def['min']}",
                        "code": "below_min",
                    }
                )
            if field_def.get("max") is not None and value > field_def["max"]:
                errors.append(
                    {
                        "field": field_name,
                        "message": f"Must be <= {field_def['max']}",
                        "code": "above_max",
                    }
                )

    return errors


@router.get("")
async def list_human_tasks(
    project_id: str,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> Dict[str, Any]:
    """List all human tasks for a project, grouped by status."""
    db = TenantDB(tenant)

    # Query all snapshot items and filter for human tasks
    items = db.query_project(project_id, "S#")
    human_tasks = [i for i in items if i.get("task_type") == "human"]

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for ht in human_tasks:
        status = ht.get("status", "pending")
        if status not in grouped:
            grouped[status] = []
        grouped[status].append(
            {
                "id": ht.get("id", ""),
                "ask": ht.get("ask", ""),
                "human_task_subtype": ht.get("human_task_subtype", ""),
                "status": status,
                "deadline_hint": ht.get("deadline_hint", ""),
                "created_at": ht.get("created_at", ""),
            }
        )

    pending_count = len(grouped.get("pending", [])) + len(grouped.get("notified", []))

    return {
        "tasks": grouped,
        "pending_count": pending_count,
        "total_count": len(human_tasks),
    }


@router.get("/{human_task_id}")
async def get_human_task(
    project_id: str,
    human_task_id: str,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> Dict[str, Any]:
    """Get a single human task with full context."""
    db = TenantDB(tenant)

    # Search for the human task across all waves/MVIs
    items = db.query_project(project_id, "S#")
    task = None
    for item in items:
        if item.get("task_type") == "human" and item.get("id") == human_task_id:
            task = item
            break

    if not task:
        raise HTTPException(status_code=404, detail="Human task not found")

    return {
        "id": task.get("id", ""),
        "ask": task.get("ask", ""),
        "instructions": task.get("instructions", ""),
        "human_task_subtype": task.get("human_task_subtype", ""),
        "status": task.get("status", ""),
        "input_schema": task.get("input_schema", {}),
        "verification": task.get("verification"),
        "blocks": task.get("blocks", []),
        "response": task.get("response"),
        "steer": task.get("steer"),
        "deadline_hint": task.get("deadline_hint", ""),
        "estimated_human_hours": task.get("estimated_human_hours", 0),
        "created_at": task.get("created_at", ""),
        "completed_at": task.get("completed_at", ""),
    }


@router.post("/{human_task_id}/respond")
async def respond_to_human_task(  # noqa: C901
    project_id: str,
    human_task_id: str,
    body: RespondRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> Dict[str, Any]:
    """Respond to a human task with input data and/or steer guidance."""
    if body.response is None and (body.steer is None or not body.steer.strip()):
        raise HTTPException(
            status_code=400,
            detail="At least one of response or steer must be provided",
        )

    db = TenantDB(tenant)

    # Find the human task
    items = db.query_project(project_id, "S#")
    task = None
    task_sk = None
    for item in items:
        if item.get("task_type") == "human" and item.get("id") == human_task_id:
            task = item
            task_sk = item.get("SK")
            break

    if not task:
        raise HTTPException(status_code=404, detail="Human task not found")

    status = task.get("status", "")
    if status in ("completed", "expired"):
        raise HTTPException(status_code=409, detail=f"Task already {status}")

    # Validate response against input schema if response is provided
    if body.response is not None:
        input_schema = task.get("input_schema", {})
        if input_schema:
            errors = _validate_response_fields(input_schema, body.response)
            if errors:
                raise HTTPException(status_code=400, detail={"errors": errors})

    # Determine next status
    has_verification = task.get("verification") is not None
    if has_verification:
        next_status = "responded"
    else:
        next_status = "completed"

    # Build updates
    now = _now_iso()
    updates: Dict[str, Any] = {"status": next_status}
    if body.response is not None:
        # Route secret fields to vault metadata (actual encryption at infra level)
        input_schema = task.get("input_schema", {})
        sanitized_response = dict(body.response)
        for field_name, field_def in input_schema.items():
            if isinstance(field_def, dict) and field_def.get("type") == "secret":
                if field_name in sanitized_response:
                    # Store vault reference instead of raw value
                    sanitized_response[field_name] = {
                        "vault_ref": f"ht_{human_task_id}_{field_name}"
                    }
                    # Write secret metadata to vault partition
                    vault_pk = f"T#{tenant.tenant_id}#VAULT"
                    vault_sk = f"P#{project_id}#S#ht_{human_task_id}_{field_name}"
                    db._table.put_item(
                        Item={
                            "PK": vault_pk,
                            "SK": vault_sk,
                            "name": f"ht_{human_task_id}_{field_name}",
                            "project": project_id,
                            "encrypted_value": body.response[field_name],
                            "created_at": now,
                            "entityType": "Secret",
                        }
                    )
        updates["response"] = sanitized_response

        # Trigger post-processing for file fields
        bucket = os.environ.get("ASSETS_BUCKET_NAME", "cawnex-assets-dev")
        task_level_pp = task.get("post_processing", "none")
        for field_name, field_def in input_schema.items():
            if not isinstance(field_def, dict) or field_def.get("type") != "file":
                continue
            if field_name not in body.response:
                continue
            file_ref = body.response[field_name]
            if not isinstance(file_ref, dict) or not file_ref.get("asset_key"):
                continue
            # Determine post-processing: field-level overrides task-level
            pp = field_def.get("post_processing", task_level_pp)
            if pp == "none":
                continue
            asset_key = file_ref["asset_key"]
            db.put_project_item(
                project_id=project_id,
                sk=f"PROCESS#{human_task_id}#{field_name}",
                entityType="Process",
                human_task_id=human_task_id,
                field=field_name,
                source=f"s3://{bucket}/{asset_key}",
                processing=pp,
                status="pending",
                created_at=now,
            )

    if body.steer is not None:
        updates["steer"] = body.steer
    if next_status == "completed":
        updates["completed_at"] = now

    assert task_sk is not None
    db.update_project_item(project_id, task_sk, updates)

    return {
        "status": next_status,
        "human_task_id": human_task_id,
    }


@router.post("/{human_task_id}/upload-url")
async def request_upload_url(
    project_id: str,
    human_task_id: str,
    body: UploadURLRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> Dict[str, Any]:
    """Generate a presigned S3 URL for file upload."""
    db = TenantDB(tenant)

    # Find the human task
    items = db.query_project(project_id, "S#")
    task = None
    for item in items:
        if item.get("task_type") == "human" and item.get("id") == human_task_id:
            task = item
            break

    if not task:
        raise HTTPException(status_code=404, detail="Human task not found")

    # Validate field exists with type "file"
    input_schema = task.get("input_schema", {})
    field_def = input_schema.get(body.field)
    if not field_def or not isinstance(field_def, dict):
        raise HTTPException(
            status_code=400, detail=f"Field '{body.field}' not found in schema"
        )
    if field_def.get("type") != "file":
        raise HTTPException(
            status_code=400, detail=f"Field '{body.field}' is not a file field"
        )

    # Validate content_type against accept list
    accept = field_def.get("accept", [])
    if accept and body.content_type not in accept:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Content type '{body.content_type}' not accepted."
                f" Allowed: {', '.join(accept)}"
            ),
        )

    bucket = os.environ.get("ASSETS_BUCKET_NAME", "cawnex-assets-dev")
    asset_key = (
        f"T/{tenant.tenant_id}/P/{project_id}/assets/{human_task_id}/{body.filename}"
    )

    try:
        s3 = boto3.client("s3")
        upload_url = s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": bucket,
                "Key": asset_key,
                "ContentType": body.content_type,
            },
            ExpiresIn=300,
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

    return {
        "upload_url": upload_url,
        "asset_key": asset_key,
        "expires_in": 300,
    }
