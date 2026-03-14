"""
Tenant context extraction from API Gateway JWT authorizer.

API Gateway validates the JWT and passes claims in requestContext.
This module extracts tenant_id and makes it available to route handlers.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TenantContext:
    """Immutable tenant context extracted from the JWT."""

    tenant_id: str
    user_sub: str
    email: str
