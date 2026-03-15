# Wave Lifecycle — State Machine

> Waves are the heartbeat of Cawnex. Each wave is a deliverable batch of work
> that flows through planning, approval, execution, review, and delivery.

---

## Problems Solved

| #   | Problem                                             |
| --- | --------------------------------------------------- |
| 2   | Human must stay in control (approve, steer, reject) |
| 7   | Failure resilience (retry, fix, escalate)           |
| 15  | New projects: zero to first commit                  |
| 16  | Existing projects: evolve without breaking things   |
| 22  | Resource discipline — budgets, limits, escalation   |

---

## Wave States

```
                    Human steers
                   ┌──────────┐
                   │           ▼
PLANNING ──► PROPOSED ──► APPROVED ──► EXECUTING ──► REVIEW ──► DELIVERED
   │              │           │            │            │
   │              ▼           ▼            ▼            ▼
   │          REVISED     REJECTED      PAUSED      STEERED
   │              │                       │            │
   │              └──► PROPOSED           └──► EXECUTING
   │                                                   │
   └──────────────────────────────────────────────────►│
                                                       ▼
                                                   CANCELLED
```

### State Definitions

| State       | Owner             | What's Happening                                              |
| ----------- | ----------------- | ------------------------------------------------------------- |
| `planning`  | Monarch + Council | Council voting on wave contents, Monarch assembling plan      |
| `proposed`  | Human             | Wave plan ready for founder review                            |
| `revised`   | Monarch           | Human requested changes, Monarch adjusting                    |
| `approved`  | Murder            | Human approved, Murder preparing to dispatch                  |
| `rejected`  | Monarch           | Human rejected the plan entirely                              |
| `executing` | Murder + Crows    | Crows actively working on MVIs                                |
| `paused`    | Human             | Human said "stop." Active crows finish current task then halt |
| `review`    | Human             | All MVIs complete, founder reviewing before merge             |
| `steered`   | Monarch           | Human changed direction mid-wave                              |
| `delivered` | Terminal          | All MVIs shipped, merged to main                              |
| `cancelled` | Terminal          | Wave abandoned                                                |

### Valid Transitions

```
planning   → proposed                    Council reached decision
planning   → cancelled                   Human or Monarch decided not to proceed

proposed   → approved                    Human approved the plan
proposed   → revised                     Human wants changes
proposed   → rejected                    Human rejected entirely

revised    → proposed                    Monarch revised, re-proposes
revised    → cancelled                   Revision not feasible

rejected   → planning                    Restart with human feedback

approved   → executing                   Murder starts dispatching

executing  → review                      All MVIs complete
executing  → paused                      Human paused
executing  → steered                     Human changed direction
executing  → cancelled                   Human cancelled mid-execution

paused     → executing                   Human resumed
paused     → steered                     Human changed direction while paused
paused     → cancelled                   Human cancelled while paused

steered    → executing                   Monarch adjusted, resumes with new plan
steered    → proposed                    Major change, needs re-approval

review     → delivered                   Human approved all deliverables
review     → steered                     Human wants changes before accepting

delivered  → (terminal)
cancelled  → (terminal)
```

---

## MVI States (Within a Wave)

Each MVI within a wave has its own lifecycle:

```
DRAFT ──► REFINED ──► QUEUED ──► EXECUTING ──► READY_TO_SHIP ──► SHIPPED
  │          │           │           │               │
  │          │           │           ▼               ▼
  │          │           │        FAILED         REJECTED
  │          │           │           │               │
  │          │           │           └──► QUEUED     └──► QUEUED (retry)
  │          │           │                              or CANCELLED
  └──────────┴───────────┴──────────────────────────► CANCELLED
```

| State           | Meaning                                                        |
| --------------- | -------------------------------------------------------------- |
| `draft`         | Identified but not detailed. Just a name and rough scope       |
| `refined`       | Council evaluated, tasks planned, estimates assigned           |
| `queued`        | Approved and waiting for Murder to start                       |
| `executing`     | Crows actively working (has active crow snapshots)             |
| `failed`        | Execution failed after max retries. Needs human decision       |
| `ready_to_ship` | All tasks done, PRs reviewed, CI green, merge checklist passed |
| `rejected`      | Human rejected at review. Back to queue or cancelled           |
| `shipped`       | Merged to main. Terminal                                       |
| `cancelled`     | Abandoned. Terminal                                            |

### MVI Ordering Constraints

The Council can set ordering constraints between MVIs:

```json
{
  "ordering": [
    {
      "before": "mvi_auth",
      "after": "mvi_payment",
      "reason": "Rate limiting must exist before payment"
    },
    {
      "parallel": ["mvi_onboarding", "mvi_auth"],
      "reason": "Independent, can run concurrently"
    }
  ]
}
```

Murder respects these: it won't start `mvi_payment` until `mvi_auth` status = `shipped`.

---

## The Full Flow

### 1. Planning

```
Trigger:  Previous wave delivered, or human gives new directive
Actor:    Monarch

Steps:
  1. Read human directive
  2. Read project memory (what's done, what's pending)
  3. Read backlog (available MVIs from planning hierarchy)
  4. Decide: does this need Council?
     └─ Yes (prioritization, architecture) → convene Council
     └─ No (simple, clear next steps) → Monarch plans directly
  5. Select MVIs for the wave
  6. Set ordering constraints
  7. Estimate budget

Output: wave snapshot, status: planning → proposed
```

### 2. Proposed → Human Review

```
Trigger:  Monarch completes plan
Actor:    Human (via iOS S70 notification)

Human sees:
  - Wave name and directive
  - MVIs included with estimates
  - Council reasoning (if Council convened)
  - Budget estimate vs available credits
  - Ordering constraints and why

Human can:
  - Approve        → status = approved
  - Request revision ("add X, remove Y") → status = revised
  - Reject ("wrong direction entirely")  → status = rejected
  - Add constraints ("auth must include 2FA")
```

### 3. Approved → Executing

```
Trigger:  Human approval
Actor:    Murder

Steps:
  1. Read wave plan (MVIs, ordering, constraints)
  2. Freeze murder config into execution snapshot
  3. For each MVI (respecting ordering):
     a. Create murder-level snapshot
     b. Dispatch first crow (planner or implementer)
     c. MVI status → executing
  4. Parallel MVIs start simultaneously
  5. Sequential MVIs wait for predecessor to ship

Wave status: approved → executing
```

### 4. Executing

```
Within each MVI, the POC5+6 pattern runs:

  Murder writes TASK → Worker picks up → Crow executes
  → Writes REPORT → Murder judges → next step

Cycles per task:
  plan → implement → review → [approve | reject+fix] → complete

Guard rails active:
  - Token budget per crow
  - Time limit per crow
  - Max retries (3 for dev, 2 for others)
  - Loop detection
  - Budget check against wave limit

Events written to EVT#{wave}#{timestamp} for live feed
```

### 5. Paused

```
Trigger:  Human taps "Pause"
Effect:
  - Active crows finish their CURRENT task (graceful, don't kill mid-execution)
  - No NEW tasks dispatched
  - Murder enters paused state — reads blackboard but doesn't assign

Resume:
  - Human taps "Resume"
  - Murder picks up where it left off
  - Checks if context changed (new commits? new issues?)
```

### 6. Steered

```
Trigger:  Human says "drop payment, add notifications instead"

Effect:
  1. Active crows finish current task
  2. Pending MVIs cancelled
  3. Monarch receives steer with human's new direction
  4. If minor (swap one MVI):
     → Monarch adjusts, resumes executing
  5. If major (different direction):
     → Goes back to proposed for re-approval

Steer record:
  {
    "steer": {
      "from_human": "Drop payment, add notifications instead",
      "affected_mvis": {
        "cancelled": ["mvi_payment"],
        "added": ["mvi_notifications"],
        "unchanged": ["mvi_auth", "mvi_onboarding"]
      },
      "monarch_response": "Adjusted wave plan. Auth and onboarding continue.",
      "timestamp": "2026-03-20T14:30:00Z"
    }
  }
```

### 7. Review

```
Trigger:  All MVIs reach ready_to_ship or shipped
Actor:    Human

Human sees:
  - All delivered MVIs with PRs
  - Cost summary vs estimate
  - ROI breakdown
  - Any concerns raised during execution

Human can:
  - Accept all → each MVI ships, wave → delivered
  - Steer ("this MVI needs changes") → targeted MVI back to queued
  - Ship partial ("ship auth and onboarding, redo payment")
```

### 8. Delivered

```
Trigger:  Human accepts all deliverables

Effect:
  1. All MVI branches merged to main (synchronized merge)
  2. Wave snapshot updated with final cost, ROI, outcomes
  3. Monarch reflection: extract learnings
  4. Advisor memories updated
  5. Monarch begins planning next wave (cycle repeats)
  6. Notification: "Wave 3 delivered — $18.50 spent, ~$12k saved"
```

---

## Wave Budget Enforcement

Budget is enforced at every level:

```
Wave budget limit: $50 (set by human or Monarch)
  │
  ├── MVI budget: proportional allocation
  │     └── Task budget: per-crow limits from murder config
  │
  ├── At 80%: Monarch notified, considers scope reduction
  ├── At 100%: Murder stops dispatching new tasks
  │             Escalates to human: "budget exhausted, X tasks remaining"
  │
  └── Human can: increase budget, reduce scope, or cancel
```

Budget checks happen:

- **Before each task dispatch** — Murder checks wave budget
- **After each crow completes** — Murder updates wave spend
- **Approaching limit** — Murder may restructure remaining work

---

## Wave → Next Wave Continuity

When a wave delivers, the cycle restarts:

```
Wave 3 delivered
    │
    ├── Monarch reflection
    │     - What worked? What didn't?
    │     - Update advisor memories
    │     - Update project memory
    │
    ├── Check backlog
    │     - Deferred MVIs from previous waves?
    │     - New goals/MVIs from human?
    │     - Bug reports or issues?
    │
    └── Begin Wave 4 planning
          - Fresh council session (if needed)
          - Propose next wave
          - Human approves
          - Execute
```

Continuity maintained by:

1. **Project memory** — learnings accumulate across waves
2. **Advisor memories** — each advisor gets smarter
3. **Backlog** — deferred MVIs carry forward
4. **Human directive** — may change between waves

---

## DynamoDB: Wave Snapshot

```json
{
  "PK": "T#acme#P#cawnex",
  "SK": "S#w003",
  "level": "wave",
  "status": "executing",

  "human_directive": "Ship onboarding in 2 weeks",
  "deadline": "2026-03-28",

  "plan": {
    "mvis": ["mvi_auth", "mvi_onboarding", "mvi_payment"],
    "ordering": [{ "before": "mvi_auth", "after": "mvi_payment" }],
    "estimated_budget": 45.0,
    "estimated_human_equiv": 12000.0
  },

  "council_ref": "S#w003#council_001",

  "progress": {
    "mvis_total": 3,
    "mvis_shipped": 1,
    "mvis_executing": 1,
    "mvis_queued": 1,
    "tasks_done": 8,
    "tasks_total": 15
  },

  "budget": {
    "spent": 18.5,
    "limit": 50.0,
    "human_equiv_saved": 4800.0,
    "roi": 259
  },

  "steers": [
    {
      "from_human": "Drop payment, add notifications",
      "affected_mvis": {
        "cancelled": ["mvi_payment"],
        "added": ["mvi_notifications"]
      },
      "timestamp": "2026-03-20T14:30:00Z"
    }
  ],

  "state_history": [
    {
      "from": "planning",
      "to": "proposed",
      "at": "2026-03-14T10:00:00Z",
      "actor": "monarch"
    },
    {
      "from": "proposed",
      "to": "approved",
      "at": "2026-03-14T10:05:00Z",
      "actor": "human"
    },
    {
      "from": "approved",
      "to": "executing",
      "at": "2026-03-14T10:05:01Z",
      "actor": "murder"
    }
  ],

  "created_at": "2026-03-14T09:55:00Z",
  "entityType": "Snapshot"
}
```

---

## Design Principles

1. **11 wave states, 9 MVI states** — explicit, no ambiguity
2. **Every transition has an owner** — Monarch, Human, or Murder
3. **Pause is graceful** — finish current task, don't kill mid-execution
4. **Steer is first-class** — not an exception, a designed flow with records
5. **Budget enforcement at every level** — wave, MVI, task
6. **State history preserved** — full audit trail of transitions
7. **Ordering constraints** — Council can mandate MVI sequencing
8. **Continuity between waves** — memory, backlog, and directive carry forward
