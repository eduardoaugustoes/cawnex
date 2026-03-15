"""Client configuration endpoint — no auth required.

Returns Cognito and API configuration so iOS/web clients
don't need hardcoded values. Survives stack redeploys.
"""

import os
from typing import Any, Dict

from fastapi import APIRouter

router = APIRouter()


@router.get("/config")
async def get_config() -> Dict[str, Any]:
    """Return client configuration from deployed infrastructure.

    All values come from Lambda environment variables set by CDK.
    No secrets are exposed — only public Cognito identifiers.
    """
    return {
        "userPoolId": os.environ.get("USER_POOL_ID", ""),
        "iosClientId": os.environ.get("IOS_CLIENT_ID", ""),
        "webClientId": os.environ.get("USER_POOL_CLIENT_ID", ""),
        "region": os.environ.get("AWS_REGION_NAME", "us-east-1"),
        "cognitoDomain": os.environ.get("COGNITO_DOMAIN", ""),
        "stage": os.environ.get("STAGE", "unknown"),
    }
