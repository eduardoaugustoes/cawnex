"""Tests for health endpoint."""

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    """Test health endpoint returns correct status and stage."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert "stage" in data


@patch.dict(os.environ, {"STAGE": "test"})
def test_health_endpoint_with_stage() -> None:
    """Test health endpoint returns configured stage from environment."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert data["stage"] == "test"


def test_health_endpoint_unknown_stage() -> None:
    """Test health endpoint returns 'unknown' when STAGE not set."""
    with patch.dict(os.environ, {}, clear=True):
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ok"
        assert data["stage"] == "unknown"
