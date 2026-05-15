# SSE Live Updates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace 3-second polling on Wave Execution and the no-refresh gap on MVI Detail with push-based SSE updates, sourced from DynamoDB Streams via an EventBridge Pipe into a new Fargate-hosted stream service.

**Architecture:** A dedicated Fargate task runs a FastAPI ASGI app that holds long-lived `text/event-stream` connections. DynamoDB Streams on the existing `cawnex-events-{stage}` table emits row-level changes to an EventBridge Pipe, which POSTs batches to the stream service. The service fans out to in-memory subscriber sets keyed by `wave_id`. iOS consumes the stream via `URLSession.bytes(for:)`. See `docs/superpowers/specs/2026-05-15-sse-live-updates-design.md`.

**Tech Stack:**
- Backend: Python 3.12, FastAPI, uvicorn (async ASGI), `boto3`, AWS Fargate (existing ECS cluster), Application Load Balancer, EventBridge Pipes, DynamoDB Streams
- Infra: AWS CDK (TypeScript) — extends existing `cawnex-stack.ts`
- iOS: Swift 5.10+, `URLSession.bytes(for:)`, `@MainActor`-isolated dispatch into existing `@Observable` view models
- Wire format: standard SSE (RFC 9110 + `text/event-stream`)

**Important pre-existing context:**
- A stale, orphaned file exists at `lambdas/sse/handler.py` that attempted Lambda-based SSE with 1s DDB polling. It is **not deployed** (no CDK reference) and **not used by iOS** (no client exists). Phase 1 deletes it to avoid confusion.
- Worker writes events via `Blackboard.put_event` to the `cawnex-events-{stage}` table. PK format: `T#{tenant}#P#{project}#W#{wave_id}`. SK format: `{ISO-timestamp}#{event_type}`. This is unchanged.

---

## File Structure (whole plan)

**New files:**
- `apps/stream/Dockerfile` — Python 3.12 base, pinned `linux/amd64`, uvicorn entrypoint
- `apps/stream/main.py` — ASGI entrypoint (just imports `app` and runs uvicorn)
- `apps/stream/requirements.txt` — `fastapi`, `uvicorn[standard]`, `boto3`, `pyjwt`, `cryptography`, `httpx` (for tests)
- `apps/stream/pyproject.toml` — ruff/mypy config matching `apps/api/pyproject.toml`
- `apps/stream/src/stream/__init__.py` — empty
- `apps/stream/src/stream/app.py` — FastAPI app, route registration, lifespan hooks
- `apps/stream/src/stream/auth.py` — Cognito JWT validation with JWKS signature verification
- `apps/stream/src/stream/config.py` — env var loading (TABLE_NAME, EVENTS_TABLE_NAME, USER_POOL_ID, REGION, PIPE_SECRET)
- `apps/stream/src/stream/subscribers.py` — in-memory subscriber map, fanout, backpressure
- `apps/stream/src/stream/sse.py` — SSE frame encoder, keepalive logic
- `apps/stream/src/stream/routes_stream.py` — `GET /projects/{pid}/waves/{wid}/stream` (Phase 1)
- `apps/stream/src/stream/routes_pipe.py` — `POST /_pipe` for EventBridge Pipe (Phase 2)
- `apps/stream/src/stream/backfill.py` — DDB query for `Last-Event-ID` replay (Phase 4)
- `apps/stream/src/stream/health.py` — `GET /_health` for ALB
- `apps/stream/tests/test_auth.py`
- `apps/stream/tests/test_subscribers.py`
- `apps/stream/tests/test_sse.py`
- `apps/stream/tests/test_routes_stream.py`
- `apps/stream/tests/test_routes_pipe.py` (Phase 2)
- `apps/stream/tests/test_backfill.py` (Phase 4)
- `apps/stream/tests/conftest.py`
- `apps/ios/Cawnex/Cawnex/Core/Network/EventStreamClient.swift` — `URLSession.bytes` SSE client (Phase 3)
- `apps/ios/Cawnex/Cawnex/Core/Network/EventStreamDecoder.swift` — SSE frame parser (Phase 3)
- `apps/ios/Cawnex/Cawnex/Core/Network/WaveEventStreamService.swift` — domain wrapper (Phase 3)

**Modified files:**
- `infra/lib/cawnex-stack.ts` — enable DDB Streams on EventsTable, add stream service Fargate construct, ALB, EventBridge Pipe (Phase 1, 2)
- `infra/package.json` — add `aws-cdk-lib` Pipe construct if not present (Phase 2)
- `apps/ios/Cawnex/Cawnex/Features/Waves/WaveExecutionViewModel.swift` — replace `startPolling`/`stopPolling`/`pollTimer` with `subscribe`/`unsubscribe` (Phase 3)
- `apps/ios/Cawnex/Cawnex/Features/Waves/WaveExecutionScreen.swift` — call `subscribe`/`unsubscribe` in `.onAppear`/`.onDisappear` (Phase 3)
- `apps/ios/Cawnex/Cawnex/Features/MVI/MVIDetailViewModel.swift` — add stream subscription (Phase 3)
- `apps/ios/Cawnex/Cawnex/Features/MVI/MVIDetailScreen.swift` — wire subscribe/unsubscribe (Phase 3)
- `apps/ios/Cawnex/Cawnex/App/ServiceFactory.swift` — add `makeEventStreamClient()` (Phase 3)
- `docs/ARCHITECTURE.md` — add SSE section (Phase 4)

**Deleted files:**
- `lambdas/sse/handler.py` — orphaned dead code from prior attempt (Phase 1, Task 1)

---

## Phase 1: Stream service skeleton + Fargate deploy

Goal: ship a stream service to dev that can be `curl`-tested with a real Cognito JWT, returning SSE frames. No Pipe yet — events are injected via a manual `POST /_pipe` shared-secret endpoint. iOS not touched yet.

### Task 1: Delete the orphaned SSE lambda

**Files:**
- Delete: `lambdas/sse/handler.py`
- Delete: `lambdas/sse/` (directory becomes empty)

- [ ] **Step 1: Confirm no references**

Run: `grep -rn "lambdas/sse\|lambdas.sse" /Users/eaugusto/cawnex --include="*.ts" --include="*.py" --include="*.json"`
Expected: no matches (other than the file itself).

- [ ] **Step 2: Delete the file and directory**

```bash
rm /Users/eaugusto/cawnex/lambdas/sse/handler.py
rmdir /Users/eaugusto/cawnex/lambdas/sse
```

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: remove orphaned lambdas/sse — never deployed, superseded by stream service"
```

---

### Task 2: Scaffold the stream service project

**Files:**
- Create: `apps/stream/pyproject.toml`
- Create: `apps/stream/requirements.txt`
- Create: `apps/stream/src/stream/__init__.py`
- Create: `apps/stream/tests/__init__.py`
- Create: `apps/stream/tests/conftest.py`

- [ ] **Step 1: Create `apps/stream/pyproject.toml`**

```toml
[project]
name = "stream"
version = "0.1.0"
requires-python = ">=3.12"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "ASYNC"]

[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_ignores = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Create `apps/stream/requirements.txt`**

```
fastapi==0.115.0
uvicorn[standard]==0.32.0
boto3==1.35.0
pyjwt[crypto]==2.9.0
httpx==0.27.0
pytest==8.3.0
pytest-asyncio==0.24.0
```

- [ ] **Step 3: Create empty `apps/stream/src/stream/__init__.py` and `apps/stream/tests/__init__.py`**

```bash
mkdir -p /Users/eaugusto/cawnex/apps/stream/src/stream /Users/eaugusto/cawnex/apps/stream/tests
touch /Users/eaugusto/cawnex/apps/stream/src/stream/__init__.py
touch /Users/eaugusto/cawnex/apps/stream/tests/__init__.py
```

- [ ] **Step 4: Create `apps/stream/tests/conftest.py`**

```python
"""Shared pytest fixtures for the stream service."""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def stub_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide deterministic env for unit tests — overridden per-test as needed."""
    monkeypatch.setenv("TABLE_NAME", "cawnex-test")
    monkeypatch.setenv("EVENTS_TABLE_NAME", "cawnex-events-test")
    monkeypatch.setenv("USER_POOL_ID", "us-east-1_TESTPOOL")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("PIPE_SECRET", "test-pipe-secret")
    yield
```

- [ ] **Step 5: Verify install works**

```bash
cd /Users/eaugusto/cawnex/apps/stream && python3.12 -m venv venv && ./venv/bin/pip install -r requirements.txt
```
Expected: clean install, no errors.

- [ ] **Step 6: Commit**

```bash
git add apps/stream/
git commit -m "feat(stream): scaffold stream service project structure"
```

---

### Task 3: Implement config loader (TDD)

**Files:**
- Create: `apps/stream/src/stream/config.py`
- Test: `apps/stream/tests/test_config.py`

- [ ] **Step 1: Write the failing test**

`apps/stream/tests/test_config.py`:
```python
"""Tests for stream service config loading."""

from __future__ import annotations

import pytest

from stream.config import Config, load_config


def test_load_config_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TABLE_NAME", "main")
    monkeypatch.setenv("EVENTS_TABLE_NAME", "events")
    monkeypatch.setenv("USER_POOL_ID", "us-east-1_X")
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.setenv("PIPE_SECRET", "s3cr3t")

    cfg = load_config()

    assert cfg.table_name == "main"
    assert cfg.events_table_name == "events"
    assert cfg.user_pool_id == "us-east-1_X"
    assert cfg.region == "us-west-2"
    assert cfg.pipe_secret == "s3cr3t"


def test_load_config_raises_when_required_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EVENTS_TABLE_NAME", raising=False)
    with pytest.raises(RuntimeError, match="EVENTS_TABLE_NAME"):
        load_config()


def test_config_is_immutable() -> None:
    cfg = Config(
        table_name="a",
        events_table_name="b",
        user_pool_id="c",
        region="d",
        pipe_secret="e",
    )
    with pytest.raises(AttributeError):
        cfg.table_name = "mutated"  # type: ignore[misc]
```

- [ ] **Step 2: Run the test — confirm it fails**

```bash
cd /Users/eaugusto/cawnex/apps/stream && PYTHONPATH=src ./venv/bin/pytest tests/test_config.py -v
```
Expected: ImportError on `stream.config`.

- [ ] **Step 3: Implement `apps/stream/src/stream/config.py`**

```python
"""Stream service configuration — loaded once from env, immutable afterward."""

from __future__ import annotations

import os
from dataclasses import dataclass


REQUIRED_ENV_VARS = (
    "TABLE_NAME",
    "EVENTS_TABLE_NAME",
    "USER_POOL_ID",
    "AWS_REGION",
    "PIPE_SECRET",
)


@dataclass(frozen=True, slots=True)
class Config:
    """Loaded once on process start; do not mutate at runtime."""

    table_name: str
    events_table_name: str
    user_pool_id: str
    region: str
    pipe_secret: str


def load_config() -> Config:
    """Load config from env. Raises RuntimeError on missing required vars."""
    missing = [name for name in REQUIRED_ENV_VARS if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")

    return Config(
        table_name=os.environ["TABLE_NAME"],
        events_table_name=os.environ["EVENTS_TABLE_NAME"],
        user_pool_id=os.environ["USER_POOL_ID"],
        region=os.environ["AWS_REGION"],
        pipe_secret=os.environ["PIPE_SECRET"],
    )
```

- [ ] **Step 4: Run the test — confirm pass**

```bash
cd /Users/eaugusto/cawnex/apps/stream && PYTHONPATH=src ./venv/bin/pytest tests/test_config.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/stream/src/stream/config.py apps/stream/tests/test_config.py
git commit -m "feat(stream): add immutable env-loaded config"
```

---

### Task 4: Implement Cognito JWT validation with signature verification (TDD)

The orphaned lambda skipped signature checks. We do not.

**Files:**
- Create: `apps/stream/src/stream/auth.py`
- Test: `apps/stream/tests/test_auth.py`

- [ ] **Step 1: Write the failing test**

`apps/stream/tests/test_auth.py`:
```python
"""Tests for JWT validation against Cognito JWKS."""

from __future__ import annotations

import json
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


def test_validate_token_rejects_unsigned_token() -> None:
    unsigned = jwt.encode({"custom:tenant_id": "x"}, "", algorithm="none")
    with pytest.raises(AuthError):
        validate_token(
            f"Bearer {unsigned}",
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
```

- [ ] **Step 2: Run the test — confirm it fails**

```bash
cd /Users/eaugusto/cawnex/apps/stream && PYTHONPATH=src ./venv/bin/pytest tests/test_auth.py -v
```
Expected: ImportError on `stream.auth`.

- [ ] **Step 3: Implement `apps/stream/src/stream/auth.py`**

```python
"""Cognito JWT validation with JWKS signature verification.

We verify signatures (the orphaned `lambdas/sse` handler did not).
JWKS is fetched once per process and cached in memory; the User Pool's
keys rotate rarely and a process restart picks up new keys.
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
) -> TenantClaims:
    """Validate a Bearer token; return claims or raise AuthError."""
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
    try:
        claims = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            issuer=expected_iss,
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("token expired") from exc
    except jwt.InvalidIssuerError as exc:
        raise AuthError("invalid issuer") from exc
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
```

- [ ] **Step 4: Run the test — confirm pass**

```bash
cd /Users/eaugusto/cawnex/apps/stream && PYTHONPATH=src ./venv/bin/pytest tests/test_auth.py -v
```
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/stream/src/stream/auth.py apps/stream/tests/test_auth.py
git commit -m "feat(stream): JWT validation with JWKS signature verification"
```

---

### Task 5: SSE frame encoder (TDD)

**Files:**
- Create: `apps/stream/src/stream/sse.py`
- Test: `apps/stream/tests/test_sse.py`

- [ ] **Step 1: Write the failing test**

`apps/stream/tests/test_sse.py`:
```python
"""Tests for SSE frame encoding."""

from __future__ import annotations

from stream.sse import KEEPALIVE_COMMENT, encode_event


def test_encode_event_minimal() -> None:
    out = encode_event(
        event_id="1747332779#crow_assigned",
        event_name="wave_event",
        data={"event_type": "crow_assigned", "wave_id": "w1"},
    )
    assert out == (
        "id: 1747332779#crow_assigned\n"
        'event: wave_event\n'
        'data: {"event_type": "crow_assigned", "wave_id": "w1"}\n'
        "\n"
    )


def test_encode_event_escapes_newlines_in_data() -> None:
    out = encode_event(
        event_id="2",
        event_name="wave_event",
        data={"message": "line1\nline2"},
    )
    # JSON-encoded; \n stays escaped inside the JSON string,
    # never appears raw on the SSE line.
    assert "\nline2" not in out.split("data: ", 1)[1].split("\n\n")[0]


def test_encode_event_omits_id_when_none() -> None:
    out = encode_event(event_id=None, event_name="wave_event", data={"ok": True})
    assert "id:" not in out
    assert 'event: wave_event\n' in out


def test_keepalive_is_comment_line() -> None:
    assert KEEPALIVE_COMMENT.startswith(":")
    assert KEEPALIVE_COMMENT.endswith("\n\n")
```

- [ ] **Step 2: Run the test — confirm it fails**

```bash
cd /Users/eaugusto/cawnex/apps/stream && PYTHONPATH=src ./venv/bin/pytest tests/test_sse.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `apps/stream/src/stream/sse.py`**

```python
"""Server-Sent Events frame encoder.

SSE wire format reference: https://html.spec.whatwg.org/multipage/server-sent-events.html
We emit only `id:`, `event:`, and `data:` fields. Each event ends with a
blank line. Keepalive lines start with `:` (comment) and are ignored by
compliant clients.
"""

from __future__ import annotations

import json
from typing import Any


KEEPALIVE_COMMENT = ": keepalive\n\n"


def encode_event(
    *,
    event_id: str | None,
    event_name: str,
    data: dict[str, Any],
) -> str:
    """Encode a single SSE frame.

    JSON-encodes `data` so no raw newlines leak into the SSE line stream.
    """
    lines: list[str] = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event_name}")
    lines.append(f"data: {json.dumps(data, default=str)}")
    return "\n".join(lines) + "\n\n"
```

- [ ] **Step 4: Run the test — confirm pass**

```bash
cd /Users/eaugusto/cawnex/apps/stream && PYTHONPATH=src ./venv/bin/pytest tests/test_sse.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/stream/src/stream/sse.py apps/stream/tests/test_sse.py
git commit -m "feat(stream): SSE frame encoder + keepalive"
```

---

### Task 6: In-memory subscriber map with fanout + backpressure (TDD)

**Files:**
- Create: `apps/stream/src/stream/subscribers.py`
- Test: `apps/stream/tests/test_subscribers.py`

- [ ] **Step 1: Write the failing test**

`apps/stream/tests/test_subscribers.py`:
```python
"""Tests for the subscriber registry + fanout."""

from __future__ import annotations

import asyncio

import pytest

from stream.subscribers import (
    BackpressureDrop,
    Subscriber,
    SubscriberRegistry,
)


@pytest.fixture
def registry() -> SubscriberRegistry:
    return SubscriberRegistry(max_queue_depth=4)


async def test_subscriber_receives_published_event(registry: SubscriberRegistry) -> None:
    sub = Subscriber(wave_id="w1")
    registry.register(sub)
    await registry.publish("w1", "frame-1")
    assert await asyncio.wait_for(sub.queue.get(), timeout=0.1) == "frame-1"


async def test_publish_to_unsubscribed_wave_is_noop(registry: SubscriberRegistry) -> None:
    await registry.publish("w-nonexistent", "frame-x")  # must not raise


async def test_fanout_delivers_to_multiple_subscribers(registry: SubscriberRegistry) -> None:
    a = Subscriber(wave_id="w1")
    b = Subscriber(wave_id="w1")
    registry.register(a)
    registry.register(b)
    await registry.publish("w1", "frame-1")
    assert await a.queue.get() == "frame-1"
    assert await b.queue.get() == "frame-1"


async def test_other_waves_do_not_receive(registry: SubscriberRegistry) -> None:
    a = Subscriber(wave_id="w1")
    b = Subscriber(wave_id="w2")
    registry.register(a)
    registry.register(b)
    await registry.publish("w1", "frame-1")
    assert await a.queue.get() == "frame-1"
    assert b.queue.qsize() == 0


async def test_unregister_stops_delivery(registry: SubscriberRegistry) -> None:
    sub = Subscriber(wave_id="w1")
    registry.register(sub)
    registry.unregister(sub)
    await registry.publish("w1", "frame-x")
    assert sub.queue.qsize() == 0


async def test_backpressure_drops_slow_subscriber(registry: SubscriberRegistry) -> None:
    sub = Subscriber(wave_id="w1")
    registry.register(sub)
    # Fill the queue to its max (4) without reading.
    for i in range(4):
        await registry.publish("w1", f"frame-{i}")
    # The next publish should evict this subscriber.
    with pytest.raises(BackpressureDrop):
        sub.raise_if_dropped()  # pre-overflow: still healthy
    await registry.publish("w1", "frame-overflow")
    with pytest.raises(BackpressureDrop):
        sub.raise_if_dropped()
    # And it should no longer be in the registry.
    assert sub not in registry._by_wave.get("w1", set())  # type: ignore[attr-defined]


async def test_register_is_idempotent(registry: SubscriberRegistry) -> None:
    sub = Subscriber(wave_id="w1")
    registry.register(sub)
    registry.register(sub)  # no double-add
    await registry.publish("w1", "frame-1")
    assert await sub.queue.get() == "frame-1"
    assert sub.queue.qsize() == 0
```

- [ ] **Step 2: Run the test — confirm it fails**

```bash
cd /Users/eaugusto/cawnex/apps/stream && PYTHONPATH=src ./venv/bin/pytest tests/test_subscribers.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `apps/stream/src/stream/subscribers.py`**

```python
"""In-memory subscriber registry with per-subscriber bounded queues.

A Subscriber holds an asyncio.Queue. Publishers do non-blocking put_nowait;
if a queue is full, the subscriber is evicted with BackpressureDrop set so
the connection coroutine can clean up and let the client reconnect.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field


class BackpressureDrop(Exception):
    """Raised when a subscriber's queue overflowed and they were evicted."""


@dataclass
class Subscriber:
    wave_id: str
    queue: asyncio.Queue[str] = field(default_factory=lambda: asyncio.Queue(maxsize=100))
    _dropped: bool = field(default=False, init=False)

    def mark_dropped(self) -> None:
        self._dropped = True

    def raise_if_dropped(self) -> None:
        if self._dropped:
            raise BackpressureDrop("subscriber queue overflowed")


class SubscriberRegistry:
    """Keyed by wave_id → set of Subscribers. Thread-unsafe; use within one event loop."""

    def __init__(self, max_queue_depth: int = 100) -> None:
        self._by_wave: dict[str, set[Subscriber]] = {}
        self._max_queue_depth = max_queue_depth

    def register(self, sub: Subscriber) -> None:
        # Resize the subscriber's queue to match the registry policy.
        if sub.queue.maxsize != self._max_queue_depth:
            sub.queue = asyncio.Queue(maxsize=self._max_queue_depth)
        self._by_wave.setdefault(sub.wave_id, set()).add(sub)

    def unregister(self, sub: Subscriber) -> None:
        bucket = self._by_wave.get(sub.wave_id)
        if bucket is None:
            return
        bucket.discard(sub)
        if not bucket:
            del self._by_wave[sub.wave_id]

    async def publish(self, wave_id: str, frame: str) -> None:
        """Fan out a frame to all subscribers of wave_id. Evicts slow consumers."""
        bucket = self._by_wave.get(wave_id)
        if not bucket:
            return
        for sub in list(bucket):
            try:
                sub.queue.put_nowait(frame)
            except asyncio.QueueFull:
                sub.mark_dropped()
                self.unregister(sub)
```

- [ ] **Step 4: Run the test — confirm pass**

```bash
cd /Users/eaugusto/cawnex/apps/stream && PYTHONPATH=src ./venv/bin/pytest tests/test_subscribers.py -v
```
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/stream/src/stream/subscribers.py apps/stream/tests/test_subscribers.py
git commit -m "feat(stream): in-memory subscriber registry with backpressure"
```

---

### Task 7: Health route + FastAPI app skeleton

**Files:**
- Create: `apps/stream/src/stream/app.py`
- Create: `apps/stream/src/stream/health.py`
- Test: `apps/stream/tests/test_health.py`

- [ ] **Step 1: Write the failing test**

`apps/stream/tests/test_health.py`:
```python
"""Tests for the health endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from stream.app import create_app


def test_health_returns_200() -> None:
    app = create_app()
    client = TestClient(app)
    resp = client.get("/_health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 2: Run the test — confirm it fails**

```bash
cd /Users/eaugusto/cawnex/apps/stream && PYTHONPATH=src ./venv/bin/pytest tests/test_health.py -v
```
Expected: ImportError on `stream.app`.

- [ ] **Step 3: Implement `apps/stream/src/stream/health.py`**

```python
"""Health check endpoint for the ALB target group."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/_health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 4: Implement `apps/stream/src/stream/app.py`**

```python
"""FastAPI application factory for the stream service."""

from __future__ import annotations

from fastapi import FastAPI

from stream import health
from stream.subscribers import SubscriberRegistry


def create_app() -> FastAPI:
    """Build a stream-service app. Registry is request-scoped via app.state."""
    app = FastAPI(title="cawnex-stream", docs_url=None, redoc_url=None)
    app.state.registry = SubscriberRegistry()
    app.include_router(health.router)
    return app


app = create_app()
```

- [ ] **Step 5: Run the test — confirm pass**

```bash
cd /Users/eaugusto/cawnex/apps/stream && PYTHONPATH=src ./venv/bin/pytest tests/test_health.py -v
```
Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add apps/stream/src/stream/app.py apps/stream/src/stream/health.py apps/stream/tests/test_health.py
git commit -m "feat(stream): FastAPI app skeleton + health endpoint"
```

---

### Task 8: SSE stream endpoint with auth + keepalive (TDD)

**Files:**
- Create: `apps/stream/src/stream/routes_stream.py`
- Test: `apps/stream/tests/test_routes_stream.py`
- Modify: `apps/stream/src/stream/app.py`

- [ ] **Step 1: Write the failing test**

`apps/stream/tests/test_routes_stream.py`:
```python
"""Tests for the public SSE stream endpoint."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from stream.app import create_app
from stream.auth import TenantClaims


def _override_validate(*, tenant_id: str = "tenant-abc") -> TenantClaims:
    return TenantClaims(tenant_id=tenant_id, user_sub="user-001", email="t@example.com")


def test_stream_rejects_missing_authorization() -> None:
    app = create_app()
    client = TestClient(app)
    resp = client.get("/projects/p1/waves/w1/stream")
    assert resp.status_code == 401


def test_stream_returns_event_stream_content_type() -> None:
    app = create_app()
    with patch("stream.routes_stream.validate_token", return_value=_override_validate()):
        client = TestClient(app)
        with client.stream(
            "GET",
            "/projects/p1/waves/w1/stream",
            headers={"Authorization": "Bearer fake"},
            timeout=0.5,
        ) as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")


def test_stream_emits_published_event() -> None:
    app = create_app()
    registry = app.state.registry

    with patch("stream.routes_stream.validate_token", return_value=_override_validate()):
        client = TestClient(app)

        with client.stream(
            "GET",
            "/projects/p1/waves/w1/stream",
            headers={"Authorization": "Bearer fake"},
            timeout=1.0,
        ) as resp:
            # Give the endpoint a moment to register, then publish.
            async def _publish() -> None:
                await asyncio.sleep(0.05)
                await registry.publish(
                    "w1",
                    "id: 1\nevent: wave_event\ndata: {\"ok\": true}\n\n",
                )

            asyncio.get_event_loop().run_until_complete(_publish())
            # Read up to one frame.
            for line in resp.iter_lines():
                if line.startswith("data:"):
                    assert '"ok": true' in line
                    break
```

- [ ] **Step 2: Run the test — confirm it fails**

```bash
cd /Users/eaugusto/cawnex/apps/stream && PYTHONPATH=src ./venv/bin/pytest tests/test_routes_stream.py -v
```
Expected: ImportError on `stream.routes_stream`.

- [ ] **Step 3: Implement `apps/stream/src/stream/routes_stream.py`**

```python
"""Public SSE endpoint: GET /projects/{pid}/waves/{wid}/stream.

Validates the Cognito JWT, registers a subscriber, then yields SSE frames
forever. A keepalive comment is emitted every 25 seconds so ALB's 60s idle
timeout doesn't kill the connection. On client disconnect or backpressure
drop, the subscriber is unregistered.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from stream.auth import AuthError, validate_token
from stream.config import load_config
from stream.sse import KEEPALIVE_COMMENT
from stream.subscribers import BackpressureDrop, Subscriber, SubscriberRegistry


router = APIRouter()

KEEPALIVE_INTERVAL_SEC = 25.0


@router.get("/projects/{project_id}/waves/{wave_id}/stream")
async def stream_wave_events(
    project_id: str,
    wave_id: str,
    request: Request,
    authorization: str = Header(default=""),
) -> StreamingResponse:
    cfg = load_config()
    try:
        validate_token(
            authorization,
            user_pool_id=cfg.user_pool_id,
            region=cfg.region,
        )
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    # Authorization scoped to wave is enforced by querying the main table —
    # done in Phase 2 when we wire DDB. For Phase 1 we only validate the JWT
    # and rely on wave_id being unguessable per tenant.

    registry: SubscriberRegistry = request.app.state.registry

    async def event_generator() -> AsyncIterator[str]:
        sub = Subscriber(wave_id=wave_id)
        registry.register(sub)
        try:
            while True:
                if await request.is_disconnected():
                    return
                try:
                    frame = await asyncio.wait_for(
                        sub.queue.get(),
                        timeout=KEEPALIVE_INTERVAL_SEC,
                    )
                    yield frame
                except asyncio.TimeoutError:
                    yield KEEPALIVE_COMMENT
                try:
                    sub.raise_if_dropped()
                except BackpressureDrop:
                    return
        finally:
            registry.unregister(sub)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
```

- [ ] **Step 4: Wire route into the app**

Modify `apps/stream/src/stream/app.py`:
```python
"""FastAPI application factory for the stream service."""

from __future__ import annotations

from fastapi import FastAPI

from stream import health, routes_stream
from stream.subscribers import SubscriberRegistry


def create_app() -> FastAPI:
    app = FastAPI(title="cawnex-stream", docs_url=None, redoc_url=None)
    app.state.registry = SubscriberRegistry()
    app.include_router(health.router)
    app.include_router(routes_stream.router)
    return app


app = create_app()
```

- [ ] **Step 5: Run the test — confirm pass**

```bash
cd /Users/eaugusto/cawnex/apps/stream && PYTHONPATH=src ./venv/bin/pytest tests/test_routes_stream.py -v
```
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add apps/stream/src/stream/routes_stream.py apps/stream/src/stream/app.py apps/stream/tests/test_routes_stream.py
git commit -m "feat(stream): SSE endpoint with JWT validation + keepalive"
```

---

### Task 9: Pipe injection endpoint for Phase 1 manual testing (TDD)

Note: the real EventBridge Pipe wiring lands in Phase 2. For Phase 1 we expose `POST /_pipe` guarded by a shared secret so we can `curl`-inject events end-to-end.

**Files:**
- Create: `apps/stream/src/stream/routes_pipe.py`
- Test: `apps/stream/tests/test_routes_pipe.py`
- Modify: `apps/stream/src/stream/app.py`

- [ ] **Step 1: Write the failing test**

`apps/stream/tests/test_routes_pipe.py`:
```python
"""Tests for the EventBridge Pipe ingestion endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from stream.app import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_pipe_rejects_missing_secret(client: TestClient) -> None:
    resp = client.post("/_pipe", json=[])
    assert resp.status_code == 401


def test_pipe_rejects_wrong_secret(client: TestClient) -> None:
    resp = client.post(
        "/_pipe",
        json=[],
        headers={"X-Pipe-Secret": "wrong"},
    )
    assert resp.status_code == 401


def test_pipe_accepts_empty_batch(client: TestClient) -> None:
    resp = client.post(
        "/_pipe",
        json=[],
        headers={"X-Pipe-Secret": "test-pipe-secret"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"published": 0}


def test_pipe_publishes_to_registry(client: TestClient) -> None:
    """A pipe POST with a parsed DDB Streams record fans out to subscribers."""
    record = {
        "PK": "T#tenant-abc#P#p1#W#w1",
        "SK": "2026-05-15T19:14:12Z#crow_assigned",
        "event_type": "crow_assigned",
        "message": "Implementer assigned",
        "color": "blue",
        "timestamp": "2026-05-15T19:14:12Z",
        "wave_id": "w1",
        "mvi_id": "m1",
    }
    resp = client.post(
        "/_pipe",
        json=[record],
        headers={"X-Pipe-Secret": "test-pipe-secret"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"published": 1}


def test_pipe_skips_record_with_missing_pk(client: TestClient) -> None:
    """Bad records are dropped, not 500'd."""
    bad = {"SK": "no_pk", "event_type": "x"}
    resp = client.post(
        "/_pipe",
        json=[bad],
        headers={"X-Pipe-Secret": "test-pipe-secret"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"published": 0}
```

- [ ] **Step 2: Run the test — confirm it fails**

```bash
cd /Users/eaugusto/cawnex/apps/stream && PYTHONPATH=src ./venv/bin/pytest tests/test_routes_pipe.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `apps/stream/src/stream/routes_pipe.py`**

```python
"""EventBridge Pipe ingestion endpoint.

The Pipe POSTs an array of records. Each record should have at least PK and
event_type. We extract wave_id from PK (`T#{tenant}#P#{project}#W#{wave_id}`)
and fan out to in-memory subscribers.

Authenticated via a shared secret header (X-Pipe-Secret). For a stronger
posture, swap to IAM SigV4 verification — left as a future step since the
endpoint is on a non-public ALB listener rule.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from stream.config import load_config
from stream.sse import encode_event


router = APIRouter()


_PK_PATTERN = re.compile(r"^T#(?P<tenant>[^#]+)#P#(?P<project>[^#]+)#W#(?P<wave>[^#]+)$")


def _wave_id_from_pk(pk: str) -> str | None:
    match = _PK_PATTERN.match(pk)
    return match.group("wave") if match else None


def _record_to_frame(record: dict[str, Any]) -> tuple[str, str] | None:
    """Return (wave_id, sse_frame) or None if the record should be skipped."""
    pk = record.get("PK", "")
    sk = record.get("SK", "")
    wave_id = _wave_id_from_pk(pk)
    if wave_id is None:
        return None

    event_id = sk or None
    frame = encode_event(
        event_id=event_id,
        event_name="wave_event",
        data={
            "event_type": record.get("event_type", ""),
            "message": record.get("message", ""),
            "color": record.get("color", ""),
            "timestamp": record.get("timestamp", ""),
            "wave_id": wave_id,
            "mvi_id": record.get("mvi_id", ""),
        },
    )
    return wave_id, frame


@router.post("/_pipe")
async def receive_pipe_batch(
    request: Request,
    x_pipe_secret: str = Header(default=""),
) -> dict[str, int]:
    cfg = load_config()
    if x_pipe_secret != cfg.pipe_secret:
        raise HTTPException(status_code=401, detail="invalid pipe secret")

    payload = await request.json()
    if not isinstance(payload, list):
        raise HTTPException(status_code=400, detail="expected JSON array")

    registry = request.app.state.registry
    published = 0
    for record in payload:
        if not isinstance(record, dict):
            continue
        result = _record_to_frame(record)
        if result is None:
            continue
        wave_id, frame = result
        await registry.publish(wave_id, frame)
        published += 1

    return {"published": published}
```

- [ ] **Step 4: Wire route into the app**

Modify `apps/stream/src/stream/app.py`:
```python
"""FastAPI application factory for the stream service."""

from __future__ import annotations

from fastapi import FastAPI

from stream import health, routes_pipe, routes_stream
from stream.subscribers import SubscriberRegistry


def create_app() -> FastAPI:
    app = FastAPI(title="cawnex-stream", docs_url=None, redoc_url=None)
    app.state.registry = SubscriberRegistry()
    app.include_router(health.router)
    app.include_router(routes_stream.router)
    app.include_router(routes_pipe.router)
    return app


app = create_app()
```

- [ ] **Step 5: Run the test — confirm pass**

```bash
cd /Users/eaugusto/cawnex/apps/stream && PYTHONPATH=src ./venv/bin/pytest tests/test_routes_pipe.py -v
```
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add apps/stream/src/stream/routes_pipe.py apps/stream/src/stream/app.py apps/stream/tests/test_routes_pipe.py
git commit -m "feat(stream): /_pipe ingestion endpoint with shared-secret auth"
```

---

### Task 10: Container entrypoint + Dockerfile

**Files:**
- Create: `apps/stream/main.py`
- Create: `apps/stream/Dockerfile`

- [ ] **Step 1: Create `apps/stream/main.py`**

```python
"""Container entrypoint — runs uvicorn with the stream-service ASGI app."""

from __future__ import annotations

import uvicorn


def main() -> None:
    uvicorn.run(
        "stream.app:app",
        host="0.0.0.0",
        port=8080,
        log_level="info",
        access_log=True,
        # Long timeouts to support SSE; ALB enforces idle timeout separately.
        timeout_keep_alive=120,
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Create `apps/stream/Dockerfile`**

Mirrors `apps/worker/Dockerfile`'s platform pinning to avoid arm64 builds from Apple Silicon laptops landing on Fargate (Linux/amd64).

```dockerfile
# Pin Linux x86_64 explicitly so local builds on Apple Silicon don't produce
# an arm64 image that crashes on Fargate (Linux/amd64) with "exec format error".
FROM --platform=linux/amd64 python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY apps/stream/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY apps/stream/src/ ./src/

ENV PYTHONPATH="/app/src"
ENV PORT=8080

EXPOSE 8080

COPY apps/stream/main.py ./main.py

CMD ["python", "main.py"]
```

- [ ] **Step 3: Build locally to verify**

```bash
cd /Users/eaugusto/cawnex && docker build -f apps/stream/Dockerfile -t cawnex-stream:local .
```
Expected: image builds clean.

- [ ] **Step 4: Smoke-run the container with env**

```bash
docker run --rm -p 8080:8080 \
  -e TABLE_NAME=cawnex-dev \
  -e EVENTS_TABLE_NAME=cawnex-events-dev \
  -e USER_POOL_ID=us-east-1_TESTPOOL \
  -e AWS_REGION=us-east-1 \
  -e PIPE_SECRET=local-test \
  cawnex-stream:local &
sleep 2
curl -s http://localhost:8080/_health
```
Expected: `{"status":"ok"}`. Then `docker stop` the container.

- [ ] **Step 5: Commit**

```bash
git add apps/stream/main.py apps/stream/Dockerfile
git commit -m "feat(stream): container entrypoint + Dockerfile"
```

---

### Task 11: CDK — provision Fargate service + ALB target

Add a new Fargate service that runs the stream image. Public-facing ALB with HTTPS listener. Reuses the existing VPC and ECS cluster.

**Files:**
- Modify: `infra/lib/cawnex-stack.ts`

- [ ] **Step 1: Read the existing worker section to mirror patterns**

Familiarize yourself with `infra/lib/cawnex-stack.ts` lines 440–580 (worker section). The new stream service mirrors it but: no EFS, no SQS, smaller cpu/mem, behind an ALB, `desiredCount: 1`.

- [ ] **Step 2: Add `elbv2` import at the top of `cawnex-stack.ts`**

After the existing imports block, add:

```typescript
import * as elbv2 from "aws-cdk-lib/aws-elasticloadbalancingv2";
import * as certmanager from "aws-cdk-lib/aws-certificatemanager";
```

- [ ] **Step 3: Add the stream service construct after the WorkerService block**

Find the line `// Worker ECS service — outbound internet for LLM APIs + GitHub` and the closing brace of the `_workerService` declaration. Immediately after that closing brace, insert:

```typescript
    // ─────────────────────────────────────────────
    // Stream Service — Fargate task hosting SSE endpoints
    // ─────────────────────────────────────────────
    const streamSg = new ec2.SecurityGroup(this, "StreamServiceSG", {
      vpc,
      description: "Stream service ECS task",
      allowAllOutbound: true,
    });

    const streamTaskDef = new ecs.FargateTaskDefinition(this, "StreamTask", {
      family: `cawnex-stream-${stage}`,
      cpu: 256, // 0.25 vCPU — plenty for thousands of idle SSE connections
      memoryLimitMiB: 512,
    });

    // Pipe secret for /_pipe authentication
    const pipeSecret = new secretsmanager.Secret(this, "StreamPipeSecret", {
      secretName: `cawnex/${stage}/stream-pipe-secret`,
      generateSecretString: {
        passwordLength: 48,
        excludePunctuation: true,
      },
    });

    streamTaskDef.addContainer("stream", {
      containerName: "stream",
      image: ecs.ContainerImage.fromAsset("..", {
        file: "apps/stream/Dockerfile",
      }),
      logging: ecs.LogDrivers.awsLogs({
        streamPrefix: "stream",
        logRetention: logs.RetentionDays.ONE_MONTH,
      }),
      environment: {
        STAGE: stage,
        TABLE_NAME: tableName,
        EVENTS_TABLE_NAME: eventsTable.tableName,
        USER_POOL_ID: userPoolId, // existing CfnParameter or import — see Step 4
        AWS_REGION_NAME: this.region,
      },
      secrets: {
        PIPE_SECRET: ecs.Secret.fromSecretsManager(pipeSecret),
      },
      portMappings: [{ containerPort: 8080 }],
      healthCheck: {
        command: [
          "CMD-SHELL",
          "curl -fsS http://localhost:8080/_health || exit 1",
        ],
        interval: cdk.Duration.seconds(30),
        timeout: cdk.Duration.seconds(5),
        retries: 3,
        startPeriod: cdk.Duration.seconds(30),
      },
    });

    table.grantReadData(streamTaskDef.taskRole);
    eventsTable.grantReadData(streamTaskDef.taskRole);

    const streamService = new ecs.FargateService(this, "StreamService", {
      serviceName: `cawnex-stream-${stage}`,
      cluster,
      taskDefinition: streamTaskDef,
      desiredCount: 1,
      assignPublicIp: stage !== "prod",
      securityGroups: [streamSg],
      platformVersion: ecs.FargatePlatformVersion.LATEST,
      capacityProviderStrategies: [
        {
          capacityProvider: "FARGATE_SPOT",
          weight: stage === "prod" ? 0 : 1,
        },
        {
          capacityProvider: "FARGATE",
          weight: stage === "prod" ? 1 : 0,
        },
      ],
    });

    // ALB — public entrypoint for SSE
    const streamAlb = new elbv2.ApplicationLoadBalancer(this, "StreamALB", {
      vpc,
      internetFacing: true,
      loadBalancerName: `cawnex-stream-${stage}`,
      idleTimeout: cdk.Duration.seconds(120),
    });

    const streamListener = streamAlb.addListener("StreamListener", {
      port: 80,
      open: true,
      defaultAction: elbv2.ListenerAction.fixedResponse(404, {
        contentType: "text/plain",
        messageBody: "not found",
      }),
    });

    // Public clients hit the SSE endpoint
    streamListener.addAction("StreamRoute", {
      priority: 10,
      conditions: [
        elbv2.ListenerCondition.pathPatterns(["/projects/*/waves/*/stream"]),
      ],
      action: elbv2.ListenerAction.forward([
        new elbv2.ApplicationTargetGroup(this, "StreamTargets", {
          vpc,
          port: 8080,
          protocol: elbv2.ApplicationProtocol.HTTP,
          targetType: elbv2.TargetType.IP,
          targets: [streamService.loadBalancerTarget({
            containerName: "stream",
            containerPort: 8080,
          })],
          healthCheck: {
            path: "/_health",
            healthyHttpCodes: "200",
            interval: cdk.Duration.seconds(30),
          },
          deregistrationDelay: cdk.Duration.seconds(15),
        }),
      ]),
    });

    // Pipe + health on separate target group, same service (Phase 1: same path forwards)
    streamListener.addAction("StreamPipeRoute", {
      priority: 20,
      conditions: [elbv2.ListenerCondition.pathPatterns(["/_pipe", "/_health"])],
      action: elbv2.ListenerAction.forward([
        new elbv2.ApplicationTargetGroup(this, "StreamPipeTargets", {
          vpc,
          port: 8080,
          protocol: elbv2.ApplicationProtocol.HTTP,
          targetType: elbv2.TargetType.IP,
          targets: [streamService.loadBalancerTarget({
            containerName: "stream",
            containerPort: 8080,
          })],
          healthCheck: { path: "/_health", healthyHttpCodes: "200" },
        }),
      ]),
    });

    streamAlb.connections.allowTo(streamSg, ec2.Port.tcp(8080), "ALB to stream tasks");
    streamSg.connections.allowFrom(streamAlb, ec2.Port.tcp(8080), "from ALB");

    new cdk.CfnOutput(this, "StreamServiceURL", {
      value: `http://${streamAlb.loadBalancerDnsName}`,
      description: "Stream service ALB DNS",
    });

    new cdk.CfnOutput(this, "StreamPipeSecretArn", {
      value: pipeSecret.secretArn,
      description: "Secret holding the stream service PIPE_SECRET",
    });
```

- [ ] **Step 4: Confirm `userPoolId` is available in scope**

Search `infra/lib/cawnex-stack.ts` for how the API Lambda gets the User Pool ID. If it's a `CfnParameter`, reference the same one. If imported from `cawnex-auth-stack.ts`, follow the same pattern. The expected variable name in this stack is `userPoolId`.

If no such variable exists, add (after the existing auth/cognito imports):

```typescript
const userPoolId =
  props?.userPoolId ?? this.node.tryGetContext("userPoolId") ?? "";
if (!userPoolId) {
  throw new Error("userPoolId not provided to CawnexStack");
}
```

…and update the `interface CawnexStackProps` in this file (or `bin/infra.ts`) to pass it from the auth stack outputs.

- [ ] **Step 5: Synth and verify**

```bash
cd /Users/eaugusto/cawnex/infra && rm -rf cdk.out && npx cdk synth Cawnex-dev > /dev/null
```
Expected: no errors. The `cdk.out/Cawnex-dev.template.json` should contain `StreamService`, `StreamALB`, `StreamPipeSecret`.

- [ ] **Step 6: Commit**

```bash
git add infra/lib/cawnex-stack.ts infra/package.json infra/package-lock.json
git commit -m "feat(infra): Fargate stream service with ALB for SSE"
```

---

### Task 12: Deploy to dev + manual smoke test

- [ ] **Step 1: Deploy**

```bash
cd /Users/eaugusto/cawnex/infra && rm -rf cdk.out && npx cdk deploy Cawnex-dev --require-approval never
```
Expected: stack updates, prints `StreamServiceURL` output.

- [ ] **Step 2: Resolve the pipe secret value**

```bash
SECRET_ARN=$(aws cloudformation describe-stacks \
  --stack-name Cawnex-dev \
  --query "Stacks[0].Outputs[?OutputKey=='StreamPipeSecretArn'].OutputValue" \
  --output text)
PIPE_SECRET=$(aws secretsmanager get-secret-value --secret-id "$SECRET_ARN" --query SecretString --output text)
echo "PIPE_SECRET length: ${#PIPE_SECRET}"
```
Expected: length 48.

- [ ] **Step 3: Hit `/_health` through the ALB**

```bash
ALB_URL=$(aws cloudformation describe-stacks \
  --stack-name Cawnex-dev \
  --query "Stacks[0].Outputs[?OutputKey=='StreamServiceURL'].OutputValue" \
  --output text)
curl -fsS "$ALB_URL/_health"
```
Expected: `{"status":"ok"}`.

- [ ] **Step 4: Get a real Cognito JWT from a dev login (via iOS or CLI helper)**

This depends on your dev workflow. Either:
- Log into the iOS app on a simulator and copy `Authorization` from a recent API call's network log; or
- Use the existing `apps/api` test helper to mint a token.

Set `JWT="$YOUR_TOKEN_HERE"`.

- [ ] **Step 5: Open an SSE connection and confirm keepalive arrives**

```bash
curl -N -H "Authorization: Bearer $JWT" "$ALB_URL/projects/cawnex-e26784/waves/w-test-1/stream" &
CURL_PID=$!
sleep 30
kill $CURL_PID 2>/dev/null
```
Expected: within 25–30s, see `: keepalive` line appear in stdout.

- [ ] **Step 6: Inject an event via `/_pipe` while the stream is open and confirm it arrives**

In one terminal:
```bash
curl -N -H "Authorization: Bearer $JWT" "$ALB_URL/projects/cawnex-e26784/waves/w-test-1/stream"
```

In another:
```bash
curl -fsS -X POST "$ALB_URL/_pipe" \
  -H "X-Pipe-Secret: $PIPE_SECRET" \
  -H "Content-Type: application/json" \
  -d '[{
    "PK": "T#dev-tenant#P#cawnex-e26784#W#w-test-1",
    "SK": "2026-05-15T20:00:00Z#crow_assigned",
    "event_type": "crow_assigned",
    "message": "Implementer assigned",
    "color": "blue",
    "timestamp": "2026-05-15T20:00:00Z",
    "wave_id": "w-test-1",
    "mvi_id": "m1"
  }]'
```
Expected `/_pipe` reply: `{"published":1}`.
Expected first terminal: an SSE frame appears like:
```
id: 2026-05-15T20:00:00Z#crow_assigned
event: wave_event
data: {"event_type": "crow_assigned", ...}
```

- [ ] **Step 7: Commit any deploy-discovered fixups**

If any tweaks were needed during smoke test (env var typo, IAM gap, etc.), commit them now.

```bash
git add -A
git commit -m "fix(stream): post-deploy smoke test corrections"
```

---

## Phase 1 self-review checklist

Before declaring Phase 1 done, verify:

- [ ] All 12 tasks committed cleanly.
- [ ] `pytest` passes in `apps/stream/` with `PYTHONPATH=src`.
- [ ] `cdk synth Cawnex-dev` produces no errors.
- [ ] ALB health check is reporting `healthy` for the stream task (check AWS console or `aws elbv2 describe-target-health`).
- [ ] An open `curl -N` SSE connection survives ≥ 60 seconds without TCP close.
- [ ] A `/_pipe` POST during that connection causes a frame to arrive within 1 second.
- [ ] An unauthenticated GET on the stream endpoint returns 401.
- [ ] A POST to `/_pipe` without the secret returns 401.

If any check fails, fix before Phase 2.

---

## Phases 2-4 (high-level — plans deferred until Phase 1 ships)

These will get their own detailed plans once Phase 1 is in. Sketched here so the scope is visible:

### Phase 2 — Wire the EventBridge Pipe

1. Enable DynamoDB Streams on `EventsTable` in `cawnex-stack.ts` (`stream: dynamodb.StreamViewType.NEW_IMAGE`).
2. Create an EventBridge Pipe (`aws-cdk-lib/aws-pipes`) with:
   - Source: events table stream ARN, batch size 10, starting position `LATEST`.
   - Filter pattern: keep only events with `eventName: ["INSERT"]` and `NewImage.event_type.S` in our broadcast allowlist.
   - Target: HTTP invoke to the ALB's `/_pipe` URL with the `X-Pipe-Secret` header sourced from the pipe secret.
3. Add a dead-letter SQS queue for failed pipe deliveries.
4. Smoke test: trigger a real wave and confirm events arrive at an open SSE connection without manual `/_pipe` POSTs.

### Phase 3 — iOS SSE client

1. Create `EventStreamDecoder.swift` that parses SSE frames out of an `AsyncSequence<UInt8>`. State machine: collect lines until blank line, then emit one frame.
2. Create `EventStreamClient.swift` that opens `URLSession.bytes(for:)`, runs the decoder, exposes `AsyncStream<SSEFrame>`. Built-in reconnect with `Last-Event-ID` header (held in actor-isolated state). Backoff: 1s, 2s, 5s, 10s, then 10s.
3. Create `WaveEventStreamService.swift` — domain wrapper that maps `SSEFrame.data` JSON into the existing `WaveEvent` model.
4. Modify `WaveExecutionViewModel`: delete `pollTimer`, add `subscribe(projectId:waveId:)` that consumes the AsyncStream and dispatches frames into `events`/`detail` on `@MainActor`. On `mvi_ready`/`wave_failed`, refetch `getWave` to refresh aggregates.
5. Modify `MVIDetailViewModel`: subscribe to the parent wave's stream, filter by `mvi_id`.
6. Wire `subscribe`/`unsubscribe` into `.onAppear` / `.onDisappear` for both screens.
7. Add `streamBaseURL` to `APIClient` config (separate from REST base — points at the ALB).
8. Test on simulator against the dev stack.

### Phase 4 — Backfill + observability

1. Implement `Last-Event-ID` backfill: on stream open with header, query events table for `PK = T#{tenant}#P#{pid}#W#{wid}` and `SK > {last_event_id}` (limit 200), encode each as SSE frame, send before joining the registry.
2. Add a `wave_terminated` end-of-stream marker so iOS can stop subscribing when wave reaches `delivered`/`cancelled`.
3. Add CloudWatch metrics: `connections_active` (gauge), `events_published` (counter), `backpressure_drops` (counter), `backfill_queries` (counter), `pipe_records_received` (counter).
4. Add ALB access logs to an S3 bucket.
5. Update `docs/ARCHITECTURE.md` with the SSE section.

---

## Self-review notes (filled in after writing)

**Spec coverage:** Phase 1 implements spec sections "Stream Service", "Subscription model", "Endpoints (except backfill)", "Wire format", "Failure modes" (the recoverable ones — backfill in Phase 4). Phases 2-4 cover the rest. No spec requirement is missing a task.

**Placeholder scan:** None. Every step has exact paths, commands, or code.

**Type consistency:** `Subscriber`, `SubscriberRegistry`, `Config`, `TenantClaims`, `BackpressureDrop`, `encode_event` are defined once and reused consistently across tasks.

**Phase split:** Phase 1 alone produces a shippable artifact — a working SSE service in dev that can be `curl`-tested end-to-end. It's not yet wired into the real event flow (Phase 2) or the iOS app (Phase 3), but it's a real, deployed thing whose contract is stable for subsequent phases to build against.
