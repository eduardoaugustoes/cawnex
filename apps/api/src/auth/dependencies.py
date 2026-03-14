"""
FastAPI dependencies for auth and tenant context.

JWT validation is handled by API Gateway's JWT authorizer.
By the time a request reaches Lambda, the token is already validated.
We just extract claims from the Mangum-adapted request context.
"""

from fastapi import Request, HTTPException

from src.auth.tenant import TenantContext


async def get_tenant(request: Request) -> TenantContext:
    """Extract tenant context from API Gateway JWT authorizer claims.

    API Gateway passes validated JWT claims in:
      event["requestContext"]["authorizer"]["jwt"]["claims"]

    Mangum makes the raw event available via request.scope["aws.event"].
    """
    event = request.scope.get("aws.event", {})
    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
    )

    tenant_id = claims.get("custom:tenant_id", "")
    user_sub = claims.get("sub", "")
    email = claims.get("email", "")

    if not tenant_id:
        raise HTTPException(status_code=403, detail="Missing tenant context")

    return TenantContext(tenant_id=tenant_id, user_sub=user_sub, email=email)
