# Project State Readout — Computed Status from System Truth

> Spec for replacing the project's stored `status` field with a computed `current_state` derived from the project's actual execution reality. The chip on the dashboard becomes a real-time gauge, not a user-controlled setting.

---

## Overview

Today, `Project.status` is a stored DDB field that is written exactly once (as `"draft"` on `POST /projects`) and never updated. The iOS dashboard renders a "Draft" chip on every project regardless of execution reality. The chip's tap menu shows a "Start" transition that does nothing — its `onTransition` callback is a no-op.

This spec replaces the stored status field with a **computed `current_state`** field on the API response, derived deterministically from the project's underlying entities (Monarch docs, waves, MVIs). The chip becomes read-only: it always shows the truth, can't drift, and has no mutation path to maintain.

Halt/stop functionality is **explicitly out of scope** for this spec — it lives in a separate spec (project-level halt) that operates on the underlying entities, not on this status field. The chip will reflect a halted project as `idle` because that's what halting produces (no work running). The fact that it was halted lives in the event log, not the status.

---

## The State Set

Five computed states. Definitions are precise and ordered (first match wins on read). The pseudocode and the implementation in the **Computation function** section below use identical helper names — there is one source of truth.

```python
def compute_current_state(project_id: str, db: TenantDB) -> str:
    """Return the project's computed current state. First match wins."""

    # 1. draft — Monarch hasn't finished generating the 4 setup docs
    if not _monarch_docs_complete(project_id, db):
        return "draft"

    # 2. running — at least one wave is executing
    if _has_executing_wave(project_id, db):
        return "running"

    # 3. active — set up, no waves created yet
    waves = _list_waves(project_id, db)
    if not waves:
        return "active"

    # 4. completed — every wave is terminal AND at least one MVI shipped
    if _all_terminal(waves) and _has_shipped(project_id, db):
        return "completed"

    # 5. idle — has wave history, none executing, not yet completed
    return "idle"
```

### State definitions

| State | Meaning | Detection rule |
|---|---|---|
| **`draft`** | Project exists, Monarch is generating docs (vision/architecture/glossary/design), no waves yet | At least one of the 4 docs at `SK: DOC#{doc_type}` is missing or `status != "complete"` |
| **`active`** | Monarch finished, factory open, no waves created yet | All 4 docs complete, zero wave-root items (SK matches `S#{wave_id}` with no `#` after) |
| **`running`** | At least one wave is executing right now | Any wave-root item with `status == "executing"` |
| **`idle`** | Has wave history, currently nothing executing, not yet completed | At least one wave-root exists, none executing, and either some wave is non-terminal or no MVI has shipped |
| **`completed`** | Every wave is terminal AND at least one MVI shipped | All wave-roots in `{delivered, cancelled}`, at least one MVI item at `S#{wave_id}#m{mvi_id}` with `status == "shipped"` |

### State transitions (informational only — backend doesn't manage these)

```
draft → active     (when Monarch finishes the 4th doc)
active → running   (when first wave activates)
running → idle     (when last wave drains)
running → running  (waves come and go, computed state stays the same)
idle → running     (next wave activates)
idle → completed   (all MVIs shipped, nothing pending)
running → completed (last wave delivers the last MVI)
```

There is no `halted` state in this computation. Halting (separate spec) leaves the project in `idle` because that's what's true — no work is running. The history of having been halted lives in events, not in the status field.

### Why this state set

- **No `paused` or `halted`** — paused/halted are transient operations, not persistent project states. A paused/halted project is *idle* by definition (nothing executing). The history of pause/halt lives in the event log where it belongs.
- **`active` exists** — distinguishes "set up but no work loaded" from "set up and has work history but nothing running right now." Useful for empty-state UX vs work-history UX.
- **`completed` requires shipped work** — prevents fresh-but-empty projects from being labeled completed.
- **Ordering matters** — `draft` shadows everything (during setup, we don't care about wave state). `running` shadows `idle` (executing wins over history). `completed` requires both conditions to avoid false positives.

---

## API Changes

### Response shape

The `current_state` field is added to every project response. The stored `status` field remains for backward compat and is unchanged.

```jsonc
{
  "project_id": "p_abc",
  "name": "Cawnex",
  "one_liner": "Multi-agent orchestration",
  "status": "draft",          // ← stored field, unchanged, vestigial
  "current_state": "running",  // ← NEW: computed each read
  "murders": ["dev"],
  "created_at": "2026-05-13T..."
}
```

### Endpoints affected

| Endpoint | Change |
|---|---|
| `GET /projects` | Add `current_state` to each item |
| `GET /projects/{project_id}` | Add `current_state` to response |
| `GET /projects/{project_id}/hub` | Add `current_state` to the project block (replaces today's `"status": project.get("status", "draft")` at `apps/api/src/routes/hub.py:120`) |
| `POST /projects` | Add `current_state: "draft"` to creation response (always `draft` on creation since Monarch hasn't run) |

### Endpoints NOT affected

- `PATCH /projects/{project_id}` — no new field. Status remains immutable from the user's side. (Auto-mode field stays as the only patchable thing.)
- All wave/MVI/task endpoints — unchanged.
- Murder/Council/Worker Lambdas — unchanged. They don't read `Project.status` today, and they don't read `current_state` either.

### Computation function

Lives in `apps/api/src/services/project_state.py` (new file):

```python
"""Compute project's current_state from underlying entity truth."""

from typing import Dict, Any
from src.db.tenant import TenantDB

_DOC_TYPES = {"vision", "architecture", "glossary", "design"}
_TERMINAL_WAVE_STATUSES = {"delivered", "cancelled"}
_TERMINAL_MVI_STATUSES = {"shipped", "cancelled"}


def compute_current_state(project_id: str, db: TenantDB) -> str:
    """Return the project's computed current state. First match wins."""
    if not _monarch_docs_complete(project_id, db):
        return "draft"
    if _has_executing_wave(project_id, db):
        return "running"
    waves = _list_waves(project_id, db)
    if not waves:
        return "active"
    if _all_terminal(waves) and _has_shipped(project_id, db):
        return "completed"
    return "idle"


def _monarch_docs_complete(project_id: str, db: TenantDB) -> bool:
    """All 4 setup documents exist and are status=complete."""
    items = db.query_project(project_id=project_id, sk_prefix="DOC#")
    complete_types = {
        i.get("doc_type") for i in items
        if i.get("status") == "complete"
    }
    return _DOC_TYPES.issubset(complete_types)


def _has_executing_wave(project_id: str, db: TenantDB) -> bool:
    """Any wave root with status=executing."""
    return any(w.get("status") == "executing" for w in _list_waves(project_id, db))


def _list_waves(project_id: str, db: TenantDB) -> list[dict]:
    """Root wave snapshots only (excludes nested MVI items)."""
    items = db.query_project(project_id=project_id, sk_prefix="S#")
    return [i for i in items if _is_wave_root(i.get("SK", ""))]


def _is_wave_root(sk: str) -> bool:
    """SK pattern S#{wave_id} is a wave root; S#{wave_id}#m{mvi_id} is not."""
    parts = sk.split("#")
    return len(parts) == 2 and parts[0] == "S" and parts[1] != ""


def _all_terminal(waves: list[dict]) -> bool:
    """Every wave in a terminal status."""
    return all(w.get("status") in _TERMINAL_WAVE_STATUSES for w in waves)


def _has_shipped(project_id: str, db: TenantDB) -> bool:
    """Any MVI in shipped status anywhere on the project."""
    items = db.query_project(project_id=project_id, sk_prefix="S#")
    for item in items:
        if item.get("level") == "murder" and item.get("status") == "shipped":
            return True
    return False
```

Function is **pure given DB state**. No side effects. Easy to unit test against fixture DBs.

### Performance

Each call to `compute_current_state` does up to 2 DDB queries: one with `DOC#` prefix, and one with `S#` prefix shared between `_list_waves` and `_has_shipped` if the implementer caches the result. The naive version above queries `S#` twice; an obvious refactor is to call `db.query_project(project_id, "S#")` once at the top of `compute_current_state` and pass the result to both helpers.

For `GET /projects` (listing), the computation runs once per project. For 50 projects on a dashboard, that's ~150 queries. Cawnex's DDB is single-table tenant-scoped; the listing endpoint already does one query per project to enrich. Adding 1-2 more queries per project is acceptable for v1. If load becomes a concern, cache the computed state for ~30s in DDB on the project root snapshot (`computed_state`, `computed_state_at` fields), refreshing lazily on read.

---

## iOS Changes

### `ProjectStatus` enum updates

`apps/ios/Cawnex/Cawnex/Domain/Project.swift`:

```swift
enum ProjectStatus: String, Equatable, CaseIterable, Hashable {
    case draft = "Draft"
    case active = "Active"
    case running = "Running"     // NEW — backend sends this
    case idle = "Idle"           // NEW — backend sends this
    case completed = "Completed"
    case paused = "Paused"       // LEGACY — kept for compile compat; backend never sends
    case archived = "Archived"   // LEGACY — kept for compile compat; backend never sends

    var label: String { rawValue }

    var color: Color {
        switch self {
        case .draft:     CawnexColors.mutedForeground
        case .active:    CawnexColors.primary
        case .running:   CawnexColors.success
        case .idle:      CawnexColors.warning  // soft amber
        case .completed: CawnexColors.success
        case .paused:    CawnexColors.warning
        case .archived:  CawnexColors.muted
        }
    }

    var icon: String {
        switch self {
        case .draft:     "doc"
        case .active:    "play.circle"
        case .running:   "play.fill"
        case .idle:      "pause.circle"
        case .completed: "checkmark.circle.fill"
        case .paused:    "pause.fill"
        case .archived:  "archivebox"
        }
    }

    // Empty transitions — chip is read-only now for ALL cases
    var transitions: [StatusTransition<ProjectStatus>] { [] }
}
```

**Why keep `.paused` and `.archived` as legacy cases:**

`ProjectServiceContractTests.swift:53` references both in a `Set<ProjectStatus>`, and `StatusChip.swift:87` uses `.archived` in the SwiftUI preview. Removing them is a separate cleanup; this spec stays minimal. The cases compile but are unreachable in production because the backend's `current_state` never emits `paused` or `archived`.

### `StatusChip` behavior

Per `Components/StatusChip.swift:11-13`, when `transitions.isEmpty` the chip renders as a non-interactive label (no menu, no chevron). With the empty `transitions` above, the chip automatically becomes a read-only display. **No `StatusChip` code changes needed.**

### DTO decoding

`apps/ios/Cawnex/Cawnex/Core/Network/APIProjectService.swift` updates the 3 read paths to read `current_state` instead of `status`:

```swift
// At line 35 (createProject response):
status: ProjectStatus(rawValue: response.current_state.capitalized) ?? .draft,

// At line 74 (listProjects DTO):
status: ProjectStatus(rawValue: current_state.capitalized) ?? .draft,
```

DTO additions:

```swift
private struct ProjectDTO: Decodable {
    let project_id: String
    let name: String
    let one_liner: String
    let status: String          // keep for now, unused
    let current_state: String   // NEW: drives display
    // ...
}
```

Same change in `APIProjectHubService.swift` at line 41.

### Optional: tap-to-explain

If the chip later needs tap behavior, the recommendation is **tap = explain** (show a tooltip/sheet with *why* the state is what it is, sourced from a `GET /projects/{id}/state-detail` endpoint). Out of scope for this spec. The chip ships as pure read-only for v1.

---

## Behavior Examples

| Scenario | Stored `status` | Computed `current_state` | Chip shows |
|---|---|---|---|
| Project just created, Monarch generating docs | `draft` | `draft` | "Draft" (muted) |
| Monarch finished, no wave created yet | `draft` | `active` | "Active" (primary) |
| Wave executing | `draft` | `running` | "Running" (success green) |
| Wave delivered, no new waves | `draft` | `idle` | "Idle" (warning amber) |
| User halts project (separate spec) — waves cancelled, no execution | `draft` | `idle` | "Idle" (warning amber) |
| All milestones shipped | `draft` | `completed` | "Completed" (success green) |
| User unhalts and starts a new wave | `draft` | `running` | "Running" (success green) |

The user never has to do anything to make the chip correct. The system tells the truth.

---

## Why this design

### vs. the original spec'd state machine (draft/active/paused/completed/archived with transitions)

The original `ProjectStatus` enum was designed as a user-controlled state machine: tap a chip, advance the project. After ~12 months of code (the chip exists, the enum is mature, the API has the field), **nothing was ever wired to mutate `status` beyond initial creation**. That's a strong signal the state-machine framing was wrong for this entity — users don't want to manage project status manually. They want to know what the system is doing.

This spec removes the manual control entirely and replaces it with computed truth. The chip becomes a gauge.

### vs. wiring the original state machine (control framing)

Wiring the control framing would mean: PATCH endpoint with status field, validated transitions, `onTransition` callback wired, write-side tests, drift-prevention logic. All of that maintenance to give the user a button they didn't ask for. The read-out framing eliminates the control surface entirely — no PATCH, no transitions, no drift.

### vs. doing nothing

Today every project shows "Draft." That's misinformation. Users either learn to ignore the chip (it becomes noise) or are actively misled. Either outcome is worse than no chip at all. This spec gives the chip a real job.

---

## Testing

### Backend

`apps/api/tests/test_project_state.py` (new file):

- `test_draft_when_no_docs` — project with no DOC# items returns `draft`
- `test_draft_when_partial_docs` — 3 of 4 docs complete returns `draft`
- `test_active_when_docs_complete_no_waves` — all 4 docs, no S# items, returns `active`
- `test_running_when_wave_executing` — wave with `status=executing` returns `running`
- `test_running_shadows_idle` — multiple waves, one executing one delivered, returns `running`
- `test_idle_when_waves_delivered` — all waves `delivered`, no shipped MVIs, returns `idle`
- `test_idle_when_waves_cancelled` — all waves `cancelled`, returns `idle`
- `test_completed_when_shipped_and_terminal` — all waves terminal, at least one MVI shipped, returns `completed`
- `test_completed_requires_shipped` — all waves terminal but no MVIs shipped, returns `idle` (not completed)

Each test sets up a minimal fixture DB with just the relevant items, calls `compute_current_state`, asserts the return.

### Backend integration

- `test_get_projects_includes_current_state` — listing endpoint returns `current_state` on each item
- `test_get_project_hub_includes_current_state` — hub endpoint returns `current_state` in the project block

### iOS

Existing `ProjectServiceContractTests` should be extended:

- DTO decoder accepts `current_state` field
- DTO decoder ignores `status` field (or treats it as optional / informational only)
- `ProjectStatus.running` and `.idle` decode correctly
- `Project.preview` updated to use a running state for visual testing

---

## Migration

No DDB migration. The stored `status` field stays as-is for backward compat. `current_state` is computed on read; no historical data needs touching.

iOS clients on old versions will read `status` (stuck on `draft`) — fine, they're already stuck on `draft`. The new field is purely additive.

---

## Out of Scope

Explicit list so this spec doesn't drift:

- ❌ **Halt/stop functionality** — separate spec. This spec is read-only.
- ❌ **Resume button** — there's no halted state to resume from in this computation.
- ❌ **Auto-promotion of `Project.status` in DDB** — the stored field stays as `draft` forever. We could clean it up later but it's not load-bearing for this spec.
- ❌ **Tap-to-explain on the chip** — possible follow-up, not in v1.
- ❌ **Caching the computed state in DDB** — optimization, defer until profiling demands it.
- ❌ **Other entities (Milestone/Goal/MVI/Wave) getting computed states** — this spec is project-only. The pattern can extend later but the entities below already have meaningful stored states managed by the Murder.
- ❌ **`completed` auto-detection that ships milestones/goals** — out of scope. This is just a display state, not a hand-off.
- ❌ **Web/dashboard surfaces beyond iOS** — Cawnex is iOS-first; future web ports inherit the same `current_state` field.

---

## Implementation Order

Suggested slicing:

1. **Backend computation function + unit tests** — pure logic, no integration. Ships value immediately as testable code.
2. **Add `current_state` to listing endpoint** — ship the field on the wire. iOS can ignore it for now.
3. **iOS DTO + enum + decoding** — display the new state on the dashboard chip.
4. **Hub endpoint + project detail** — propagate `current_state` to other surfaces.
5. **Integration test in real DDB** — end-to-end against a real project moving through states.

Each step is independently mergeable.
