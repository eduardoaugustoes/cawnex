"""Tests for JWT validation against Cognito JWKS."""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import patch

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from stream.auth import (
    AuthError,
    TenantClaims,
    validate_token,
)


@pytest.fixture(autouse=True)
def reset_jwks_cache() -> None:
    import stream.auth

    stream.auth._jwks_cache = None
    yield


@pytest.fixture
def rsa_keypair() -> tuple[rsa.RSAPrivateKey, dict[str, Any]]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_numbers = key.public_key().public_numbers()

    def _b64uint(n: int) -> str:
        import base64

        length = (n.bit_length() + 7) // 8
        return base64.urlsafe_b64encode(n.to_bytes(length, "big")).rstrip(b"=").decode()

    jwk = {
        "kty": "RSA",
        "kid": "test-kid",
        "use": "sig",
        "alg": "RS256",
        "n": _b64uint(public_numbers.n),
        "e": _b64uint(public_numbers.e),
    }
    return key, jwk


def _make_token(
    key: rsa.RSAPrivateKey,
    *,
    iss: str = "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_TESTPOOL",
    exp_offset: int = 3600,
    tenant_id: str = "tenant-abc",
    sub: str = "user-001",
    kid: str = "test-kid",
) -> str:
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return jwt.encode(
        {
            "iss": iss,
            "sub": sub,
            "custom:tenant_id": tenant_id,
            "email": "t@example.com",
            "exp": int(time.time()) + exp_offset,
            "iat": int(time.time()),
            "token_use": "access",
        },
        pem,
        algorithm="RS256",
        headers={"kid": kid},
    )


def test_validate_token_returns_tenant_claims(
    rsa_keypair: tuple[rsa.RSAPrivateKey, dict[str, Any]],
) -> None:
    key, jwk = rsa_keypair
    token = _make_token(key)

    with patch("stream.auth._fetch_jwks", return_value={"keys": [jwk]}):
        claims = validate_token(
            f"Bearer {token}",
            user_pool_id="us-east-1_TESTPOOL",
            region="us-east-1",
        )

    assert isinstance(claims, TenantClaims)
    assert claims.tenant_id == "tenant-abc"
    assert claims.user_sub == "user-001"


def test_validate_token_rejects_expired(
    rsa_keypair: tuple[rsa.RSAPrivateKey, dict[str, Any]],
) -> None:
    key, jwk = rsa_keypair
    token = _make_token(key, exp_offset=-10)

    with patch("stream.auth._fetch_jwks", return_value={"keys": [jwk]}):
        with pytest.raises(AuthError, match="expired"):
            validate_token(
                f"Bearer {token}",
                user_pool_id="us-east-1_TESTPOOL",
                region="us-east-1",
            )


def test_validate_token_rejects_wrong_issuer(
    rsa_keypair: tuple[rsa.RSAPrivateKey, dict[str, Any]],
) -> None:
    key, jwk = rsa_keypair
    token = _make_token(
        key, iss="https://cognito-idp.us-east-1.amazonaws.com/us-east-1_OTHER"
    )

    with patch("stream.auth._fetch_jwks", return_value={"keys": [jwk]}):
        with pytest.raises(AuthError, match="issuer"):
            validate_token(
                f"Bearer {token}",
                user_pool_id="us-east-1_TESTPOOL",
                region="us-east-1",
            )


def test_validate_token_rejects_missing_tenant_id(
    rsa_keypair: tuple[rsa.RSAPrivateKey, dict[str, Any]],
) -> None:
    key, jwk = rsa_keypair
    token = _make_token(key, tenant_id="")

    with patch("stream.auth._fetch_jwks", return_value={"keys": [jwk]}):
        with pytest.raises(AuthError, match="tenant"):
            validate_token(
                f"Bearer {token}",
                user_pool_id="us-east-1_TESTPOOL",
                region="us-east-1",
            )


def test_validate_token_rejects_missing_header() -> None:
    with pytest.raises(AuthError, match="authorization"):
        validate_token("", user_pool_id="x", region="us-east-1")


def test_validate_token_rejects_kid_not_in_jwks(
    rsa_keypair: tuple[rsa.RSAPrivateKey, dict[str, Any]],
) -> None:
    key, jwk = rsa_keypair
    token = _make_token(key, kid="unknown-kid")

    with patch("stream.auth._fetch_jwks", return_value={"keys": [jwk]}):
        with pytest.raises(AuthError, match="key id"):
            validate_token(
                f"Bearer {token}",
                user_pool_id="us-east-1_TESTPOOL",
                region="us-east-1",
            )
