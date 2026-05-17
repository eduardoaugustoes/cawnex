# Stage 4 Layer B — iOS surface for Council verdicts

**Status:** Draft for review.
**Strategic context:** [docs/CAWNEX-BUILDS-ITSELF-PLAN.md](../../CAWNEX-BUILDS-ITSELF-PLAN.md) §Stage 4, Layer B.
**Predecessor:** [Layer A spec](2026-05-16-council-layer-a-design.md) — backend Council Fargate service. Layer A produces the data this layer renders.

---

## Why

Layer A made every wave's Council session adversarially investigate the code and write a structured `CouncilSession` row with six advisor votes, each carrying an `investigation_trace` and `cited_evidence`. Today nothing surfaces that to the founder. The merge gate is unchanged from before Layer A — founders still approve PRs one-by-one in the PR Review screen, blind to the Council's analysis.

Layer B closes that loop: when Council completes, the founder sees the verdict on a dedicated Wave Review screen, can drill into any advisor's investigation trace, and approves or rejects the whole wave from there. **Founder still gates everything** — Council is informational. Auto-merge is Layer C.

The principle running through this layer mirrors Layer A's: **at this stage the founder sees what Council saw, in the same evidence-grade detail Council saw it.** If Security blocked because it grep'd `tenant_id` and found a missing filter on `foo.py:42`, the founder sees those exact two tool calls and the file:line citation — not a prose summary.

## Scope

In Layer B:

- New `Features/WaveReview/` Swift module mirroring the existing `Features/PR/` Contract-First pattern (protocol service → InMemory implementation → API implementation → `@Observable` ViewModel → View)
- One new backend endpoint: `GET /projects/{project_id}/council/sessions/{session_id}` — thin DDB read, returns the full session JSON
- Live feed banner triggered by the `council_decision` SSE event (already emitted by Layer A's Council Fargate handler) — taps deep-link to Wave Review screen
- Persistent "Council Review Ready" card on the Wave detail screen when wave status is `under_human_review`
- Approve / Reject founder actions on the Wave Review screen, gated by confirmation sheets
- Investigation trace drill-in screen showing the full timeline of tool calls per advisor

Explicitly out of Layer B:

- Per-PR approve/reject within a wave (Layer B is whole-wave only — keeps founder decision atomic)
- Steer action with a planning loop (deferred — current Reject only writes the reason to wave metadata)
- Auto-merge or any non-human gating (Layer C)
- Push notifications (Live feed banner is the real-time signal; SSE already wired)
- New backend wave-mutation endpoints (reuse existing approve/cancel paths; if none exists for whole-wave approve, the implementation plan adds the minimum needed)
- Editing or commenting on a Council session (read-only, except for the wave-level decision)

## Architecture

### High-level flow

```
Layer A backend                      iOS (Layer B)
─────────────────                    ──────────────
Council Fargate writes
COUNCIL#{session} row
status=completed
    │
    │ DDB Stream
    ▼
Murder reactor (existing)
emits SSE event
event_type=council_decision
    │
    │ EventBridge → SQS → Stream Fargate → ALB
    ▼
                                    LiveFeedViewModel
                                    receives council_decision
                                       │
                                       │ surfaces tappable banner
                                       │ + adds card to Wave detail
                                       ▼
                                    Founder taps banner / card
                                       │
                                       ▼
                                    WaveReviewScreen(waveId, sessionId)
                                       │
                                       │ GET /projects/{p}/council/sessions/{s}
                                       ▼
apps/api/src/routes/council.py      WaveReviewViewModel
GET handler                         renders header + 6 AdvisorCards
single Blackboard.read              cited evidence inline
returns full session                tap advisor → InvestigationTraceScreen
                                       │
                                       │ Approve / Reject
                                       ▼
apps/api/src/routes/waves.py        Existing wave-action endpoints
(existing approve/cancel paths)
```

### File layout

```
apps/ios/Cawnex/Cawnex/
└── Features/
    └── WaveReview/                                NEW
        ├── WaveReviewModels.swift                 Domain models (one-to-one with API)
        ├── WaveReviewService.swift                Protocol contract
        ├── InMemoryWaveReviewService.swift        Seed data for previews + UI tests
        ├── APIWaveReviewService.swift             Calls the new GET endpoint
        ├── WaveReviewViewModel.swift              @Observable, owns state + polling
        ├── WaveReviewScreen.swift                 Top-level screen
        ├── InvestigationTraceScreen.swift         Drill-in: full tool-call timeline
        └── Components/
            ├── CouncilHeaderCard.swift            Decision chip + reasoning + cost
            ├── AdvisorCard.swift                  One per advisor (vote + reasoning + inline evidence)
            └── CitedEvidenceRow.swift             file:line + reason

apps/ios/Cawnex/Cawnex/Core/
└── (existing AnyCodable shim added if not present)

apps/ios/Cawnex/CawnexTests/
├── Features/WaveReview/
│   ├── CouncilSessionDecodingTests.swift
│   ├── WaveReviewViewModelTests.swift
│   ├── AdvisorCardTests.swift
│   └── InvestigationTraceScreenTests.swift
└── Contracts/
    └── Fixtures/
        ├── council_session_completed.json
        ├── council_session_pending.json
        └── council_session_errored.json

apps/ios/Cawnex/CawnexUITests/
└── WaveReviewUITests.swift

apps/api/src/routes/
└── council.py                                     EXTEND: add GET handler

apps/api/tests/
└── test_council_get_session.py                    NEW

tests/integration/
└── test_stage4_b_wave_review.py                   NEW: end-to-end via DDB Local

docs/
└── stage-4-layer-b-smoke-test.md                  NEW: post-deploy runbook
```

### Why Contract-First (Option B)

The existing iOS architecture (per `memory/ios-data-architecture.md`) is: Protocol service → InMemory implementation → API implementation → ViewModel → View. `WaveReview` follows that pattern unchanged — same as `Features/PR/`. The InMemory service powers SwiftUI previews + UI tests so the screen can be developed and validated without a live backend, and swapping to the real API is a single DI line change.

### Why one big GET, not per-advisor

The Council session row in DDB already contains the entire result graph: `decision`, `rounds[].votes[]` with embedded `investigation_trace` and `cited_evidence`. One read serves both the main screen and the drill-in trace screen — no second round-trip when the founder taps an advisor. Bandwidth is bounded (≤6 advisors × ≤15 tool calls × ≤200-char result_summary ≈ 18 KB worst case, typically <10 KB).

## Data models

### Domain (`WaveReviewModels.swift`)

```swift
// MARK: - Session

struct CouncilSession: Equatable, Codable {
    let sessionId: String
    let waveId: String
    let projectId: String
    let status: CouncilSessionStatus
    let integrationSK: String
    let createdAt: Date
    let completedAt: Date?
    let decision: CouncilDecision?      // nil while pending/running
    let rounds: [VotingRound]           // [] while pending/running, partial during running
    let cost: AdvisorCost?
    let pipelineHealth: PipelineHealth
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
    let confidence: Double                       // 0.0 – 1.0
    let conditions: [String]
    let orderingConstraints: [String]
    let dissentRecord: [String: String]          // advisor name → dissent summary
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
    let lineRange: [Int]?                        // [start, end] when provided
    let prNumber: Int?
    let reason: String
}

struct ToolCall: Equatable, Codable, Identifiable {
    var id = UUID()
    let toolName: String
    let args: [String: AnyCodable]
    let resultSummary: String
    let durationMs: Int
    let error: String?
}

struct AdvisorCost: Equatable, Codable {
    let tokensIn: Int
    let tokensOut: Int
    let durationMs: Int
}
```

### Display extensions

Per-view extensions compute SwiftUI `Color`, `Image(systemName:)`, and formatted strings from the domain types. Mirrors `PRModels.swift::VerdictStatus.color`. Examples:

```swift
extension VoteType {
    var chipColor: Color { /* approve→success, block→destructive, abstain→muted, etc */ }
    var chipLabel: String { /* "Approve", "Block (Veto)", "Abstain" */ }
}

extension AdvisorType {
    var icon: String { /* SF Symbol per advisor */ }
    var hasVeto: Bool { self == .security || self == .clarity }
}

extension CouncilDecision {
    var actionChipColor: Color { /* approve→success, reject→destructive, etc */ }
}
```

### `AnyCodable` shim

Tool args are free-shape (`{"path": "foo.py"}`, `{"pattern": "x", "path": "y"}`, `{"file_path": "x", "max_entries": 10}`). A small `AnyCodable` wrapper (~30 LoC) allows decoding any JSON value, so the trace screen renders generic key:value rows without per-tool typing. If the codebase already has an equivalent, reuse it; otherwise add one.

### Assumptions tracked

- `AdvisorVote.id = advisor.rawValue` is unique within a round (true today; Council's `ALL_ADVISORS` has 6 distinct enum values per round). Composite ID is a follow-up if multi-vote-per-advisor is introduced.
- iOS only knows the 6 current advisor types. Legacy `quality / market / maturity` are gone post-Layer A.

## API contract

### New endpoint

`GET /projects/{project_id}/council/sessions/{session_id}`

Lives in `apps/api/src/routes/council.py`. Authz: project-owner guard (same as existing `apply_council_override` route in that file).

**Request:**

```http
GET /projects/p1/council/sessions/wr_w1_a8f3b2c1
Authorization: Bearer <cognito-jwt>
```

**Response 200 (always — status reflects reality):**

```json
{
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
    "reasoning": "All advisors approved. Cited tenant_id filter, no auth regression, no perf concerns.",
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
            {
              "file_path": "apps/api/foo.py",
              "line_range": [42, 58],
              "pr_number": 42,
              "reason": "tenant_id filter present"
            }
          ],
          "investigation_trace": [
            {
              "tool_name": "read_file",
              "args": { "path": "apps/api/foo.py" },
              "result_summary": "def query()...",
              "duration_ms": 18,
              "error": null
            },
            {
              "tool_name": "grep",
              "args": { "pattern": "tenant_id", "path": "apps/api" },
              "result_summary": "12 matches",
              "duration_ms": 42,
              "error": null
            }
          ]
        }
      ]
    }
  ]
}
```

Notes:

- `status` is the source of truth for iOS rendering. `pending` / `running` may have `decision: null` and partial `rounds`. iOS branches on `status` rather than relying on null fields.
- Snake↔camel conversion happens at the FastAPI boundary using existing project conventions.
- Field truncation already enforced upstream: `result_summary ≤ 200 chars`, `reasoning ≤ 1000` (backend `_emit_pipeline_error` style limits already in Layer A code).

**Errors:**

- `403` — project not owned by caller
- `404` — session not found at `PK=P#{project_id}, SK=COUNCIL#{session_id}`

**No `409`** — pending/running sessions return `200` with `status` reflecting reality. iOS branches on status; this simplifies the client.

### Reused infrastructure

- SSE event already emitted by Layer A (`council.handler.process_pending_session`):
  ```json
  {
    "event_type": "council_decision",
    "wave_id": "w1",
    "session_id": "wr_w1_a8f3b2c1",
    "decision_action": "approve",
    "confidence": 0.86,
    "pipeline_health": "ok"
  }
  ```
  Verify during implementation that the events table → EventBridge Pipe → SQS → Stream Fargate path lets `council_decision` through. If a filter is too narrow, widen it.
- **Wave Approve / Reject:** reuse existing endpoints in `apps/api/src/routes/waves.py` where possible. The Reject path maps to the existing `POST /projects/{id}/waves/{wave_id}/cancel` (which already handles wave termination). The Approve path requires a whole-wave merge: if no endpoint exists today, the implementation plan adds `POST /projects/{id}/waves/{wave_id}/approve` that flips `under_human_review` → `delivered` and triggers per-PR merge using existing PR-merge logic. This decision is made in the implementation plan after a 5-minute audit of the current waves routes, not in this spec.

## Error handling and edge states

### Session-level

- **`status: pending` or `running`:** screen shows "Council is still investigating — N of 6 advisors voted" with progress derived from `rounds[0].votes.count`. iOS polls the GET endpoint every 5s while status is `running`. Polling auto-stops on `completed` / `errored`, **and has a hard 5-minute timeout** — if the session is still `pending` / `running` after 5 minutes the screen shows the same error card as the `errored` state ("Council pipeline appears stuck — founder must decide manually"), with Approve / Reject still enabled. The SSE banner that brought the founder here is the trigger; no manual refresh button.
- **`status: errored`:** explicit error card: "Council failed — pipeline health: degraded. Founder must decide manually." Linked `council_pipeline_error` event rows (from the events table the Live feed already reads from) are fetched and rendered inline so the founder sees _what_ failed. Approve / Reject buttons stay enabled — backend errors don't block the human gate.
- **HTTP 404 (session not found / deleted):** "This council session doesn't exist." + back button. No retry.
- **Network failure on initial load:** error card + retry button. Same `NetworkError` display pattern as `PRReviewScreen`. No silent retries.
- **Network failure on Approve / Reject:** toast-level error, button re-enabled, action is idempotent on the backend so re-tap is safe. UI never optimistically navigates away on Approve — waits for 2xx.

### Per-advisor (local degradation)

Each `AdvisorCard` degrades independently — one broken advisor doesn't break the screen.

- **`vote=abstain` with `confidence=0`:** gray "Abstained" chip, the Layer-A-populated reasoning (`"investigation incomplete: terminated by call_cap after 16 tool calls (cap=15)"`). No cited evidence section, no trace affordance.
- **`vote=block` (veto):** red border, 🛡️ icon for Security/Clarity, `blockers[]` listed above `cited_evidence`. The decision card at top shows a "Vetoed" chip if any veto is present even when `decision.action == "escalate"`.
- **Empty `cited_evidence`:** section hidden. The absence is the signal — no "no evidence" placeholder.
- **Empty `investigation_trace`:** "View trace ›" affordance hidden entirely.

### Investigation trace screen

- **Tool call with `error != null`:** row gets yellow ⚠️ icon + the error string. Doesn't fail the screen.
- **`ToolCall.args` value too long:** truncate display to ~80 chars per value, tap-to-expand for full.
- **Empty trace (defensive — affordance should be hidden first):** "Advisor submitted vote without calling any tools." — a meaningful signal that the advisor short-circuited.

### Approve / Reject

- **Approve:** confirmation sheet (matches `MergeConfirmSheet.swift` pattern) summarizing: "Merge N PRs from Wave M. Council voted Approve unanimously." Explicit "Approve & Merge" CTA. No accidental taps.
- **Reject:** confirmation sheet with a **required** reason text field. Reason is written to wave metadata as a steering input for the next planning pass (added to `rework_reasons[]`). "Reject Wave" CTA.

### SSE re-entry

- If the founder is on `WaveReviewScreen` when a `council_decision` event fires for the same session (debate round triggered a re-vote), the screen silently refetches and animates the changed `AdvisorCard`s. The banner does not fire again for the same session.
- If the founder dismisses the Live feed banner, the persistent card on the Wave detail screen remains the entry point.

### Logging

iOS structured logger emits: `wave_review_opened`, `wave_review_approved`, `wave_review_rejected`, `advisor_trace_opened`. Same pattern as the existing PR Review logging.

### Explicitly NOT in Layer B

- Auto-merge when Council is unanimous (Layer C)
- Optimistic UI on Approve — the merge can fail (conflicts, race with stream); never tell the founder the wave was approved if it wasn't
- Persistent state if founder backgrounds the app mid-decision — state restoration brings them back to the screen, but a half-typed reject reason is not preserved. YAGNI for Layer B.

## Testing strategy

Same test pyramid Layer A used, applied to iOS + the one backend change.

### iOS unit tests (`Cawnex/CawnexTests/Features/WaveReview/`)

- **`CouncilSessionDecodingTests`** — JSON fixtures decoded into domain models. Covers:
  - All 4 `DecisionAction` values
  - All 4 `VoteType` values (including `approve_with_condition` snake-case mapping)
  - All 6 `AdvisorType` values
  - Pending session (`decision: null`, `rounds: []`)
  - Errored session (missing fields)
  - Partial advisor list during `running` (e.g. 3 of 6 votes)
  - Empty `cited_evidence` / `investigation_trace`
  - `ToolCall.args` as heterogeneous shapes (strings, ints, nested objects) → `AnyCodable`
  - Veto vote (Security `block`) preserves `blockers[]`
- **`WaveReviewViewModelTests`** — `@Observable` state transitions using `InMemoryWaveReviewService`:
  - Happy path `load(sessionId:)` → `idle → loading → loaded`
  - Pending session → polling fires every 5s, stops on `completed`
  - Errored session → state goes to `error`, polling stops
  - Network failure on load → `error` + retry transitions to `loading`
  - Approve / Reject success → success state, no premature navigation
  - Approve / Reject failure → toast state, button re-enabled, no navigation
  - SSE re-vote event for same session → silent refetch, animated diff
- **`AdvisorCardTests`** — renders the right chip color per vote type, veto border, evidence visibility (snapshot or rendering-state tests per existing CawnexTests convention).
- **`InvestigationTraceScreenTests`** — empty trace placeholder, errored tool calls show ⚠️, long args truncate.

### iOS contract tests (`Cawnex/CawnexTests/Contracts/`)

Single test decodes canonical fixtures committed in the test bundle and asserts every domain field is populated. Catches API↔iOS drift without a live backend.

Fixtures:

- `Fixtures/council_session_completed.json`
- `Fixtures/council_session_pending.json`
- `Fixtures/council_session_errored.json`

### iOS UI tests (`CawnexUITests`)

One end-to-end smoke through the InMemory service:

- Launch with `--ui-test-wave-review-ready` flag → app seeds InMemory service with completed session, lands on `WaveReviewScreen`
- Assert: 6 advisor cards visible, decision card shows action
- Tap Security advisor → trace screen pushes, tool calls visible
- Back, tap Approve → confirm sheet → tap "Approve & Merge" → success state
- Re-launch with `--ui-test-wave-review-pending` → polling banner visible

Accessibility identifiers required on every interactive element. Minimum set:

- `wave-review.advisor.{type}` (one per advisor)
- `wave-review.advisor.{type}.view-trace`
- `wave-review.approve`
- `wave-review.reject`
- `wave-review.confirm-approve`
- `wave-review.confirm-reject`
- `wave-review.reject-reason-field`
- `investigation-trace.tool-call.{index}`

### Backend tests (`apps/api/tests/`)

- **`test_council_get_session.py`** — unit-level tests for the new GET handler:
  - 200 happy path returns full shape (assert every top-level field)
  - 200 pending session (decision null, rounds empty)
  - 200 running session (partial rounds)
  - 200 errored session
  - 403 when caller doesn't own the project
  - 404 when SK doesn't exist
  - Snake↔camel boundary correctness for every field

### Integration test (`tests/integration/`)

`test_stage4_b_wave_review.py` — end-to-end against DDB Local: write a fully-formed CouncilSession row → hit GET via FastAPI TestClient → assert iOS-shaped response. ~50 LoC. Mirrors `test_stage4_m1.py` style.

### Manual smoke test (`docs/stage-4-layer-b-smoke-test.md`)

Post-deploy runbook:

1. Trigger a synthetic wave through Layer A → Council completes
2. Open iOS dev build → Live feed shows banner → tap
3. Wave Review screen renders all 6 advisors
4. Tap each advisor → trace shows tool calls
5. Approve → confirm → verify wave transitions to `delivered` in DDB and PRs merged on GitHub
6. Repeat with synthetic-failure wave (force one advisor to block) → verify veto chip + Reject path

### Budgets

- iOS unit + contract tests: <2s total
- iOS UI tests: <30s
- Backend tests: <1s
- No new heavy dependencies (`AnyCodable` is a ~30-LoC shim)

## Open questions for implementation

These are deliberately deferred to the implementation plan, not the spec:

1. **Whole-wave approve endpoint** — does one exist in `apps/api/src/routes/waves.py` today, or does the plan add one? Implementation discovers this and either reuses or adds the minimum needed.
2. **`council_decision` SSE delivery** — verify the events table → EventBridge Pipe → SQS → Stream Fargate path passes this event type through. If filtered out, widen the filter.
3. **`AnyCodable` reuse** — check if an equivalent already exists in the iOS codebase before adding a new shim.

## Success criteria

Layer B is shippable when:

1. All iOS unit, contract, and UI tests pass
2. Backend unit + integration tests pass
3. CDK synth clean
4. Manual smoke test (the 6-step runbook) passes end-to-end on dev
5. A founder, given a real Council session in `under_human_review` state, can: reach the screen via Live feed banner OR Wave detail card; see all 6 advisor verdicts with cited evidence; drill into any investigation trace; Approve or Reject the wave with confirmation; observe the wave transition correctly in DDB

When all 5 pass, tag `stage-4-layer-b-ga` and continue to Layer C (graduated auto-merge with quarantine zones) after the observation window.
