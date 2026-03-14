"""Tests for tenant context."""

from src.auth.tenant import TenantContext


def test_tenant_context_creation() -> None:
    """Test TenantContext can be created with valid data."""
    tenant = TenantContext(
        tenant_id="test-tenant-123", user_sub="user-456", email="test@example.com"
    )

    assert tenant.tenant_id == "test-tenant-123"
    assert tenant.user_sub == "user-456"
    assert tenant.email == "test@example.com"


def test_tenant_context_equality() -> None:
    """Test TenantContext equality comparison."""
    tenant1 = TenantContext(
        tenant_id="test-tenant", user_sub="user-123", email="test@example.com"
    )
    tenant2 = TenantContext(
        tenant_id="test-tenant", user_sub="user-123", email="test@example.com"
    )
    tenant3 = TenantContext(
        tenant_id="different-tenant", user_sub="user-123", email="test@example.com"
    )

    assert tenant1 == tenant2
    assert tenant1 != tenant3
