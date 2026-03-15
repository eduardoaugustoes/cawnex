# Cawnex Data Model V2 — Recursive Snapshots

> The data structure IS the algorithm.
> Like git's tree/blob/commit model made branches cheap and merging natural,
> our recursive snapshot model makes traceability, rewind, budget tracking,
> and training data generation fall out as natural byproducts.

---

## Design Principles

1. **One universal primitive** — The Snapshot. Same shape at every level (wave, council, murder, crow).
2. **Dual hierarchy** — Planning (milestone → goal → MVI) and Execution (wave → council → murder → crow) are orthogonal. MVI bridges them.
3. **Write-time aggregation** — Materialized views updated via Streams, not query-time fan-out.
4. **Config vs snapshot** — Mutable templates (murders, skills) frozen into immutable snapshots at execution start.
5. **Every layer is training data** — ask + reasoning + code + outcome = complete training sample.

---

## DynamoDB Single Table Design

### Table: `cawnex`

```
Billing Mode: PAY_PER_REQUEST (on-demand)
Point-in-time Recovery: ENABLED
Streams: NEW_AND_OLD_IMAGES
TTL Attribute: ttl
```

---

## Partition Patterns

### 1. Per-Project: `T#{tenant}#P#{project}`

The core partition. Contains the recursive snapshot tree, planning hierarchy, documents, events, conversations, and memory.

#### SK Patterns

```
EXECUTION SNAPSHOTS (recursive tree):
  S#{wave_id}                                              → wave snapshot
  S#{wave_id}#{council_id}                                 → council session
  S#{wave_id}#{council_id}#{murder_id}                     → murder/MVI execution
  S#{wave_id}#{council_id}#{murder_id}#{crow_id}           → crow/task execution
  S#{wave_id}#...#{crow_id}#R{n}                           → retry cycle (append, never overwrite)

PLANNING HIERARCHY:
  S#PLAN#MS#{milestone_id}                                 → milestone
  S#PLAN#MS#{ms}#GL#{goal_id}                              → goal
  S#PLAN#MS#{ms}#GL#{gl}#MVI#{mvi_id}                      → MVI (bridges to execution)

DOCUMENTS:
  DOC#{type}                                                → document metadata (vision, architecture, etc.)

EVENTS:
  EVT#{wave_id}#{iso_timestamp}                             → live feed events (append-only)

CONVERSATIONS:
  CONV#PR#{pr_id}#MSG#{timestamp}                           → PR review chat messages

PULL REQUESTS:
  S#{wave}#M#{murder}#C#{crow}#PR#{pr_id}                  → PR record with verdict
  S#{wave}#M#{murder}#C#reviewer#PR#{pr_id}                → reviewer verdict

TASKS (denormalized summary):
  S#{wave}#M#{murder}#TASK#{task_id}                        → task summary (updated after each crow step)

MATERIALIZED VIEWS:
  SUMMARY                                                   → project summary for S10 Dashboard
  HUB                                                       → project hub data for S12

MEMORY:
  MEM#{level}#{topic}                                       → agent learnings (project-level)
  MEMORY                                                    → monarch memory

ROOT:
  S#                                                        → project root snapshot
  META                                                      → project metadata
```

### 2. Document Chat: `T#{tenant}#P#{project}#DOC#{type}`

Separate partition for unbounded chat history (isolates growth from project partition).

```
  MSG#{timestamp}#{ulid}                                    → chat message
```

### 3. Project List: `T#{tenant}#PROJECTS`

```
  P#{project_id}                                            → project entry (name, phase, status)
  META                                                      → anchor record
```

### 4. Dynasty (Org Config): `T#{tenant}#DYNASTY`

```
  META                                                      → org settings, unreadNotificationCount
  SETTINGS                                                  → preferences
  MURDER#{murder_id}                                        → murder config (crows embedded)
  SKILL#{skill_id}                                          → skill config
  DEVICE#{device_id}                                        → push notification registration
  MEM#dynasty#{topic}                                       → org-wide agent memory
  MEM#agent#{crow_type}                                     → specialization memory
```

### 5. Notifications: `T#{tenant}#NOTIFICATIONS`

```
  N#{iso_timestamp}#{notification_id}                       → notification record
```

Cross-project inbox. TTL at 30 days.

### 6. Billing: `T#{tenant}#BILLING`

```
  CREDITS                                                   → atomic credit balance counter
  ROLLUP#CURRENT                                            → pre-aggregated ROI totals
  PROJECT#{project_id}                                      → per-project spend
  CROW#{period}#{crow_name}                                 → per-crow cost tracking
  BUDGET#{project_id}                                       → user-set budget limits
  TXN#{timestamp}                                           → purchase history (append-only)
```

### 7. Marketplace: `MARKETPLACE`

```
  TEMPLATE#{template_id}                                    → murder templates (global, non-tenant)
  SKILL#{skill_id}                                          → skill templates (global)
```

### 8. User: `T#{tenant}#USER#{user_id}`

```
  PROFILE                                                   → user profile
  INTEGRATION#{provider}                                    → linked integrations
```

---

## GSIs

### GSI1: Worker Dispatch

```
PK: DISPATCH#{status}
SK: T#{tenant}#P#{project}#S#{path}
Projected: id, level, crow_type, ask, project_id, wave_id, repo, branch, instructions
Sparse: only crow-level snapshots with status field
```

Worker queries `PK = DISPATCH#pending`, grabs task, conditional update to `running`.

### GSI2: Wave-to-MVI Lookup (optional)

```
PK: T#{tenant}#P#{project}#W#{wave_id}
SK: S#PLAN#MS#{ms}#GL#{gl}#MVI#{mvi_id}
Sparse: only MVI items with execution.wave_id set
```

Monarch/Murder needs "which MVIs are in this wave?" for completion tracking.

---

## The Snapshot Primitive

Every snapshot at every level has the same shape:

```json
{
  "PK": "T#acme#P#cawnex",
  "SK": "S#w001#c01#m_dev#cr_impl",

  "id": "snap_abc123",
  "level": "crow",
  "parent_path": "S#w001#c01#m_dev",
  "sequence": 2,

  "ask": "Implement OAuth token validation middleware",
  "context": {
    "phase": "execution",
    "tech_stack": "FastAPI",
    "memory_refs": ["MEM#project#conventions"]
  },

  "decisions": [
    {
      "actor": "murder",
      "action": "assign",
      "reasoning": "Implementer needed after planner completed"
    }
  ],

  "crow_type": "implementer",
  "status": "completed",
  "outcome": {
    "summary": "Created token validation middleware with async pattern",
    "artifacts": {
      "files_changed": ["src/middleware/auth.py", "tests/test_auth.py"],
      "git_diff_ref": "s3://cawnex-artifacts/diffs/snap_abc123.diff"
    }
  },
  "git_commit": "abc123def",
  "git_branch": "cawnex/w001-auth",

  "cost": {
    "tokens_in": 2000,
    "tokens_out": 500,
    "credits": 0.06,
    "duration_ms": 30000
  },

  "learning": "FastAPI middleware needs async pattern for token validation",

  "pr": {
    "number": 14,
    "title": "Add token validation middleware",
    "branch": "cawnex/w001-auth",
    "status": "ready"
  },

  "created_at": "2026-03-14T14:32:00Z",
  "completed_at": "2026-03-14T14:32:30Z",

  "project_id": "proj_cawnex",
  "wave_id": "w001",
  "mvi_id": "mvi_auth",
  "feature_tag": "auth",

  "entityType": "Snapshot"
}
```

### Level-Specific Fields

| Level | Extra Fields |
|-------|-------------|
| **Wave** | `mvis_shipped`, `mvis_total`, `wave_budget`, `human_directive` |
| **Council** | `round` (debate round number), `advisor_votes[]`, `dissent[]`, `consensus` |
| **Murder** | `tasks_done`, `tasks_total`, `merge_checklist[]`, `can_ship`, `murder_config_snapshot` |
| **Crow** | `crow_type`, `behavior_state`, `git_commit`, `git_diff_ref`, `pr`, `retry_count` |

---

## The MVI Bridge Record

The MVI item lives in the planning hierarchy but references the execution hierarchy:

```json
{
  "PK": "T#acme#P#cawnex",
  "SK": "S#PLAN#MS#m1#GL#g1#MVI#mvi_auth",

  "name": "MVI 1.1: REST API Endpoints",
  "status": "completed",

  "planning": {
    "milestone_id": "m1",
    "goal_id": "g1",
    "order": 1,
    "human_estimate_hours": 24,
    "human_equiv_cost": 1200.00
  },

  "execution": {
    "wave_id": "w001",
    "council_id": "c01",
    "murder_id": "m_dev"
  },

  "counters": {
    "tasks_done": 4,
    "tasks_total": 4,
    "ai_minutes": 23,
    "ai_cost": 18.00,
    "human_equiv_cost": 1200.00,
    "roi": 67
  },

  "entityType": "MVI"
}
```

---

## Materialized Views (Streams-Powered)

### Project SUMMARY (for S10 Dashboard)

```json
{
  "PK": "T#acme#P#cawnex",
  "SK": "SUMMARY",
  "tasks_done": 12,
  "tasks_active": 3,
  "tasks_refined": 8,
  "tasks_draft": 5,
  "credits_spent": 247.50,
  "human_equiv_saved": 4200.00,
  "active_crow_count": 3,
  "updated_at": "2026-03-14T10:32:00Z"
}
```

**Updated by:** Stream Lambda on snapshot status transitions. Atomic ADD/SET operations.

### Project HUB (for S12 Project Hub)

```json
{
  "PK": "T#acme#P#cawnex",
  "SK": "HUB",
  "project_name": "Cawnex",
  "project_description": "...",
  "progress_pct": 40,
  "tasks_completed": 12,
  "tasks_total": 30,
  "pending_approvals": 3,
  "roi_multiplier": 78,
  "credits_spent": 182,
  "human_equiv": 14200,
  "documents": [...],
  "backlog": { "milestones": 3, "mvi_shipped": 4, "mvi_total": 9, "pipeline": {...} },
  "murders": [...]
}
```

**Updated by:** Stream Lambda on any project state change. Full overwrite (item is a projection).

### Planning Counters (for S24/S30/S31)

Milestone and Goal items include pre-computed counters:

```json
{
  "SK": "S#PLAN#MS#m1",
  "counters": {
    "tasks_done": 8,
    "tasks_total": 15,
    "credits_spent": 142
  }
}
```

**Updated by:** Stream Lambda when task snapshots transition status.

### Billing Rollups (for S61)

```json
{
  "PK": "T#acme#BILLING",
  "SK": "ROLLUP#CURRENT",
  "roi_multiplier": 8.4,
  "ai_minutes": 1240,
  "human_hours": 312,
  "ai_cost": 574.20,
  "human_cost": 15600.00,
  "monthly_burn": 1200,
  "days_remaining": 42
}
```

**Updated by:** EventBridge rule on task.completed events. Incremental ADD operations.

### Notification Badge (for S10 bell icon)

```json
{
  "PK": "T#acme#DYNASTY",
  "SK": "META",
  "unread_notification_count": 3
}
```

**Updated by:** Atomic increment on notification create, decrement on seen/acted_on.

---

## Event Flow: Write Path

```
1. Human/System triggers action
2. Murder Lambda writes snapshot(s) to DynamoDB
3. DynamoDB Streams fires
4. Stream Lambda:
   a. Updates materialized views (SUMMARY, HUB, counters)
   b. Creates notifications if approval needed
   c. Updates billing rollups
   d. Pushes SSE events to connected clients
   e. Dispatches next Murder reaction (if REPORT written)
```

---

## Training Data Structure

Every snapshot is a self-contained training sample:

```
Layer (snapshot) {
    ask        → what was requested
    context    → project state at decision time
    decisions  → who decided what and why (council votes, dissent)
    cycles     → feedback loop (rejected attempts preserved)
    git_commit → the actual code produced
    outcome    → human approved? tests passed?
    cost       → tokens, time, credits
    learning   → extracted insight for memory

    // Long-term signal (updated retroactively)
    bugs_reported → count (updated weeks later)
    reverted      → bool
    tech_debt     → bool
}
```

Export: `Query PK=T#acme#P#cawnex, SK begins_with S#w001` → full tree = one wave training sample. Each subtree is a sample at its own level.

---

## Query Count Per Screen

| Screen | Reads | Writes | SSE | Total DDB Ops |
|--------|-------|--------|-----|---------------|
| S01 Splash | 0 | 0 | No | 0 |
| S02 Sign In | 0 | 0 | No | 0 |
| S10 Dashboard | 2 | 0 | Optional | 2 |
| S11 Create Project | 0 | 3 | No | 3 |
| S12 Project Hub | 1 | 0 | WS | 1 |
| S20-S23 Documents | 2 | 2 | SSE | 4 |
| S24 Backlog | 1 | 0 | No | 1 |
| S30 Milestone | 3 | 0 | No | 3 |
| S31 Goal Detail | 3 | 1 | No | 4 |
| S32 MVI Blackboard | 3 | 1 | SSE | 4 |
| S33 Task Detail | 1 | 0 | No | 1 |
| S34 PR Review | 3 | 2 | SSE | 5 |
| S40 Murders | 3 | 0 | No | 3 |
| S41 Create Murder | 1 | 1 | No | 2 |
| S42 Create Crow | 1 | 1 | No | 2 |
| S50 Skills | 2 | 0 | No | 2 |
| S51 Add Skill | 1 | 1 | No | 2 |
| S60 Settings | 2 | 0 | No | 2 |
| S61 Billing | 4 | 0 | No | 4 |
| S70 Notifications | 2 | 1 | SSE+Push | 3 |

---

## Size Estimates

| Entity | Count per project (mature) | Avg item size | Total |
|--------|---------------------------|---------------|-------|
| Snapshots | ~500 (50 waves × 10 tasks) | 2-5 KB | ~1.5 MB |
| Events | ~2000 | 0.5 KB | ~1 MB |
| Planning items | ~50 | 1 KB | ~50 KB |
| Documents | 4 | 2 KB | ~8 KB |
| Doc chat messages | ~800 (200 per doc) | 2 KB | ~1.6 MB |
| Conversations | ~200 | 1 KB | ~200 KB |
| **Total per project** | | | **~4.4 MB** |

At 1000 projects per tenant: ~4.4 GB. Well within DynamoDB limits.

Large blobs (git diffs, raw LLM output) stored in S3 with reference in snapshot.

---

## Capacity Estimates (MVP: 10-50 tenants)

| Metric | Estimate |
|--------|----------|
| Items in table | ~50,000 |
| Table size | ~500 MB |
| WCU (peak, during execution) | ~50 |
| RCU (peak, dashboard load) | ~100 |
| Stream Lambda invocations/day | ~5,000 |
| Monthly cost (DynamoDB on-demand) | ~$5-15 |
| Monthly cost (Lambda) | ~$1-5 |
| **Total monthly infra** | **~$10-25** |
