"""Stage 4 Layer B integration: Council session round-trip via FastAPI + DDB Local.

Writes a fully-formed CouncilSession row directly to DDB Local, then hits the
new GET endpoint via FastAPI TestClient and asserts the iOS-shaped response.
"""

from __future__ import annotations

import json
import os
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest


def _floats_to_decimal(obj: Any) -> Any:
    """Recursively convert floats to Decimal — DynamoDB rejects float types."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _floats_to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_floats_to_decimal(v) for v in obj]
    return obj

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))
sys.path.insert(0, str(REPO_ROOT / "apps" / "api" / "src"))

FIXTURES = REPO_ROOT / "apps" / "api" / "tests" / "fixtures"


def test_round_trip_completed_session(ddb_table: Any) -> None:
    """Write a completed CouncilSession row; GET returns the iOS-shaped JSON.

    The API route reads via TenantDB.get_project_item which constructs
    PK=T#{tenant_id}#P#{project_id}. We must seed the row with the same key
    shape (overriding the fixture's PK).
    """
    from fastapi.testclient import TestClient
    from src.auth.dependencies import get_tenant
    from src.auth.tenant import TenantContext
    from src.main import app

    fixture = json.loads((FIXTURES / "council_session_completed.json").read_text())
    fixture["PK"] = "T#tenant-test#P#p1"
    fixture["SK"] = "COUNCIL#wr_w1_a8f3b2c1"

    os.environ["TABLE_NAME"] = ddb_table.name
    ddb_table.put_item(Item=_floats_to_decimal(fixture))

    # Pin TenantDB._table to the explicit-endpoint table from the fixture.
    # boto3.resource('dynamodb') inside TenantDB resolves the endpoint via env,
    # but in pytest the AWS_ENDPOINT_URL_DYNAMODB env var isn't honored reliably
    # (Session caching), so we patch the construction.
    import boto3
    from unittest.mock import patch
    explicit = boto3.resource(
        "dynamodb",
        endpoint_url=os.environ.get("DYNAMODB_ENDPOINT", "http://localhost:8000"),
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    explicit_table = explicit.Table(ddb_table.name)

    tenant = TenantContext(
        tenant_id="tenant-test", user_sub="u-001", email="t@x.test"
    )
    app.dependency_overrides[get_tenant] = lambda: tenant
    try:
        with patch("src.db.client.boto3.resource") as mock_resource:
            mock_resource.return_value.Table.return_value = explicit_table
            client = TestClient(app)
            resp = client.get("/projects/p1/council/sessions/wr_w1_a8f3b2c1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "completed"
        assert len(body["rounds"][0]["votes"]) == 6
        advisors = [v["advisor"] for v in body["rounds"][0]["votes"]]
        assert set(advisors) == {
            "security",
            "architecture",
            "clarity",
            "performance",
            "ux",
            "cost",
        }
    finally:
        app.dependency_overrides.clear()
