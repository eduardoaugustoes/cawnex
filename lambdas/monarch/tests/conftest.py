"""Shared fixtures for monarch tests."""

import os

import boto3
import pytest


@pytest.fixture
def dynamodb_table() -> "boto3.resources.factory.dynamodb.Table":  # type: ignore[name-defined]
    endpoint_url = os.environ.get("DYNAMODB_ENDPOINT", "http://localhost:8000")
    dynamodb = boto3.resource(
        "dynamodb",
        endpoint_url=endpoint_url,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )

    table_name = "cawnex-monarch-test"

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
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()

    yield table

    table.delete()
