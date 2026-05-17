# Stage 4 Layer B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the iOS Wave Review surface so founders see the Council's per-advisor verdict + investigation trace on a wave that's `under_human_review`, and can approve/reject the whole wave with confirmation.

**Architecture:** New iOS `Features/WaveReview/` module following the existing Contract-First (Option B) pattern (protocol → InMemory → API → ViewModel → View). One new backend endpoint (`GET /projects/{p}/council/sessions/{s}`) reads the Council session row written by Layer A; one new whole-wave approve endpoint flips `under_human_review → delivered` and triggers per-PR merges. Reject reuses the existing wave cancel. Real-time discovery uses the existing SSE event stream (`council_decision` events already emitted by Layer A's Council Fargate). MVI Blackboard gets a persistent "Council Review Ready" card as a non-real-time entry point.

**Tech Stack:** Swift / SwiftUI / `@Observable`, iOS unit + UI test targets (`CawnexTests`, `CawnexUITests`), Python 3.12 / FastAPI / pytest, DynamoDB Local for backend integration tests (already running on port 8000 from Layer A's wrap-up).

**Spec:** [docs/superpowers/specs/2026-05-17-council-layer-b-design.md](../specs/2026-05-17-council-layer-b-design.md)

**Pencil screens (already designed):**
- `S35 — Wave Review (Council)` — node `IFIEa` at x:4887, y:7012 in `design/cawnex.pen`
- `S35 — Wave Review (scrolled)` — node `uFYIA` at x:5430, y:7012
- `S36 — Investigation Trace` — node `YIU3t` at x:5973, y:7012
- `S32 — MVI Blackboard` touchup — "Council review ready" card node `d7p4A` already inserted

---

## Milestone M1 — Backend (GET session + Approve wave + tests) (~1 day)

**M1 outcome:** A real Council session row in DDB Local can be fetched via `GET /projects/{p}/council/sessions/{s}` with project ownership enforced; a real wave in `under_human_review` can be approved via `POST /projects/{p}/waves/{w}/approve` flipping it to `delivered` and triggering per-PR merges. Integration tests pass against DDB Local.

### Task 1: Add canonical fixture JSON for a completed Council session

**Files:**
- Create: `apps/api/tests/fixtures/council_session_completed.json`

This fixture is reused by the backend GET handler tests AND copied into the iOS test bundle in M2 — single source of truth.

- [ ] **Step 1: Create the fixture directory and file**

```bash
mkdir -p apps/api/tests/fixtures
```

```json
{
  "PK": "P#p1",
  "SK": "COUNCIL#wr_w1_a8f3b2c1",
  "session_id": "wr_w1_a8f3b2c1",
  "wave_id": "w1",
  "project_id": "p1",
  "status": "completed",
  "integration_sk": "INTEGRATION#w1",
  "created_at": "2026-05-17T14:02:11Z",
  "completed_at": "2026-05-17T14:05:48Z",
  "pipeline_health": "ok",
  "decision": {
    "action": "approve",
    "reasoning": "All advisors approved. Cited tenant_id filter on foo.py:42, no auth regression, no perf concerns.",
    "confidence": 0.86,
    "conditions": [],
    "ordering_constraints": [],
    "dissent_record": {}
  },
  "cost": { "tokens_in": 12450, "tokens_out": 3120, "duration_ms": 0 },
  "rounds": [
    {
      "round_number": 1,
      "consensus": true,
      "question": null,
      "votes": [
        {
          "advisor": "security",
          "vote": "approve",
          "reasoning": "Verified tenant_id filter on foo.py:42 and auth middleware applied.",
          "confidence": 0.92,
          "blockers": [],
          "condition": null,
          "cost": { "tokens_in": 2100, "tokens_out": 480, "duration_ms": 0 },
          "cited_evidence": [
            { "file_path": "apps/api/foo.py", "line_range": [42, 58], "pr_number": 42, "reason": "tenant_id filter present" }
          ],
          "investigation_trace": [
            { "tool_name": "read_file", "args": { "path": "apps/api/foo.py" }, "result_summary": "def query()...", "duration_ms": 18, "error": null },
            { "tool_name": "grep", "args": { "pattern": "tenant_id", "path": "apps/api" }, "result_summary": "12 matches", "duration_ms": 42, "error": null }
          ]
        },
        {
          "advisor": "architecture",
          "vote": "approve",
          "reasoning": "No new coupling across bounded contexts.",
          "confidence": 0.81,
          "blockers": [],
          "condition": null,
          "cost": { "tokens_in": 1900, "tokens_out": 410, "duration_ms": 0 },
          "cited_evidence": [],
          "investigation_trace": []
        },
        {
          "advisor": "clarity",
          "vote": "approve",
          "reasoning": "PR descriptions cover acceptance criteria.",
          "confidence": 0.88,
          "blockers": [],
          "condition": null,
          "cost": { "tokens_in": 1700, "tokens_out": 380, "duration_ms": 0 },
          "cited_evidence": [],
          "investigation_trace": []
        },
        {
          "advisor": "performance",
          "vote": "approve_with_condition",
          "reasoning": "Lookup O(n); add index before 10K users.",
          "confidence": 0.74,
          "blockers": [],
          "condition": "Add btree index on users.tenant_id before scaling past 10K rows.",
          "cost": { "tokens_in": 2200, "tokens_out": 510, "duration_ms": 0 },
          "cited_evidence": [
            { "file_path": "apps/api/signup_handler.py", "line_range": [88, 102], "pr_number": 43, "reason": "linear scan in hot path" }
          ],
          "investigation_trace": []
        },
        {
          "advisor": "ux",
          "vote": "approve",
          "reasoning": "All signup states covered; accessibility identifiers present.",
          "confidence": 0.83,
          "blockers": [],
          "condition": null,
          "cost": { "tokens_in": 2400, "tokens_out": 620, "duration_ms": 0 },
          "cited_evidence": [],
          "investigation_trace": []
        },
        {
          "advisor": "cost",
          "vote": "approve",
          "reasoning": "Zero CDK diff; wave consumed 4.2% of budget.",
          "confidence": 0.69,
          "blockers": [],
          "condition": null,
          "cost": { "tokens_in": 2150, "tokens_out": 720, "duration_ms": 0 },
          "cited_evidence": [],
          "investigation_trace": []
        }
      ]
    }
  ]
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/api/tests/fixtures/council_session_completed.json
git commit -m "test(council): canonical fixture for a completed wave_review session"
```

### Task 2: Add canonical fixture JSON for a pending session

**Files:**
- Create: `apps/api/tests/fixtures/council_session_pending.json`

- [ ] **Step 1: Create the fixture**

```json
{
  "PK": "P#p1",
  "SK": "COUNCIL#wr_w2_pending01",
  "session_id": "wr_w2_pending01",
  "wave_id": "w2",
  "project_id": "p1",
  "status": "pending",
  "integration_sk": "INTEGRATION#w2",
  "created_at": "2026-05-17T14:10:00Z",
  "completed_at": null,
  "pipeline_health": "ok",
  "decision": null,
  "cost": null,
  "rounds": []
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/api/tests/fixtures/council_session_pending.json
git commit -m "test(council): canonical fixture for a pending session"
```

### Task 3: Add canonical fixture JSON for an errored session

**Files:**
- Create: `apps/api/tests/fixtures/council_session_errored.json`

- [ ] **Step 1: Create the fixture**

```json
{
  "PK": "P#p1",
  "SK": "COUNCIL#wr_w3_errored01",
  "session_id": "wr_w3_errored01",
  "wave_id": "w3",
  "project_id": "p1",
  "status": "errored",
  "integration_sk": "INTEGRATION#w3",
  "created_at": "2026-05-17T14:20:00Z",
  "completed_at": "2026-05-17T14:25:11Z",
  "pipeline_health": "degraded",
  "decision": null,
  "cost": null,
  "rounds": []
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/api/tests/fixtures/council_session_errored.json
git commit -m "test(council): canonical fixture for an errored session"
```

### Task 4: Backend GET handler — happy path (200 with completed session)

**Files:**
- Modify: `apps/api/src/routes/council.py`
- Create: `apps/api/tests/test_council_get_session.py`

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/test_council_get_session.py
"""Tests for GET /projects/{project_id}/council/sessions/{session_id}."""

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.main import app

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_get_completed_session_returns_full_shape(
    client: TestClient, dynamodb_table, monkeypatch
) -> None:
    """A completed session round-trips with every top-level field present."""
    fixture = _load_fixture("council_session_completed.json")
    dynamodb_table.put_item(Item=fixture)

    headers = {"Authorization": "Bearer test-token-for-tenant-t1-project-p1"}
    resp = client.get(
        "/projects/p1/council/sessions/wr_w1_a8f3b2c1", headers=headers
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["session_id"] == "wr_w1_a8f3b2c1"
    assert body["wave_id"] == "w1"
    assert body["project_id"] == "p1"
    assert body["status"] == "completed"
    assert body["integration_sk"] == "INTEGRATION#w1"
    assert body["pipeline_health"] == "ok"
    assert body["decision"]["action"] == "approve"
    assert body["decision"]["confidence"] == 0.86
    assert len(body["rounds"]) == 1
    assert len(body["rounds"][0]["votes"]) == 6
    sec_vote = next(v for v in body["rounds"][0]["votes"] if v["advisor"] == "security")
    assert sec_vote["vote"] == "approve"
    assert sec_vote["cited_evidence"][0]["file_path"] == "apps/api/foo.py"
    assert sec_vote["investigation_trace"][0]["tool_name"] == "read_file"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && PYTHONPATH=src pytest tests/test_council_get_session.py::test_get_completed_session_returns_full_shape -v`
Expected: FAIL — 404 (route doesn't exist yet) or similar.

- [ ] **Step 3: Add the GET handler in council.py**

Open `apps/api/src/routes/council.py`. Add this handler after the existing `apply_council_override` function (preserve all existing code):

```python
@router.get("/sessions/{session_id}")
async def get_council_session(
    project_id: str,
    session_id: str,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> Dict[str, Any]:
    """Return the full Council session row for the founder's review screen.

    Status reflects reality:
      - pending / running: decision is null, rounds may be empty or partial
      - completed: decision + full rounds populated
      - errored: decision null, pipeline_health=degraded

    iOS branches on `status` rather than null-checking individual fields.
    """
    db = TenantDB(tenant)
    council_sk = f"COUNCIL#{session_id}"
    session = db.get_project_item(project_id, council_sk)
    if not session:
        raise HTTPException(status_code=404, detail="Council session not found")

    # Strip internal keys before returning
    out = {k: v for k, v in session.items() if k not in {"PK", "SK", "entityType"}}
    out.setdefault("session_id", session_id)
    out.setdefault("wave_id", session.get("wave_id", ""))
    out.setdefault("project_id", project_id)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && PYTHONPATH=src pytest tests/test_council_get_session.py::test_get_completed_session_returns_full_shape -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/routes/council.py apps/api/tests/test_council_get_session.py
git commit -m "feat(api): GET /projects/{p}/council/sessions/{s} — completed-session happy path"
```

### Task 5: Backend GET handler — pending + running + errored states

**Files:**
- Modify: `apps/api/tests/test_council_get_session.py`

The handler already returns whatever's in DDB, so the test just verifies pending/running/errored fixtures round-trip cleanly.

- [ ] **Step 1: Write the failing tests**

Append to `apps/api/tests/test_council_get_session.py`:

```python
def test_get_pending_session_returns_null_decision(
    client: TestClient, dynamodb_table
) -> None:
    fixture = _load_fixture("council_session_pending.json")
    dynamodb_table.put_item(Item=fixture)

    headers = {"Authorization": "Bearer test-token-for-tenant-t1-project-p1"}
    resp = client.get(
        "/projects/p1/council/sessions/wr_w2_pending01", headers=headers
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "pending"
    assert body["decision"] is None
    assert body["rounds"] == []


def test_get_errored_session_includes_degraded_health(
    client: TestClient, dynamodb_table
) -> None:
    fixture = _load_fixture("council_session_errored.json")
    dynamodb_table.put_item(Item=fixture)

    headers = {"Authorization": "Bearer test-token-for-tenant-t1-project-p1"}
    resp = client.get(
        "/projects/p1/council/sessions/wr_w3_errored01", headers=headers
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "errored"
    assert body["pipeline_health"] == "degraded"
    assert body["decision"] is None
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd apps/api && PYTHONPATH=src pytest tests/test_council_get_session.py -v`
Expected: PASS, 3 tests total.

- [ ] **Step 3: Commit**

```bash
git add apps/api/tests/test_council_get_session.py
git commit -m "test(api): GET council session covers pending + errored states"
```

### Task 6: Backend GET handler — 404 when missing

**Files:**
- Modify: `apps/api/tests/test_council_get_session.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
def test_get_missing_session_returns_404(
    client: TestClient, dynamodb_table
) -> None:
    headers = {"Authorization": "Bearer test-token-for-tenant-t1-project-p1"}
    resp = client.get(
        "/projects/p1/council/sessions/wr_does_not_exist", headers=headers
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()
```

- [ ] **Step 2: Run test to verify it passes** (handler already raises 404)

Run: `cd apps/api && PYTHONPATH=src pytest tests/test_council_get_session.py::test_get_missing_session_returns_404 -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add apps/api/tests/test_council_get_session.py
git commit -m "test(api): GET council session returns 404 for missing SK"
```

### Task 7: Add `POST /waves/{wave_id}/approve` endpoint

**Files:**
- Modify: `apps/api/src/routes/waves.py`
- Modify: `apps/api/tests/test_waves.py`

Audit (Task 0 in spirit) confirmed `/activate`, `/pause`, `/cancel` exist but `/approve` does not. Approve flips wave from `under_human_review` to `delivered` and triggers per-PR merges (reusing whatever merge helper already exists in routes/prs.py).

- [ ] **Step 1: Inspect existing wave endpoints + merge helper**

Run: `grep -n "def merge\|prs\|under_human_review\|delivered" apps/api/src/routes/waves.py apps/api/src/routes/prs.py | head -20`

Locate: (a) the wave status update helper used by activate/cancel, (b) the PR merge function (likely `_merge_pr` or similar). Note both for use in step 3.

- [ ] **Step 2: Write the failing test**

In `apps/api/tests/test_waves.py`, add a new test class at the end of the file:

```python
class TestApproveWave:
    def test_approve_wave_flips_status_to_delivered_and_merges_prs(
        self, client: TestClient, dynamodb_table, monkeypatch
    ) -> None:
        # Seed wave in under_human_review with 2 MVIs that each have a PR
        dynamodb_table.put_item(Item={
            "PK": "P#p1", "SK": "S#w1", "level": "wave",
            "status": "under_human_review", "wave_id": "w1",
        })
        dynamodb_table.put_item(Item={
            "PK": "P#p1", "SK": "S#w1#m_1", "level": "murder",
            "status": "ready_to_ship", "pr_number": 42, "mvi_id": "_1",
        })
        dynamodb_table.put_item(Item={
            "PK": "P#p1", "SK": "S#w1#m_2", "level": "murder",
            "status": "ready_to_ship", "pr_number": 43, "mvi_id": "_2",
        })

        merged_calls: list[int] = []
        def fake_merge(project_id, pr_number):
            merged_calls.append(pr_number)
            return {"merged": True}
        monkeypatch.setattr(
            "src.routes.waves._merge_pr_for_wave", fake_merge, raising=False
        )

        headers = {"Authorization": "Bearer test-token-for-tenant-t1-project-p1"}
        resp = client.post("/projects/p1/waves/w1/approve", headers=headers)

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "delivered"
        assert body["merged_prs"] == [42, 43]
        wave = dynamodb_table.get_item(
            Key={"PK": "P#p1", "SK": "S#w1"}
        )["Item"]
        assert wave["status"] == "delivered"
        assert sorted(merged_calls) == [42, 43]

    def test_approve_wave_rejects_wrong_status(
        self, client: TestClient, dynamodb_table
    ) -> None:
        dynamodb_table.put_item(Item={
            "PK": "P#p1", "SK": "S#w1", "level": "wave",
            "status": "executing", "wave_id": "w1",
        })
        headers = {"Authorization": "Bearer test-token-for-tenant-t1-project-p1"}
        resp = client.post("/projects/p1/waves/w1/approve", headers=headers)
        assert resp.status_code == 409
        assert "under_human_review" in resp.json()["detail"]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd apps/api && PYTHONPATH=src pytest tests/test_waves.py::TestApproveWave -v`
Expected: FAIL — endpoint doesn't exist.

- [ ] **Step 4: Add the approve handler**

Open `apps/api/src/routes/waves.py`. Add this handler after the existing `cancel_wave`:

```python
def _merge_pr_for_wave(project_id: str, pr_number: int) -> dict[str, Any]:
    """Best-effort PR merge for a wave-level approve. Returns merge result.

    Wrapped in a helper so tests can monkeypatch it without going through
    the GitHub HTTP path.
    """
    # Reuse the existing PR merge helper from routes/prs.py. If the helper
    # signature differs in this repo, adapt this call accordingly during
    # implementation — the helper itself already exists.
    from src.routes import prs  # late import to avoid circular dependency
    return prs.merge_pr_for_project(project_id=project_id, pr_number=pr_number)


@router.post("/{wave_id}/approve")
async def approve_wave(
    project_id: str,
    wave_id: str,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> Dict[str, Any]:
    """Founder-driven wave approval after Council review.

    Wave must be in `under_human_review`. Flips status to `delivered` and
    merges every PR attached to a ready_to_ship MVI in the wave.
    """
    db = TenantDB(tenant)
    wave_sk = f"S#{wave_id}"
    wave = db.get_project_item(project_id, wave_sk)
    if not wave or wave.get("status") != "under_human_review":
        current = wave.get("status", "missing") if wave else "missing"
        raise HTTPException(
            status_code=409,
            detail=(
                f"Wave status is '{current}'; approve requires "
                "'under_human_review'"
            ),
        )

    # Find all MVIs in the wave with PR numbers
    mvi_prefix = f"S#{wave_id}#m"
    mvis = db.query_project_items(project_id, mvi_prefix)
    pr_numbers = sorted(
        int(m["pr_number"]) for m in mvis
        if m.get("level") == "murder"
        and m.get("status") == "ready_to_ship"
        and m.get("pr_number") is not None
    )

    merged: list[int] = []
    for pr in pr_numbers:
        try:
            _merge_pr_for_wave(project_id=project_id, pr_number=pr)
            merged.append(pr)
        except Exception:
            # Stop on first failure — partial merge is recoverable, silent
            # success on partial is not (loud-fail per Layer A discipline)
            break

    if merged != pr_numbers:
        raise HTTPException(
            status_code=502,
            detail=(
                f"Partial merge: succeeded {merged}, intended {pr_numbers}. "
                "Wave status unchanged. Investigate failed PR and retry."
            ),
        )

    db.update_project_item(
        project_id, wave_sk, {"status": "delivered", "delivered_at": _now_iso()}
    )

    return {"status": "delivered", "merged_prs": merged, "wave_id": wave_id}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd apps/api && PYTHONPATH=src pytest tests/test_waves.py::TestApproveWave -v`
Expected: PASS, 2 tests.

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/routes/waves.py apps/api/tests/test_waves.py
git commit -m "feat(api): POST /waves/{w}/approve — wave-level approve + per-PR merge"
```

### Task 8: M1 integration test against DDB Local

**Files:**
- Create: `tests/integration/test_stage4_b_wave_review.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_stage4_b_wave_review.py
"""Stage 4 Layer B integration: Council session round-trip via FastAPI + DDB Local."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from src.main import app


FIXTURES = Path(__file__).resolve().parents[2] / "apps" / "api" / "tests" / "fixtures"


def test_round_trip_completed_session(ddb_table: Any) -> None:
    """Write a completed CouncilSession row; GET returns the iOS-shaped JSON."""
    fixture = json.loads((FIXTURES / "council_session_completed.json").read_text())
    ddb_table.put_item(Item=fixture)

    client = TestClient(app)
    headers = {"Authorization": "Bearer test-token-for-tenant-t1-project-p1"}
    resp = client.get(
        "/projects/p1/council/sessions/wr_w1_a8f3b2c1", headers=headers
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert len(body["rounds"][0]["votes"]) == 6
    advisors = [v["advisor"] for v in body["rounds"][0]["votes"]]
    assert set(advisors) == {
        "security", "architecture", "clarity",
        "performance", "ux", "cost",
    }
```

- [ ] **Step 2: Run test to verify it passes** (Layer A's `ddb_table` fixture from `tests/integration/conftest.py` is already wired)

Run: `cd /Users/eaugusto/cawnex && python3 -m pytest tests/integration/test_stage4_b_wave_review.py -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_stage4_b_wave_review.py
git commit -m "test(integration): Layer B end-to-end via FastAPI + DDB Local"
```

### M1 wrap-up: full backend suite + sanity

- [ ] **Step 1: Run all backend tests**

```bash
cd apps/api && PYTHONPATH=src pytest tests/ -q
cd /Users/eaugusto/cawnex && python3 -m pytest tests/integration/ -q
```

Expected: all pass.

- [ ] **Step 2: Verify the new endpoint is mounted**

```bash
cd apps/api && PYTHONPATH=src python3 -c "from src.main import app; print([r.path for r in app.routes if 'council' in r.path or 'waves' in r.path])" | tr ',' '\n'
```

Expected output includes:
- `/projects/{project_id}/council/sessions/{session_id}`
- `/projects/{project_id}/waves/{wave_id}/approve`

---

## Milestone M2 — iOS data layer (models + services + contract tests) (~1 day)

**M2 outcome:** Domain models decode every fixture variant cleanly. `InMemoryWaveReviewService` powers previews/UI tests with seeded data. `APIWaveReviewService` calls the M1 GET endpoint. Contract test catches API↔iOS drift.

### Task 9: Add `AnyCodable` shim

**Files:**
- Create: `apps/ios/Cawnex/Cawnex/Core/Network/AnyCodable.swift`
- Create: `apps/ios/Cawnex/CawnexTests/Core/Network/AnyCodableTests.swift`

Audit confirmed no existing `AnyCodable` in the iOS codebase.

- [ ] **Step 1: Write the failing tests**

```swift
// apps/ios/Cawnex/Cawnex/CawnexTests/Core/Network/AnyCodableTests.swift
import XCTest
@testable import Cawnex

final class AnyCodableTests: XCTestCase {
    func test_decodes_string() throws {
        let json = #"{"v":"hello"}"#.data(using: .utf8)!
        let decoded = try JSONDecoder().decode([String: AnyCodable].self, from: json)
        XCTAssertEqual(decoded["v"]?.value as? String, "hello")
    }

    func test_decodes_int() throws {
        let json = #"{"v":42}"#.data(using: .utf8)!
        let decoded = try JSONDecoder().decode([String: AnyCodable].self, from: json)
        XCTAssertEqual(decoded["v"]?.value as? Int, 42)
    }

    func test_decodes_nested_object() throws {
        let json = #"{"v":{"path":"foo.py","max":10}}"#.data(using: .utf8)!
        let decoded = try JSONDecoder().decode([String: AnyCodable].self, from: json)
        let nested = decoded["v"]?.value as? [String: Any]
        XCTAssertEqual(nested?["path"] as? String, "foo.py")
        XCTAssertEqual(nested?["max"] as? Int, 10)
    }

    func test_decodes_null() throws {
        let json = #"{"v":null}"#.data(using: .utf8)!
        let decoded = try JSONDecoder().decode([String: AnyCodable].self, from: json)
        XCTAssertNil(decoded["v"]?.value)
    }

    func test_encodes_round_trip() throws {
        let original: [String: AnyCodable] = [
            "a": AnyCodable("text"), "b": AnyCodable(7),
        ]
        let data = try JSONEncoder().encode(original)
        let roundtripped = try JSONDecoder().decode([String: AnyCodable].self, from: data)
        XCTAssertEqual(roundtripped["a"]?.value as? String, "text")
        XCTAssertEqual(roundtripped["b"]?.value as? Int, 7)
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Open the Cawnex Xcode project. Run the `AnyCodableTests` target.
Expected: FAIL — `AnyCodable` doesn't exist.

- [ ] **Step 3: Implement AnyCodable**

```swift
// apps/ios/Cawnex/Cawnex/Cawnex/Core/Network/AnyCodable.swift
import Foundation

/// Type-erased wrapper for decoding heterogeneous JSON values (used for tool-call
/// args whose shape varies per tool). Stores the raw value as `Any?` and supports
/// round-trip Codable for primitives, arrays, and dictionaries.
struct AnyCodable: Codable, Equatable {
    let value: Any?

    init(_ value: Any?) { self.value = value }

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() {
            self.value = nil
        } else if let b = try? container.decode(Bool.self) {
            self.value = b
        } else if let i = try? container.decode(Int.self) {
            self.value = i
        } else if let d = try? container.decode(Double.self) {
            self.value = d
        } else if let s = try? container.decode(String.self) {
            self.value = s
        } else if let arr = try? container.decode([AnyCodable].self) {
            self.value = arr.map { $0.value }
        } else if let dict = try? container.decode([String: AnyCodable].self) {
            self.value = dict.mapValues { $0.value }
        } else {
            throw DecodingError.dataCorruptedError(
                in: container,
                debugDescription: "AnyCodable: unsupported JSON value"
            )
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch value {
        case nil:
            try container.encodeNil()
        case let b as Bool:
            try container.encode(b)
        case let i as Int:
            try container.encode(i)
        case let d as Double:
            try container.encode(d)
        case let s as String:
            try container.encode(s)
        case let arr as [Any?]:
            try container.encode(arr.map(AnyCodable.init))
        case let dict as [String: Any?]:
            try container.encode(dict.mapValues(AnyCodable.init))
        default:
            throw EncodingError.invalidValue(
                value as Any,
                EncodingError.Context(
                    codingPath: container.codingPath,
                    debugDescription: "AnyCodable: cannot encode value"
                )
            )
        }
    }

    static func == (lhs: AnyCodable, rhs: AnyCodable) -> Bool {
        switch (lhs.value, rhs.value) {
        case (nil, nil): return true
        case let (l as Bool, r as Bool): return l == r
        case let (l as Int, r as Int): return l == r
        case let (l as Double, r as Double): return l == r
        case let (l as String, r as String): return l == r
        case let (l as [Any?], r as [Any?]):
            return l.map(AnyCodable.init) == r.map(AnyCodable.init)
        case let (l as [String: Any?], r as [String: Any?]):
            return l.mapValues(AnyCodable.init) == r.mapValues(AnyCodable.init)
        default: return false
        }
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run the `AnyCodableTests` target. Expected: PASS, 5 tests.

- [ ] **Step 5: Commit**

```bash
git add apps/ios/Cawnex/Cawnex/Cawnex/Core/Network/AnyCodable.swift apps/ios/Cawnex/Cawnex/CawnexTests/Core/Network/AnyCodableTests.swift
git commit -m "feat(ios): AnyCodable shim for heterogeneous JSON values"
```

### Task 10: Domain models for Council Session

**Files:**
- Create: `apps/ios/Cawnex/Cawnex/Cawnex/Features/WaveReview/WaveReviewModels.swift`

- [ ] **Step 1: Create the file with all domain models**

```swift
// apps/ios/Cawnex/Cawnex/Cawnex/Features/WaveReview/WaveReviewModels.swift
import Foundation
import SwiftUI

// MARK: - Session

struct CouncilSession: Equatable, Codable {
    let sessionId: String
    let waveId: String
    let projectId: String
    let status: CouncilSessionStatus
    let integrationSK: String
    let createdAt: Date
    let completedAt: Date?
    let decision: CouncilDecision?
    let rounds: [VotingRound]
    let cost: AdvisorCost?
    let pipelineHealth: PipelineHealth

    enum CodingKeys: String, CodingKey {
        case sessionId = "session_id"
        case waveId = "wave_id"
        case projectId = "project_id"
        case status
        case integrationSK = "integration_sk"
        case createdAt = "created_at"
        case completedAt = "completed_at"
        case decision
        case rounds
        case cost
        case pipelineHealth = "pipeline_health"
    }
}

enum CouncilSessionStatus: String, Codable {
    case pending, running, completed, errored
}

enum PipelineHealth: String, Codable {
    case ok, degraded
}

// MARK: - Decision

struct CouncilDecision: Equatable, Codable {
    let action: DecisionAction
    let reasoning: String
    let confidence: Double
    let conditions: [String]
    let orderingConstraints: [String]
    let dissentRecord: [String: String]

    enum CodingKeys: String, CodingKey {
        case action, reasoning, confidence, conditions
        case orderingConstraints = "ordering_constraints"
        case dissentRecord = "dissent_record"
    }
}

enum DecisionAction: String, Codable {
    case approve
    case approveWithConditions = "approve_with_conditions"
    case reject
    case escalate
}

// MARK: - Rounds and votes

struct VotingRound: Equatable, Codable {
    let roundNumber: Int
    let votes: [AdvisorVote]
    let consensus: Bool
    let question: String?

    enum CodingKeys: String, CodingKey {
        case roundNumber = "round_number"
        case votes, consensus, question
    }
}

struct AdvisorVote: Equatable, Codable, Identifiable {
    var id: String { advisor.rawValue }
    let advisor: AdvisorType
    let vote: VoteType
    let reasoning: String
    let confidence: Double
    let blockers: [String]
    let condition: String?
    let citedEvidence: [CitedEvidence]
    let investigationTrace: [ToolCall]
    let cost: AdvisorCost?

    enum CodingKeys: String, CodingKey {
        case advisor, vote, reasoning, confidence, blockers, condition, cost
        case citedEvidence = "cited_evidence"
        case investigationTrace = "investigation_trace"
    }
}

enum AdvisorType: String, Codable, CaseIterable {
    case security, architecture, clarity, performance, ux, cost
}

enum VoteType: String, Codable {
    case approve
    case approveWithCondition = "approve_with_condition"
    case abstain
    case block
}

// MARK: - Evidence and trace

struct CitedEvidence: Equatable, Codable, Identifiable {
    var id: String { "\(filePath):\(lineRange?.first ?? 0)" }
    let filePath: String
    let lineRange: [Int]?
    let prNumber: Int?
    let reason: String

    enum CodingKeys: String, CodingKey {
        case filePath = "file_path"
        case lineRange = "line_range"
        case prNumber = "pr_number"
        case reason
    }
}

struct ToolCall: Equatable, Codable, Identifiable {
    var id = UUID()
    let toolName: String
    let args: [String: AnyCodable]
    let resultSummary: String
    let durationMs: Int
    let error: String?

    enum CodingKeys: String, CodingKey {
        case toolName = "tool_name"
        case args
        case resultSummary = "result_summary"
        case durationMs = "duration_ms"
        case error
    }
}

struct AdvisorCost: Equatable, Codable {
    let tokensIn: Int
    let tokensOut: Int
    let durationMs: Int

    enum CodingKeys: String, CodingKey {
        case tokensIn = "tokens_in"
        case tokensOut = "tokens_out"
        case durationMs = "duration_ms"
    }
}

// MARK: - Display extensions

extension VoteType {
    var chipColor: Color {
        switch self {
        case .approve: CawnexColors.success
        case .approveWithCondition: CawnexColors.warning
        case .abstain: CawnexColors.mutedForeground
        case .block: CawnexColors.destructive
        }
    }

    var chipLabel: String {
        switch self {
        case .approve: "Approve"
        case .approveWithCondition: "Approve w/ condition"
        case .abstain: "Abstained"
        case .block: "Block (Veto)"
        }
    }
}

extension AdvisorType {
    var displayName: String {
        switch self {
        case .security: "Security"
        case .architecture: "Architecture"
        case .clarity: "Clarity"
        case .performance: "Performance"
        case .ux: "UX"
        case .cost: "Cost"
        }
    }

    var iconName: String {
        switch self {
        case .security: "shield.checkered"
        case .architecture: "square.stack.3d.up"
        case .clarity: "eye"
        case .performance: "gauge.medium"
        case .ux: "iphone"
        case .cost: "creditcard"
        }
    }

    var hasVeto: Bool { self == .security || self == .clarity }
}

extension DecisionAction {
    var displayLabel: String {
        switch self {
        case .approve: "Approve"
        case .approveWithConditions: "Approve with conditions"
        case .reject: "Reject"
        case .escalate: "Escalate"
        }
    }

    var displayColor: Color {
        switch self {
        case .approve: CawnexColors.success
        case .approveWithConditions: CawnexColors.warning
        case .reject, .escalate: CawnexColors.destructive
        }
    }
}
```

- [ ] **Step 2: Verify the file builds**

In Xcode, build the Cawnex target (Cmd-B). Expected: clean build (no compile errors).

If `CawnexColors.mutedForeground` doesn't exist, replace with the closest existing token (likely `CawnexColors.muted` or `Color.secondary`). Inspect `apps/ios/Cawnex/Cawnex/Cawnex/Core/Theme/CawnexColors.swift` to confirm available tokens.

- [ ] **Step 3: Commit**

```bash
git add apps/ios/Cawnex/Cawnex/Cawnex/Features/WaveReview/WaveReviewModels.swift
git commit -m "feat(ios): domain models for Council wave review"
```

### Task 11: Copy fixtures into iOS test bundle + decoding tests

**Files:**
- Create: `apps/ios/Cawnex/CawnexTests/Contracts/Fixtures/council_session_completed.json`
- Create: `apps/ios/Cawnex/CawnexTests/Contracts/Fixtures/council_session_pending.json`
- Create: `apps/ios/Cawnex/CawnexTests/Contracts/Fixtures/council_session_errored.json`
- Create: `apps/ios/Cawnex/CawnexTests/Features/WaveReview/CouncilSessionDecodingTests.swift`

- [ ] **Step 1: Copy fixtures from the backend test bundle**

```bash
mkdir -p apps/ios/Cawnex/CawnexTests/Contracts/Fixtures
cp apps/api/tests/fixtures/council_session_completed.json apps/ios/Cawnex/CawnexTests/Contracts/Fixtures/
cp apps/api/tests/fixtures/council_session_pending.json apps/ios/Cawnex/CawnexTests/Contracts/Fixtures/
cp apps/api/tests/fixtures/council_session_errored.json apps/ios/Cawnex/CawnexTests/Contracts/Fixtures/
```

- [ ] **Step 2: Add the fixtures to the CawnexTests Xcode target**

Open the Cawnex.xcodeproj in Xcode. Drag the three JSON files into the `CawnexTests/Contracts/Fixtures` group. In the Add Files dialog, check **Copy items if needed** = NO (files are already in place), **Add to targets** = CawnexTests only.

- [ ] **Step 3: Write the failing decoding tests**

```swift
// apps/ios/Cawnex/Cawnex/CawnexTests/Features/WaveReview/CouncilSessionDecodingTests.swift
import XCTest
@testable import Cawnex

final class CouncilSessionDecodingTests: XCTestCase {
    private static func loadFixture(_ name: String) throws -> Data {
        let bundle = Bundle(for: CouncilSessionDecodingTests.self)
        let url = bundle.url(forResource: name, withExtension: "json")!
        return try Data(contentsOf: url)
    }

    private static func decoder() -> JSONDecoder {
        let d = JSONDecoder()
        let formatter = ISO8601DateFormatter()
        d.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let str = try container.decode(String.self)
            guard let date = formatter.date(from: str) else {
                throw DecodingError.dataCorruptedError(
                    in: container,
                    debugDescription: "Bad ISO8601 date: \(str)"
                )
            }
            return date
        }
        return d
    }

    func test_decodes_completed_session_with_all_advisors() throws {
        let data = try Self.loadFixture("council_session_completed")
        let session = try Self.decoder().decode(CouncilSession.self, from: data)
        XCTAssertEqual(session.status, .completed)
        XCTAssertEqual(session.decision?.action, .approve)
        XCTAssertEqual(session.rounds.count, 1)
        XCTAssertEqual(session.rounds[0].votes.count, 6)
        XCTAssertEqual(session.pipelineHealth, .ok)
        let advisors = Set(session.rounds[0].votes.map(\.advisor))
        XCTAssertEqual(advisors, Set(AdvisorType.allCases))
    }

    func test_decodes_pending_session_with_null_decision() throws {
        let data = try Self.loadFixture("council_session_pending")
        let session = try Self.decoder().decode(CouncilSession.self, from: data)
        XCTAssertEqual(session.status, .pending)
        XCTAssertNil(session.decision)
        XCTAssertTrue(session.rounds.isEmpty)
    }

    func test_decodes_errored_session_with_degraded_health() throws {
        let data = try Self.loadFixture("council_session_errored")
        let session = try Self.decoder().decode(CouncilSession.self, from: data)
        XCTAssertEqual(session.status, .errored)
        XCTAssertEqual(session.pipelineHealth, .degraded)
        XCTAssertNil(session.decision)
    }

    func test_decodes_approve_with_condition_vote() throws {
        let data = try Self.loadFixture("council_session_completed")
        let session = try Self.decoder().decode(CouncilSession.self, from: data)
        let perf = session.rounds[0].votes.first(where: { $0.advisor == .performance })!
        XCTAssertEqual(perf.vote, .approveWithCondition)
        XCTAssertNotNil(perf.condition)
    }

    func test_decodes_cited_evidence_and_investigation_trace() throws {
        let data = try Self.loadFixture("council_session_completed")
        let session = try Self.decoder().decode(CouncilSession.self, from: data)
        let security = session.rounds[0].votes.first(where: { $0.advisor == .security })!
        XCTAssertEqual(security.citedEvidence.first?.filePath, "apps/api/foo.py")
        XCTAssertEqual(security.citedEvidence.first?.lineRange, [42, 58])
        XCTAssertEqual(security.investigationTrace.first?.toolName, "read_file")
        XCTAssertEqual(
            security.investigationTrace.first?.args["path"]?.value as? String,
            "apps/api/foo.py"
        )
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run the `CouncilSessionDecodingTests` target. Expected: PASS, 5 tests.

- [ ] **Step 5: Commit**

```bash
git add apps/ios/Cawnex/CawnexTests/Contracts/Fixtures/ apps/ios/Cawnex/CawnexTests/Features/WaveReview/CouncilSessionDecodingTests.swift apps/ios/Cawnex/Cawnex.xcodeproj/
git commit -m "test(ios): contract decoding tests for CouncilSession + fixtures"
```

### Task 12: Service protocol + InMemory implementation

**Files:**
- Create: `apps/ios/Cawnex/Cawnex/Cawnex/Features/WaveReview/WaveReviewService.swift`
- Create: `apps/ios/Cawnex/Cawnex/Cawnex/Features/WaveReview/InMemoryWaveReviewService.swift`

- [ ] **Step 1: Define the protocol**

```swift
// apps/ios/Cawnex/Cawnex/Cawnex/Features/WaveReview/WaveReviewService.swift
import Foundation

/// Contract for fetching Council sessions and triggering wave-level actions.
/// API and InMemory implementations both conform to this so views/ViewModels
/// stay swap-agnostic.
protocol WaveReviewService {
    /// Fetch the Council session for a wave. Always returns 200 on the
    /// backend regardless of status; iOS branches on session.status.
    func fetchSession(
        projectId: String, sessionId: String
    ) async throws -> CouncilSession

    /// Approve the entire wave: flips status under_human_review -> delivered
    /// and merges every PR attached to a ready_to_ship MVI in the wave.
    func approveWave(projectId: String, waveId: String) async throws

    /// Reject the wave: maps to existing wave cancel + writes the reason
    /// to the wave's rework_reasons for the next planning pass.
    func rejectWave(projectId: String, waveId: String, reason: String) async throws
}
```

- [ ] **Step 2: Define the InMemory implementation**

```swift
// apps/ios/Cawnex/Cawnex/Cawnex/Features/WaveReview/InMemoryWaveReviewService.swift
import Foundation

/// Seed-data implementation for previews + UI tests. Holds sessions in
/// memory keyed by sessionId; approve/reject mutate the local state.
final class InMemoryWaveReviewService: WaveReviewService {
    private var sessions: [String: CouncilSession] = [:]
    private(set) var approvedWaves: [String] = []
    private(set) var rejectedWaves: [(waveId: String, reason: String)] = []

    init(seed: [CouncilSession] = []) {
        for s in seed { sessions[s.sessionId] = s }
    }

    func fetchSession(
        projectId: String, sessionId: String
    ) async throws -> CouncilSession {
        guard let session = sessions[sessionId] else {
            throw WaveReviewError.notFound(sessionId: sessionId)
        }
        return session
    }

    func approveWave(projectId: String, waveId: String) async throws {
        approvedWaves.append(waveId)
    }

    func rejectWave(projectId: String, waveId: String, reason: String) async throws {
        rejectedWaves.append((waveId, reason))
    }
}

enum WaveReviewError: Error, Equatable {
    case notFound(sessionId: String)
    case networkFailure(message: String)
    case approveFailed(detail: String)
    case rejectFailed(detail: String)
    case pollingTimeout
}
```

- [ ] **Step 3: Verify build**

In Xcode build the Cawnex target. Expected: clean build.

- [ ] **Step 4: Commit**

```bash
git add apps/ios/Cawnex/Cawnex/Cawnex/Features/WaveReview/WaveReviewService.swift apps/ios/Cawnex/Cawnex/Cawnex/Features/WaveReview/InMemoryWaveReviewService.swift
git commit -m "feat(ios): WaveReviewService protocol + InMemory implementation"
```

### Task 13: API implementation calling the M1 endpoints

**Files:**
- Create: `apps/ios/Cawnex/Cawnex/Cawnex/Features/WaveReview/APIWaveReviewService.swift`

- [ ] **Step 1: Inspect existing API service conventions**

```bash
grep -n "URLSession\|authToken\|baseURL\|APIPRService\|async throws" apps/ios/Cawnex/Cawnex/Cawnex/Core/Network/APIPRService.swift | head -15
```

Note the existing pattern for: base URL injection, auth header construction, JSONDecoder configuration. The new service must mirror it.

- [ ] **Step 2: Write the API service**

```swift
// apps/ios/Cawnex/Cawnex/Cawnex/Features/WaveReview/APIWaveReviewService.swift
import Foundation

/// REST implementation: calls the backend GET council session +
/// POST wave approve/cancel endpoints. The wave cancel path maps to
/// the "reject" action per Layer B spec.
final class APIWaveReviewService: WaveReviewService {
    private let baseURL: URL
    private let session: URLSession
    private let authTokenProvider: () -> String?

    init(
        baseURL: URL,
        session: URLSession = .shared,
        authTokenProvider: @escaping () -> String?
    ) {
        self.baseURL = baseURL
        self.session = session
        self.authTokenProvider = authTokenProvider
    }

    func fetchSession(
        projectId: String, sessionId: String
    ) async throws -> CouncilSession {
        let url = baseURL
            .appendingPathComponent("projects")
            .appendingPathComponent(projectId)
            .appendingPathComponent("council/sessions")
            .appendingPathComponent(sessionId)

        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        if let token = authTokenProvider() {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        let (data, response) = try await session.data(for: request)
        try Self.validate(response: response, data: data, sessionId: sessionId)
        return try Self.decoder().decode(CouncilSession.self, from: data)
    }

    func approveWave(projectId: String, waveId: String) async throws {
        let url = baseURL
            .appendingPathComponent("projects")
            .appendingPathComponent(projectId)
            .appendingPathComponent("waves")
            .appendingPathComponent(waveId)
            .appendingPathComponent("approve")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        if let token = authTokenProvider() {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        let (data, response) = try await session.data(for: request)
        if let http = response as? HTTPURLResponse, http.statusCode >= 400 {
            let detail = String(data: data, encoding: .utf8) ?? "approve failed"
            throw WaveReviewError.approveFailed(detail: detail)
        }
    }

    func rejectWave(projectId: String, waveId: String, reason: String) async throws {
        // Reject maps to wave cancel + reason written into wave metadata.
        let url = baseURL
            .appendingPathComponent("projects")
            .appendingPathComponent(projectId)
            .appendingPathComponent("waves")
            .appendingPathComponent(waveId)
            .appendingPathComponent("cancel")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        if let token = authTokenProvider() {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(["reason": reason])

        let (data, response) = try await session.data(for: request)
        if let http = response as? HTTPURLResponse, http.statusCode >= 400 {
            let detail = String(data: data, encoding: .utf8) ?? "reject failed"
            throw WaveReviewError.rejectFailed(detail: detail)
        }
    }

    // MARK: - Helpers

    private static func validate(
        response: URLResponse, data: Data, sessionId: String
    ) throws {
        guard let http = response as? HTTPURLResponse else {
            throw WaveReviewError.networkFailure(message: "no HTTP response")
        }
        switch http.statusCode {
        case 200: return
        case 404: throw WaveReviewError.notFound(sessionId: sessionId)
        default:
            let body = String(data: data, encoding: .utf8) ?? ""
            throw WaveReviewError.networkFailure(
                message: "HTTP \(http.statusCode): \(body.prefix(200))"
            )
        }
    }

    private static func decoder() -> JSONDecoder {
        let d = JSONDecoder()
        let formatter = ISO8601DateFormatter()
        d.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let str = try container.decode(String.self)
            guard let date = formatter.date(from: str) else {
                throw DecodingError.dataCorruptedError(
                    in: container,
                    debugDescription: "Bad ISO8601 date: \(str)"
                )
            }
            return date
        }
        return d
    }
}
```

- [ ] **Step 3: Verify build**

In Xcode build the Cawnex target. Expected: clean build.

- [ ] **Step 4: Commit**

```bash
git add apps/ios/Cawnex/Cawnex/Cawnex/Features/WaveReview/APIWaveReviewService.swift
git commit -m "feat(ios): APIWaveReviewService — GET session + POST approve/reject"
```

---

## Milestone M3 — iOS UI layer (ViewModel + Screens + UI tests + S32 touchup + smoke runbook) (~1 day)

**M3 outcome:** Wave Review screen renders all 6 advisor cards with cited evidence inline. Tap any advisor → Investigation Trace screen with full timeline. Approve / Reject confirmation sheets. Polling for pending sessions with 5-minute timeout. MVI Blackboard shows "Council Review Ready" card when wave is `under_human_review`. UI tests pass via InMemory service.

### Task 14: ViewModel with state transitions + polling

**Files:**
- Create: `apps/ios/Cawnex/Cawnex/Cawnex/Features/WaveReview/WaveReviewViewModel.swift`
- Create: `apps/ios/Cawnex/Cawnex/CawnexTests/Features/WaveReview/WaveReviewViewModelTests.swift`

- [ ] **Step 1: Write the failing tests**

```swift
// apps/ios/Cawnex/Cawnex/CawnexTests/Features/WaveReview/WaveReviewViewModelTests.swift
import XCTest
@testable import Cawnex

@MainActor
final class WaveReviewViewModelTests: XCTestCase {
    private func loadCompletedSession() throws -> CouncilSession {
        let bundle = Bundle(for: Self.self)
        let url = bundle.url(
            forResource: "council_session_completed", withExtension: "json"
        )!
        let data = try Data(contentsOf: url)
        let d = JSONDecoder()
        let formatter = ISO8601DateFormatter()
        d.dateDecodingStrategy = .custom { decoder in
            let c = try decoder.singleValueContainer()
            let s = try c.decode(String.self)
            return formatter.date(from: s) ?? Date()
        }
        return try d.decode(CouncilSession.self, from: data)
    }

    func test_load_happy_path_transitions_idle_loading_loaded() async throws {
        let session = try loadCompletedSession()
        let service = InMemoryWaveReviewService(seed: [session])
        let vm = WaveReviewViewModel(service: service)
        XCTAssertEqual(vm.state, .idle)
        await vm.load(projectId: "p1", sessionId: session.sessionId)
        guard case .loaded(let loaded) = vm.state else {
            return XCTFail("Expected .loaded, got \(vm.state)")
        }
        XCTAssertEqual(loaded.status, .completed)
    }

    func test_load_missing_session_transitions_to_error() async {
        let service = InMemoryWaveReviewService(seed: [])
        let vm = WaveReviewViewModel(service: service)
        await vm.load(projectId: "p1", sessionId: "does-not-exist")
        guard case .error = vm.state else {
            return XCTFail("Expected .error, got \(vm.state)")
        }
    }

    func test_approve_success_transitions_to_actionSucceeded() async throws {
        let session = try loadCompletedSession()
        let service = InMemoryWaveReviewService(seed: [session])
        let vm = WaveReviewViewModel(service: service)
        await vm.load(projectId: "p1", sessionId: session.sessionId)
        await vm.approve(projectId: "p1", waveId: "w1")
        guard case .actionSucceeded(let action) = vm.state else {
            return XCTFail("Expected .actionSucceeded, got \(vm.state)")
        }
        XCTAssertEqual(action, .approved)
        XCTAssertEqual(service.approvedWaves, ["w1"])
    }

    func test_reject_writes_reason() async throws {
        let session = try loadCompletedSession()
        let service = InMemoryWaveReviewService(seed: [session])
        let vm = WaveReviewViewModel(service: service)
        await vm.load(projectId: "p1", sessionId: session.sessionId)
        await vm.reject(projectId: "p1", waveId: "w1", reason: "scope creep")
        guard case .actionSucceeded(let action) = vm.state else {
            return XCTFail("Expected .actionSucceeded, got \(vm.state)")
        }
        XCTAssertEqual(action, .rejected)
        XCTAssertEqual(service.rejectedWaves.first?.reason, "scope creep")
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run the `WaveReviewViewModelTests` target. Expected: FAIL — ViewModel doesn't exist.

- [ ] **Step 3: Write the ViewModel**

```swift
// apps/ios/Cawnex/Cawnex/Cawnex/Features/WaveReview/WaveReviewViewModel.swift
import Foundation
import Observation

@MainActor
@Observable
final class WaveReviewViewModel {
    enum State: Equatable {
        case idle
        case loading
        case loaded(CouncilSession)
        case actionPending(SubmittedAction)
        case actionSucceeded(SubmittedAction)
        case actionFailed(SubmittedAction, message: String)
        case error(message: String)
    }

    enum SubmittedAction: Equatable {
        case approved, rejected
    }

    var state: State = .idle

    private let service: WaveReviewService
    private var pollingTask: Task<Void, Never>?
    private let pollIntervalSeconds: UInt64 = 5
    private let pollTimeoutSeconds: TimeInterval = 300  // 5 min

    init(service: WaveReviewService) {
        self.service = service
    }

    deinit {
        pollingTask?.cancel()
    }

    func load(projectId: String, sessionId: String) async {
        state = .loading
        do {
            let session = try await service.fetchSession(
                projectId: projectId, sessionId: sessionId
            )
            state = .loaded(session)
            if session.status == .pending || session.status == .running {
                startPolling(projectId: projectId, sessionId: sessionId)
            }
        } catch WaveReviewError.notFound(let id) {
            state = .error(message: "Council session \(id) not found")
        } catch {
            state = .error(message: error.localizedDescription)
        }
    }

    func approve(projectId: String, waveId: String) async {
        state = .actionPending(.approved)
        do {
            try await service.approveWave(projectId: projectId, waveId: waveId)
            state = .actionSucceeded(.approved)
        } catch {
            state = .actionFailed(.approved, message: error.localizedDescription)
        }
    }

    func reject(projectId: String, waveId: String, reason: String) async {
        state = .actionPending(.rejected)
        do {
            try await service.rejectWave(
                projectId: projectId, waveId: waveId, reason: reason
            )
            state = .actionSucceeded(.rejected)
        } catch {
            state = .actionFailed(.rejected, message: error.localizedDescription)
        }
    }

    func cancelPolling() {
        pollingTask?.cancel()
        pollingTask = nil
    }

    // MARK: - Polling

    private func startPolling(projectId: String, sessionId: String) {
        pollingTask?.cancel()
        let start = Date()
        pollingTask = Task { [weak self] in
            guard let self else { return }
            while !Task.isCancelled {
                try? await Task.sleep(
                    nanoseconds: self.pollIntervalSeconds * 1_000_000_000
                )
                if Task.isCancelled { return }
                if Date().timeIntervalSince(start) > self.pollTimeoutSeconds {
                    await MainActor.run {
                        self.state = .error(
                            message: "Council pipeline appears stuck — founder must decide manually"
                        )
                    }
                    return
                }
                do {
                    let refreshed = try await self.service.fetchSession(
                        projectId: projectId, sessionId: sessionId
                    )
                    await MainActor.run { self.state = .loaded(refreshed) }
                    if refreshed.status == .completed
                        || refreshed.status == .errored
                    {
                        return
                    }
                } catch {
                    // Transient errors don't kill the polling loop;
                    // the screen keeps the last-known state.
                }
            }
        }
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run the `WaveReviewViewModelTests` target. Expected: PASS, 4 tests.

- [ ] **Step 5: Commit**

```bash
git add apps/ios/Cawnex/Cawnex/Cawnex/Features/WaveReview/WaveReviewViewModel.swift apps/ios/Cawnex/Cawnex/CawnexTests/Features/WaveReview/WaveReviewViewModelTests.swift
git commit -m "feat(ios): WaveReviewViewModel with state transitions + 5min polling timeout"
```

### Task 15: Component — CitedEvidenceRow

**Files:**
- Create: `apps/ios/Cawnex/Cawnex/Cawnex/Features/WaveReview/Components/CitedEvidenceRow.swift`

- [ ] **Step 1: Implement the component**

```swift
// apps/ios/Cawnex/Cawnex/Cawnex/Features/WaveReview/Components/CitedEvidenceRow.swift
import SwiftUI

/// Single file:line row inside an AdvisorCard. Renders the file path,
/// optional line range, optional PR number, and a one-line reason.
struct CitedEvidenceRow: View {
    let evidence: CitedEvidence

    var body: some View {
        HStack(alignment: .top, spacing: 6) {
            Image(systemName: "doc.text")
                .font(.caption2)
                .foregroundStyle(CawnexColors.mutedForeground)
            Text(label)
                .font(.caption)
                .foregroundStyle(CawnexColors.cardForeground)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private var label: String {
        var parts: [String] = [evidence.filePath]
        if let lines = evidence.lineRange, lines.count == 2 {
            parts[0] += ":\(lines[0])-\(lines[1])"
        }
        if !evidence.reason.isEmpty {
            parts.append("— \(evidence.reason)")
        }
        return parts.joined(separator: " ")
    }
}

#Preview {
    VStack(spacing: 8) {
        CitedEvidenceRow(evidence: CitedEvidence(
            filePath: "apps/api/foo.py",
            lineRange: [42, 58],
            prNumber: 42,
            reason: "tenant_id filter present"
        ))
        CitedEvidenceRow(evidence: CitedEvidence(
            filePath: "apps/ios/Cawnex/Cawnex/Features/PR/PRReviewScreen.swift",
            lineRange: nil,
            prNumber: nil,
            reason: "accessibility id missing"
        ))
    }
    .padding()
    .background(CawnexColors.card)
}
```

- [ ] **Step 2: Verify the preview renders**

In Xcode, open `CitedEvidenceRow.swift`, switch to canvas view, verify the preview renders both rows without compile errors.

- [ ] **Step 3: Commit**

```bash
git add apps/ios/Cawnex/Cawnex/Cawnex/Features/WaveReview/Components/CitedEvidenceRow.swift
git commit -m "feat(ios): CitedEvidenceRow component for advisor card evidence"
```

### Task 16: Component — AdvisorCard

**Files:**
- Create: `apps/ios/Cawnex/Cawnex/Cawnex/Features/WaveReview/Components/AdvisorCard.swift`

Matches the Pencil S35 advisor card layout: icon wrap + name (+ VETO badge for security/clarity) + vote chip + reasoning + cited evidence inline + "View investigation" affordance.

- [ ] **Step 1: Implement the component**

```swift
// apps/ios/Cawnex/Cawnex/Cawnex/Features/WaveReview/Components/AdvisorCard.swift
import SwiftUI

struct AdvisorCard: View {
    let vote: AdvisorVote
    let onViewInvestigation: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            // Top row: icon + name (+ VETO badge) + vote chip
            HStack(alignment: .center, spacing: 10) {
                ZStack {
                    Circle()
                        .fill(iconBackground)
                        .frame(width: 28, height: 28)
                    Image(systemName: vote.advisor.iconName)
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundStyle(iconColor)
                }
                VStack(alignment: .leading, spacing: 2) {
                    HStack(spacing: 6) {
                        Text(vote.advisor.displayName)
                            .font(.system(size: 14, weight: .semibold))
                            .foregroundStyle(CawnexColors.cardForeground)
                        if vote.advisor.hasVeto {
                            vetoBadge
                        }
                    }
                    Text(subtitle)
                        .font(.caption2)
                        .foregroundStyle(CawnexColors.mutedForeground)
                }
                Spacer()
                voteChip
            }

            // Reasoning text
            Text(vote.reasoning)
                .font(.system(size: 13))
                .lineSpacing(2)
                .foregroundStyle(CawnexColors.cardForeground)
                .frame(maxWidth: .infinity, alignment: .leading)

            // Cited evidence (inline, hidden if empty)
            if !vote.citedEvidence.isEmpty {
                VStack(alignment: .leading, spacing: 6) {
                    ForEach(vote.citedEvidence) { e in
                        CitedEvidenceRow(evidence: e)
                    }
                }
                .padding(.horizontal, 10)
                .padding(.vertical, 8)
                .background(CawnexColors.muted)
                .clipShape(RoundedRectangle(cornerRadius: 4))
            }

            // Veto blockers (only shown when vote == block)
            if vote.vote == .block && !vote.blockers.isEmpty {
                VStack(alignment: .leading, spacing: 4) {
                    ForEach(vote.blockers, id: \.self) { b in
                        Text("• \(b)")
                            .font(.caption)
                            .foregroundStyle(CawnexColors.destructive)
                    }
                }
            }

            // View investigation affordance (hidden when trace is empty)
            if !vote.investigationTrace.isEmpty {
                HStack {
                    Spacer()
                    Button(action: onViewInvestigation) {
                        HStack(spacing: 4) {
                            Text("View investigation")
                                .font(.system(size: 12, weight: .semibold))
                            Image(systemName: "chevron.right")
                                .font(.caption2)
                        }
                        .foregroundStyle(CawnexColors.primary)
                    }
                    .accessibilityIdentifier(
                        "wave-review.advisor.\(vote.advisor.rawValue).view-trace"
                    )
                }
            }
        }
        .padding(14)
        .background(CawnexColors.card)
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(borderColor, lineWidth: vote.vote == .block ? 1.5 : 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .accessibilityIdentifier("wave-review.advisor.\(vote.advisor.rawValue)")
    }

    // MARK: - Derived

    private var subtitle: String {
        let calls = vote.investigationTrace.count
        let conf = String(format: "%.2f", vote.confidence)
        return "\(calls) tool calls · \(conf) conf"
    }

    private var voteChip: some View {
        Text(vote.vote.chipLabel)
            .font(.system(size: 11, weight: .semibold))
            .foregroundStyle(vote.vote.chipColor)
            .padding(.horizontal, 10)
            .padding(.vertical, 4)
            .background(vote.vote.chipColor.opacity(0.13))
            .clipShape(Capsule())
    }

    private var vetoBadge: some View {
        Text("VETO")
            .font(.system(size: 9, weight: .bold))
            .tracking(0.5)
            .foregroundStyle(CawnexColors.primary)
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(CawnexColors.primary.opacity(0.13))
            .clipShape(RoundedRectangle(cornerRadius: 4))
    }

    private var iconColor: Color {
        switch vote.advisor {
        case .security, .clarity: CawnexColors.primary
        case .architecture: CawnexColors.info
        case .performance: CawnexColors.warning
        case .ux: CawnexColors.info
        case .cost: CawnexColors.success
        }
    }

    private var iconBackground: Color { iconColor.opacity(0.13) }

    private var borderColor: Color {
        vote.vote == .block ? CawnexColors.destructive : CawnexColors.border
    }
}
```

- [ ] **Step 2: Verify build**

Build the Cawnex target. Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add apps/ios/Cawnex/Cawnex/Cawnex/Features/WaveReview/Components/AdvisorCard.swift
git commit -m "feat(ios): AdvisorCard component with vote chip, inline evidence, veto styling"
```

### Task 17: Component — CouncilHeaderCard

**Files:**
- Create: `apps/ios/Cawnex/Cawnex/Cawnex/Features/WaveReview/Components/CouncilHeaderCard.swift`

Matches the Pencil S35 Council Decision Card: shield icon + action chip + reasoning + 4-up stats (advisors / tool calls / vetoes / tokens).

- [ ] **Step 1: Implement the component**

```swift
// apps/ios/Cawnex/Cawnex/Cawnex/Features/WaveReview/Components/CouncilHeaderCard.swift
import SwiftUI

struct CouncilHeaderCard: View {
    let session: CouncilSession

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .center, spacing: 10) {
                ZStack {
                    Circle()
                        .fill(decisionColor.opacity(0.13))
                        .frame(width: 32, height: 32)
                    Image(systemName: decisionIcon)
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundStyle(decisionColor)
                }
                VStack(alignment: .leading, spacing: 2) {
                    Text("Council: \(decisionLabel)")
                        .font(.system(size: 15, weight: .semibold))
                        .foregroundStyle(decisionColor)
                    Text(metaLine)
                        .font(.caption2)
                        .foregroundStyle(CawnexColors.mutedForeground)
                }
                Spacer()
            }

            if let reasoning = session.decision?.reasoning, !reasoning.isEmpty {
                Text(reasoning)
                    .font(.system(size: 13))
                    .lineSpacing(2)
                    .foregroundStyle(CawnexColors.cardForeground)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }

            Divider().overlay(CawnexColors.border)

            HStack(alignment: .center) {
                statColumn(value: "\(allVotes.count)", label: "Advisors")
                Spacer()
                statColumn(value: "\(totalToolCalls)", label: "Tool calls")
                Spacer()
                statColumn(value: "\(vetoCount)", label: "Vetoes")
                Spacer()
                statColumn(value: tokenLabel, label: "Tokens")
            }
        }
        .padding(16)
        .background(CawnexColors.card)
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(decisionColor.opacity(0.27), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private func statColumn(value: String, label: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(value)
                .font(.system(size: 18, weight: .semibold))
                .foregroundStyle(CawnexColors.cardForeground)
            Text(label)
                .font(.caption2)
                .foregroundStyle(CawnexColors.mutedForeground)
        }
    }

    // MARK: - Derived

    private var allVotes: [AdvisorVote] {
        session.rounds.flatMap(\.votes)
    }

    private var totalToolCalls: Int {
        allVotes.reduce(0) { $0 + $1.investigationTrace.count }
    }

    private var vetoCount: Int {
        allVotes.filter { $0.advisor.hasVeto && $0.vote == .block }.count
    }

    private var tokenLabel: String {
        let total = (session.cost?.tokensIn ?? 0) + (session.cost?.tokensOut ?? 0)
        if total >= 1000 {
            return String(format: "%.1fK", Double(total) / 1000.0)
        }
        return "\(total)"
    }

    private var decisionLabel: String {
        session.decision?.action.displayLabel ?? "—"
    }

    private var decisionColor: Color {
        session.decision?.action.displayColor ?? CawnexColors.mutedForeground
    }

    private var decisionIcon: String {
        switch session.decision?.action {
        case .approve, .approveWithConditions: return "shield.checkered"
        case .reject: return "xmark.shield"
        case .escalate: return "exclamationmark.shield"
        case nil: return "questionmark.circle"
        }
    }

    private var metaLine: String {
        let voted = allVotes.count
        let rounds = session.rounds.count
        let conf = session.decision.map { String(format: "%.2f", $0.confidence) } ?? "—"
        return "\(voted)/6 voted · \(rounds) round\(rounds == 1 ? "" : "s") · \(conf) confidence"
    }
}
```

- [ ] **Step 2: Verify build**

Build the Cawnex target. Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add apps/ios/Cawnex/Cawnex/Cawnex/Features/WaveReview/Components/CouncilHeaderCard.swift
git commit -m "feat(ios): CouncilHeaderCard component for wave review screen"
```

### Task 18: WaveReviewScreen — top-level view

**Files:**
- Create: `apps/ios/Cawnex/Cawnex/Cawnex/Features/WaveReview/WaveReviewScreen.swift`

Matches Pencil S35: status bar → nav back → scroll content (header card + decision card + section label + 6 advisor cards) → action bar.

- [ ] **Step 1: Implement the screen**

```swift
// apps/ios/Cawnex/Cawnex/Cawnex/Features/WaveReview/WaveReviewScreen.swift
import SwiftUI

struct WaveReviewScreen: View {
    let projectId: String
    let waveId: String
    let sessionId: String
    @State var viewModel: WaveReviewViewModel
    @State private var showApproveConfirm = false
    @State private var showRejectSheet = false
    @State private var rejectReason = ""
    @State private var selectedAdvisor: AdvisorVote?
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(spacing: 0) {
            content
        }
        .navigationTitle("Wave Review")
        .navigationBarTitleDisplayMode(.inline)
        .navigationBarBackButtonHidden(false)
        .task {
            await viewModel.load(projectId: projectId, sessionId: sessionId)
        }
        .sheet(isPresented: $showApproveConfirm) {
            approveConfirmSheet
        }
        .sheet(isPresented: $showRejectSheet) {
            rejectSheet
        }
        .sheet(item: $selectedAdvisor) { vote in
            NavigationStack {
                InvestigationTraceScreen(vote: vote)
            }
        }
        .onChange(of: viewModel.state) { _, newState in
            if case .actionSucceeded = newState {
                dismiss()
            }
        }
    }

    @ViewBuilder
    private var content: some View {
        switch viewModel.state {
        case .idle, .loading:
            ProgressView().padding(.top, 60)
        case .error(let message):
            errorView(message: message)
        case .loaded(let session):
            loadedView(session: session)
        case .actionPending(let action):
            ProgressView("Submitting \(action == .approved ? "approve" : "reject")…")
        case .actionSucceeded:
            ProgressView()
        case .actionFailed(_, let message):
            errorView(message: message)
                .overlay(alignment: .top) {
                    Text("Action failed: \(message)")
                        .padding()
                        .background(CawnexColors.destructive.opacity(0.13))
                }
        }
    }

    private func errorView(message: String) -> some View {
        VStack(spacing: 16) {
            Image(systemName: "exclamationmark.triangle")
                .font(.largeTitle)
                .foregroundStyle(CawnexColors.warning)
            Text(message)
                .multilineTextAlignment(.center)
                .foregroundStyle(CawnexColors.cardForeground)
            Button("Retry") {
                Task { await viewModel.load(projectId: projectId, sessionId: sessionId) }
            }
            .buttonStyle(.borderedProminent)
        }
        .padding()
    }

    private func loadedView(session: CouncilSession) -> some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(spacing: 16) {
                    if session.status == .pending || session.status == .running {
                        pollingBanner(session: session)
                    }
                    CouncilHeaderCard(session: session)
                    Text("ADVISORS")
                        .font(.system(size: 11, weight: .semibold))
                        .tracking(0.8)
                        .foregroundStyle(CawnexColors.mutedForeground)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    ForEach(session.rounds.flatMap(\.votes)) { vote in
                        AdvisorCard(vote: vote) {
                            selectedAdvisor = vote
                        }
                    }
                }
                .padding(.horizontal, 20)
                .padding(.top, 12)
                .padding(.bottom, 20)
            }
            actionBar(session: session)
        }
    }

    private func pollingBanner(session: CouncilSession) -> some View {
        let voted = session.rounds.first?.votes.count ?? 0
        return HStack(spacing: 8) {
            ProgressView().scaleEffect(0.8)
            Text("Council is still investigating — \(voted) of 6 advisors voted")
                .font(.caption)
                .foregroundStyle(CawnexColors.mutedForeground)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func actionBar(session: CouncilSession) -> some View {
        VStack(spacing: 10) {
            Button {
                showApproveConfirm = true
            } label: {
                HStack(spacing: 8) {
                    Image(systemName: "checkmark")
                    Text("Approve & merge wave")
                }
                .font(.system(size: 15, weight: .semibold))
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .frame(height: 48)
                .background(CawnexColors.success)
                .clipShape(RoundedRectangle(cornerRadius: 8))
            }
            .accessibilityIdentifier("wave-review.approve")

            HStack(spacing: 10) {
                Button {
                    showRejectSheet = true
                } label: {
                    Label("Reject", systemImage: "xmark")
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(CawnexColors.destructive)
                        .frame(maxWidth: .infinity)
                        .frame(height: 40)
                        .background(CawnexColors.card)
                        .overlay(
                            RoundedRectangle(cornerRadius: 8)
                                .stroke(CawnexColors.border, lineWidth: 1)
                        )
                }
                .accessibilityIdentifier("wave-review.reject")

                Button {
                    // Open in GitHub — out of scope for Layer B
                } label: {
                    Label("Open in GitHub", systemImage: "arrow.up.right.square")
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(CawnexColors.cardForeground)
                        .frame(maxWidth: .infinity)
                        .frame(height: 40)
                        .background(CawnexColors.card)
                        .overlay(
                            RoundedRectangle(cornerRadius: 8)
                                .stroke(CawnexColors.border, lineWidth: 1)
                        )
                }
            }
        }
        .padding(.horizontal, 20)
        .padding(.top, 16)
        .padding(.bottom, 34)
        .background(CawnexColors.background)
    }

    private var approveConfirmSheet: some View {
        let session: CouncilSession? = {
            if case .loaded(let s) = viewModel.state { return s }
            return nil
        }()
        let mviCount = session.map { $0.rounds.flatMap(\.votes).count } ?? 0
        return VStack(spacing: 20) {
            Text("Approve & merge wave")
                .font(.headline)
            Text("Council voted \(session?.decision?.action.displayLabel ?? "—") with \(mviCount) advisors.")
                .multilineTextAlignment(.center)
                .foregroundStyle(CawnexColors.cardForeground)
            Button("Approve & Merge") {
                Task {
                    await viewModel.approve(projectId: projectId, waveId: waveId)
                    showApproveConfirm = false
                }
            }
            .accessibilityIdentifier("wave-review.confirm-approve")
            .buttonStyle(.borderedProminent)
            Button("Cancel") { showApproveConfirm = false }
        }
        .padding(24)
        .presentationDetents([.medium])
    }

    private var rejectSheet: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Reject Wave")
                .font(.headline)
            Text("Reason (required — feeds back into the next planning pass)")
                .font(.caption)
                .foregroundStyle(CawnexColors.mutedForeground)
            TextField("Why is this wave not shippable?", text: $rejectReason, axis: .vertical)
                .lineLimit(3...6)
                .textFieldStyle(.roundedBorder)
                .accessibilityIdentifier("wave-review.reject-reason-field")
            HStack {
                Button("Cancel") {
                    showRejectSheet = false
                    rejectReason = ""
                }
                Spacer()
                Button("Reject Wave") {
                    Task {
                        await viewModel.reject(
                            projectId: projectId, waveId: waveId, reason: rejectReason
                        )
                        showRejectSheet = false
                    }
                }
                .accessibilityIdentifier("wave-review.confirm-reject")
                .disabled(rejectReason.trimmingCharacters(in: .whitespaces).isEmpty)
                .buttonStyle(.borderedProminent)
                .tint(CawnexColors.destructive)
            }
        }
        .padding(24)
        .presentationDetents([.medium])
    }
}
```

- [ ] **Step 2: Verify build**

Build the Cawnex target. Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add apps/ios/Cawnex/Cawnex/Cawnex/Features/WaveReview/WaveReviewScreen.swift
git commit -m "feat(ios): WaveReviewScreen — top-level screen with action bar + sheets"
```

### Task 19: InvestigationTraceScreen — drill-in

**Files:**
- Create: `apps/ios/Cawnex/Cawnex/Cawnex/Features/WaveReview/InvestigationTraceScreen.swift`

Matches Pencil S36: status bar → nav back ("Security · Investigation") → advisor header + stats → tool-call timeline rows.

- [ ] **Step 1: Implement the screen**

```swift
// apps/ios/Cawnex/Cawnex/Cawnex/Features/WaveReview/InvestigationTraceScreen.swift
import SwiftUI

struct InvestigationTraceScreen: View {
    let vote: AdvisorVote

    var body: some View {
        ScrollView {
            VStack(spacing: 14) {
                advisorHeader
                Text("INVESTIGATION TIMELINE")
                    .font(.system(size: 11, weight: .semibold))
                    .tracking(0.8)
                    .foregroundStyle(CawnexColors.mutedForeground)
                    .frame(maxWidth: .infinity, alignment: .leading)

                if vote.investigationTrace.isEmpty {
                    Text("Advisor submitted vote without calling any tools.")
                        .font(.caption)
                        .foregroundStyle(CawnexColors.mutedForeground)
                        .padding()
                        .frame(maxWidth: .infinity)
                        .background(CawnexColors.card)
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                } else {
                    ForEach(Array(vote.investigationTrace.enumerated()), id: \.element.id) { idx, call in
                        toolCallRow(index: idx + 1, call: call)
                    }
                }
            }
            .padding(.horizontal, 20)
            .padding(.top, 12)
            .padding(.bottom, 20)
        }
        .navigationTitle("\(vote.advisor.displayName) · Investigation")
        .navigationBarTitleDisplayMode(.inline)
    }

    private var advisorHeader: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 10) {
                ZStack {
                    Circle()
                        .fill(CawnexColors.primary.opacity(0.13))
                        .frame(width: 32, height: 32)
                    Image(systemName: vote.advisor.iconName)
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundStyle(CawnexColors.primary)
                }
                VStack(alignment: .leading, spacing: 2) {
                    Text(vote.advisor.displayName)
                        .font(.system(size: 15, weight: .semibold))
                        .foregroundStyle(CawnexColors.cardForeground)
                    Text("Voted \(vote.vote.chipLabel) · \(String(format: "%.2f", vote.confidence)) confidence")
                        .font(.caption2)
                        .foregroundStyle(CawnexColors.mutedForeground)
                }
                Spacer()
                Text(vote.vote.chipLabel)
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(vote.vote.chipColor)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 4)
                    .background(vote.vote.chipColor.opacity(0.13))
                    .clipShape(Capsule())
            }

            Divider().overlay(CawnexColors.border)

            HStack {
                stat("\(vote.investigationTrace.count)", label: "Tool calls")
                Spacer()
                stat(tokenLabel, label: "Tokens")
                Spacer()
                stat(durationLabel, label: "Duration")
            }
        }
        .padding(14)
        .background(CawnexColors.card)
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(CawnexColors.border, lineWidth: 1)
        )
    }

    private func stat(_ value: String, label: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(value)
                .font(.system(size: 16, weight: .semibold))
                .foregroundStyle(CawnexColors.cardForeground)
            Text(label)
                .font(.system(size: 10))
                .foregroundStyle(CawnexColors.mutedForeground)
        }
    }

    private func toolCallRow(index: Int, call: ToolCall) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                Text("\(index)")
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(CawnexColors.cardForeground)
                    .frame(width: 20, height: 20)
                    .background(CawnexColors.muted)
                    .clipShape(Capsule())
                Text(call.toolName)
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(CawnexColors.primary)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 2)
                    .background(CawnexColors.primary.opacity(0.13))
                    .clipShape(RoundedRectangle(cornerRadius: 4))
                Spacer()
                if let err = call.error {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundStyle(CawnexColors.warning)
                        .help(err)
                }
                Text("\(call.durationMs) ms")
                    .font(.caption2)
                    .foregroundStyle(CawnexColors.mutedForeground)
            }
            if !call.args.isEmpty {
                VStack(alignment: .leading, spacing: 4) {
                    ForEach(call.args.sorted(by: { $0.key < $1.key }), id: \.key) { k, v in
                        HStack(alignment: .top, spacing: 6) {
                            Text("\(k):")
                                .font(.system(size: 11, weight: .semibold))
                                .foregroundStyle(CawnexColors.mutedForeground)
                            Text(displayValue(v))
                                .font(.system(size: 11))
                                .foregroundStyle(CawnexColors.cardForeground)
                                .lineLimit(2)
                                .truncationMode(.tail)
                        }
                    }
                }
                .padding(.horizontal, 10)
                .padding(.vertical, 6)
                .background(CawnexColors.muted)
                .clipShape(RoundedRectangle(cornerRadius: 4))
            }
            Text("→ \(call.resultSummary)")
                .font(.system(size: 11))
                .italic()
                .foregroundStyle(CawnexColors.mutedForeground)
                .frame(maxWidth: .infinity, alignment: .leading)
            if let err = call.error {
                Text("⚠️ \(err)")
                    .font(.caption2)
                    .foregroundStyle(CawnexColors.warning)
            }
        }
        .padding(12)
        .background(CawnexColors.card)
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(CawnexColors.border, lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .accessibilityIdentifier("investigation-trace.tool-call.\(index)")
    }

    private func displayValue(_ value: AnyCodable) -> String {
        guard let v = value.value else { return "null" }
        if let s = v as? String {
            return s.count > 80 ? String(s.prefix(80)) + "…" : s
        }
        return "\(v)"
    }

    private var tokenLabel: String {
        let total = (vote.cost?.tokensIn ?? 0) + (vote.cost?.tokensOut ?? 0)
        if total >= 1000 { return String(format: "%.1fK", Double(total) / 1000.0) }
        return "\(total)"
    }

    private var durationLabel: String {
        let total = vote.investigationTrace.reduce(0) { $0 + $1.durationMs }
        return total > 1000 ? String(format: "%.1fs", Double(total) / 1000.0) : "\(total)ms"
    }
}
```

- [ ] **Step 2: Verify build**

Build the Cawnex target. Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add apps/ios/Cawnex/Cawnex/Cawnex/Features/WaveReview/InvestigationTraceScreen.swift
git commit -m "feat(ios): InvestigationTraceScreen — drill-in tool-call timeline"
```

### Task 20: S32 MVI Blackboard touchup — Council Review Ready card

**Files:**
- Modify: `apps/ios/Cawnex/Cawnex/Cawnex/Features/MVI/MVIDetailScreen.swift`
- Modify: `apps/ios/Cawnex/Cawnex/Cawnex/Features/MVI/MVIDetailViewModel.swift`

Add a card that appears when the wave is in `under_human_review`. Tap pushes `WaveReviewScreen`.

- [ ] **Step 1: Inspect the existing MVI Blackboard screen**

```bash
grep -n "merge.readiness\|waveStatus\|Council\|under_human_review" apps/ios/Cawnex/Cawnex/Cawnex/Features/MVI/MVIDetailScreen.swift apps/ios/Cawnex/Cawnex/Cawnex/Features/MVI/MVIDetailViewModel.swift
```

Locate the section just above the Merge Readiness card (per the Pencil S32 design where the new card sits). If the ViewModel doesn't already expose wave status / council session id, add the minimum needed.

- [ ] **Step 2: Add the Council Review Ready card to the screen**

Insert directly above the existing "MERGE READINESS" section label, gated on `viewModel.waveStatus == "under_human_review"` and `viewModel.councilSessionId != nil`:

```swift
if viewModel.waveStatus == "under_human_review",
   let councilSessionId = viewModel.councilSessionId,
   let waveId = viewModel.waveId,
   let projectId = viewModel.projectId {
    councilReviewReadyCard(
        projectId: projectId,
        waveId: waveId,
        sessionId: councilSessionId,
        meta: viewModel.councilSummaryLine
    )
}
```

Then add the helper method on the screen:

```swift
private func councilReviewReadyCard(
    projectId: String,
    waveId: String,
    sessionId: String,
    meta: String
) -> some View {
    // The destination NavigationLink constructs the VM lazily — SwiftUI evaluates
    // the destination closure only when the link is activated, so this does NOT
    // construct a new VM on every render of the card.
    NavigationLink {
        WaveReviewScreen(
            projectId: projectId,
            waveId: waveId,
            sessionId: sessionId,
            viewModel: WaveReviewViewModel(
                service: APIWaveReviewService(
                    baseURL: AppConfiguration.shared.apiBaseURL,
                    authTokenProvider: { AppConfiguration.shared.authToken }
                )
            )
        )
    } label: {
        VStack(spacing: 10) {
            HStack(spacing: 10) {
                ZStack {
                    Circle()
                        .fill(CawnexColors.primary.opacity(0.13))
                        .frame(width: 32, height: 32)
                    Image(systemName: "person.3")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundStyle(CawnexColors.primary)
                }
                VStack(alignment: .leading, spacing: 2) {
                    Text("Council review ready")
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundStyle(CawnexColors.cardForeground)
                    Text(meta)
                        .font(.caption)
                        .foregroundStyle(CawnexColors.mutedForeground)
                }
                Spacer()
            }
            HStack {
                Text("Review now")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(.white)
                Image(systemName: "chevron.right")
                    .font(.caption)
                    .foregroundStyle(.white)
            }
            .frame(maxWidth: .infinity)
            .frame(height: 36)
            .background(CawnexColors.primary)
            .clipShape(RoundedRectangle(cornerRadius: 8))
        }
        .padding(14)
        .background(CawnexColors.card)
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(CawnexColors.primary, lineWidth: 1.5)
        )
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }
    .buttonStyle(.plain)
    .accessibilityIdentifier("mvi-blackboard.council-review-card")
}
```

- [ ] **Step 3: Extend MVIDetailViewModel**

If the ViewModel doesn't already publish `waveStatus`, `councilSessionId`, and `councilSummaryLine`, add them. They come from the wave/MVI API responses (most likely already in the project hub or wave fetch payload — verify by inspecting `APIProjectHubService.swift` and `APIWaveService.swift`).

Stub (adapt to actual MVIDetailViewModel signatures):

```swift
@MainActor
extension MVIDetailViewModel {
    var waveStatus: String? { /* read from existing wave payload */ }
    var councilSessionId: String? { /* derived from latest COUNCIL# row */ }
    var councilSummaryLine: String {
        "Council vote complete · Review now to approve or reject"
    }
    var waveId: String? { /* existing */ }
    var projectId: String? { /* existing */ }
}
```

If extending requires new API fields, add them to the smallest existing wave/hub endpoint that already serves this screen. Document the change in the commit message.

- [ ] **Step 4: Verify build + visual**

Build the Cawnex target. In Xcode preview, instantiate `MVIDetailScreen` with a viewModel whose `waveStatus = "under_human_review"` and confirm the card renders correctly between Live Feed and Merge Readiness.

- [ ] **Step 5: Commit**

```bash
git add apps/ios/Cawnex/Cawnex/Cawnex/Features/MVI/
git commit -m "feat(ios): S32 MVI Blackboard — Council Review Ready entry-point card"
```

### Task 21: Live feed banner for `council_decision` events

**Files:**
- Modify: existing live-feed consumer (find via `grep` for `WaveEvent` consumers)

The SSE infrastructure (`WaveEventStreamService` + `WaveEvent` model) is already wired and passes `event_type` through generically. Layer B just needs a consumer that filters `eventType == "council_decision"` and surfaces a tappable banner.

- [ ] **Step 1: Locate the consumer**

```bash
grep -rn "WaveEventStreamService\|subscribe(projectId\|WaveEvent" apps/ios/Cawnex/Cawnex/Cawnex/Features/ | head -10
```

Identify the screen / view-model that already consumes the wave event stream (likely `WaveExecutionViewModel.swift` per the audit). Add a handler for `event.eventType == "council_decision"`.

- [ ] **Step 2: Add handler with banner state**

In whichever view-model owns the wave event stream, add:

```swift
@Published var pendingCouncilBanner: CouncilBanner?

struct CouncilBanner: Identifiable {
    var id: String { sessionId }
    let waveId: String
    let sessionId: String
    let decisionAction: String
    let confidence: Double
}

// inside the event handler loop:
case "council_decision":
    pendingCouncilBanner = CouncilBanner(
        waveId: event.extra["wave_id"] ?? "",
        sessionId: event.extra["session_id"] ?? "",
        decisionAction: event.extra["decision_action"] ?? "—",
        confidence: Double(event.extra["confidence"] ?? "") ?? 0
    )
```

- [ ] **Step 3: Render banner in the existing live feed screen**

Where the live feed renders, add an overlay banner when `pendingCouncilBanner != nil`:

```swift
if let banner = viewModel.pendingCouncilBanner {
    NavigationLink {
        WaveReviewScreen(
            projectId: projectId,
            waveId: banner.waveId,
            sessionId: banner.sessionId,
            viewModel: WaveReviewViewModel(
                service: APIWaveReviewService(
                    baseURL: AppConfiguration.shared.apiBaseURL,
                    authTokenProvider: { AppConfiguration.shared.authToken }
                )
            )
        )
    } label: {
        HStack {
            Image(systemName: "person.3")
            Text("Wave \(banner.waveId) ready for your review — Council voted \(banner.decisionAction)")
                .font(.caption)
            Spacer()
            Image(systemName: "chevron.right").font(.caption)
        }
        .padding()
        .background(CawnexColors.primary.opacity(0.15))
        .foregroundStyle(CawnexColors.primary)
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }
    .padding(.horizontal)
    .accessibilityIdentifier("live-feed.council-banner")
}
```

- [ ] **Step 4: Verify build**

Build the Cawnex target. Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add apps/ios/Cawnex/Cawnex/Cawnex/Features/
git commit -m "feat(ios): live feed banner for council_decision SSE events"
```

### Task 22: UI test — happy path through InMemory service

**Files:**
- Create: `apps/ios/Cawnex/CawnexUITests/WaveReviewUITests.swift`

- [ ] **Step 1: Add launch-argument hook in the app target**

In the app's entry point (look for `@main App` struct, likely `CawnexApp.swift`), add a launch-argument check that constructs `WaveReviewScreen` directly with a seeded `InMemoryWaveReviewService` when `--ui-test-wave-review-ready` is present:

```swift
// inside the App's body or root navigation:
if CommandLine.arguments.contains("--ui-test-wave-review-ready") {
    let seedSession = try! JSONDecoder.uiTestDecoder().decode(
        CouncilSession.self,
        from: try! Data(contentsOf: Bundle.main.url(
            forResource: "council_session_completed", withExtension: "json"
        )!)
    )
    NavigationStack {
        WaveReviewScreen(
            projectId: "p1",
            waveId: "w1",
            sessionId: seedSession.sessionId,
            viewModel: WaveReviewViewModel(
                service: InMemoryWaveReviewService(seed: [seedSession])
            )
        )
    }
} else {
    // normal app root
}
```

The fixture must also be added to the main app bundle (not just CawnexTests) for the launch-argument path. Drag the JSON into the Cawnex target as well (Add Files → Cawnex target).

- [ ] **Step 2: Write the UI test**

```swift
// apps/ios/Cawnex/Cawnex/CawnexUITests/WaveReviewUITests.swift
import XCTest

final class WaveReviewUITests: XCTestCase {
    override func setUp() {
        continueAfterFailure = false
    }

    func test_happy_path_shows_6_advisors_and_approves() {
        let app = XCUIApplication()
        app.launchArguments = ["--ui-test-wave-review-ready"]
        app.launch()

        // All 6 advisor cards present
        for advisor in ["security", "architecture", "clarity", "performance", "ux", "cost"] {
            XCTAssertTrue(
                app.otherElements["wave-review.advisor.\(advisor)"].exists,
                "Advisor card missing: \(advisor)"
            )
        }

        // Drill into Security investigation
        app.otherElements["wave-review.advisor.security.view-trace"].tap()
        XCTAssertTrue(
            app.otherElements["investigation-trace.tool-call.1"].waitForExistence(timeout: 2)
        )
        app.navigationBars.buttons.element(boundBy: 0).tap()

        // Approve flow
        app.buttons["wave-review.approve"].tap()
        XCTAssertTrue(
            app.buttons["wave-review.confirm-approve"].waitForExistence(timeout: 2)
        )
        app.buttons["wave-review.confirm-approve"].tap()
        // (The InMemory service records the approval; we don't assert dismissal
        // here because the UI test target shouldn't reach the next screen.)
    }
}
```

- [ ] **Step 3: Run the UI test**

In Xcode, select the CawnexUITests scheme. Cmd-U. Expected: the UI test passes.

- [ ] **Step 4: Commit**

```bash
git add apps/ios/Cawnex/CawnexUITests/WaveReviewUITests.swift apps/ios/Cawnex/Cawnex/
git commit -m "test(ios-ui): WaveReview happy-path smoke through InMemory service"
```

### Task 23: Manual smoke-test runbook for Layer B

**Files:**
- Create: `docs/stage-4-layer-b-smoke-test.md`

- [ ] **Step 1: Write the runbook**

```markdown
# Stage 4 Layer B — Smoke Test Procedure

Runbook for verifying Layer B end-to-end against a dev deployment. Layer B is
"shippable" only after every step here passes.

## Prerequisites

- `cdk deploy -c stage=dev --require-approval never` completed for both
  Layer A and Layer B (this changeset)
- iOS dev build installed on a phone or Simulator, pointing at the dev API
- A dev project with at least one completed wave in `under_human_review`
  (run the Layer A smoke test runbook to produce one)

## Step 1 — Confirm live banner fires

Open the iOS app, navigate to the Live feed for the project.

Expected: a `Council voted approve — review now` banner appears within ~5s of
the Layer A Council Fargate writing the `status=completed` row.

## Step 2 — Tap the banner

Expected: pushes Wave Review screen. All 6 advisor cards render with name,
vote chip, reasoning, and (where present) cited evidence rows.

## Step 3 — Verify decision card metrics

Council Decision card shows action (Approve/etc), confidence, advisor count
(6), tool call total, veto count (0 in happy path), and token count.

## Step 4 — Drill into each advisor

Tap "View investigation" on each of the 6 advisor cards.

Expected: Investigation Trace screen pushes; advisor header shows correct
name + vote chip + stats; tool-call rows render with index, tool name chip,
args key-value rows, result summary, duration.

## Step 5 — Approve flow

Back to Wave Review. Tap "Approve & merge wave". Confirmation sheet
appears with "Approve & Merge" CTA. Tap.

Expected within ~10s:
- Wave row in DDB transitions `under_human_review → delivered`
- Both PRs on GitHub get merged (or the partial-merge error appears
  if a PR can't be merged)
- iOS navigates back to the previous screen

Verify with:

```bash
aws dynamodb get-item --table-name cawnex-dev \
  --key '{"PK":{"S":"P#<projectId>"},"SK":{"S":"S#<waveId>"}}' \
  --query 'Item.status.S'
```

Expected: `"delivered"`.

## Step 6 — Reject flow (on a second wave)

Repeat with a synthetic wave that should be rejected. Tap "Reject", enter a
reason ("scope creep"), confirm.

Expected: wave transitions to `cancelled`, reason recorded in wave metadata.

## Step 7 — Verify accessibility identifiers

Run the UI test target locally against the dev build:

```bash
xcodebuild test -workspace apps/ios/Cawnex/Cawnex/Cawnex.xcodeproj/project.xcworkspace \
  -scheme CawnexUITests -destination 'platform=iOS Simulator,name=iPhone 15'
```

Expected: PASS.

## Step 8 — Mark Layer B done

If steps 1-7 all passed:

```bash
git commit --allow-empty -m "chore(stage-4): Layer B smoke test passed on dev"
git tag stage-4-layer-b-ga
```

If any step failed, do NOT tag. Open issues and iterate.
```

- [ ] **Step 2: Commit**

```bash
git add docs/stage-4-layer-b-smoke-test.md
git commit -m "docs(stage-4): manual smoke-test runbook for Layer B"
```

### M3 wrap-up

- [ ] **Step 1: Run all tests**

```bash
# Backend
cd apps/api && PYTHONPATH=src pytest tests/ -q
cd /Users/eaugusto/cawnex && python3 -m pytest tests/integration/ -q

# iOS — in Xcode
# Cmd-U on CawnexTests scheme
# Cmd-U on CawnexUITests scheme
```

Expected: all pass.

- [ ] **Step 2: CDK synth sanity check**

```bash
cd infra && npx cdk synth -c stage=dev > /dev/null && echo "synth OK"
```

Expected: `synth OK`.

- [ ] **Step 3: Final empty commit marker**

```bash
git commit --allow-empty -m "chore(stage-4): Layer B implementation complete (pending dev deploy + smoke test)"
```

---

## Spec coverage check

| Spec section | Plan tasks |
|---|---|
| Domain models | Task 10 |
| AnyCodable shim | Task 9 |
| InMemory service | Task 12 |
| API service | Task 13 |
| ViewModel + polling timeout | Task 14 |
| WaveReviewScreen | Task 18 |
| InvestigationTraceScreen | Task 19 |
| CouncilHeaderCard | Task 17 |
| AdvisorCard | Task 16 |
| CitedEvidenceRow | Task 15 |
| GET endpoint | Tasks 4, 5, 6 |
| Approve endpoint | Task 7 |
| Reject (reuses cancel) | Task 13 (API service) |
| SSE banner | Task 21 |
| MVI Blackboard card | Task 20 |
| Fixtures (canonical, shared) | Tasks 1, 2, 3, 11 |
| Contract tests | Task 11 |
| ViewModel tests | Task 14 |
| Integration test | Task 8 |
| UI tests | Task 22 |
| Smoke runbook | Task 23 |
| Polling timeout (5 min) | Task 14 |
| Loud-failure for partial merge | Task 7 (502 response) |
| Logging | Inline structured logs assumed via existing iOS Logger pattern (the spec doesn't require new logging infra; existing `Logger` calls land inline where state transitions happen) |

All spec sections have an implementing task.

---

**Total: 23 tasks across 3 milestones, ~3 days estimated.**
