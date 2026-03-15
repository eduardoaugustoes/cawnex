# Screen Query Analysis — S32 MVI Blackboard

> DynamoDB single-table mapping for the live execution monitor.

---

## 1. Screen Purpose

Real-time window into Murder orchestration for a single MVI — shows active crows, task progress, live event feed, merge readiness, and the ship action.

---

## 2. Data Needed

| Field            | Type     | Example                               |
| ---------------- | -------- | ------------------------------------- |
| mvi.name         | string   | "MVI 1.2: Auth & JWT"                 |
| mvi.status       | enum     | executing, ready_to_ship, shipped     |
| mvi.tasksDone    | number   | 2                                     |
| mvi.tasksTotal   | number   | 3                                     |
| mvi.creditsSpent | currency | $4.20                                 |
| mvi.humanEquiv   | currency | ~$1,200                               |
| mvi.roi          | number   | 286                                   |
| activeCrows[]    | array    | [{name, behaviorState, model, color}] |
| tasks[]          | array    | [{name, status, prNumber, crowName}]  |
| liveFeed[]       | array    | [{timestamp, message, color}]         |
| mergeChecklist[] | array    | [{label, passed: boolean}]            |
| canShip          | boolean  | false                                 |

---

## 3. DynamoDB Queries

The snapshot tree uses the path format `S#{wave}#{council}#{murder}#{crow}`. An MVI maps to murder-level scope within a wave.

### 3.1 MVI Header (murder-level snapshot)

```
Table: cawnex
PK: T#{tenant_id}#P#{project_id}
SK: S#{wave_id}#council#murder#{murder_id}
```

`GetItem` — returns the murder-level snapshot containing:

- MVI name, status, tasksDone, tasksTotal, creditsSpent, humanEquiv, roi
- mergeChecklist, canShip
- These are aggregated values maintained by the Murder as crows report back

### 3.2 Active Crows (crow-level snapshots with status=running)

```
PK: T#{tenant_id}#P#{project_id}
SK: begins_with("S#{wave_id}#council#murder#{murder_id}#")
```

`Query` with SK prefix — returns all crow-level snapshots under this murder. Filter on `status IN (running, reviewing, building)` to get active crows. Each crow snapshot contains:

- name, behaviorState, model, color

### 3.3 Tasks (also crow-level snapshots)

Same query as 3.2 — each crow-level snapshot represents one task assignment. The snapshot contains:

- task name, status, prNumber, crowName
- A crow snapshot IS a task. The crow is assigned to the task, and its snapshot tracks both crow state and task progress.

### 3.4 Live Feed (EVT records)

```
PK: T#{tenant_id}#P#{project_id}
SK: begins_with("EVT#{wave_id}#")
```

`Query` with ScanIndexForward=false, Limit=50 — returns most recent events first. Each EVT record contains:

- timestamp, message, color (green for approvals, amber for retries, purple for builds, muted for kickoffs)

Optional: filter by murder_id attribute if events are wave-wide and need scoping to a specific MVI.

### Query Summary

| Purpose              | Operation    | PK                | SK Pattern                                    |
| -------------------- | ------------ | ----------------- | --------------------------------------------- |
| MVI header           | GetItem      | `T#{tid}#P#{pid}` | `S#{wave}#council#murder#{mid}`               |
| Active crows + tasks | Query        | `T#{tid}#P#{pid}` | `begins_with(S#{wave}#council#murder#{mid}#)` |
| Live feed            | Query (desc) | `T#{tid}#P#{pid}` | `begins_with(EVT#{wave}#)`                    |

**Total: 1 GetItem + 2 Queries = 3 DynamoDB calls to render the full screen.**

---

## 4. How MVI Maps to the Snapshot Tree

An MVI is a **murder-level snapshot**. The hierarchy:

```
S#{wave}                              ← wave snapshot (milestone-level)
  S#{wave}#council                    ← council decision record
    S#{wave}#council#murder#{mid}     ← MVI snapshot (THIS SCREEN)
      S#{wave}#council#murder#{mid}#crow#{cid}  ← crow/task snapshot
```

The MVI is the murder's execution scope within a wave. The Murder receives the wave plan from the Monarch, then orchestrates crows to deliver the MVI. The murder-level snapshot is the single source of truth for:

- Aggregated progress (tasksDone/tasksTotal)
- Accumulated cost (creditsSpent)
- Computed ROI (humanEquiv / creditsSpent)
- Merge readiness (mergeChecklist, canShip)

The Murder updates this snapshot every time a crow reports back (task completed, PR created, CI passed).

---

## 5. How Live Feed Maps to EVT Records

EVT records are append-only event logs within a wave:

```
PK: T#{tenant_id}#P#{project_id}
SK: EVT#{wave_id}#{timestamp_iso}
```

Each EVT record:

```json
{
  "PK": "T#acme#P#cawnex",
  "SK": "EVT#w2#2026-03-14T14:32:00.000Z",
  "murder_id": "dev-murder",
  "crow": "implementer",
  "message": "Implementer started building Session management",
  "color": "purple",
  "type": "crow_state_change"
}
```

Events are written by:

- **Murder** — kickoff, task assignment, PR approval, merge queue decisions
- **Crows** — started, completed, failed, retry
- **CI** — checks passing, checks failing
- **Human** — approved, steered, rejected

The live feed query reads the last N events with `ScanIndexForward=false`. The ISO timestamp in the SK guarantees chronological ordering.

---

## 6. How Active Crows Map to Crow-Level Snapshots

Each crow working on this MVI has a snapshot at:

```
PK: T#{tenant_id}#P#{project_id}
SK: S#{wave_id}#council#murder#{mid}#crow#{crow_id}
```

The crow snapshot contains:

```json
{
  "name": "implementer",
  "behaviorState": "building",
  "model": "claude-sonnet-4-20250514",
  "color": "#10B981",
  "status": "running",
  "taskName": "Session management",
  "prNumber": null,
  "creditsUsed": 1.8,
  "startedAt": "2026-03-14T14:32:00Z"
}
```

Active crows = crow-level snapshots where `status = running`. The behavior state field (planning, building, reviewing, testing, fixing) maps directly to what the UI shows in the crow cards.

When a crow finishes, the Murder updates its snapshot to `status=completed` and writes the PR number. It also updates the parent murder-level snapshot (tasksDone++, creditsSpent+=).

---

## 7. How Tasks Map to Crow-Level Snapshots

A task and a crow snapshot are the **same record**. This is the key insight: in the snapshot model, a crow-level snapshot IS the task. The Murder assigns one crow to one task within an MVI, and the crow's snapshot tracks both the agent's runtime state and the task's delivery state.

```
Crow snapshot fields that serve the task list:
  - taskName        → "RBAC middleware"
  - status          → completed | in_progress | pending_approval | queued | failed
  - prNumber        → 14 (null if not yet created)
  - crowName        → "implementer" (the crow assigned to this task)
```

If a task is reassigned (e.g., fixer crow takes over from implementer), the Murder writes a new crow snapshot and marks the old one as `status=handed_off`. The UI always shows the latest active snapshot per task.

For the task list on S32, the query from section 3.2 returns all crow snapshots. The UI groups and displays them as tasks.

---

## 8. Real-Time: SSE with DynamoDB Streams

### Architecture

```
DynamoDB Table
    │
    ▼ (DynamoDB Streams - NEW_IMAGE)
Lambda (stream processor)
    │
    ├── Filter: PK matches project, SK is EVT# or S# under this murder
    │
    ▼
API Gateway WebSocket / SSE endpoint
    │
    ▼
iOS client (EventSource / SSE)
```

### Flow

1. **Crow reports to Murder** — Murder writes crow snapshot update + EVT record to DynamoDB
2. **DynamoDB Streams** triggers a Lambda with the new/modified records
3. **Lambda filters** by project PK and murder_id, then routes to the appropriate SSE connection
4. **SSE pushes** three event types to the client:

```
event: crow_state
data: {"name": "implementer", "behaviorState": "building", "status": "running"}

event: task_update
data: {"taskName": "RBAC middleware", "status": "completed", "prNumber": 14}

event: live_feed
data: {"timestamp": "14:32", "message": "Implementer started building", "color": "purple"}
```

### Connection Management

- SSE connection opened when user enters S32, closed on exit
- Connection scoped to: `T#{tenant_id}#P#{project_id}` + `murder_id` + `wave_id`
- Lambda maintains a connection table (DynamoDB or ElastiCache) mapping active subscriptions to connection IDs
- Heartbeat every 30s to keep connection alive

### Why SSE over WebSocket

- S32 is read-heavy (watch execution) with rare writes (ship action)
- SSE is simpler, works over HTTP/2, auto-reconnects
- The ship action uses a regular POST, not the stream

---

## 9. Ship Operation: What Happens in DynamoDB

When the user taps "Ship this MVI", a transactional write executes:

### Precondition Check

Read murder-level snapshot, verify `canShip = true`. If false, reject with reason.

### TransactWriteItems (atomic)

```
1. UPDATE murder snapshot
   PK: T#{tid}#P#{pid}
   SK: S#{wave}#council#murder#{mid}
   SET status = "shipped", shippedAt = NOW()
   CONDITION: canShip = true AND status = "ready_to_ship"

2. WRITE EVT record
   PK: T#{tid}#P#{pid}
   SK: EVT#{wave}#${NOW()}
   {message: "MVI 1.2 shipped — all PRs merged", color: "green", type: "mvi_shipped"}

3. UPDATE wave snapshot (parent)
   PK: T#{tid}#P#{pid}
   SK: S#{wave}
   SET mvisShipped = mvisShipped + 1
   (rolls up to milestone/project aggregates)
```

### Side Effects (async, triggered by DynamoDB Streams)

1. **GitHub**: Merge all PRs in the MVI's merge queue (synchronized merge strategy)
2. **Notification**: Push "MVI shipped" notification to S70
3. **Monarch**: Inform Monarch that the MVI is delivered so it can plan next work
4. **Cost rollup**: Update project-level and dynasty-level cost aggregates
5. **If all MVIs in wave shipped**: Update wave status to "delivered", trigger Monarch to plan next wave

### Failure Handling

- If any PR merge fails on GitHub, the Lambda reverts the DynamoDB transaction (sets status back to "ready_to_ship") and writes an EVT with the failure reason
- The user sees a live feed event: "Ship failed: PR #14 has merge conflicts" (red)

---

## 10. Why S32 Proves the Snapshot Model

S32 is the stress test. Every other screen reads static or slowly-changing data. S32 reads **live, fast-changing state** and must render it coherently. Here is why the recursive snapshot model works:

### The Murder-Level Snapshot is the Aggregation Point

Without the snapshot model, rendering S32 would require:

- Query all tasks for this MVI (separate table or complex filter)
- Query all crow executions (another table)
- Aggregate progress, cost, ROI on the fly
- Query all events (yet another table)
- Compute merge readiness from CI status + review status (cross-system)

With the snapshot model, the Murder maintains a single snapshot that IS the MVI state. Every time a crow reports, the Murder writes the crow snapshot AND updates the parent murder snapshot atomically. The aggregation is done at write time, not read time.

**Read cost: 1 GetItem + 2 Queries.** That is it. No joins, no aggregation, no fan-out reads.

### The EVT Stream is Append-Only

Live feed events never update — they only append. This is the ideal DynamoDB access pattern: write-once, query-recent. The SK is a timestamp, so the latest events are always at the end of the partition, and `ScanIndexForward=false` with a limit gives the client exactly what it needs.

### Crow Snapshots are the Task State

The decision to make crow snapshots and task state the same record eliminates the impedance mismatch between "what the agent is doing" and "what the task status is." When the implementer crow starts building, its snapshot updates to `behaviorState: building` — and the UI shows both the crow card (active, building) and the task row (in progress) from the same record.

### DynamoDB Streams Enable Real-Time Without Polling

The snapshot model writes to DynamoDB. DynamoDB Streams captures every write. A Lambda filters and pushes to SSE. The client never polls. This is the key architectural property: **the same writes that maintain the snapshot tree also power the real-time feed.**

### Ship is a Conditional Write

The ship operation uses DynamoDB's conditional write (`canShip = true AND status = "ready_to_ship"`) to prevent race conditions. If the Murder is still updating the snapshot (a crow just finished), the condition prevents premature shipping. The TransactWriteItems ensures the murder snapshot, the EVT record, and the wave rollup all succeed or all fail.

### The Tree Proves Itself

```
Project PK ─────────────────────────────────────────────
  │
  ├── S#w2                          wave (milestone view)
  │    ├── S#w2#council             council decisions
  │    ├── S#w2#council#murder#dev  MVI snapshot ← S32 reads THIS
  │    │    ├── S#w2#...#crow#impl  task/crow ← S32 reads THESE
  │    │    ├── S#w2#...#crow#rev   task/crow
  │    │    └── S#w2#...#crow#test  task/crow
  │    └── S#w2#council#murder#ed   another MVI (different murder)
  │
  ├── EVT#w2#2026-03-14T14:32:00Z  live feed ← S32 reads THESE
  ├── EVT#w2#2026-03-14T14:28:00Z
  └── EVT#w2#2026-03-14T14:14:00Z
```

All data for S32 lives under one PK (`T#{tid}#P#{pid}`). One partition, three access patterns, zero cross-partition reads. The recursive snapshot tree collapses what would be 5-6 relational tables into a single-table design where the Murder is both the writer (during execution) and the read model (for the UI).

This is the screen where the model either works or breaks. It works.
