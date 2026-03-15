"""Shared fixtures for murder tests."""

import os

import boto3
import pytest


@pytest.fixture
def dynamodb_table() -> "boto3.resources.factory.dynamodb.Table":  # type: ignore[name-defined]
    """Create a DynamoDB Local table for testing.

    Requires DynamoDB Local running on port 8000:
        docker run -p 8000:8000 amazon/dynamodb-local
    """
    endpoint_url = os.environ.get("DYNAMODB_ENDPOINT", "http://localhost:8000")
    dynamodb = boto3.resource(
        "dynamodb",
        endpoint_url=endpoint_url,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )

    table_name = "cawnex-test"

    # Delete table if exists from a previous run
    try:
        existing = dynamodb.Table(table_name)
        existing.delete()
        existing.wait_until_not_exists()
    except Exception:
        pass

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
