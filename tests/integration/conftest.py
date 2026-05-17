"""Shared fixtures for Stage 4 integration tests.

These tests use DynamoDB Local (port 8000 by default, overridable via
DYNAMODB_ENDPOINT) — moto is not installed in this environment and
DynamoDB Local round-trips give us higher fidelity anyway.
"""

from __future__ import annotations

import os
import sys
import uuid
from collections.abc import Iterator
from typing import Any

import boto3
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "lambdas", "murder", "src"))


@pytest.fixture(autouse=True)
def aws_creds() -> Iterator[None]:
    """DDB Local accepts any creds; set predictable values so boto stops complaining."""
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
    os.environ.setdefault("AWS_SESSION_TOKEN", "testing")
    os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
    os.environ.setdefault(
        "AWS_ENDPOINT_URL_DYNAMODB",
        os.environ.get("DYNAMODB_ENDPOINT", "http://localhost:8000"),
    )
    yield


@pytest.fixture
def ddb_table() -> Iterator[Any]:
    """Per-test DDB Local table — unique name avoids cross-test contamination."""
    endpoint_url = os.environ.get("DYNAMODB_ENDPOINT", "http://localhost:8000")
    dynamodb = boto3.resource(
        "dynamodb",
        endpoint_url=endpoint_url,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )

    table_name = f"cawnex-stage4-{uuid.uuid4().hex[:8]}"
    table = dynamodb.create_table(
        TableName=table_name,
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
            {"AttributeName": "GSI1PK", "AttributeType": "S"},
            {"AttributeName": "GSI1SK", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "GSI1",
                "KeySchema": [
                    {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                    {"AttributeName": "GSI1SK", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    yield table
    table.delete()
