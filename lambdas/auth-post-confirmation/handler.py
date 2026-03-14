"""
Post-confirmation Lambda trigger for Cognito.

Fires on PostConfirmation_ConfirmSignUp. Creates a tenant record in DynamoDB
and writes the tenant_id back to the Cognito user as a custom attribute.

Environment variables:
  TABLE_NAME  — DynamoDB table name (cawnex-{stage})
  STAGE       — dev | staging | prod
"""

import os
import time
import logging
import uuid

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
cognito = boto3.client("cognito-idp")


def generate_tenant_id() -> str:
    """Generate a compact, sortable tenant ID."""
    ts_hex = format(int(time.time() * 1000), "x")
    rand_hex = uuid.uuid4().hex[:8]
    return f"t_{ts_hex}_{rand_hex}"


def handler(event, context):
    logger.info("PostConfirmation trigger: %s", event.get("triggerSource"))

    trigger = event.get("triggerSource", "")
    if trigger != "PostConfirmation_ConfirmSignUp":
        logger.info("Skipping trigger: %s", trigger)
        return event

    user_pool_id = event["userPoolId"]
    username = event["userName"]
    user_attrs = {
        attr["Name"]: attr["Value"]
        for attr in event["request"].get("userAttributes", [])
    }
    # Cognito passes userAttributes as a flat dict in the event
    if not user_attrs:
        user_attrs = event["request"].get("userAttributes", {})

    email = user_attrs.get("email", "")
    name = user_attrs.get("name", username)
    sub = user_attrs.get("sub", username)

    # Check if user already has a tenant_id (e.g., federated user linked to existing)
    existing_tenant = user_attrs.get("custom:tenant_id")
    if existing_tenant:
        logger.info("User %s already has tenant_id: %s", username, existing_tenant)
        return event

    tenant_id = generate_tenant_id()
    table_name = os.environ["TABLE_NAME"]
    table = dynamodb.Table(table_name)

    # Write tenant profile to DynamoDB
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    table.put_item(
        Item={
            "PK": f"T#{tenant_id}",
            "SK": "PROFILE",
            "GSI1PK": f"TENANT#{tenant_id}",
            "GSI1SK": "PROFILE",
            "tenantId": tenant_id,
            "ownerSub": sub,
            "ownerEmail": email,
            "ownerName": name,
            "plan": "free",
            "creditsBalance": 0,
            "createdAt": now_iso,
            "updatedAt": now_iso,
            "entityType": "TenantProfile",
        }
    )
    logger.info("Created tenant profile: T#%s", tenant_id)

    # Write tenant_id back to Cognito user
    cognito.admin_update_user_attributes(
        UserPoolId=user_pool_id,
        Username=username,
        UserAttributes=[
            {"Name": "custom:tenant_id", "Value": tenant_id},
        ],
    )
    logger.info("Set custom:tenant_id=%s on user %s", tenant_id, username)

    return event
