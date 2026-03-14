"""
FastAPI dependencies for auth and tenant context.

JWT validation is handled by API Gateway's JWT authorizer.
By the time a request reaches Lambda, the token is already validated.
We just extract claims from the Mangum-adapted request context.
"""

from typing import Any, Dict

from fastapi import HTTPException, Request

from src.auth.tenant import TenantContext


async def get_tenant(request: Request) -> TenantContext:
    """Extract tenant context from API Gateway JWT authorizer claims.

    API Gateway passes validated JWT claims in:
      event["requestContext"]["authorizer"]["jwt"]["claims"]

    Mangum makes the raw event available via request.scope["aws.event"].

    Args:
        request: FastAPI request object containing AWS event context

    Returns:
        TenantContext with extracted tenant information

    Raises:
        HTTPException: If tenant_id is missing from JWT claims
    """
    event: Dict[str, Any] = request.scope.get("aws.event", {})
    claims: Dict[str, Any] = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
    )

    tenant_id: str = claims.get("custom:tenant_id", "")
    user_sub: str = claims.get("sub", "")
    email: str = claims.get("email", "")

    if not tenant_id:
        raise HTTPException(status_code=403, detail="Missing tenant context")

    return TenantContext(tenant_id=tenant_id, user_sub=user_sub, email=email)
