# Auto Mode — Wave-to-Wave Autonomous Execution

> Spec for continuous wave execution with council-based quality gating and smart continuation planning.

---

## Overview

Auto mode enables Cawnex projects to execute continuously without human intervention. When a wave completes, the system reviews the output against standards, plans the next wave intelligently, and launches it — repeating until the backlog is empty or budget is exhausted.

Three components close the loop: Murder detects wave completion and triggers quality review, a new Council Lambda evaluates output via 6 specialized advisors, and Monarch plans and launches the next wave in continuation mode.

---

## Project Settings

### Auto Mode Field

Added to the project root snapshot (`SK: S#`):

```python
"auto_mode": "off"  # "off" | "auto" | "supervised"
```

- **`off`** (default) — wave delivers, system stops. Human launches next wave manually.
- **`auto`** — wave delivers, Council is the quality gate, Monarch plans and launches next wave. No human in the loop.
- **`supervised`** — same as auto, but human receives notifications on council escalations and can intervene via override protocol.

**API:** `PATCH /projects/{project_id}` accepts `auto_mode` updates. Disabling mid-wave does not interrupt current wave — takes effect after wave completion.

### Project Maturity Stage

Inferred by Monarch (not user-set), stored on the project root snapshot:

```python
"maturity_stage": "mvp"  # "mvp" | "growth" | "scale" | "mature"
```

Monarch updates this during continuation planning based on signals:
- Waves completed count
- Total MVIs shipped
- Test coverage trend (from deterministic check history)
- Codebase size growth
- Frequency of council rejections

The maturity stage influences what the council considers acceptable (e.g., 60% test coverage is fine for MVP, 80% required at scale).

**API:** `maturity_stage` is read-only (Monarch-managed).

---

## Deterministic MVI Checks (Per-MVI Gate)

When an MVI reaches `ready_to_ship` (reviewer crow approves), Murder runs a deterministic check suite before writing the final status. This happens inside the existing `_handle_mvi_ready()` flow.

### Check Suite

| Check | Source | Hard/Soft |
|-------|--------|-----------|
| Tests pass | Crow outcome `test_results` (exit code) | Hard |
| No secrets in diff | Regex + entropy scan on changed files (`detect-secrets`) | Hard |
| Integration check | Git merge all in-flight MVI branches + build | Hard |
| Lint passes | Crow outcome `lint_results` (exit code) | Soft |
| Coverage doesn't drop | Crow outcome `coverage_delta` (before/after comparison) | Soft |
| Acceptance criteria addressed | Structured check against MVI `acceptance_criteria` | Soft |

### Failure Flow

```
Hard block fails → fixer crow loop (max 2 retries via existing FIX_CYCLE_LIMIT)
  → still failing → escalate as soft signal to council wave review

Soft signal fails → recorded as warnings, forwarded to council at wave review
```

### MVI Snapshot Additions

```python
"deterministic_checks": {
    "passed": ["tests_pass", "no_secrets", "integration"],
    "failed": [],
    "warnings": ["coverage_drop"],
    "run_at": "2026-04-09T..."
}
```

### Integration Check

Murder maintains a wave-level integration branch. As each MVI reaches `ready_to_ship`, its branch is merged into the integration branch and a build is triggered. Merge conflicts or build failures are hard blocks — the fixer crow receives the conflict/build error as context. The integration branch is ephemeral — created per wave, deleted after delivery.

---

## Council Lambda — Wave Quality Gate

New Lambda: `cawnex-council-{stage}`

Triggered by DynamoDB Stream inserts where `SK` begins with `COUNCIL#`.

### Trigger Record

```python
{
    "PK": "T#{tenant}#P#{project}",
    "SK": "COUNCIL#{session_id}",
    "level": "council",
    "status": "pending",
    "type": "wave_review",  # or "wave_planning", "escalation"
    "wave_id": "w1710340540000",
    "context": {
        "wave_summary": { ... },
        "mvi_check_results": [ ... ],
        "project_maturity": "mvp",
        "backlog_remaining": [ ... ],
        "human_directive": "...",
        "project_memory": "..."
    }
}
```

### Protocol

Implements the full council protocol from `docs/design/council-protocol.md`:

1. 6 advisors (Security, Quality, Performance, Market, Maturity, Clarity) run in parallel
2. Each advisor uses 5-layer prompt structure (identity, org standards, project context, advisor memory, decision context)
3. Security and Clarity have veto (BLOCK) power
4. Monarch synthesis: check vetoes, weigh scores by confidence, identify disagreements
5. Up to 3 debate rounds if needed
6. After decision, execute action

### Vote Types

| Vote | Meaning | Effect |
|------|---------|--------|
| `APPROVE` | No concerns | Counts toward consensus |
| `APPROVE_WITH_CONDITION` | Proceed if condition met | Condition recorded, Monarch decides |
| `ABSTAIN` | Not enough context | Ignored in tally |
| `BLOCK` | Hard stop (Security/Clarity only) | Forces debate or escalation |

### Post-Decision Actions

| Decision | Action |
|----------|--------|
| `approve` | Transition wave to `delivered`, write `MONARCH#continuation` task |
| `approve_with_conditions` | Same as approve, conditions attached to continuation context |
| `reject` | Transition wave to `steered`, write rejection reasons with flagged MVIs and advisor concerns |
| `escalate` | `supervised` mode: notify human. `auto` mode: Monarch makes final call based on advisor scores |

### Reject Flow

Council identifies specific MVIs and issues. Wave transitions to `steered`. Murder picks up steered MVIs and assigns fixer crows with council feedback as context. When fixes land: deterministic checks re-run, wave re-enters `review`, council reconvenes. Max 2 council rejections per wave before escalating to human regardless of `auto_mode`.

### Advisor Memory Update

After each session, the Lambda appends learnings to `dynasty/{org}/agents/{advisor_type}.md`. Pruned when over ~2000 token budget (old entries summarized).

### Storage

Full council session stored per council protocol design:

```python
{
    "PK": "T#{tenant}#P#{project}",
    "SK": "COUNCIL#{session_id}",
    "level": "council",
    "status": "completed",
    "type": "wave_review",
    "rounds": [ ... ],
    "decision": { ... },
    "cost": { ... },
    "created_at": "...",
    "completed_at": "...",
    "entityType": "Snapshot"
}
```

---

## Murder Lambda — Wave Completion & Council Trigger

Two additions to the existing Murder Lambda.

### Enhanced `_maybe_transition_wave()`

Currently transitions waves to `review` when all MVIs are terminal. Extended:

```
All MVIs terminal
  ├── auto_mode = "off" → transition to "review", stop (current behavior)
  └── auto_mode = "auto" | "supervised"
       → transition to "review"
       → gather all MVI deterministic check results
       → write COUNCIL#{session_id} task with type="wave_review"
```

Reads `auto_mode` from the project root snapshot (`SK: S#`). If `off`, behavior is unchanged.

### React to Wave Steered

When the council rejects and transitions the wave to `steered`, Murder handles it via existing stream processing:

1. Read council decision to identify flagged MVIs and issues
2. Transition flagged MVIs back to `executing`
3. Assign fixer crows with council feedback as instructions
4. Transition wave back to `executing`

Existing `FIX_CYCLE_LIMIT` plus max 2 council rejections prevent infinite loops.

### No New Handler Routes

Murder doesn't react to council completion directly. The Council Lambda writes wave status changes (`delivered` or `steered`), and Murder's existing stream handler picks up the `steered` transition naturally.

---

## Monarch Lambda — Continuation Mode

New entry path alongside existing initial setup flow.

### Trigger Record

```python
{
    "PK": "T#{tenant}#P#{project}",
    "SK": "MONARCH#continuation_{timestamp}",
    "status": "pending",
    "mode": "continuation",
    "delivered_wave_id": "w1710340540000",
    "council_decision": {
        "action": "approve",
        "conditions": [...],
        "dissent_record": {...}
    },
    "backlog_remaining": [
        {"milestone_id": "ms_01", "goals": [
            {"goal_id": "g_03", "mvis": ["mvi_07", "mvi_08"]},
            {"goal_id": "g_04", "mvis": ["mvi_09"]}
        ]}
    ],
    "project_memory": "..."
}
```

### Continuation Flow (`run_monarch_continuation()`)

1. **Reflection** — Read delivered wave results (shipped, failed, cost, duration, council feedback). Append learnings to project memory.

2. **Maturity assessment** — Evaluate project signals, update `maturity_stage` on root snapshot if warranted.

3. **Budget check** — Estimate next wave cost based on historical MVI costs. If estimated cost exceeds remaining credits, notify user and stop.

4. **Wave planning via Council** — Write `COUNCIL#` task with `type=wave_planning`, including remaining backlog, project maturity, and reflection learnings. Council scores and prioritizes remaining MVIs (smart selection — not sequential, but weighing dependencies, security foundations, business value, maturity concerns). Council writes its approved wave plan into a new `MONARCH#wave_launch_{timestamp}` task, which triggers step 5.

5. **Wave creation** (separate Monarch invocation, triggered by `MONARCH#wave_launch_*` INSERT) — Reads the council-approved wave plan. Using existing `wave_launcher.py` logic: create wave snapshot, create MVI snapshots with branches, transition to `executing`, scale ECS workers. No LLM needed for this step.

### Handler Routing

```python
def lambda_handler(event, context):
    task = deserialize(record)
    mode = task.get("mode")
    if mode == "continuation":
        run_monarch_continuation(task)  # reflection + maturity + budget + council planning
    elif mode == "wave_launch":
        run_monarch_wave_launch(task)   # council-approved plan → create wave + execute
    else:
        run_monarch(task)               # existing initial setup flow
```

### Three Monarch Modes

| Mode | Trigger SK | Purpose | LLM needed |
|------|-----------|---------|------------|
| Initial | `MONARCH#setup_*` | Generate docs, milestones, first wave | Yes |
| Continuation | `MONARCH#continuation_*` | Reflection, maturity check, budget check, request council wave planning | Yes |
| Wave launch | `MONARCH#wave_launch_*` | Create wave from council-approved plan | No |

---

## Infrastructure & Deployment

### New Council Lambda (CDK)

```
Lambda: cawnex-council-{stage}
  Runtime:     Python 3.12
  Memory:      1024 MB (6 parallel LLM calls)
  Timeout:     120s (3 debate rounds worst case)
  Trigger:     DynamoDB Stream, filter SK begins_with "COUNCIL#", INSERT only
  Environment: TABLE_NAME, EVENTS_TABLE_NAME, ANTHROPIC_MODEL
  Permissions: DynamoDB read/write, Events table write
```

### Monarch Lambda Timeout

Increased from 29s to 120s. Safe since Monarch is triggered by Streams (not API Gateway).

### Council Lambda Source Structure

```
lambdas/council/
  src/council/
    handler.py          — Stream event entry, deserialize, route
    orchestrator.py     — Run rounds, collect votes, synthesis
    advisors.py         — Build advisor prompts, parallel Anthropic API calls
    synthesis.py        — Veto check, score weighting, disagreement detection
    actions.py          — Post-decision actions (deliver, steer, write continuation)
    prompts/
      advisors/
        security.md
        quality.md
        performance.md
        market.md
        maturity.md
        clarity.md
```

### DynamoDB Stream Filters

| Lambda | Filter |
|--------|--------|
| Murder | SK begins_with `S#` (snapshots) |
| Monarch | SK begins_with `MONARCH#` |
| Council | SK begins_with `COUNCIL#` |

No overlap — each Lambda receives only its events.

### No New Tables or GSIs

Everything fits the existing single-table design with established SK patterns.

---

## Full Event Chain

```
WAVE EXECUTING
  │
  ├── Crows work MVIs (Planner → Implementer → Reviewer → Fixer loop)
  │
  ├── Each MVI reaches ready_to_ship
  │     └── Murder runs deterministic checks
  │           ├── Hard block fails → fixer loop (max 2 retries)
  │           │     └── still failing → escalate as warning
  │           └── Results stored on MVI snapshot
  │
  ├── All MVIs terminal
  │     └── Murder: _maybe_transition_wave()
  │           ├── auto_mode = "off" → wave to "review", STOP
  │           └── auto_mode = "auto"|"supervised"
  │                 → wave to "review"
  │                 → write COUNCIL#task (type: wave_review)
  │
  ▼
COUNCIL WAVE REVIEW
  │
  ├── 6 advisors evaluate in parallel
  │     Input: MVI check results, wave summary, project maturity
  │
  ├── Monarch synthesis
  │     ├── approve → wave to "delivered"
  │     │              write MONARCH#continuation task
  │     │
  │     ├── reject → wave to "steered"
  │     │             Murder assigns fixers with council feedback
  │     │             (max 2 council rejections before escalate)
  │     │             → cycle back to WAVE EXECUTING
  │     │
  │     └── escalate → notify human (supervised) or Monarch decides (auto)
  │
  ▼
MONARCH CONTINUATION
  │
  ├── Reflection: learnings from delivered wave → project memory
  ├── Maturity assessment: update stage if warranted
  ├── Budget check: estimate next wave cost vs remaining credits
  │     └── insufficient → notify user, STOP
  │
  ├── Backlog empty? → project complete, STOP
  │
  └── Write COUNCIL#task (type: wave_planning)
       │
       ▼
COUNCIL WAVE PLANNING
  │
  ├── 6 advisors score/prioritize remaining MVIs
  │     Input: remaining backlog, project maturity, reflection learnings
  │
  └── Monarch synthesis → approved wave plan
       └── Write MONARCH#wave_launch task
            │
            ▼
MONARCH WAVE LAUNCH
  │
  ├── Create wave + MVI snapshots from council-approved plan
  ├── Transition wave to "executing"
  ├── Scale ECS workers
  │
  ▼
WAVE EXECUTING (next wave — cycle repeats)
```

### Termination Conditions

The chain stops when:
- `auto_mode` is `off`
- Backlog is empty (all goals/MVIs shipped) — project complete
- Budget exhausted (insufficient credits for estimated next wave)
- Council escalates to human and no response within configurable timeout
- Max 2 council rejections on same wave (hard safety valve)
- User manually pauses or cancels via API/iOS

### Latency Per Cycle Transition

- Deterministic checks: ~30-60s (build + test)
- Council wave review: ~15-45s (1-3 rounds)
- Monarch continuation: ~30-60s (reflection + council planning + wave creation)
- Total overhead between waves: ~1.5-3 minutes
