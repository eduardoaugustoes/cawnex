# Implementation Plan — Orchestration Core V1

> Production-grade code, narrow scope. Contracts-first.
> Not another POC. The real system, built incrementally.
> Define interfaces, then build in parallel, then integrate.

---

## Philosophy

**We've done enough POCs.** POC3 proved MCP. POC5 proved stream-triggered Murder. POC6 proved EFS+worktrees. The next thing we build is the actual system.

**Contracts-first.** The system is event-driven — components communicate through DynamoDB records, not function calls. If we define the record shapes and trigger patterns first, every component can be built and tested independently. Integration bugs — the expensive bugs — are eliminated by design.

**Production-grade** means clean code, proper error handling, structured logging, and shared models. It does NOT mean over-engineering, distributed tracing, or blue-green deployments.

---

## Goal

A founder can trigger a wave, watch crows execute, and ship an MVI — all through the V2 recursive snapshot data model. This is the foundation everything else builds on.

---

## What V1 IS

One complete path through the system:

```
Create project → Create wave → Assign MVI →
Planner crow executes → Implementer crow executes →
Reviewer crow executes → Human approves → Ship MVI →
Wave delivered
```

## What V1 IS NOT

- No Council (Murder decides directly, human is the monarch)
- No agent memory / learnings (crows start fresh each time)
- No iOS integration (API exists but iOS stays on in-memory)
- No marketplace, notifications, documents, billing rollups
- No steer / pause / revised states (basic wave lifecycle only)
- No prompt caching optimization (correctness first, optimize later)

---

## Production Standards

| Standard           | What It Means for V1                                      | What It Does NOT Mean                   |
| ------------------ | --------------------------------------------------------- | --------------------------------------- |
| **Clean code**     | Shared models, modules, separation of concerns            | Plugin framework or abstract factories  |
| **Error handling** | Every failure path returns a meaningful message           | Dead letter queues or circuit breakers  |
| **Logging**        | Structured JSON with tenant/project/execution IDs         | Distributed tracing with X-Ray          |
| **Tests**          | Contract tests + integration tests                        | 80% unit test coverage on day 1         |
| **Security**       | Tenant isolation via partition keys, no hardcoded secrets | WAF, rate limiting, penetration testing |
| **Deployment**     | CDK stack that deploys cleanly                            | Blue-green or canary deployments        |
| **Local dev**      | Everything runs locally against DynamoDB Local            | Full AWS emulation                      |
| **Budget caps**    | Enforced from day 1, not deferred                         | Complex billing system                  |

---

## The 6 Contracts

The DynamoDB records ARE the interface. Each contract defines: who writes, what shape, what triggers, pre/post conditions.

### Contract 1: Project & Wave Creation

```
Writer:      API Lambda
Trigger:     HTTP request from user
Mechanism:   TransactWriteItems

Records created:

1. Project list entry
   PK: T#{tenant}#PROJECTS
   SK: P#{project_id}
   {
     project_id, name, description, repo,
     murders: ["dev"],
     status: "active",
     phase: "execution",
     created_at
   }

2. Project root snapshot
   PK: T#{tenant}#P#{project_id}
   SK: S#
   {
     level: "root",
     status: "active",
     name, description, repo,
     created_at
   }

3. Wave snapshot
   PK: T#{tenant}#P#{project_id}
   SK: S#{wave_id}
   {
     level: "wave",
     status: "planning",              ← THIS TRIGGERS MURDER
     human_directive,
     plan: { mvis: [...] },
     progress: { mvis_total, mvis_shipped: 0, tasks_done: 0, tasks_total: 0 },
     budget: { spent: 0, limit: 20.00 },
     created_at
   }

4. MVI snapshot (one per MVI in wave)
   PK: T#{tenant}#P#{project_id}
   SK: S#{wave_id}#m#{mvi_id}
   {
     level: "murder",
     status: "queued",
     name, description, acceptance_criteria,
     tasks_done: 0, tasks_total: 0,
     can_ship: false,
     merge_checklist: [],
     cost: { tokens_in: 0, tokens_out: 0, credits: 0, duration_ms: 0 },
     repo, branch: "cawnex/{wave_id}-{mvi_id}",
     created_at
   }

Preconditions:
  - tenant exists (JWT validated)
  - project_id unique
  - repo accessible via GitHub token

Postconditions:
  - Wave snapshot with status=planning exists
  - DynamoDB Stream delivers wave record to Murder
```

### Contract 2: Crow Assignment

```
Writer:      Murder Lambda
Trigger:     DynamoDB Stream (wave status=planning, or crow status=completed)
Mechanism:   PutItem with conditional check on budget

Record created:

  Crow snapshot
  PK: T#{tenant}#P#{project_id}
  SK: S#{wave_id}#m#{mvi_id}#cr#{crow_id}
  {
    level: "crow",
    status: "pending",                  ← THIS TRIGGERS WORKER (via GSI)
    crow_type: "planner"|"implementer"|"reviewer"|"fixer",
    behavior_state: "assigned",
    task_name,
    instructions,
    repo, branch,
    retry_count: 0,
    cost: { tokens_in: 0, tokens_out: 0, credits: 0, duration_ms: 0 },
    budget_remaining: <wave_budget - spent_so_far>,
    created_at
  }

  GSI record (for Worker pickup):
  GSI1PK: DISPATCH#pending
  GSI1SK: T#{tenant}#P#{project_id}#S#{wave_id}#m#{mvi_id}#cr#{crow_id}

  EVT record:
  PK: T#{tenant}#P#{project_id}
  SK: EVT#{wave_id}#{iso_timestamp}
  {
    type: "crow_assigned",
    crow_type, task_name,
    message: "Murder assigned planner for MVI 1.1",
    color: "purple"
  }

Preconditions:
  - Wave budget not exceeded
  - Max retries not exceeded for this crow type
  - Previous crow in pipeline completed (or this is the first)

Postconditions:
  - Crow snapshot with status=pending exists
  - GSI1 makes it visible to Worker
  - Parent MVI snapshot tasks_total incremented
```

### Contract 3: Crow Completion

```
Writer:      Worker Lambda
Trigger:     GSI1 DISPATCH#pending (picks up crow snapshot)
Mechanism:   UpdateItem with condition status=pending→running, then status=running→completed

Record updated:

  Crow snapshot (same PK/SK as Contract 2)
  {
    status: "completed"|"failed",
    behavior_state: "landed"|"error",
    outcome: {
      summary: "Created 3 tasks for OAuth implementation",

      # Planner-specific:
      plan: { tasks: [...], files_to_read: [...], files_to_modify: [...] },

      # Implementer-specific:
      files_changed: ["src/auth.py", "tests/test_auth.py"],
      commit_sha: "abc123",

      # Reviewer-specific:
      approved: true|false,
      issues: ["No test for token expiry"],
      suggestions: ["Consider decorator pattern"],
      plan_vs_execution: [...],

      # Fixer-specific:
      files_changed: [...],
      commit_sha: "def456",
      issues_addressed: ["Added token expiry test"]
    },
    pr: {                               # implementer/fixer only
      number: 14,
      title: "Add OAuth token validation",
      url: "https://github.com/...",
      branch: "cawnex/w001-auth"
    },
    git_commit: "abc123",
    cost: {
      tokens_in: 5000,
      tokens_out: 2000,
      credits: 0.12,
      duration_ms: 30000
    },
    completed_at
  }

  GSI record removed:
  GSI1PK: (deleted — no longer DISPATCH#pending)

  EVT record:
  PK: T#{tenant}#P#{project_id}
  SK: EVT#{wave_id}#{iso_timestamp}
  {
    type: "crow_completed"|"crow_failed",
    crow_type, task_name,
    message: "Implementer completed OAuth middleware — PR #14 created",
    color: "green"|"red",
    cost: { credits: 0.12 }
  }

Preconditions:
  - Crow snapshot exists with status=pending
  - Conditional update: status=pending→running (prevents double pickup)
  - Repo accessible, worktree creatable

Postconditions:
  - Crow snapshot status=completed|failed
  - EVT record written
  - DynamoDB Stream delivers to Murder (triggers next assignment)
  - DynamoDB Stream delivers to Stream Processor (updates counters)
```

### Contract 4: MVI Ready to Ship

```
Writer:      Murder Lambda
Trigger:     DynamoDB Stream (reviewer crow status=completed with approved=true)
Mechanism:   UpdateItem on MVI snapshot

Record updated:

  MVI snapshot
  PK: T#{tenant}#P#{project_id}
  SK: S#{wave_id}#m#{mvi_id}
  {
    status: "ready_to_ship",            ← updated
    can_ship: true,                     ← updated
    merge_checklist: [
      { label: "All tasks completed", passed: true },
      { label: "PR created", passed: true },
      { label: "Reviewer approved", passed: true }
    ],
    tasks_done: <final count>,
    cost: <aggregated from all crow snapshots>
  }

  EVT record:
  {
    type: "mvi_ready",
    message: "MVI 1.1 ready to ship — all tasks completed, PR approved",
    color: "green"
  }

Preconditions:
  - Reviewer crow approved (outcome.approved = true)
  - All tasks in MVI completed

Postconditions:
  - MVI snapshot status=ready_to_ship
  - Stream Processor updates wave progress
  - Human can now call ship endpoint
```

### Contract 5: Ship MVI

```
Writer:      API Lambda
Trigger:     HTTP POST from user
Mechanism:   TransactWriteItems with condition

Records updated:

  1. MVI snapshot
     PK: T#{tenant}#P#{project_id}
     SK: S#{wave_id}#m#{mvi_id}
     {
       status: "shipped",              ← updated
       shipped_at,
       pr_url: "https://github.com/..."
     }
     CONDITION: status = "ready_to_ship" AND can_ship = true

  2. Wave snapshot
     PK: T#{tenant}#P#{project_id}
     SK: S#{wave_id}
     {
       progress.mvis_shipped: += 1     ← incremented
     }

  3. EVT record
     {
       type: "mvi_shipped",
       message: "MVI 1.1 shipped — PR #14 created",
       color: "green"
     }

Side effect (async):
  - Create PR on GitHub (if not already created by implementer)
  - OR mark existing PR as ready for human review

Preconditions:
  - MVI status = ready_to_ship
  - can_ship = true

Postconditions:
  - MVI status = shipped
  - Wave mvis_shipped incremented
  - If all MVIs shipped → wave status = delivered
  - PR exists on GitHub for human review
```

### Contract 6: Materialized View Updates

```
Writer:      Stream Processor Lambda
Trigger:     DynamoDB Stream (any snapshot status change)
Mechanism:   UpdateItem with atomic ADD/SET

Records updated:

  On crow completion (Contract 3 triggers this):
    MVI snapshot — tasks_done += 1, cost += crow.cost
    Project SUMMARY — tasks_done += 1, credits_spent += crow.cost.credits

  On MVI ready_to_ship (Contract 4 triggers this):
    Wave snapshot — progress updated

  On MVI shipped (Contract 5 triggers this):
    Wave snapshot — mvis_shipped += 1
    If all shipped: wave status → delivered
    Project SUMMARY — updated

  Project SUMMARY record:
  PK: T#{tenant}#P#{project_id}
  SK: SUMMARY
  {
    tasks_done, tasks_active, tasks_total,
    credits_spent, human_equiv_saved,
    active_crow_count,
    updated_at
  }

Preconditions:
  - Stream event contains NEW_AND_OLD_IMAGES
  - Status actually changed (not a no-op update)

Postconditions:
  - Parent snapshot counters reflect child state
  - SUMMARY reflects current project state
```

---

## Communication Pattern Diagram

```
                  Contract 1                    Contract 2
    User ──────► API Lambda ──────► DynamoDB ──────► Murder Lambda
                                      │                   │
                                      │ Stream             │ writes crow
                                      │                   │ snapshot
                                      │                   ▼
                                      │              DynamoDB
                                      │                   │
                                      │ GSI1               │ Stream
                                      │ DISPATCH#pending   │
                                      ▼                   │
                  Contract 3     Worker Lambda ◄───────────┘
                                      │
                                      │ updates crow snapshot
                                      │ writes EVT record
                                      ▼
                                 DynamoDB
                                      │
                              ┌───────┼───────┐
                              │ Stream│       │ Stream
                              ▼       ▼       ▼
                  Contract 6  Stream   Murder  (back to Contract 2
                              Proc.   Lambda   for next crow)
                              │
                              │ updates SUMMARY,
                              │ MVI counters,
                              │ wave progress
                              ▼
                  Contract 5  DynamoDB ◄──── API Lambda (ship)
                                                  ▲
                                                  │
                                               User
```

**Key insight:** Every arrow goes through DynamoDB. No Lambda calls another Lambda directly. The table is the message bus.

---

## Shared Models Package

```
lambdas/orchestration/shared/

  models.py          Snapshot dataclasses (Wave, MVI, Crow, EVT, Summary)
  enums.py           CrowType, WaveStatus, MVIStatus, CrowStatus, BehaviorState
  db.py              DynamoDB CRUD (read, write, query, conditional_update, transact)
  events.py          EVT record builders (crow_assigned, crow_completed, mvi_ready, etc.)
  contracts.py       Contract validation (assert preconditions, verify postconditions)
  logging.py         Structured JSON logger with tenant/project/execution context
  parsing.py         JSON extraction from Claude output (with fallbacks)
  github.py          GitHub API helpers (issues, branches, PRs)
  config.py          Environment variables, constants, budget limits
  cost.py            Cost calculation (tokens → credits, budget checks)
```

### Key: `contracts.py`

```python
"""
Contract validation — ensures every DynamoDB write
matches the agreed interface between components.
"""

def validate_crow_assignment(snapshot: dict) -> None:
    """Contract 2: Murder writes a crow snapshot."""
    assert snapshot["level"] == "crow"
    assert snapshot["status"] == "pending"
    assert snapshot["crow_type"] in VALID_CROW_TYPES
    assert snapshot["instructions"], "Instructions cannot be empty"
    assert snapshot["budget_remaining"] > 0, "No budget remaining"
    assert snapshot["repo"], "Repo is required"
    assert snapshot["branch"], "Branch is required"

def validate_crow_completion(snapshot: dict) -> None:
    """Contract 3: Worker completes a crow snapshot."""
    assert snapshot["status"] in ("completed", "failed")
    assert snapshot["cost"]["credits"] > 0, "Cost must be tracked"
    assert snapshot["completed_at"], "Completion timestamp required"
    if snapshot["status"] == "completed":
        assert snapshot["outcome"], "Completed crow must have outcome"

def validate_mvi_ship(snapshot: dict) -> None:
    """Contract 5: API ships an MVI."""
    assert snapshot["status"] == "ready_to_ship"
    assert snapshot["can_ship"] == True
```

These run in every Lambda before writing. If a contract is violated, the write fails with a clear error message — not a silent data corruption.

---

## File Structure

```
lambdas/
  orchestration/
    shared/                         Shared models + contracts (all Lambdas import this)
      __init__.py
      models.py                     Snapshot dataclasses
      enums.py                      Status enums
      db.py                         DynamoDB CRUD helpers
      events.py                     EVT record builders
      contracts.py                  Contract validation
      logging.py                    Structured JSON logger
      parsing.py                    Claude output parsing
      github.py                     GitHub API helpers
      config.py                     Env vars, constants, budget limits
      cost.py                       Cost calculation + budget checks

    murder/
      handler.py                    Lambda entry point (stream trigger)
      state_machine.py              Crow pipeline logic
      context_builder.py            Assembles context for crow assignment

    worker/
      handler.py                    Lambda entry point (GSI trigger)
      executor.py                   Claude execution (prompt, call, parse)
      git_ops.py                    Git operations (clone, worktree, commit, push)
      context.py                    Context gathering per crow type
      prompts/
        planner.md
        implementer.md
        reviewer.md
        fixer.md
      Dockerfile
      requirements.txt

    stream-processor/
      handler.py                    Lambda entry point (stream trigger)
      aggregator.py                 Materialized view updates

    api/
      handler.py                    FastAPI + Mangum entry point
      routes/
        projects.py                 POST /projects
        waves.py                    POST /projects/{id}/waves
        mvi.py                      GET + POST (ship)
      models/
        requests.py                 Pydantic request/response models

    tests/
      conftest.py                   DynamoDB Local fixtures, test data builders
      test_contracts.py             Contract validation tests
      test_murder.py                Murder state machine tests
      test_worker.py                Worker execution tests
      test_stream_processor.py      Aggregation tests
      test_api.py                   API endpoint tests
      test_pipeline.py              End-to-end integration tests

infra/
  lib/
    orchestration-stack.ts          CDK (DynamoDB, Lambdas, API GW, EFS, VPC)
```

---

## Milestones (Contracts-First)

### Milestone 1: Contracts + Shared Models + Table (Week 1)

**Goal:** All interfaces defined. Shared package built. Table deployed. Any developer can start building against the contracts.

- [ ] `shared/models.py` — snapshot dataclasses (Wave, MVI, Crow, EVT, Summary)
- [ ] `shared/enums.py` — all status enums with valid transitions
- [ ] `shared/db.py` — DynamoDB CRUD with V2 PK/SK patterns
- [ ] `shared/contracts.py` — validation for all 6 contracts
- [ ] `shared/events.py` — EVT record builders
- [ ] `shared/config.py` — env vars, budget limits ($0.50/crow, $5/MVI, $20/wave)
- [ ] `shared/cost.py` — token→credit calculation, budget check
- [ ] `shared/logging.py` — structured JSON logger
- [ ] CDK stack: DynamoDB table with V2 schema + GSI + Stream
- [ ] `tests/test_contracts.py` — every contract validates correctly
- [ ] `tests/conftest.py` — DynamoDB Local fixtures
- [ ] Deploy `-dev` table to AWS

**Verify:**

- `pytest tests/test_contracts.py` — all contract shapes validate
- DynamoDB table visible in AWS Console with correct schema
- API dev can start building against `shared/models.py` immediately

**Unblocks:**

- Murder development (week 2)
- Worker development (week 2)
- API development (week 2, by other dev)

### Milestone 2: Murder + Worker (Week 2-3)

**Can be built in parallel** because they communicate only through contracts.

#### Murder track:

- [ ] `murder/handler.py` — stream trigger, deserialize, route to state machine
- [ ] `murder/state_machine.py` — determine_next_action (planner → impl → review → fix)
- [ ] `murder/context_builder.py` — assemble instructions per crow type
- [ ] Contract 2 implementation: write crow snapshots with validation
- [ ] Contract 4 implementation: mark MVI ready_to_ship
- [ ] Budget check before every assignment
- [ ] `tests/test_murder.py` — state machine transitions

#### Worker track:

- [ ] `worker/handler.py` — GSI trigger, deserialize, route to executor
- [ ] `worker/executor.py` — Claude client, prompt builder, output parser
- [ ] `worker/git_ops.py` — clone, worktree, commit, push (from POC6)
- [ ] `worker/context.py` — context gathering per crow type
- [ ] Crow prompts: `planner.md`, `implementer.md`, `reviewer.md`, `fixer.md`
- [ ] Contract 3 implementation: update crow snapshots with validation
- [ ] `Dockerfile` + `requirements.txt`
- [ ] `tests/test_worker.py` — executor and context tests

**Verify:**

- Murder: write wave snapshot → Murder assigns planner (Contract 2 validated)
- Worker: write pending crow → Worker executes → crow completed (Contract 3 validated)
- Both: insert records manually, verify contracts hold

### Milestone 3: Integration + Pipeline (Week 3-4)

**Goal:** Connect Murder + Worker via real DynamoDB Streams. Full pipeline runs.

- [ ] CDK: deploy Murder Lambda (stream trigger) + Worker Lambda (EFS + VPC)
- [ ] Stream Processor: `aggregator.py` — Contract 6 implementation
- [ ] Connect streams: crow completion → Murder reacts → assigns next crow
- [ ] Full crow pipeline: plan → implement → review → [fix] → ready_to_ship
- [ ] EVT records for live feed at every step
- [ ] Retry logic: max 3 for implementer/fixer, max 2 for reviewer
- [ ] Guard: token budget per crow, time limit per crow
- [ ] `tests/test_pipeline.py` — end-to-end against test repo

**Verify:**

- Create wave for GitHub issue "Add GET /health endpoint"
- Full pipeline runs: planner → implementer → reviewer → approved
- PR created on `cawnex-test-target` repo
- All contracts validated at every step
- Cost tracked: crow → MVI → wave sums correctly

### Milestone 4: API + Ship (Week 4-5)

**Goal:** HTTP API works. Full loop closable.

- [ ] FastAPI app: 4 endpoints (Contract 1 and Contract 5)
- [ ] Pydantic request/response models
- [ ] Mangum adapter for Lambda deployment
- [ ] Ship flow: conditional update + PR creation on GitHub
- [ ] GET endpoint returns full snapshot tree (one query)
- [ ] CDK: API Gateway + API Lambda
- [ ] `tests/test_api.py` — endpoint tests

**Verify:**

```bash
# Create project
curl -X POST /projects -d '{"name":"Test","repo":"eduardoaugustoes/cawnex-test-target"}'

# Trigger wave
curl -X POST /projects/{id}/waves -d '{"directive":"Add health endpoint","mvis":[...]}'

# Poll status
curl /projects/{id}/waves/{wave_id}
# Returns: full tree with crows, tasks, events, costs

# Ship
curl -X POST /projects/{id}/waves/{wave_id}/mvis/{mvi_id}/ship
# Returns: PR URL
```

### Milestone 5: SSE + Hardening (Week 5)

**Goal:** Real-time feed works. System handles failures gracefully.

- [ ] SSE endpoint: stream EVT records to connected clients
- [ ] Guard system: loop detection (3 similar outputs → cancel)
- [ ] Dead letter queue on Stream Lambdas + CloudWatch alarm
- [ ] Graceful failure: EVT records with human-readable error messages
- [ ] Cost validation: verify crow→MVI→wave sums at end of pipeline
- [ ] Structured logging audit: every log line has tenant/project/execution IDs
- [ ] Reconciliation: nightly Lambda verifies SUMMARY matches snapshot state

**Verify:**

- Open SSE connection, trigger wave, see events stream live
- Trigger a failure (timeout, bad output), verify escalation + EVT record
- Check CloudWatch: every log line is structured JSON with correct IDs

---

## What This Unblocks for the Other Dev

After Milestone 1 (week 1), the API/frontend dev can immediately:

1. **Build iOS API service implementations** — shared models define exactly what the API returns
2. **Build remaining API endpoints** — contract shapes define the DynamoDB queries
3. **Mock data that matches production** — use `shared/models.py` to generate seed data identical to what Murder will produce
4. **Build SSE client** — EVT record format is defined in contracts

They don't need to wait for Murder or Worker. The contracts are the handshake.

---

## Testing Strategy

### Contract tests (run first, always)

```python
def test_contract_2_crow_assignment():
    """Murder must write valid crow snapshots."""
    snapshot = build_crow_snapshot(
        crow_type="planner",
        status="pending",
        instructions="Plan the auth implementation",
        repo="eduardoaugustoes/cawnex-test-target",
        branch="cawnex/w001-auth",
    )
    validate_crow_assignment(snapshot)  # from contracts.py

def test_contract_3_crow_completion():
    """Worker must write valid completed snapshots."""
    snapshot = build_crow_snapshot(
        crow_type="planner",
        status="completed",
        outcome={"plan": {...}},
        cost={"tokens_in": 5000, "tokens_out": 2000, "credits": 0.12},
    )
    validate_crow_completion(snapshot)

def test_contract_invalid_fails():
    """Invalid snapshots must be rejected."""
    with pytest.raises(AssertionError):
        validate_crow_assignment({"status": "completed"})  # wrong status
```

### Integration tests (DynamoDB Local)

```python
def test_murder_assigns_planner_on_new_wave():
    """Contract 1 → Contract 2: wave creation triggers planner assignment."""
    write_wave_snapshot(status="planning")
    murder_react(stream_event)
    crow = read_latest_crow_snapshot()
    assert crow["crow_type"] == "planner"
    assert crow["status"] == "pending"
    validate_crow_assignment(crow)

def test_worker_completes_crow():
    """Contract 2 → Contract 3: pending crow gets executed."""
    write_crow_snapshot(status="pending", crow_type="planner")
    worker_execute(stream_event)
    crow = read_crow_snapshot()
    assert crow["status"] == "completed"
    assert crow["cost"]["credits"] > 0
    validate_crow_completion(crow)
```

### End-to-end tests (real AWS, real Claude)

```
Test: "Full pipeline on simple task"
  Issue: "Add GET /health endpoint returning {status: ok}"
  Verify: PR created on cawnex-test-target with actual code changes
  Contracts: all 6 validated at every step
  Cost: < $1 total
  Time: < 10 minutes
```

### Test repo

`eduardoaugustoes/cawnex-test-target` — simple Python FastAPI project.

---

## Risk Register

| Risk                                | Impact                         | Mitigation                                           |
| ----------------------------------- | ------------------------------ | ---------------------------------------------------- |
| Schema is wrong                     | Must recreate table            | Validate with real pipeline on `-dev` table first    |
| Contracts don't cover edge cases    | Integration bugs at boundaries | Contract tests run before every deploy               |
| Murder/Worker/Stream tight coupling | One change breaks all          | Shared models + contract validation                  |
| Claude output malformed             | Pipeline stalls                | JSON parsing with fallbacks (proven in POC6)         |
| Worker Lambda timeout (15 min)      | Complex tasks fail             | Small test repo, monitor timing                      |
| DynamoDB Stream duplicate delivery  | Double-processing              | Conditional updates (idempotent)                     |
| Runaway execution                   | Burns credits                  | Budget caps from day 1: $0.50/crow, $5/MVI, $20/wave |
| Stream processor misses update      | Materialized view drifts       | Nightly reconciliation Lambda                        |
| No rollback for shipped MVI         | Broken target repo             | Ship = create PR, not merge. Human reviews.          |

---

## Success Criteria

V1 is done when:

- [ ] All 6 contracts defined, validated, and tested
- [ ] A wave can be triggered via API call
- [ ] Murder assigns crows in sequence (plan → implement → review)
- [ ] Each crow receives scoped context (not full repo)
- [ ] Implementer creates a PR with real code changes
- [ ] Reviewer approves or rejects with structured feedback
- [ ] Fixer handles rejections (max 3 retries)
- [ ] Budget caps enforced (stops at limit, escalates)
- [ ] MVI can be shipped via API (PR created on GitHub)
- [ ] Full execution trace visible in DynamoDB (recursive snapshots)
- [ ] Cost tracked at every level (crow → murder → wave)
- [ ] Materialized SUMMARY stays in sync
- [ ] End-to-end latency < 10 minutes for a simple task
- [ ] Total cost < $1 per execution (Sonnet pricing)
- [ ] System runs locally against DynamoDB Local
- [ ] Contract validation runs in every Lambda before writes

---

## What Unlocks After V1

| V2 Feature             | What V1 Enables                                                   |
| ---------------------- | ----------------------------------------------------------------- |
| Council protocol       | Add council snapshot level + Contract 2.1 (council voting)        |
| Agent memory           | Add MEM# records, load in Layer 2-4 of context assembly           |
| iOS integration        | API serves data matching iOS protocol contracts exactly           |
| Notifications          | Stream Processor creates notification records (Contract 6.1)      |
| Multiple MVIs per wave | Murder already supports sequential ordering                       |
| Steer / pause          | Additional wave states, same state machine + contracts            |
| Billing rollups        | Stream Processor updates BILLING partition (Contract 6.2)         |
| Training data export   | Snapshot tree already contains ask+reasoning+code+outcome         |
| Second developer       | Contracts enable independent work with zero coordination overhead |
