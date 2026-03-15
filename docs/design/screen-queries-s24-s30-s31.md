# Screen Query Analysis — S24 Backlog, S30 Milestone Detail, S31 Goal Detail

> DynamoDB single-table mapping for the planning hierarchy screens.

---

## 1. Screen Purposes

- **S24 — Backlog:** Milestone list with expandable goals. The roadmap view for a project.
- **S30 — Milestone Detail:** AI-guided milestone refinement with goal list, progress stats, and chat.
- **S31 — Goal Detail:** MVI cards within a goal showing ROI per MVI, with Approve/Steer/Reject actions.

---

## 2. Data Needed

### S24 — Backlog

| Field                  | Type     | Source                           |
| ---------------------- | -------- | -------------------------------- |
| milestones[]           | array    | All milestones for this project  |
| milestone.name         | string   | "M1: Foundation"                 |
| milestone.status       | enum     | in_progress, planned, completed  |
| milestone.description  | string   | "Platform can accept..."         |
| milestone.tasksDone    | number   | Aggregated from child goals/MVIs |
| milestone.tasksTotal   | number   | Aggregated from child goals/MVIs |
| milestone.creditsSpent | currency | Aggregated from child goals/MVIs |
| milestone.goals[]      | Goal[]   | Nested goals within milestone    |

### S30 — Milestone Detail

All of S24's milestone fields, plus:

| Field              | Type     | Source                          |
| ------------------ | -------- | ------------------------------- |
| milestone.mviCount | number   | Total MVIs across all goals     |
| milestone.cost     | currency | Total credits spent             |
| goal.name          | string   | "API Infrastructure"            |
| goal.status        | enum     | in_progress, planned, completed |
| goal.mviCount      | number   | MVIs within this goal           |
| chatMessages       | array    | AI refinement conversation      |

### S31 — Goal Detail

| Field                    | Type       | Source                                |
| ------------------------ | ---------- | ------------------------------------- |
| goal.name                | string     | "API Infrastructure"                  |
| goal.status              | enum       | in_progress, planned, completed       |
| goal.mviCount            | number     | Total MVIs                            |
| goal.cost                | currency   | Total credits                         |
| goal.murderAssignment    | object     | {name, crowCount, isActive}           |
| mvis[]                   | array      | MVI cards within this goal            |
| mvi.name                 | string     | "MVI 1.1: REST API Endpoints"         |
| mvi.status               | enum       | completed, executing, refining, draft |
| mvi.tasksDone            | number     | 4                                     |
| mvi.tasksTotal           | number     | 4                                     |
| mvi.aiMinutes            | number     | 23                                    |
| mvi.humanDays            | string     | "~3 days"                             |
| mvi.aiCost               | currency   | $18                                   |
| mvi.humanEquiv           | currency   | ~$1.2k                                |
| mvi.progress             | percentage | 100%                                  |
| mvi.roi                  | number     | 67                                    |
| mvi.pendingApprovalCount | number     | 0                                     |

---

## 3. DynamoDB Queries

### Table Schema Recap

```
Main Table: cawnex
PK: T#{tenant_id}#P#{project_id}
SK: S#{wave_id}#{council_id}#{murder_id}#{crow_id}   (snapshots)
    E#{timestamp}#{event_type}                         (events)
    M#{memory_key}                                     (memory)
```

### S24 — Backlog

**Problem:** Milestones and goals are planning concepts. They do not map 1:1 to the snapshot tree (wave/council/murder/crow). The snapshot tree captures _execution state_, not _planning hierarchy_.

**Query 1 — Load all milestones for a project:**

| Operation | PK                             | SK                        | Notes          |
| --------- | ------------------------------ | ------------------------- | -------------- |
| Query     | `T#{tenant_id}#P#{project_id}` | `begins_with(S#PLAN#MS#)` | All milestones |

Each milestone item would have SK like `S#PLAN#MS#{milestone_id}` and contain the milestone metadata plus an embedded `goals[]` array (or goal IDs for separate lookup).

**Query 2 — Load goals for a milestone (if not embedded):**

| Operation | PK                             | SK                                          | Notes                  |
| --------- | ------------------------------ | ------------------------------------------- | ---------------------- |
| Query     | `T#{tenant_id}#P#{project_id}` | `begins_with(S#PLAN#MS#{milestone_id}#GL#)` | Goals within milestone |

**Aggregation:** `tasksDone`, `tasksTotal`, `creditsSpent` are rolled up from MVIs/waves. Two options:

- **Pre-computed:** Stored on the milestone/goal item, updated on every task completion event.
- **On-read:** Traverse wave snapshots and aggregate. Expensive, avoid for list screens.

Recommendation: **Pre-computed counters** on milestone and goal items, updated via DynamoDB Streams handler when wave/task state changes.

### S30 — Milestone Detail

**Query 1 — Load milestone + goals:**

| Operation | PK                             | SK                                          | Notes                  |
| --------- | ------------------------------ | ------------------------------------------- | ---------------------- |
| GetItem   | `T#{tenant_id}#P#{project_id}` | `S#PLAN#MS#{milestone_id}`                  | Milestone metadata     |
| Query     | `T#{tenant_id}#P#{project_id}` | `begins_with(S#PLAN#MS#{milestone_id}#GL#)` | Goals within milestone |

**Query 2 — Load chat history for milestone refinement:**

| Operation | PK                             | SK                                       | Notes         |
| --------- | ------------------------------ | ---------------------------------------- | ------------- |
| Query     | `T#{tenant_id}#P#{project_id}` | `begins_with(M#CHAT#MS#{milestone_id}#)` | Chat messages |

### S31 — Goal Detail

**Query 1 — Load goal metadata:**

| Operation | PK                             | SK                                      | Notes         |
| --------- | ------------------------------ | --------------------------------------- | ------------- |
| GetItem   | `T#{tenant_id}#P#{project_id}` | `S#PLAN#MS#{milestone_id}#GL#{goal_id}` | Goal metadata |

**Query 2 — Load MVIs for this goal:**

| Operation | PK                             | SK                                                        | Notes     |
| --------- | ------------------------------ | --------------------------------------------------------- | --------- |
| Query     | `T#{tenant_id}#P#{project_id}` | `begins_with(S#PLAN#MS#{milestone_id}#GL#{goal_id}#MVI#)` | MVI items |

**Query 3 — Load murder assignment:**

Each MVI links to a wave. The murder assignment is either embedded on the goal item or resolved by reading the wave's council/murder snapshot.

| Operation | PK                             | SK                                     | Notes                                        |
| --------- | ------------------------------ | -------------------------------------- | -------------------------------------------- |
| GetItem   | `T#{tenant_id}#P#{project_id}` | `S#{wave_id}#{council_id}#{murder_id}` | Murder execution state for ROI/progress data |

### Write Operations

| Screen | Operation   | PK                             | SK                         | Action                         |
| ------ | ----------- | ------------------------------ | -------------------------- | ------------------------------ |
| S31    | Approve All | `T#{tenant_id}#P#{project_id}` | `S#{wave_id}#...` per task | Update task status to approved |
| S24    | + Milestone | `T#{tenant_id}#P#{project_id}` | `S#PLAN#MS#{new_id}`       | PutItem                        |

---

## 4. Key Challenge: Planning vs Snapshot Tree

The snapshot tree uses the path `{wave_id}#{council_id}#{murder_id}#{crow_id}` — this is an **execution hierarchy**:

```
Wave (batch of deliverable work)
  └── Council (advisory session that shaped this wave)
       └── Murder (execution orchestrator)
            └── Crow (individual worker)
```

Milestones and goals are a **planning hierarchy**:

```
Milestone (strategic deliverable, e.g., "M1: Foundation")
  └── Goal (capability within milestone, e.g., "API Infrastructure")
       └── MVI (merge-ready increment, 2-5 day deliverable)
            └── Task (single unit of work, max 8h human equiv)
```

These are **orthogonal**. A wave might contain MVIs from _different_ goals, or even _different_ milestones, depending on what the Monarch and Council prioritize for that execution batch. The snapshot tree does not inherently know about milestones or goals.

---

## 5. Planning vs Execution: The Reconciliation Problem

### The two hierarchies

```
PLANNING (static, human-facing)         EXECUTION (dynamic, system-facing)
Milestone → Goal → MVI → Task          Wave → Council → Murder → Crow → Task
```

### Why they diverge

- **Waves are temporal.** A wave is "what we do this week." It can pull MVIs from multiple goals.
- **Milestones are strategic.** They represent a capability milestone regardless of when tasks execute.
- **A single wave can advance multiple milestones.** Wave 2 might contain MVI 1.3 (from Goal A in Milestone 1) and MVI 2.1 (from Goal B in Milestone 2).
- **A single milestone spans multiple waves.** Milestone 1 might take waves 1, 2, and 3 to complete.

### The mapping is many-to-many

```
Milestone 1 ──┬── Goal A ──┬── MVI 1.1 ──── Wave 1
              │            └── MVI 1.2 ──── Wave 2
              └── Goal B ──── MVI 1.3 ──── Wave 2

Milestone 2 ──── Goal C ──── MVI 2.1 ──── Wave 2
                             MVI 2.2 ──── Wave 3
```

The MVI is the **join point** between the two hierarchies. Each MVI belongs to exactly one Goal (planning) and is executed within exactly one Wave (execution).

---

## 6. Recommendation: Dual-Path Storage with MVI as Bridge

### Store planning items separately from execution snapshots

Planning items use a `S#PLAN#` prefix in the SK, living alongside but distinct from execution snapshots:

```
PK: T#{tenant_id}#P#{project_id}

Planning items:
  SK: S#PLAN#MS#{milestone_id}                              → Milestone metadata + counters
  SK: S#PLAN#MS#{milestone_id}#GL#{goal_id}                 → Goal metadata + murder ref
  SK: S#PLAN#MS#{milestone_id}#GL#{goal_id}#MVI#{mvi_id}    → MVI metadata + wave_id ref

Execution snapshots (existing):
  SK: S#{wave_id}                                           → Wave metadata
  SK: S#{wave_id}#{council_id}                              → Council session
  SK: S#{wave_id}#{council_id}#{murder_id}                  → Murder execution state
  SK: S#{wave_id}#{council_id}#{murder_id}#{crow_id}        → Crow task state
```

### The MVI item bridges both worlds

```json
{
  "PK": "T#acme#P#cawnex",
  "SK": "S#PLAN#MS#m1#GL#g1#MVI#mvi_1_1",
  "name": "MVI 1.1: REST API Endpoints",
  "status": "completed",

  "planning": {
    "milestone_id": "m1",
    "goal_id": "g1",
    "order": 1
  },

  "execution": {
    "wave_id": "w1",
    "council_id": "c1",
    "murder_id": "dev1"
  },

  "counters": {
    "tasksDone": 4,
    "tasksTotal": 4,
    "aiMinutes": 23,
    "aiCost": 18.0,
    "humanEquivCost": 1200.0,
    "roi": 67
  }
}
```

### Why this works

1. **S24 (Backlog)** queries `begins_with(S#PLAN#MS#)` — gets all planning items in one Query call. No need to traverse the wave tree.
2. **S31 (Goal Detail)** queries `begins_with(S#PLAN#MS#{ms_id}#GL#{gl_id}#MVI#)` — gets all MVIs for a goal with their execution state already embedded.
3. **S32 (MVI Blackboard)** uses the `execution.wave_id` from the MVI item to pivot into the snapshot tree: `S#{wave_id}#{council_id}#{murder_id}` for live crow/task state.
4. **Counters roll up** via DynamoDB Streams: when a task completes in the execution tree, a Lambda updates the MVI, Goal, and Milestone counter fields.
5. **No fan-out queries.** The planning screens never need to scan execution snapshots. The execution screens never need to know about milestones.

### GSI for reverse lookup (Wave → MVIs)

If we need to answer "which MVIs are in Wave 3?" (for the Monarch/Murder to track wave completion):

| GSI          | PK                                         | SK                                          |
| ------------ | ------------------------------------------ | ------------------------------------------- |
| GSI-WaveMVIs | `T#{tenant_id}#P#{project_id}#W#{wave_id}` | `S#PLAN#MS#{ms_id}#GL#{gl_id}#MVI#{mvi_id}` |

This is a sparse GSI — only MVI items that have `execution.wave_id` get projected.

### Summary

| Concept         | Where it lives                       | SK pattern                                       |
| --------------- | ------------------------------------ | ------------------------------------------------ |
| Milestone       | Planning path                        | `S#PLAN#MS#{id}`                                 |
| Goal            | Planning path                        | `S#PLAN#MS#{id}#GL#{id}`                         |
| MVI             | Planning path (bridges to execution) | `S#PLAN#MS#{id}#GL#{id}#MVI#{id}`                |
| Wave            | Execution path                       | `S#{wave_id}`                                    |
| Council session | Execution path                       | `S#{wave_id}#{council_id}`                       |
| Murder state    | Execution path                       | `S#{wave_id}#{council_id}#{murder_id}`           |
| Crow/Task state | Execution path                       | `S#{wave_id}#{council_id}#{murder_id}#{crow_id}` |

The planning hierarchy is the **human-facing view**. The execution hierarchy is the **system-facing view**. The MVI is the hinge between them.
