# Screen Query Analysis — Complete DynamoDB Access Patterns

> All screens mapped to the recursive snapshot single-table design.
> Generated from per-screen analysis by 12 parallel agents.

---

## Table Schema Summary

```
Main Table: cawnex (single table)

Partition Patterns:
  T#{tenant}#P#{project}       → snapshots, events, documents, conversations, memory
  T#{tenant}#PROJECTS          → project list for dashboard
  T#{tenant}#DYNASTY           → org settings, murders, skills
  T#{tenant}#NOTIFICATIONS     → cross-project notification inbox
  T#{tenant}#BILLING           → credits, rollups, cost breakdown
  MARKETPLACE                  → global templates (non-tenant)

SK Patterns (per project):
  S#{wave}#{council}#{murder}#{crow}   → execution snapshots (recursive tree)
  S#PLAN#MS#{ms}#GL#{gl}#MVI#{mvi}    → planning hierarchy
  S#                                    → project root snapshot
  DOC#{type}                            → document metadata
  EVT#{wave}#{timestamp}                → live event feed
  MEM#{level}#{topic}                   → agent memory
  CONV#PR#{pr_id}#MSG#{timestamp}       → PR conversations

GSIs:
  GSI1: DISPATCH#{status} → worker picks up pending crow tasks
  GSI2: T#{tenant}#W#{wave} → wave-to-MVI reverse lookup (sparse)
```

---

## Per-Screen Access Patterns

### S01 — Splash

| Query | None |
| ----- | ---- |

No DynamoDB access. Pure client-side animation.

---

### S02 — Sign In

| Query | None (client-side) |
| ----- | ------------------ |

Auth handled by Cognito. Post-confirmation Lambda bootstraps:

- `T#{tenant}#DYNASTY | META` — dynasty record
- `T#{tenant}#PROJECTS | META` — project list anchor

---

### S10 — Dashboard

| #   | Purpose             | PK                       | SK                | Op           |
| --- | ------------------- | ------------------------ | ----------------- | ------------ |
| 1   | Project list        | `T#{tenant}#PROJECTS`    | `begins_with(P#)` | Query        |
| 2   | Per-project summary | `T#{tenant}#P#{project}` | `SUMMARY`         | BatchGetItem |

**Recommendation:** Materialized SUMMARY record per project, updated via DynamoDB Streams on every task completion. Dashboard becomes 2 queries regardless of data volume.

**Real-time:** SSE for project status updates (task completions, crow activity).

---

### S11 — Create Project

| #   | Purpose          | PK                       | SK               | Op      |
| --- | ---------------- | ------------------------ | ---------------- | ------- |
| 1   | Register project | `T#{tenant}#PROJECTS`    | `P#{project_id}` | PutItem |
| 2   | Root snapshot    | `T#{tenant}#P#{project}` | `S#`             | PutItem |
| 3   | Project memory   | `T#{tenant}#P#{project}` | `MEMORY`         | PutItem |

All 3 via **TransactWriteItems**. No initial wave — waves emerge from Vision phase.

---

### S12 — Project Hub

| #   | Purpose  | PK                       | SK    | Op      |
| --- | -------- | ------------------------ | ----- | ------- |
| 1   | Hub data | `T#{tenant}#P#{project}` | `HUB` | GetItem |

**Recommendation:** Materialized HUB record containing all S12 fields (stats, documents, backlog summary, murders, cost). Updated via Streams. One GetItem renders the entire screen.

**Real-time:** WebSocket push on mutations, client refreshes HUB record.

---

### S20-S23 — AI-Guided Documents

| #   | Purpose           | PK                                  | SK                  | Op                |
| --- | ----------------- | ----------------------------------- | ------------------- | ----------------- |
| 1   | Document metadata | `T#{tenant}#P#{project}`            | `DOC#{type}`        | GetItem           |
| 2   | Chat history      | `T#{tenant}#P#{project}#DOC#{type}` | `begins_with(MSG#)` | Query (paginated) |
| 3   | Send message      | `T#{tenant}#P#{project}#DOC#{type}` | `MSG#{timestamp}`   | PutItem           |
| 4   | Update sections   | `T#{tenant}#P#{project}`            | `DOC#{type}`        | UpdateItem        |

Chat history uses separate PK to isolate unbounded growth. Documents are project-level, not wave-level.

**Real-time:** SSE for AI response streaming.

---

### S24 — Backlog

| #   | Purpose        | PK                       | SK                        | Op    |
| --- | -------------- | ------------------------ | ------------------------- | ----- |
| 1   | All milestones | `T#{tenant}#P#{project}` | `begins_with(S#PLAN#MS#)` | Query |

Pre-computed counters (tasksDone, tasksTotal, creditsSpent) on milestone items, updated via Streams.

---

### S30 — Milestone Detail

| #   | Purpose   | PK                       | SK                                   | Op      |
| --- | --------- | ------------------------ | ------------------------------------ | ------- |
| 1   | Milestone | `T#{tenant}#P#{project}` | `S#PLAN#MS#{ms_id}`                  | GetItem |
| 2   | Goals     | `T#{tenant}#P#{project}` | `begins_with(S#PLAN#MS#{ms_id}#GL#)` | Query   |
| 3   | Chat      | `T#{tenant}#P#{project}` | `begins_with(M#CHAT#MS#{ms_id}#)`    | Query   |

---

### S31 — Goal Detail

| #   | Purpose    | PK                       | SK                                         | Op      |
| --- | ---------- | ------------------------ | ------------------------------------------ | ------- |
| 1   | Goal       | `T#{tenant}#P#{project}` | `S#PLAN#MS#{ms}#GL#{gl}`                   | GetItem |
| 2   | MVIs       | `T#{tenant}#P#{project}` | `begins_with(S#PLAN#MS#{ms}#GL#{gl}#MVI#)` | Query   |
| 3   | Murder ref | `T#{tenant}#P#{project}` | `S#{wave}#{council}#{murder}`              | GetItem |

MVI items bridge planning → execution via `execution.wave_id` and `execution.murder_id` fields.

---

### S32 — MVI Blackboard (MOST CRITICAL)

| #   | Purpose       | PK                       | SK                                            | Op                     |
| --- | ------------- | ------------------------ | --------------------------------------------- | ---------------------- |
| 1   | MVI header    | `T#{tenant}#P#{project}` | `S#{wave}#council#murder#{mid}`               | GetItem                |
| 2   | Crows + tasks | `T#{tenant}#P#{project}` | `begins_with(S#{wave}#council#murder#{mid}#)` | Query                  |
| 3   | Live feed     | `T#{tenant}#P#{project}` | `begins_with(EVT#{wave}#)`                    | Query (desc, limit 50) |

**3 DynamoDB calls render the entire screen.** Crow snapshot = task record.

**Ship MVI:** TransactWriteItems with condition `canShip=true AND status="ready_to_ship"`.

**Real-time:** SSE via DynamoDB Streams → Lambda → SSE endpoint. Events: crow_state, task_update, live_feed.

---

### S33 — Task Detail

| #   | Purpose       | PK                       | SK                                         | Op      |
| --- | ------------- | ------------------------ | ------------------------------------------ | ------- |
| 1   | Task snapshot | `T#{tenant}#P#{project}` | `S#{wave}#M#{murder}#C#{crow}#TASK#{task}` | GetItem |

PR metadata denormalized on task record. No separate PR query for S33.

---

### S34 — PR Review

| #   | Purpose          | PK                       | SK                                       | Op      |
| --- | ---------------- | ------------------------ | ---------------------------------------- | ------- |
| 1   | PR detail        | `T#{tenant}#P#{project}` | `S#{wave}#M#{murder}#C#{crow}#PR#{pr}`   | GetItem |
| 2   | Reviewer verdict | `T#{tenant}#P#{project}` | `S#{wave}#M#{murder}#C#reviewer#PR#{pr}` | GetItem |
| 3   | Conversation     | `T#{tenant}#P#{project}` | `begins_with(CONV#PR#{pr}#MSG#)`         | Query   |
| 4   | Send chat msg    | `T#{tenant}#P#{project}` | `CONV#PR#{pr}#MSG#{ts}`                  | PutItem |

**Plan vs execution:** Pre-assembled by reviewer crow, stored on reviewer's PR snapshot.

**Steer/Reject:** Appends new crow snapshots with `#R{n}` retry suffix. Never overwrites.

**Approve:** TransactWriteItems updating PR status + EVT record + murder snapshot rollup.

**Real-time:** SSE for AI chat streaming + PR status updates during active review.

---

### S40 — Murders List

| #   | Purpose         | PK                    | SK                       | Op    |
| --- | --------------- | --------------------- | ------------------------ | ----- |
| 1   | All murders     | `T#{tenant}#DYNASTY`  | `begins_with(MURDER#)`   | Query |
| 2   | Behavior states | GSI: `STATUS#running` | filter by murder_id      | Query |
| 3   | Marketplace     | `MARKETPLACE`         | `begins_with(TEMPLATE#)` | Query |

---

### S41 — Create/Edit Murder

| #   | Purpose     | PK                   | SK             | Op      |
| --- | ----------- | -------------------- | -------------- | ------- |
| 1   | Load murder | `T#{tenant}#DYNASTY` | `MURDER#{mid}` | GetItem |
| 2   | Save murder | `T#{tenant}#DYNASTY` | `MURDER#{mid}` | PutItem |

Crows embedded in murder record (max ~10 per murder).

**Config vs execution:** Murder config is a mutable template. Execution freezes a snapshot at start.

---

### S42 — Create Crow

| #   | Purpose     | PK                   | SK             | Op                       |
| --- | ----------- | -------------------- | -------------- | ------------------------ |
| 1   | Load parent | `T#{tenant}#DYNASTY` | `MURDER#{mid}` | GetItem                  |
| 2   | Add crow    | `T#{tenant}#DYNASTY` | `MURDER#{mid}` | UpdateItem (list_append) |

---

### S50 — Skills List

| #   | Purpose     | PK                   | SK                    | Op    |
| --- | ----------- | -------------------- | --------------------- | ----- |
| 1   | All skills  | `T#{tenant}#DYNASTY` | `begins_with(SKILL#)` | Query |
| 2   | Marketplace | `MARKETPLACE`        | `begins_with(SKILL#)` | Query |

Category filtering done client-side (small dataset).

---

### S51 — Add/Edit Skill

| #   | Purpose    | PK                   | SK            | Op      |
| --- | ---------- | -------------------- | ------------- | ------- |
| 1   | Load skill | `T#{tenant}#DYNASTY` | `SKILL#{sid}` | GetItem |
| 2   | Save skill | `T#{tenant}#DYNASTY` | `SKILL#{sid}` | PutItem |

`usedByCrowCount` computed at read time, not stored.

---

### S60 — Settings

| #   | Purpose      | PK                      | SK         | Op      |
| --- | ------------ | ----------------------- | ---------- | ------- |
| 1   | User profile | `T#{tenant}#USER#{uid}` | `PROFILE`  | GetItem |
| 2   | Org settings | `T#{tenant}#DYNASTY`    | `SETTINGS` | GetItem |

---

### S61 — Credits & Billing

| #   | Purpose         | PK                   | SK                      | Op      |
| --- | --------------- | -------------------- | ----------------------- | ------- |
| 1   | Credit balance  | `T#{tenant}#BILLING` | `CREDITS`               | GetItem |
| 2   | Billing rollup  | `T#{tenant}#BILLING` | `ROLLUP#CURRENT`        | GetItem |
| 3   | Project budgets | `T#{tenant}#BILLING` | `begins_with(PROJECT#)` | Query   |
| 4   | Crow costs      | `T#{tenant}#BILLING` | `begins_with(CROW#)`    | Query   |

**Credit balance:** Atomic counter pattern (SET available = available - :cost with condition available >= :cost).

**Rollups:** Event-driven incremental updates via EventBridge on task completion. Never full re-scan.

---

### S70 — Notifications

| #   | Purpose             | PK                         | SK                     | Op                       |
| --- | ------------------- | -------------------------- | ---------------------- | ------------------------ |
| 1   | Inbox               | `T#{tenant}#NOTIFICATIONS` | `begins_with(N#)` desc | Query (paginated)        |
| 2   | Act on notification | `T#{tenant}#NOTIFICATIONS` | `N#{ts}#{id}`          | TransactWriteItems       |
| 3   | Badge count         | `T#{tenant}#DYNASTY`       | `META`                 | GetItem (atomic counter) |

Notifications are **explicitly created** on state transitions, not derived from snapshots. TTL at 30 days.

**Real-time:** APNs push (backgrounded) + SSE (foregrounded).

---

## Key Architectural Patterns

### 1. Materialized Views (Streams-powered)

- **SUMMARY** record per project (S10 Dashboard)
- **HUB** record per project (S12 Project Hub)
- **Counters** on milestones/goals (S24/S30/S31)
- **Billing rollups** (S61)
- **Notification badge count** (S70)

### 2. Dual Hierarchy (Planning + Execution)

- Planning: `S#PLAN#MS#{ms}#GL#{gl}#MVI#{mvi}` — human-facing roadmap
- Execution: `S#{wave}#{council}#{murder}#{crow}` — system-facing runtime
- **MVI is the bridge** — belongs to one Goal (planning) and one Wave (execution)

### 3. Config vs Snapshot

- Murder/Skill configs live in DYNASTY (mutable templates)
- Execution freezes config into snapshot at start (immutable)
- Edits affect future executions only

### 4. Separate Partitions for Cross-Project Data

- Notifications: `T#{tenant}#NOTIFICATIONS` (cross-project inbox)
- Billing: `T#{tenant}#BILLING` (cross-project cost)
- Config: `T#{tenant}#DYNASTY` (org-wide settings)

### 5. Real-Time via DynamoDB Streams

Same writes that maintain snapshots power SSE. No polling, no separate event bus for UI.

---

## Query Count Summary

| Screen             | Reads | Writes            | Real-Time       |
| ------------------ | ----- | ----------------- | --------------- |
| S01 Splash         | 0     | 0                 | No              |
| S02 Sign In        | 0     | 0 (Cognito)       | No              |
| S10 Dashboard      | 2     | 0                 | SSE (optional)  |
| S11 Create Project | 0     | 3 (transaction)   | No              |
| S12 Project Hub    | 1     | 0                 | WebSocket       |
| S20-S23 Documents  | 2     | 2                 | SSE (AI stream) |
| S24 Backlog        | 1     | 0                 | No              |
| S30 Milestone      | 3     | 0                 | No              |
| S31 Goal Detail    | 3     | 1 (approve)       | No              |
| S32 MVI Blackboard | 3     | 1 (ship)          | SSE             |
| S33 Task Detail    | 1     | 0                 | No              |
| S34 PR Review      | 3     | 2 (action + chat) | SSE             |
| S40 Murders        | 3     | 0                 | No              |
| S41 Create Murder  | 1     | 1                 | No              |
| S42 Create Crow    | 1     | 1                 | No              |
| S50 Skills         | 2     | 0                 | No              |
| S51 Add Skill      | 1     | 1                 | No              |
| S60 Settings       | 2     | 0                 | No              |
| S61 Billing        | 4     | 0                 | No              |
| S70 Notifications  | 2     | 1 (transaction)   | SSE + Push      |
