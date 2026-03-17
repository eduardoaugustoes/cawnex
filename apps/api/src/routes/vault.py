"""Vault routes — secret management (metadata only, never raw values)."""

import os
from datetime import datetime, timezone
from typing import Annotated, Any, Dict

import boto3
from boto3.dynamodb.conditions import Key
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.auth.dependencies import get_tenant
from src.auth.tenant import TenantContext
from src.db.client import TenantDB

router = APIRouter(
    prefix="/projects/{project_id}/vault/secrets",
    tags=["vault"],
)


class CreateSecretRequest(BaseModel):
    """Request body for storing a secret."""

    name: str
    value: str
    description: str = ""


class RotateSecretRequest(BaseModel):
    """Request body for rotating a secret."""

    value: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _vault_pk(tenant_id: str) -> str:
    return f"T#{tenant_id}#VAULT"


def _secret_sk(project_id: str, name: str) -> str:
    return f"P#{project_id}#S#{name}"


@router.post("", status_code=201)
async def create_secret(
    project_id: str,
    body: CreateSecretRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> Dict[str, Any]:
    """Store an encrypted secret in the vault."""
    db = TenantDB(tenant)
    now = _now_iso()

    kms_key_id = os.environ.get("VAULT_KMS_KEY_ID", "")
    encrypted_value = body.value
    if kms_key_id:
        try:
            kms = boto3.client("kms")
            result = kms.encrypt(
                KeyId=kms_key_id,
                Plaintext=body.value.encode("utf-8"),
            )
            encrypted_value = result["CiphertextBlob"]
        except Exception as e:
            raise HTTPException(status_code=503, detail=str(e))

    pk = _vault_pk(tenant.tenant_id)
    sk = _secret_sk(project_id, body.name)

    db._table.put_item(
        Item={
            "PK": pk,
            "SK": sk,
            "name": body.name,
            "project": project_id,
            "encrypted_value": encrypted_value,
            "description": body.description,
            "created_at": now,
            "entityType": "Secret",
        }
    )

    return {
        "name": body.name,
        "description": body.description,
        "created_at": now,
    }


@router.get("")
async def list_secrets(
    project_id: str,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> Dict[str, Any]:
    """List secret names and metadata. NEVER returns values."""
    db = TenantDB(tenant)
    pk = _vault_pk(tenant.tenant_id)
    sk_prefix = f"P#{project_id}#S#"

    response = db._table.query(
        KeyConditionExpression=Key("PK").eq(pk) & Key("SK").begins_with(sk_prefix),
    )
    items = response.get("Items", [])

    secrets = [
        {
            "name": item.get("name", ""),
            "description": item.get("description", ""),
            "created_at": item.get("created_at", ""),
            "rotated_at": item.get("rotated_at", ""),
        }
        for item in items
    ]

    return {"secrets": secrets, "count": len(secrets)}


@router.delete("/{name}")
async def delete_secret(
    project_id: str,
    name: str,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> Dict[str, Any]:
    """Remove a secret from the vault."""
    db = TenantDB(tenant)
    pk = _vault_pk(tenant.tenant_id)
    sk = _secret_sk(project_id, name)

    result = db._table.get_item(Key={"PK": pk, "SK": sk})
    if not result.get("Item"):
        raise HTTPException(status_code=404, detail="Secret not found")

    db._table.delete_item(Key={"PK": pk, "SK": sk})

    return {"deleted": name}


@router.put("/{name}/rotate")
async def rotate_secret(
    project_id: str,
    name: str,
    body: RotateSecretRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> Dict[str, Any]:
    """Rotate a secret — encrypt new value, update timestamp."""
    db = TenantDB(tenant)
    pk = _vault_pk(tenant.tenant_id)
    sk = _secret_sk(project_id, name)

    result = db._table.get_item(Key={"PK": pk, "SK": sk})
    if not result.get("Item"):
        raise HTTPException(status_code=404, detail="Secret not found")

    now = _now_iso()
    kms_key_id = os.environ.get("VAULT_KMS_KEY_ID", "")
    encrypted_value = body.value
    if kms_key_id:
        try:
            kms = boto3.client("kms")
            result_kms = kms.encrypt(
                KeyId=kms_key_id,
                Plaintext=body.value.encode("utf-8"),
            )
            encrypted_value = result_kms["CiphertextBlob"]
        except Exception as e:
            raise HTTPException(status_code=503, detail=str(e))

    db._table.update_item(
        Key={"PK": pk, "SK": sk},
        UpdateExpression="SET #ev = :ev, #ra = :ra",
        ExpressionAttributeNames={"#ev": "encrypted_value", "#ra": "rotated_at"},
        ExpressionAttributeValues={":ev": encrypted_value, ":ra": now},
    )

    return {
        "name": name,
        "rotated_at": now,
    }
