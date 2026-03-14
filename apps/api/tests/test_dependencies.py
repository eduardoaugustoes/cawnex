"""Tests for FastAPI dependencies."""

from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from src.auth.dependencies import get_tenant


@pytest.mark.asyncio
async def test_get_tenant_success() -> None:
    """Test get_tenant extracts tenant context from valid JWT claims."""
    # Mock request with valid AWS event context
    mock_request = Mock()
    mock_request.scope = {
        "aws.event": {
            "requestContext": {
                "authorizer": {
                    "jwt": {
                        "claims": {
                            "custom:tenant_id": "tenant-123",
                            "sub": "user-456",
                            "email": "test@example.com",
                        }
                    }
                }
            }
        }
    }

    tenant = await get_tenant(mock_request)

    assert tenant.tenant_id == "tenant-123"
    assert tenant.user_sub == "user-456"
    assert tenant.email == "test@example.com"


@pytest.mark.asyncio
async def test_get_tenant_missing_tenant_id() -> None:
    """Test get_tenant raises HTTPException when tenant_id is missing."""
    # Mock request without tenant_id
    mock_request = Mock()
    mock_request.scope = {
        "aws.event": {
            "requestContext": {
                "authorizer": {
                    "jwt": {"claims": {"sub": "user-456", "email": "test@example.com"}}
                }
            }
        }
    }

    with pytest.raises(HTTPException) as exc_info:
        await get_tenant(mock_request)

    assert exc_info.value.status_code == 403
    assert "Missing tenant context" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_get_tenant_missing_event() -> None:
    """Test get_tenant handles missing AWS event gracefully."""
    # Mock request without aws.event
    mock_request = Mock()
    mock_request.scope = {}

    with pytest.raises(HTTPException) as exc_info:
        await get_tenant(mock_request)

    assert exc_info.value.status_code == 403
    assert "Missing tenant context" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_get_tenant_empty_claims() -> None:
    """Test get_tenant handles empty JWT claims."""
    # Mock request with empty claims
    mock_request = Mock()
    mock_request.scope = {
        "aws.event": {"requestContext": {"authorizer": {"jwt": {"claims": {}}}}}
    }

    with pytest.raises(HTTPException) as exc_info:
        await get_tenant(mock_request)

    assert exc_info.value.status_code == 403
