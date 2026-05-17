# Stage 4 Layer A — Tool-Equipped Wave Council Design

**Status:** Design spec, agreed 2026-05-16
**Companion docs:** [CAWNEX-BUILDS-ITSELF-PLAN.md](../../CAWNEX-BUILDS-ITSELF-PLAN.md) (the strategic plan) · [council-protocol.md](../../design/council-protocol.md) (the original Council spec) · [DARK-FACTORY-COMPARISON.md](../../DARK-FACTORY-COMPARISON.md) (the audit) · [BACKGROUND-AGENTS-LEARNINGS.md](../../BACKGROUND-AGENTS-LEARNINGS.md) (the frames)

## Overview

This is the implementation-grade design for Stage 4 Layer A from the strategic plan: a tool-equipped, wave-level Council that fires after every PR in a wave is ready to ship but before the founder merges anything. Two new components: an **Integrator crow** that sets up workspace and runs deterministic checks, and a **Council Fargate service** that runs six advisors with scoped investigation tools.

The existing Council Lambda at `lambdas/council/` (15 modules + 9 test files, wave-review-shaped, packet-only, deployed but never run on a real wave) is the source material. Roughly half its code ports cleanly to the new Fargate service; the Lambda shell scraps; advisors.py becomes the rewrite hotspot to add tool-use loops.

The principle running through every section: **at this stage Cawnex should be a loud system that surfaces every failure, not a quiet one that swallows them.**

## Scope

In Layer A:

- New `crow_kind=integrator` on the existing Worker Fargate service (per-PR worktrees, integration merge, lint/typecheck/test on merged branch, structured `IntegratorFindings`)
- New `cawnex-council-${stage}` Fargate service (dedicated task, read-only IAM, 6 advisors in parallel asyncio tasks, scoped tool palettes, 15-call/180s caps per advisor)
- Wave state machine extension: three new states (`integrating`, `needs_rework`, `under_council_review`)
- Murder reactor dispatch for three new transitions
- Loud-failure rule: every error path emits a structured `council_pipeline_error` event to the events table and logs at ERROR level
- Test coverage matching the test pyramid (many unit, some integration, a few end-to-end), plus a manual smoke test gate

Explicitly out of Layer A:

- iOS Council panel UI (Layer B)
- Graduated auto-merge (Layer C)
- Cost-routed model dispatch (all advisors use Haiku 4.5 in Layer A)
- Per-advisor model selection (Sonnet for Plan adversary, Opus for tiebreak, etc.)
- Performance/load tests under concurrency
- Plan adversary (Stage 2)
- Living context for docs (Stage 1)

## Architecture

The wave loop gains two components and one new wave-state branch. Everything else (Murder, existing Worker crow kinds, Reviewer crow, founder gate) stays unchanged.

```
                                            ┌────────────────────────┐
   ... → executing → review                 │  Murder reactor        │
                       │                    │  (DDB Stream trigger)  │
                       │ all MVIs in        └────────┬───────────────┘
                       │ ready_to_ship              │
                       ▼                             │ writes
                  ┌─────────┐                        │ S#{wave}/integrator-task
                  │ integ-  │                        ▼
                  │ rating  │           ┌─────────────────────────────┐
                  └────┬────┘           │  Worker Fargate (existing)  │
                       │                │  crow_kind=integrator (NEW) │
                       │                │  - per-PR worktrees on EFS  │
                       │                │  - integration merge        │
                       │                │  - lint / type / test       │
                       │                │  - emit IntegratorFindings  │
                       │                └─────────┬───────────────────┘
                       │                          │ writes
                       │                          ▼ INTEGRATION#{wave}
   ┌───────────────────┴──────────────────┐  ┌──────────────┐
   │                                      │  │   DDB main   │
   ▼ conflict /                           ▼ all green       ▲
needs_rework                       under_council_review     │
   │                                      │                 │
   │                                      │ writes          │
   │                                      ▼ COUNCIL#{session}│
   │                            ┌─────────────────────────┐ │
   │                            │  Council Fargate (NEW)  │ │
   │                            │  - 6 advisors parallel  │ │
   │                            │  - tool-equipped        │ │
   │                            │  - read-only IAM        │ │
   │                            │  - 180s/advisor cap     │ │
   │                            └─────────┬───────────────┘ │
   │                                      │ writes          │
   │                                      ▼ CouncilDecision │
   │                                      │                 │
   └──────────────────────────┐           ▼                 │
                              │     ┌───────────────┐       │
                              ▼     ▼               │       │
                          delivered or steered      │       │
                          (founder decides)         │       │
                                                    │       │
                                                  iOS reads SSE
```

### Three new wave states

Inserted between existing `review` and `delivered`/`steered`:

- **`integrating`** — Integrator crow is running on Worker. Worktrees being set up, integration merge attempted, deterministic checks running.
- **`needs_rework`** — Integrator found merge conflicts or check failures. Murder reactor dispatches fixer crows; wave returns to `executing` once fixers start.
- **`under_council_review`** — Integrator emitted all-green findings, Council session created with status `pending`. Council Fargate will pick it up.

Existing states (`executing`, `review`, `delivered`, `steered`) keep their existing semantics.

## Data models

All new or extended SK patterns live on the main DDB table.

### 1. NEW: `INTEGRATION#{wave_id}` — IntegratorFindings record

Written by the Integrator crow. One row per wave (idempotent on retry).

```python
@dataclass
class IntegratorFindings:
    PK: str              # P#{project_id}
    SK: str              # INTEGRATION#{wave_id}
    wave_id: str
    pr_numbers: list[int]
    integration_branch: str   # e.g. "council-review-w1234567"

    # Merge phase
    merge_status: Literal["ok", "conflict"]
    merge_conflicts: list[MergeConflict]   # empty if ok

    # Deterministic checks (only run if merge ok)
    lint: CheckResult | None
    typecheck: CheckResult | None
    tests: CheckResult | None

    # Worktree pointers (consumed by Council)
    worktree_paths: dict[int, str]   # {pr_number: "/mnt/repos/T/.../pr-{n}"}
    integration_worktree: str        # "/mnt/repos/T/.../integration"

    # Overall verdict
    overall: Literal["ready_for_council", "needs_rework"]
    rework_reasons: list[str]

    started_at: str
    completed_at: str
    duration_ms: int

@dataclass
class MergeConflict:
    pr_a: int
    pr_b: int
    files: list[str]
    hunks: list[str]   # first 500 chars per hunk, max 5 hunks
    mvi_a: str         # MVI that produced pr_a (for fixer dispatch routing)
    mvi_b: str

@dataclass
class CheckResult:
    status: Literal["ok", "fail", "timeout", "error", "skipped"]
    failures: list[str]   # first 5 failure lines
    duration_ms: int
    command: str          # e.g. "black --check ."
```

### 2. EXTENDED: `S#{wave_id}` — wave snapshot gains new status values

The existing row gains three new `status` enum values: `integrating`, `needs_rework`, `under_council_review`. No new fields — just new state machine transitions handled by the Murder reactor.

### 3. NEW: `COUNCIL#{session_id}` — Council session record

Extended from the existing Lambda's shape. New fields prefixed `NEW:`.

```python
@dataclass
class CouncilSession:
    PK: str              # P#{project_id}
    SK: str              # COUNCIL#{session_id}
    session_id: str
    type: Literal["wave_review"]   # only one type for Layer A
    wave_id: str
    integration_sk: str  # NEW: pointer to INTEGRATION#{wave_id}

    status: Literal["pending", "running", "completed", "errored"]
    auto_mode: bool      # whether founder pre-approved auto-ship if Council unanimous

    context: dict        # the rich packet (see Packet section)

    rounds: list[VotingRound]
    decision: CouncilDecision | None
    cost: dict           # tokens + dollars per advisor
    pipeline_health: Literal["ok", "degraded"]   # NEW: ≥2 errors → degraded

    created_at: str
    completed_at: str | None
```

### 4. EXTENDED: `AdvisorVote` adds investigation fields

Existing fields preserved (advisor, vote, confidence, concerns, conditions). Three new fields:

```python
@dataclass
class AdvisorVote:
    # Existing
    advisor: AdvisorType
    vote: VoteType        # APPROVE | APPROVE_WITH_CONDITION | ABSTAIN | BLOCK
    confidence: float
    concerns: list[str]
    conditions: list[str]

    # NEW
    investigation_trace: list[ToolCall]
    cited_evidence: list[CitedEvidence]
    tokens_consumed: int

@dataclass
class ToolCall:
    tool_name: str
    args: dict
    result_summary: str   # first 200 chars
    duration_ms: int
    error: str | None

@dataclass
class CitedEvidence:
    file_path: str
    line_range: tuple[int, int] | None
    pr_number: int | None
    reason: str
```

### 5. NEW: events table — three new event types

No new SK patterns on events table. Existing `E#{ts}#{uuid}` shape, new `event_type` values:

- `wave_state_change` — transitions to/from integrating, needs_rework, under_council_review
- `integrator_finished` — payload: overall verdict + check summary
- `council_decision` — payload: final decision summary + per-advisor verdict summary
- `council_pipeline_error` — **loud-failure event.** Payload: `phase`, `error_class`, `error_message`, `traceback_head` (first 1000 chars), `wave_id`, `session_id?`, `retry_count`, `final?` (boolean)

All four event types flow through the existing events table → EventBridge Pipe → SQS → Stream Fargate → ALB → iOS SSE pipeline. No infrastructure change to SSE.

## The rich packet

Each advisor reads the same packet up front before investigating with tools. Roughly 3-5K tokens per advisor.

Contents:

- **Wave metadata** — wave_id, project_id, total MVI count, total PR count, started_at
- **Project docs** — Vision, Architecture, Glossary, Design (the four static docs, possibly excerpted to fit token budget)
- **Per-MVI summary** — for each MVI in the wave: MVI spec, planner output summary, Reviewer verdict + blocking_issues
- **Open PRs** — for each: pr_number, title, head_sha, files_changed, diff_stat (additions/deletions per file), URL
- **IntegratorFindings** — full record: merge status, check results, worktree pointers, overall verdict

The packet is stored on `CouncilSession.context` so we have a full audit trail of exactly what each advisor saw.

## Components & file layout

### New: `apps/integrator/`

Lives alongside other crow kinds in the Worker. No new container image — runs inside the existing Worker. Imported by the Worker's handler when `crow_kind=integrator`.

```
apps/integrator/
├── __init__.py
├── handler.py           # Entry: load wave context, dispatch to phases
├── worktree.py          # git worktree setup/cleanup per PR
├── integration.py       # attempt merge into council-review-{wave_id} branch
├── checks/
│   ├── __init__.py
│   ├── lint.py          # black + flake8 runners, parse output
│   ├── typecheck.py     # mypy runner, parse output
│   ├── tests.py         # pytest runner, parse output
│   └── runner.py        # orchestrates checks, builds CheckResult
├── findings.py          # IntegratorFindings dataclass + DDB write
└── tests/
    ├── test_worktree.py
    ├── test_integration.py
    ├── test_checks_lint.py
    ├── test_checks_typecheck.py
    ├── test_checks_tests.py
    └── test_findings.py
```

### New: `apps/council/`

Standalone Fargate service. Own Dockerfile, own requirements.txt, own deployment.

```
apps/council/
├── Dockerfile
├── requirements.txt
├── main.py              # Fargate entrypoint — poll loop (mirror apps/worker/main.py)
├── handler.py           # Entry per session: load packet, run advisors, write decision
├── orchestrator.py      # PORTED from lambdas/council/orchestrator.py
│                        # Round management; replace ThreadPoolExecutor → asyncio.gather
├── synthesis.py         # PORTED unchanged
├── reflection.py        # PORTED unchanged
├── memory_store.py      # PORTED; DDB read-only on Fargate (no writes except MEM#)
├── models.py            # PORTED + extended (AdvisorVote new fields)
├── enums.py             # PORTED unchanged
├── config.py            # ADAPTED: Fargate env vars, model = haiku-4.5
├── advisors/
│   ├── __init__.py
│   ├── base.py          # Base advisor: tool-use loop, streaming, caps
│   ├── security.py      # Security-specific system prompt + tool palette
│   ├── architecture.py
│   ├── clarity.py
│   ├── performance.py
│   ├── ux.py
│   ├── cost.py
│   └── prompts/         # System prompts as markdown files
│       ├── security.md
│       ├── architecture.md
│       ├── clarity.md
│       ├── performance.md
│       ├── ux.md
│       └── cost.md
├── tools/
│   ├── __init__.py
│   ├── filesystem.py    # read_file, list_directory, grep
│   ├── git.py           # git_log_for_file, get_pr_diff, read_integration_file
│   ├── github.py        # get_pr_metadata (REST API, no clone)
│   ├── palette.py       # per-advisor scoping + dispatch
│   └── trace.py         # Build investigation_trace as tools are called
├── packet.py            # Build rich packet from wave_id + IntegratorFindings
├── claude_client.py     # Anthropic streaming + tool-use loop
└── tests/
    ├── test_orchestrator.py    # PORTED
    ├── test_synthesis.py       # PORTED
    ├── test_reflection.py      # PORTED
    ├── test_memory_store.py    # PORTED
    ├── test_models.py          # PORTED + extended
    ├── test_advisors_base.py
    ├── test_advisors_security.py   # plus per-advisor variants
    ├── test_tools_filesystem.py
    ├── test_tools_git.py
    ├── test_tools_palette.py       # scoping enforcement
    ├── test_packet.py
    └── test_claude_client.py
```

### Modified: `lambdas/murder/src/murder/reactor.py`

Three new dispatch paths:

- `_handle_wave_review_ready` — fires when all MVIs in a wave reach `ready_to_ship`. Transitions wave to `integrating`. Writes `S#{wave}/integrator-task`. Triggers Worker via `ecs:UpdateService`.
- `_handle_integration_complete` — fires on `INTEGRATION#{wave_id}` write. If `overall=needs_rework`: dispatch fixers per affected MVI; transition wave to `executing`. If `overall=ready_for_council`: write `COUNCIL#{session_id}` row; transition wave to `under_council_review`.
- `_handle_council_complete` — fires on `CouncilSession.status=completed`. Layer A: transition `S#{wave}.status` to `under_human_review` (existing behavior).

Removed: `_maybe_write_council_task` at lines 969-991 (was for the obsolete wave-after-delivery flow).

### Modified: `infra/lib/cawnex-stack.ts`

CDK changes:

- DELETE `cawnex-council-${stage}` Lambda + its DDB Stream event source + its log group
- ADD `cawnex-council-${stage}` ECS Service (new TaskDefinition): 0.5 vCPU / 1 GB, mounts EFS read-only at `/mnt/repos`
- ADD `CouncilServiceSG` security group (egress only)
- ADD EFS access point `CouncilTenantAP` (read-only mode, same `/T/{tenant}` paths Worker uses)
- ADD `cawnex-council-${stage}` task role: DDB read main + events; DDB write only on `COUNCIL#*` and `MEM#*` SK patterns; SecretsManager read on `anthropic-auth-token`; EFS read on access point. **No GitHub token, no S3 write, no ECS scaling permissions.**
- ADD DDB-stream-driven scaler for Council (mirrors existing Worker scaler): on `COUNCIL#*` INSERT with status=pending, bump `desiredCount: 0 → 1`

Worker IAM already has DDB RW on main table — no change needed to support `INTEGRATION#{wave}` writes.

### `lambdas/council/` — port verdict per module

From the audit:

| Module | Verdict | Notes |
|---|---|---|
| `handler.py` | SCRAP | DDB-Stream-event-driven Lambda entry; Fargate uses poll loop. |
| `orchestrator.py` | PORT | Replace `ThreadPoolExecutor` → `asyncio.gather`. |
| `advisors.py` | REFERENCE | Big rewrite — needs streaming + tool-use loop + scoped palette. |
| `synthesis.py` | PORT | Pure deterministic; drops in unchanged. |
| `reflection.py` | PORT | Pure function; drops in unchanged. |
| `memory_store.py` | PORT | DDB schema stable. |
| `overrides.py` | PORT (with care) | `request_round` trigger path changes for Fargate. |
| `actions.py` | SCRAP | Wave-execution semantics don't map to Layer A. |
| `models.py` | PORT + EXTEND | Add `investigation_trace`, `cited_evidence` to AdvisorVote. |
| `enums.py` | PORT | Rename `SessionType.WAVE_REVIEW` if needed. |
| `config.py` | REFERENCE | Lambda-specific env vars replaced. Switch model to haiku-4.5. |
| `_blackboard.py` | REFERENCE | Recreate as read-only on Fargate. |
| `_claude_client.py` | REFERENCE | Rewrite around `messages.stream(...)` + tool-use loop. |
| `keys.py` | SCRAP | New SK shape. |
| `__init__.py` | SCRAP | Empty. |

## Per-advisor tool palettes

Each role gets the tools its investigation actually needs, scoped where appropriate.

| Advisor | Tools | Path scope |
|---|---|---|
| Security | read_file, grep, list_directory, git_log_for_file, get_pr_diff, read_integration_file, get_pr_metadata | All paths |
| Architecture | read_file, grep, list_directory, git_log_for_file, get_pr_diff, read_integration_file, get_pr_metadata | All paths |
| Clarity | read_file, grep, get_pr_diff, read_integration_file, get_pr_metadata | All paths |
| Performance | read_file, grep, git_log_for_file, get_pr_diff, read_integration_file, get_pr_metadata | All paths |
| UX | read_file, grep, get_pr_diff, read_integration_file, get_pr_metadata | **Scoped to `apps/ios/...` and string/asset files only.** Calls outside scope return structured error. |
| Cost | read_file, grep, list_directory, get_pr_diff, read_integration_file, get_pr_metadata | **Scoped to `infra/...` only.** Calls outside scope return structured error. |

**Hard caps per advisor:** 15 tool calls, 180s wall-clock. Hitting either cap produces an `abstain` vote with concerns capturing what was investigated.

**No write tools, ever. No recursive tools (no tool that calls Anthropic).**

## Data flow — end-to-end sequence

### Phase 1: Wave reaches ready_to_ship everywhere

1. Last MVI's Reviewer crow writes `ready_to_ship` to `S#{wave}#m{mvi}`.
2. DDB Stream MODIFY → Murder reactor `_handle_mvi_ready`.
3. Reactor checks: are all MVIs ≥ ready_to_ship? YES → call `_maybe_start_integrator(wave_id)`.
4. `_maybe_start_integrator`:
   - Read all open PRs for the wave's MVIs.
   - Update `S#{wave}.status`: `review → integrating`.
   - Write `S#{wave}/integrator-task` DDB item (claim semantics).
   - `ecs:UpdateService cawnex-worker-${stage}` desiredCount 0 → 1.
5. Emit events row: `wave_state_change` (review → integrating).

### Phase 2: Integrator runs on Worker

6. Worker poll loop picks up the integrator-task.
7. Worker dispatches to `apps/integrator/handler.py`.
8. **Phase 2A** — workspace setup (per-PR worktrees):
   - For each PR: `git fetch origin pull/{pr_number}/head`, `git worktree add .pr-{pr_number} FETCH_HEAD`.
9. **Phase 2B** — integration merge:
   - `git worktree add .integration origin/main`.
   - In `.integration`, for each PR in order: `git merge --no-ff origin/pr-{pr_number}`.
   - On conflict: capture MergeConflict with files + hunks + owning MVI; continue to next PR to capture all conflicts.
   - Result: clean merge OR list of MergeConflict.
10. If conflicts: skip Phase 2C; write IntegratorFindings with `merge_status=conflict`, `overall=needs_rework`. Go to step 14.
11. **Phase 2C** — deterministic checks (only if merge clean):
    - `cd .integration`; run black --check, flake8, mypy, pytest each in subprocess (timeouts: 60s, 60s, 120s, 300s).
    - Each produces CheckResult.
12. If any check failed: `overall=needs_rework` with rework_reasons (failed checks + first 5 failures per check). If all passed: `overall=ready_for_council`.
13. Write `INTEGRATION#{wave_id}` row with full IntegratorFindings.
14. Emit events row: `integrator_finished` (overall + summary).
15. Integrator exits. Worker eventually scales to 0.

### Phase 3: Murder reactor routes on integrator output

16. DDB Stream INSERT on `INTEGRATION#{wave_id}` → reactor `_handle_integration_complete`.
17. Read `IntegratorFindings.overall`:
    - **needs_rework path:** Update `S#{wave}.status`: integrating → needs_rework. For each MergeConflict/failed check, dispatch fixer crows for affected MVIs with structured feedback. Wave returns to executing. Emit `wave_state_change`. END (Phase 1 starts again after fixers).
    - **ready_for_council path:** Update `S#{wave}.status`: integrating → under_council_review. Write `COUNCIL#{session_id}` row with status=pending, context=rich packet, integration_sk pointer. Emit `wave_state_change`.

### Phase 4: Council Fargate runs

18. Council scaler sees `COUNCIL#*.status=pending`.
19. `ecs:UpdateService cawnex-council-${stage}` desiredCount 0 → 1.
20. Council task starts; poll loop picks up pending session.
21. Council handler:
    - Update CouncilSession.status: pending → running.
    - Load packet from session.context.
    - Load worktree pointers from `INTEGRATION#{wave}` (separate read).
    - Load advisor memory via memory_store for all 6 advisors.
    - Spawn 6 advisor tasks via `asyncio.gather(return_exceptions=True)`.
22. Each advisor task (parallel):
    - Build advisor-specific 5-layer prompt (identity / org standards / project context / advisor memory / decision context).
    - Open Anthropic streaming conversation with the advisor's tool definitions.
    - Tool-use loop: stream output, route tool_use blocks to tool implementations (scoped by palette), append to investigation_trace, send tool_result, repeat. Terminate on submit_vote, 15-call cap, or 180s wall-clock.
    - Parse submit_vote into AdvisorVote with investigation_trace + cited_evidence.
23. asyncio.gather completes with 6 votes OR exceptions.
24. Orchestrator: exception in advisor → abstain vote with error reason.
25. Synthesis (Monarch, deterministic):
    - Vetoes (Security + Clarity) → block decision.
    - Unanimous approve → approve decision.
    - Conditional votes → conditional decision with merged conditions.
    - Disagreement → trigger debate round (advisors who voted block see others' votes, re-vote once; max 3 rounds).
    - Final → CouncilDecision.
26. Council writes:
    - Update `COUNCIL#{session_id}`: status=completed, rounds[], decision, cost, completed_at, pipeline_health (degraded if ≥2 pipeline_error events emitted in this session).
    - Reflection pass (deterministic) → write learnings to MEM#advisor#{type} rows.
27. Emit events row: `council_decision`.
28. Murder reactor `_handle_council_complete` sees status=completed.
29. Layer A behavior: transition `S#{wave}.status` under_council_review → under_human_review. Founder still gates.
30. Council Fargate scales back to 0.

### Phase 5: Founder sees the decision

31. iOS SSE stream sees `integrator_finished` then `council_decision`.
32. (Layer B) PR Review screen renders the Council panel.
33. Founder decides what to merge.
34. Existing merge flow continues unchanged.

**Wall-clock budget:** Phase 2 ~5-15 min (test-suite dependent). Phase 4 ~3-5 min. Total ready-to-decision: ~10-20 min.

## Error handling and the loud-failure rule

**Principle: silence is the bug, not the failure.** Every error path emits a structured `council_pipeline_error` event to the events table, logs at ERROR level with structured JSON, and the iOS Council panel surfaces a non-auto-dismiss banner. No `except Exception: pass` anywhere; lint rule enforced in CI.

### Per-failure handling

**Integrator workspace setup (Phase 2A):**

- Git fetch fails (network/auth/5xx) → retry 3× with exponential backoff. Still failing: emit IntegratorFindings with `overall=needs_rework`, `rework_reasons=["unable to fetch PR #N: <error>"]`. Founder sees clear "GitHub unreachable" message.
- Worktree add fails (EFS, corruption) → integrator exits with exception. Worker crashes. Checker Lambda releases claim. Next poll retries. Idempotent — same worktree names overwrite.
- Cleanup always runs in `finally`. Cleanup failures emit `council_pipeline_error` (EFS state may be inconsistent).

**Integration merge (Phase 2B):**

- Conflict is expected behavior, not error — captured as MergeConflict; wave → needs_rework; fixer crows dispatched.
- Non-conflict merge failure (workspace corruption) → force-reset integration branch to origin/main, retry once. Still failing: emit IntegratorFindings with `overall=needs_rework`, `rework_reasons=["workspace corruption detected"]`. Emits `council_pipeline_error` with `final=true`.

**Deterministic checks (Phase 2C):**

- Command not found (e.g. mypy not installed) → CheckResult `status=skipped`. Skipped ≠ failed for the overall verdict.
- Timeout → CheckResult `status=timeout`, treated as failed for overall. `rework_reasons` says "tests timed out after 300s — split into smaller suites."
- Crash (segfault, OOM) → CheckResult `status=error`, treated as failed. `rework_reasons` includes first 500 chars of stderr.

**Council per-advisor failures (Phase 4):**

- 15-tool-call cap → returns `vote=abstain`, `confidence=0`, `concerns=["investigation incomplete: 15-call cap"]`.
- 180s wall-clock cap → asyncio task cancelled, returns abstain with whatever trace was captured.
- Anthropic API error → retry 2× with backoff. Still failing: return abstain with `concerns=["API error: <type>"]`. Other 5 advisors continue (asyncio.gather isolation).
- Malformed JSON → JSON-repair retry once. Still failing: abstain with `concerns=["malformed advisor response"]`. **Every JSON-repair attempt logs WARN and emits `council_pipeline_error`** so we see how often this happens.
- Tool call error (file not found, regex invalid) → tool returns error result, model continues. Log at WARN. If an advisor has >5 tool errors in one run, emits `council_pipeline_error` (something is wrong with the tool itself).
- All 6 advisors abstain → CouncilDecision `action=escalate`, reason "no quorum."

**Council orchestration (Phase 4):**

- Synthesis crashes → emit CouncilDecision with `action=escalate`, reason "synthesis error: <traceback head>". Emit `council_pipeline_error`. Wave → under_human_review.
- Reflection crashes → log ERROR, emit `council_pipeline_error`, still write the CouncilDecision (decision valid). iOS banner: "Memory learning failed for this session."

**Wave state machine corruption:**

- Wave stuck in `integrating` >30 min → Checker Lambda (existing hourly cron) releases claim, resets to `review`, Murder reactor retries.
- Wave stuck in `under_council_review` >60 min → Checker releases COUNCIL# claim, retries.
- Multiple Council sessions for same wave (retry) → most-recent wins; earlier ignored.

**CDK / deployment:**

- EFS access point not yet provisioned → task fails health check, ECS restarts. Acceptable for cold-deploy.
- Two-pass migration: deploy Fargate alongside old Lambda, verify on test wave, then delete Lambda. Avoids the no-Council gap during deploy.

### Aggregation rule

Per Council session, if ≥2 `council_pipeline_error` events fire during the session, the final `CouncilDecision.pipeline_health="degraded"`. Synthesis still produces a decision; the decision record carries the warning. iOS treats degraded decisions as informational only (no auto-merge eligibility in Layer C even if approve+unanimous).

### Cost ceiling on failure

A "advisor hit 180s cap" failure burns ~5K-10K input tokens + ~1K output tokens before timing out (~$0.01-0.02 per failed advisor). Worst case: 6 advisors all hit caps = ~$0.12 per failed Council session. Bounded.

### Known gaps for Layer A

- **No retry on workspace corruption.** A workspace-corrupt failure causes wave → needs_rework which dispatches fixers. Fixers don't know how to fix workspace corruption — it'll loop. Mitigation: workspace failures are rare (we control EFS); Checker eventually intervenes; CloudWatch + iOS banner alert devs.
- **No retry on Council `escalate`.** Founder sees escalation, decides. Manual re-vote affordance is Layer B.
- **No alarms in Layer A.** CloudWatch logs + iOS banners + events are sufficient. Alarming follows after Layer A produces signal patterns.

## Testing strategy

### Test pyramid

- ~70% unit (modules in isolation, mocked dependencies)
- ~25% integration (real DDB via moto/LocalStack, mocked Anthropic, real EFS-like filesystem fixtures)
- ~5% end-to-end (full Council session against real Anthropic in sandbox; manual)

### Integrator unit tests (`apps/integrator/tests/`)

- `test_worktree.py` — fixture repo + fake PR; verify worktree create/cleanup. Failure cases: fetch fails, EFS write fails, worktree exists.
- `test_integration.py` — clean merge, single conflict, multi-PR pile-up. Verify MergeConflict includes files + hunks + PR-pair + owning MVI.
- `test_checks_lint.py`, `test_checks_typecheck.py`, `test_checks_tests.py` — fixture project with intentional failures. Verify CheckResult parsing. Cover: clean, fail, command-not-found, timeout.
- `test_findings.py` — builder + idempotency (same `INTEGRATION#{wave}` write twice produces same result).

### Council unit tests (`apps/council/tests/`)

Ported from `lambdas/council/tests/` mostly unchanged:

- `test_orchestrator.py` — round management, consensus, veto. Adapt ThreadPoolExecutor mocks → asyncio.gather.
- `test_synthesis.py`, `test_reflection.py`, `test_memory_store.py` — port unchanged.
- `test_models.py` — port + extend for new AdvisorVote fields (investigation_trace serialization, cited_evidence shape).

New:

- `test_advisors_base.py` — tool-use loop with mocked Anthropic streaming. Verify caps fire (15-call → abstain, 180s → abstain), tool errors propagate, JSON repair runs once, malformed-twice → abstain.
- `test_advisors_security.py` (+ per-advisor variants) — verify prompt loads from `prompts/security.md`, palette correctly scoped.
- `test_tools_filesystem.py` — read_file (line ranges, missing file), grep (regex errors, empty results), list_directory.
- `test_tools_git.py` — git_log_for_file, get_pr_diff (mocked GitHub), read_integration_file.
- `test_tools_palette.py` — **scoping enforcement, non-negotiable.** Security read_file works anywhere; UX read_file on `apps/api/...` returns structured error `{tool_error: "out_of_scope", advisor: "ux", path: "apps/api/..."}`. The advisor continues investigating (model recovers), but the disallowed file content is never returned to the model.
- `test_packet.py` — given wave_id + IntegratorFindings, build packet with expected sections.
- `test_claude_client.py` — streaming + tool-use loop, fully mocked.

### Murder reactor tests (extend `lambdas/murder/tests/test_reactor.py`)

- `TestHandleWaveReviewReady` — all MVIs ready_to_ship → integrator-task written, ECS UpdateService called.
- `TestHandleIntegrationComplete` — two paths: ready_for_council writes COUNCIL#, needs_rework dispatches fixers per affected MVI.
- `TestHandleCouncilComplete` — wave transitions under_council_review → under_human_review.

### Integration tests (new `tests/integration/test_stage4_layer_a.py`)

Real DDB (moto/LocalStack), mocked Anthropic, fixture filesystem. Scenarios:

- `test_happy_path` — synthetic wave + 2 fake PRs, all advisors approve, verify CouncilDecision written + wave → under_human_review.
- `test_merge_conflict_path` — conflicting PRs → wave → needs_rework, fixers dispatched, no Council session.
- `test_failing_test_path` — clean merge, pytest fails → wave → needs_rework with rework_reasons.
- `test_advisor_timeout` — one advisor exceeds 180s → abstain, other 5 proceed, decision written.
- `test_security_veto` — Security votes block → CouncilDecision.action=block regardless of others.
- `test_pipeline_error_event` — force a failure → `council_pipeline_error` event written.

### Smoke test (manual gate before Layer A is "done")

One real Council session against real Anthropic, on a controlled synthetic wave in dev. Two PRs with simple changes. Verify:

- Integrator runs to completion; lint/typecheck/test pass
- Council fires; 6 advisors each make 3-8 tool calls; all return votes within 180s
- CouncilDecision written with full traces
- Total cost ~$0.21 as predicted
- No `council_pipeline_error` events emitted

If smoke test reveals issues, Layer A isn't done — even with all CI passing. Did we actually run this once for real?

### Fixtures needed

- Synthetic git repo at `apps/integrator/tests/fixtures/clean-repo/` — ~10 files, base for integration tests
- Mock PRs as `tests/fixtures/pr-{n}-{scenario}.patch`
- Mock Anthropic response fixtures at `apps/council/tests/fixtures/anthropic-responses/` — one per scenario

### What we are NOT testing in Layer A

- Performance under concurrent waves (multiple integrators/Councils in flight) — Layer A targets correctness on serial flow.
- Cost-routing tests — all advisors use Haiku 4.5 in Layer A.
- iOS UI tests for Council panel — Layer B.
- Auto-merge tests — Layer C.

### CI integration

Existing pytest + GitHub Actions handles unit + integration tests. New CI workflow `Stage 4 Layer A` runs on changes to `apps/integrator/`, `apps/council/`, `lambdas/murder/src/murder/reactor.py`, `infra/lib/cawnex-stack.ts`. Smoke test stays manual.

## Implementation order

Three milestones inside Layer A. Each ships value independently and is testable in isolation before moving to the next.

### M1: Integrator crow + wave state machine extension

Outcome: a real wave's Integrator can run on Worker, attempt the merge, run checks, and emit IntegratorFindings. Murder reactor routes the wave to needs_rework or to a pending Council session that nobody picks up yet.

- New `apps/integrator/` package, full implementation + unit tests
- New `crow_kind=integrator` dispatch in existing Worker handler
- Murder reactor `_handle_wave_review_ready` + `_handle_integration_complete`
- Wave state machine extension (integrating, needs_rework, under_council_review states)
- IntegratorFindings DDB schema + writes
- Loud-failure: `council_pipeline_error` events for integrator failures
- Integration test: `test_merge_conflict_path` + `test_failing_test_path`
- ~5-6 days

### M2: Council Fargate service

Outcome: a Council session that's been written by the reactor can be picked up, 6 advisors investigate in parallel, decision is written.

- New `apps/council/` package
- Port `orchestrator`, `synthesis`, `reflection`, `memory_store`, `models` (extended), `enums`
- Rewrite `advisors` for streaming + tool-use + scoped palette
- New `tools/` package (filesystem, git, github, palette, trace)
- New `claude_client.py` with streaming + tool-use loop
- CDK: new TaskDefinition, Service, IAM role, SG, EFS read-only access point
- Council scaler (mirror Worker scaler) for COUNCIL#* INSERT
- Loud-failure: `council_pipeline_error` for advisor and synthesis failures
- Integration tests: `test_happy_path`, `test_advisor_timeout`, `test_security_veto`
- ~5-6 days

### M3: Murder reactor `_handle_council_complete` + cleanup

Outcome: Council decision → wave transitions to under_human_review. Old Council Lambda deleted from CDK. Full end-to-end loop runs.

- Murder reactor `_handle_council_complete`
- CDK: delete `cawnex-council-${stage}` Lambda + event source + log group
- Migration sanity test in dev (deploy Fargate, verify decision write, then delete Lambda)
- Smoke test on a controlled synthetic wave
- ~1-2 days

**Total estimate: ~10-12 days for Layer A done right.**

## Cost of execution

- **Anthropic API tokens per Council vote:** ~$0.21 (6 advisors × ~$0.035 each at Haiku 4.5 pricing, ~18K input + ~3.3K output per advisor including tool-call rounds).
- **Integrator API tokens:** ~$0 — integrator does no Anthropic calls, only subprocess + git.
- **Fargate compute per Council vote:** ~$0.0014 on-demand, ~$0.0004 Spot (0.5 vCPU / 1 GB for ~3 min including cold start).
- **Fargate compute per Integrator run:** ~$0.005-0.015 on Worker (varies with test-suite time; existing Worker capacity).
- **EFS / DDB / CloudWatch:** pennies/month at current volume.
- **One-time engineering:** ~10-12 days for Layer A.
- **Ongoing operational tax:** ~2 hrs/month for the new Council service's monitoring/deploys.

## What changes if this works

- Cawnex's first L4 cell: the rework loop (element 4 in the dark-factory matrix) graduates from L3 to L4 because needs_rework dispatches automatically based on deterministic + adversarial signal.
- Verification gate (element 3) graduates from L1 to L3 — not as a Worker-side gate, but as a wave-level integrator gate.
- The 4-altitude approval gates start *actually* operating at multiple altitudes. Wave-level decisions get a Council signal before they reach the founder, even if the founder still merges.
- The Council Lambda — deployed-but-silent for months — finally activates and earns its CDK presence.

## What this does NOT do

- It does not auto-merge anything. Layer A always escalates to founder review.
- It does not run on per-PR scope. Council is wave-level only in Layer A.
- It does not equip advisors with semantic search, embeddings, or cross-PR memory. Stateless investigation only.
- It does not modify the founder gate or PR Review screen UI. Layer B will.

## Success criteria

Layer A is done when:

1. A real wave with at least 2 MVIs reaches the under_council_review state via the Integrator pathway.
2. A real Council session writes a CouncilDecision with 6 AdvisorVotes, each containing a non-empty investigation_trace and cited_evidence.
3. Total wall-clock from "last MVI ready_to_ship" to "CouncilDecision written" is under 25 minutes.
4. Smoke test cost is ~$0.21 ± 25%.
5. No `council_pipeline_error` events emitted on the smoke test.
6. iOS PR Review screen shows the wave is `under_human_review` (existing behavior; Layer B adds the Council panel).
