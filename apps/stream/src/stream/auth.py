"""Cognito JWT validation with JWKS signature verification.

The orphaned `lambdas/sse` skipped signature checks; we don't. JWKS is
fetched once per process and cached; User Pool keys rotate rarely and a
process restart picks up new keys.
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import Any

import jwt
from jwt.algorithms import RSAAlgorithm


class AuthError(Exception):
    """Raised when a token is missing, malformed, expired, or unauthorized."""


@dataclass(frozen=True, slots=True)
class TenantClaims:
    tenant_id: str
    user_sub: str
    email: str


_jwks_cache: dict[str, Any] | None = None


def _fetch_jwks(user_pool_id: str, region: str) -> dict[str, Any]:
    """Fetch the JWKS document for the User Pool. Cached process-wide."""
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache
    url = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json"
    with urllib.request.urlopen(url, timeout=5) as resp:  # noqa: S310 — controlled URL
        _jwks_cache = json.loads(resp.read())
    assert _jwks_cache is not None
    return _jwks_cache


def _public_key_for_kid(jwks: dict[str, Any], kid: str) -> Any:
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return RSAAlgorithm.from_jwk(json.dumps(key))
    raise AuthError(f"unknown key id: {kid}")


def validate_token(
    authorization_header: str,
    *,
    user_pool_id: str,
    region: str,
    allowed_audiences: tuple[str, ...] | None = None,
) -> TenantClaims:
    """Validate a Bearer token; return claims or raise AuthError.

    If `allowed_audiences` is set, the token's `aud` claim must match one of
    them — Cognito ID tokens carry the App Client ID here. If None,
    audience validation is skipped (signature + issuer are still enforced).
    """
    if not authorization_header or not authorization_header.lower().startswith("bearer "):
        raise AuthError("missing or malformed authorization header")

    token = authorization_header.split(" ", 1)[1].strip()
    if not token:
        raise AuthError("empty bearer token")

    try:
        unverified_header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise AuthError(f"malformed token: {exc}") from exc

    kid = unverified_header.get("kid")
    if not kid:
        raise AuthError("token missing key id")

    public_key = _public_key_for_kid(_fetch_jwks(user_pool_id, region), kid)

    expected_iss = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"
    decode_kwargs: dict[str, Any] = {
        "algorithms": ["RS256"],
        "issuer": expected_iss,
        "options": {"require": ["exp", "iat", "sub"]},
    }
    if allowed_audiences:
        # PyJWT accepts a list of acceptable audiences; matches if any overlap.
        decode_kwargs["audience"] = list(allowed_audiences)
    else:
        decode_kwargs["options"]["verify_aud"] = False

    try:
        claims = jwt.decode(token, public_key, **decode_kwargs)
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("token expired") from exc
    except jwt.InvalidIssuerError as exc:
        raise AuthError("invalid issuer") from exc
    except jwt.InvalidAudienceError as exc:
        raise AuthError("invalid audience") from exc
    except jwt.PyJWTError as exc:
        raise AuthError(f"token validation failed: {exc}") from exc

    tenant_id = claims.get("custom:tenant_id", "")
    if not tenant_id:
        raise AuthError("token missing tenant_id")

    return TenantClaims(
        tenant_id=tenant_id,
        user_sub=claims.get("sub", ""),
        email=claims.get("email", ""),
    )
