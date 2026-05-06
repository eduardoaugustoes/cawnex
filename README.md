<div align="center">

# Cawnex

### Coordinated Intelligence

**Multi-agent AI orchestration platform — voice command to shipped, reviewed, and committed code, with human approval at every step.**

[![CI](https://github.com/eduardoaugustoes/cawnex/actions/workflows/main-pipeline.yml/badge.svg)](https://github.com/eduardoaugustoes/cawnex/actions/workflows/main-pipeline.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](apps/api)
[![Swift](https://img.shields.io/badge/swift-5.9-orange.svg)](apps/ios)
[![AWS CDK](https://img.shields.io/badge/infra-AWS%20CDK-232F3E.svg)](infra)

_One caw. Three Lambdas. Zero bottlenecks._

---

[Quick Start](#quick-start) · [Architecture](#system-architecture) · [Codebase Map](#codebase-map) · [Tech Stack](#tech-stack) · [How It Works](#how-it-works) · [API Reference](#integration-endpoints) · [DynamoDB Schema](#dynamodb-schema)

</div>

---

## What is Cawnex?

Cawnex is a **fully serverless, multi-tenant AI orchestration platform** built on AWS. A user speaks a project idea into their iPhone. An AI planner (Monarch) asks clarifying questions, generates architecture documents, breaks the work into milestones and MVIs (Minimum Valuable Increments), then autonomously dispatches specialized AI agents — **Crows** — that plan, implement, review, and fix code in real GitHub repositories.

The entire execution lifecycle is observable in real time via Server-Sent Events. Every decision passes through a human approval gate. Every cost is tracked to the microdollar.

**Built as a solo engineering project from scratch** — full-stack mobile (SwiftUI), serverless backend (Python/FastAPI), event-driven orchestration (DynamoDB Streams), multi-stage IaC (AWS CDK TypeScript), and a 550+ test suite across five bounded contexts.

---

## Quick Start

The core orchestration logic runs without AWS. Clone and explore the most interesting parts locally:

```bash
# API + all REST endpoints (87 tests, no AWS required)
cd apps/api
python -m venv venv && source venv/bin/activate
pip install -e .[dev]
pytest                          # 87 tests, ~1s

# Murder Lambda — crow state machine (301 tests)
cd lambdas/murder
pip install -e .[dev]
pytest

# Council Lambda — 6-advisor review protocol (70 tests)
cd lambdas/council
pip install -e .[dev]
pytest

# Worker — crow execution engine (159 tests)
cd lambdas/worker
pip install -e .[dev]
pytest
```

All test suites use local DynamoDB mocks — no credentials, no network.

---

## Codebase Map

| Path | What it is | Key files |
|------|-----------|-----------|
| [`apps/api/`](apps/api/) | FastAPI Lambda — all REST endpoints | [`src/routes/`](apps/api/src/routes/), [`src/db/client.py`](apps/api/src/db/client.py) |
| [`apps/api/src/routes/autopilot.py`](apps/api/src/routes/autopilot.py) | Monarch chat — stateful voice-to-plan flow | Prompt engineering, multi-turn state machine |
| [`apps/api/src/db/client.py`](apps/api/src/db/client.py) | Tenant-isolated DynamoDB client | Single-table design, `T#{tenant}#P#{project}` key scheme |
| [`apps/worker/`](apps/worker/) | ECS Fargate crow runner | `main.py` continuous poll loop, Dockerfile |
| [`apps/ios/`](apps/ios/) | SwiftUI native app (162 Swift files) | [`Features/`](apps/ios/Cawnex/Cawnex/Features/), [`Core/Network/`](apps/ios/Cawnex/Cawnex/Core/) |
| [`lambdas/murder/`](lambdas/murder/) | **Core orchestrator** — DynamoDB Stream reactor | [`src/murder/state_machine.py`](lambdas/murder/src/murder/state_machine.py), [`reactor.py`](lambdas/murder/src/murder/reactor.py) |
| [`lambdas/monarch/`](lambdas/monarch/) | Project setup agent — docs → milestones → wave | [`src/monarch/agent.py`](lambdas/monarch/src/monarch/), [`planner.py`](lambdas/monarch/src/monarch/) |
| [`lambdas/council/`](lambdas/council/) | 6-advisor AI review protocol | [`prompts/advisors/`](lambdas/council/prompts/advisors/) (clarity, market, maturity, performance, quality, security) |
| [`lambdas/worker/`](lambdas/worker/) | Shared crow execution library | [`src/worker/`](lambdas/worker/src/worker/) — git ops, Claude client, contracts, parsing |
| [`lambdas/orchestration/`](lambdas/orchestration/) | Checker + Worker Scaler Lambdas | Hourly verification, ECS auto scale-down |
| [`lambdas/sse/`](lambdas/sse/) | Server-Sent Events streaming | Real-time wave event feed |
| [`infra/lib/cawnex-stack.ts`](infra/lib/cawnex-stack.ts) | CDK — all AWS resources in one stack | API Gateway, ECS, DynamoDB, EFS, KMS, Cognito |
| [`infra/lib/cawnex-auth-stack.ts`](infra/lib/cawnex-auth-stack.ts) | Cognito user pool + JWT auth | Auth stack deployed independently |
| [`docs/VISION.md`](docs/VISION.md) | Product vision and domain model | Full glossary, core principles |
| [`docs/ARCHITECTURE-V2.md`](docs/ARCHITECTURE-V2.md) | Architecture evolution doc | Dynasty → Court → Murder → Crow hierarchy |

---

## System Architecture

```
iOS App (SwiftUI)
  │
  ▼
CloudFront → API Gateway v2 → API Lambda (FastAPI + Mangum)
  │                                  │
  │  JWT via Cognito                 ├─→ DynamoDB (single-table design)
  │                                  ├─→ DynamoDB (events table + SSE feed)
  │                                  ├─→ S3 (assets + artifacts)
  │                                  ├─→ KMS (vault encryption)
  │                                  └─→ Claude API (via Secrets Manager)
  │
  ▼
DynamoDB Streams ──┬──→ Murder Lambda   (crow orchestration state machine)
                   ├──→ Monarch Lambda  (async project setup agent)
                   └──→ Council Lambda  (6-advisor quality review)
  │
  ▼
ECS Fargate Worker (continuous poll, SPOT)
  ├─→ Claims pending crows from GSI1 (DISPATCH#pending)
  ├─→ Clones repo into EFS worktree (tenant-isolated)
  ├─→ Calls Claude API (plan / implement / review / fix)
  ├─→ Commits code + pushes to GitHub
  └─→ Writes completion snapshot → triggers Murder Lambda
  │
  ▼
Murder Lambda (DynamoDB Stream reactor)
  ├─→ Planner done    → assign Implementer
  ├─→ Implementer done → assign Reviewer
  ├─→ Reviewer rejects → assign Fixer (max 2 cycles)
  ├─→ Reviewer approves → MVI ready_to_ship
  └─→ All MVIs terminal → wave transitions to review
```

### AWS Resources

| Resource | Name Pattern | Purpose |
|----------|-------------|---------|
| **API Gateway v2** | `cawnex-api-{stage}` | HTTP routing to API Lambda |
| **Lambda: API** | `cawnex-api-{stage}` | FastAPI app (29s timeout, 512MB) |
| **Lambda: Murder** | `cawnex-murder-{stage}` | Crow orchestration reactor (60s) |
| **Lambda: Monarch** | `cawnex-monarch-{stage}` | Async project setup agent (5min) |
| **Lambda: Council** | `cawnex-council-{stage}` | 6-advisor quality review (5min) |
| **Lambda: Checker** | `cawnex-checker-{stage}` | Hourly verification scan |
| **Lambda: Scaler** | `cawnex-worker-scaler-{stage}` | 15-min ECS auto scale-down |
| **Lambda: SSE** | `cawnex-sse-{stage}` | Server-Sent Events streaming |
| **ECS Fargate** | `cawnex-worker-{stage}` | Crow execution (1 vCPU, 2GB, SPOT) |
| **DynamoDB** | `cawnex-{stage}` | Main table (single-table design) |
| **DynamoDB** | `cawnex-events-{stage}` | Wave event log (TTL: 90d dev / 365d prod) |
| **S3** | `cawnex-artifacts-{stage}` | Repo snapshots, context files |
| **S3** | `cawnex-assets-{stage}` | Human task file uploads |
| **EFS** | `cawnex-repos-{stage}` | Git worktrees (tenant-isolated) |
| **KMS** | `alias/cawnex-vault-{stage}` | Secret encryption |
| **Cognito** | Imported from AuthStack | JWT authentication |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Mobile** | Swift 5.9 + SwiftUI (native iOS) — 162 Swift files, 19 feature modules |
| **API** | Python 3.12 · FastAPI · Mangum · Pydantic v2 |
| **AI / LLM** | Anthropic Claude (Haiku 4.5 for crows) · OAuth token auth · cost tracking |
| **Orchestration** | DynamoDB Streams · event-driven state machine · bounded context Lambdas |
| **Database** | DynamoDB single-table design · GSI1 for dispatch · microdollar cost tracking |
| **Compute** | AWS Lambda (6 functions) · ECS Fargate SPOT · EFS (git worktrees) |
| **Storage** | S3 (assets + artifacts) · EFS (persistent repo mounts) |
| **Auth** | Amazon Cognito · JWT · API Gateway authorizer |
| **Secrets** | AWS KMS (vault) · Secrets Manager (API keys) |
| **Infra** | AWS CDK (TypeScript) · multi-stage (dev / staging / prod) |
| **CI/CD** | GitHub Actions · smart change detection · tag-based incremental deploys · OIDC auth |
| **Quality** | mypy strict · black · flake8 · pytest · 550+ tests across 5 bounded contexts |

---

## How It Works

### 1. Autopilot Flow (Voice → Shipped Code)

```
User holds FAB → speaks "Build a URL shortener on AWS"
  │
  ▼  (SFSpeechRecognizer transcribes on-device)
POST /projects/autopilot/chat { message: "Build a URL shortener, Python, new repo" }
  │
  ▼  (Monarch asks 2-3 clarifying questions via Claude)
POST /projects/autopilot/chat { action: "launch" }
  │
  ├─ Creates project (instant) → returns project_id
  └─ Writes MONARCH#task to DynamoDB
       │
       ▼  (DynamoDB Stream triggers Monarch Lambda, ~60s async)
  Monarch Lambda:
    ├─ Generates vision doc via Claude        → emits SSE event
    ├─ Generates architecture doc             → emits SSE event
    ├─ Generates milestones + goals + MVIs    → emits SSE event
    ├─ Creates wave + activates               → emits SSE event
    └─ Scales ECS worker to 1
         │
         ▼  (Worker ECS Fargate, continuous poll)
  Worker claims Planner crow:
    ├─ Planner:     breaks MVI into tasks → writes completion snapshot
    │    ▼  Murder Lambda reacts
    ├─ Implementer: writes code, commits, pushes → writes completion snapshot
    │    ▼  Murder Lambda reacts
    ├─ Reviewer:    code review → approves or rejects
    │    ▼  (rejected → Fixer → re-review, max 2 cycles)
    └─ MVI approved → ready_to_ship → wave transitions to review
```

### 2. Crow State Machine

```
Planner (completed)
  ├─ has tasks           → Implementer
  ├─ has human tasks     → HumanTask created + Implementer (non-blocked tasks)
  ├─ oversized tasks     → SplitRequired (re-plan with split instructions)
  └─ no tasks            → FailMVI

Implementer (completed) → Reviewer

Reviewer (completed)
  ├─ approved            → MarkMVIReady
  ├─ rejected            → Fixer
  └─ fix cycles exceeded → FailMVI

Fixer (completed) → Reviewer (re-review)

Any crow (failed)
  ├─ retries < max       → retry same crow type
  └─ retries exhausted   → FailMVI
```

### 3. Wave Lifecycle

```
planning → approved → executing → review → delivered
                          │
                          ├─→ paused    → executing (resume)
                          ├─→ steered   → proposed / executing
                          └─→ cancelled
```

### 4. Council Review Protocol

When auto mode is enabled, completed MVIs pass through the Council Lambda before shipping. Six specialized AI advisors review in parallel — **clarity, market fit, maturity, performance, quality, security** — each returning a vote with reasoning. The Council synthesizes votes and either approves, requests changes, or escalates to the human.

### 5. Worker Execution Loop

```python
while True:
    pending = query(GSI1PK="DISPATCH#pending")  # claim crows atomically
    for crow in pending:
        worktree = create_worktree(crow.repo, crow.branch)  # EFS isolation
        result = call_claude(crow.instructions, worktree_context)
        git_commit_and_push(worktree, result)
        write_completion(crow, result)  # triggers Murder Lambda via Stream
    sleep(10)
```

---

## Integration Endpoints

### Public

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness — `{status, stage}` |
| GET | `/config` | Client config — Cognito IDs, region, stage |

### Projects

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/projects` | Create project |
| GET | `/projects` | List all (tenant-scoped) |
| GET | `/projects/{id}/hub` | Aggregated hub — project + docs + waves + tasks |
| PATCH | `/projects/{id}` | Update settings (auto\_mode, etc.) |

### Documents

| Method | Path | Purpose |
|--------|------|---------|
| PUT | `/projects/{id}/documents/{type}` | Save (vision / architecture / glossary / design) |
| GET | `/projects/{id}/documents/{type}` | Get document |

### Backlog

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/projects/{id}/milestones` | Add milestone with goals |
| PUT | `/projects/{id}/milestones` | Replace all milestones |
| GET | `/projects/{id}/milestones` | Get milestones with MVI counts |
| POST | `/projects/{id}/goals/{gid}/mvis` | Save MVIs for goal (max 8h per MVI) |
| GET | `/projects/{id}/goals/{gid}/mvis` | Get MVIs |

### Waves (Execution)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/projects/{id}/waves` | Create wave from goal MVIs or directive |
| GET | `/projects/{id}/waves/{wid}` | Wave detail — MVIs + crows + human tasks |
| POST | `/projects/{id}/waves/{wid}/activate` | Activate → queue MVIs → scale ECS |
| POST | `/projects/{id}/waves/{wid}/pause` | Pause execution |
| GET | `/projects/{id}/waves/{wid}/events` | Paginated SSE event feed |
| POST | `/projects/{id}/waves/{wid}/mvis/{mid}/ship` | Ship approved MVI |

### Autopilot

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/projects/autopilot/chat` | Monarch chat — gathering → proposed → executing |

### Human Tasks

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/projects/{id}/human-tasks` | List tasks by status |
| POST | `/projects/{id}/human-tasks/{htid}/respond` | Submit response + optional steering |
| POST | `/projects/{id}/human-tasks/{htid}/upload-url` | Presigned S3 upload (5min expiry) |

### Vault

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/projects/{id}/vault/secrets` | Store KMS-encrypted secret |
| GET | `/projects/{id}/vault/secrets` | List metadata (values never returned) |
| PUT | `/projects/{id}/vault/secrets/{name}/rotate` | Re-encrypt with new value |

---

## DynamoDB Schema

### Main Table — Single-Table Design

| PK | SK | Entity | Purpose |
|----|----|--------|---------|
| `T#{tenant}` | `P#{project}` | ProjectEntry | Project list |
| `T#{tenant}` | `AUTOPILOT#{session}` | Session | Monarch chat state |
| `T#{tenant}#VAULT` | `P#{project}#S#{name}` | Secret | KMS-encrypted secrets |
| `T#{tenant}#P#{project}` | `S#` | Snapshot | Project root |
| `T#{tenant}#P#{project}` | `DOC#{type}` | Document | Vision / arch / glossary / design |
| `T#{tenant}#P#{project}` | `BACKLOG#milestones` | Backlog | Milestones + goals |
| `T#{tenant}#P#{project}` | `BACKLOG#goal#{gid}#mvis` | GoalMVIs | MVIs per goal |
| `T#{tenant}#P#{project}` | `MONARCH#task` | MonarchTask | Async setup trigger |
| `T#{tenant}#P#{project}` | `S#{wave}` | Snapshot | Wave root |
| `T#{tenant}#P#{project}` | `S#{wave}#m{mvi}` | Snapshot | MVI under wave |
| `T#{tenant}#P#{project}` | `S#{wave}#m{mvi}#cr_{type}_{n}` | Snapshot | Crow execution record |
| `T#{tenant}#P#{project}` | `S#{wave}#m{mvi}#ht_{id}` | Snapshot | Human task |

**GSI1** (worker dispatch): `GSI1PK=DISPATCH#pending` → crows waiting for execution

### Events Table

| PK | SK | Purpose |
|----|----|---------|
| `T#{tenant}#P#{project}#W#{wave}` | `{timestamp}#{type}` | Live wave event feed |

**TTL**: `expires_at` (90 days dev, 365 days prod)

---

## Glossary

| Term | Meaning |
|------|---------|
| **Crow** | Specialized AI agent with a defined role (planner, implementer, reviewer, fixer) |
| **Murder** | Orchestrator Lambda — coordinates crow lifecycle via DynamoDB Streams |
| **Monarch** | Project setup agent — generates docs, plans milestones, launches first wave |
| **Council** | 6-advisor AI review panel (clarity, market, maturity, performance, quality, security) |
| **Wave** | Execution batch — a set of MVIs dispatched together with a budget cap |
| **MVI** | Minimum Valuable Increment — a 2–8 hour deliverable (the merge unit) |
| **Nest** | Git worktree on EFS where a crow works (isolated per execution) |
| **Blackboard** | Shared DynamoDB state that crows and the Murder read and write |
| **Human Task** | Work item requiring human input — secrets, approvals, design decisions |
| **Autopilot** | Voice-driven project creation — speak → refine → launch |
| **Vault** | KMS-encrypted per-project secret store |

---

<div align="center">

**Cawnex** — _Coordinated Intelligence_

Built with obsession by humans and crows.

</div>
