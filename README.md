<div align="center">

# Cawnex

### Coordinated Intelligence

**AI orchestration platform that turns a voice command into a shipped, tested, documented codebase — with human approval at every step.**

_One caw. Three Lambdas. Zero bottlenecks._

---

[System Architecture](#system-architecture) · [Integration Endpoints](#integration-endpoints) · [How It Works](#how-it-works) · [DynamoDB Schema](#dynamodb-schema) · [Glossary](#glossary)

</div>

---

## System Architecture

Cawnex is a fully serverless multi-agent platform on AWS. A user speaks a project idea into their phone, an AI planner (Monarch) asks clarifying questions, then autonomously generates project documents, plans milestones, breaks work into MVIs, and launches AI agents (Crows) that write, review, and fix code in real GitHub repos.

```
iOS App
  │
  ▼
CloudFront → API Gateway v2 (HTTP) → API Lambda (FastAPI + Mangum)
  │                                         │
  │  JWT auth via Cognito                   ├─→ DynamoDB (main table)
  │                                         ├─→ DynamoDB (events table)
  │                                         ├─→ S3 (assets + artifacts)
  │                                         ├─→ KMS (vault encryption)
  │                                         └─→ Claude API (via Secrets Manager)
  │
  ▼
DynamoDB Streams ──┬──→ Murder Lambda (crow orchestration)
                   └──→ Monarch Lambda (async project setup)
  │
  ▼
ECS Fargate Worker (continuous poll)
  ├─→ Claims pending crows from GSI1
  ├─→ Clones repo into EFS worktree
  ├─→ Calls Claude API (plan/implement/review/fix)
  ├─→ Commits code + pushes to GitHub
  └─→ Writes completion snapshot → triggers Murder Lambda
  │
  ▼
Murder Lambda (DynamoDB Stream)
  ├─→ Planner done → assign Implementer
  ├─→ Implementer done → assign Reviewer
  ├─→ Reviewer rejects → assign Fixer
  ├─→ Reviewer approves → MVI ready to ship
  └─→ All MVIs terminal → wave transitions to review
```

### AWS Resources

| Resource            | Name Pattern                   | Purpose                                  |
| ------------------- | ------------------------------ | ---------------------------------------- |
| **API Gateway v2**  | `cawnex-api-{stage}`           | HTTP routing to API Lambda               |
| **Lambda: API**     | `cawnex-api-{stage}`           | FastAPI app (29s timeout, 512MB)         |
| **Lambda: Murder**  | `cawnex-murder-{stage}`        | Crow orchestration reactor (60s timeout) |
| **Lambda: Monarch** | `cawnex-monarch-{stage}`       | Async project setup agent (5min timeout) |
| **Lambda: Checker** | `cawnex-checker-{stage}`       | Hourly verification scan                 |
| **Lambda: Scaler**  | `cawnex-worker-scaler-{stage}` | 15-min auto scale-down                   |
| **Lambda: SSE**     | `cawnex-sse-{stage}`           | Server-Sent Events streaming             |
| **ECS Fargate**     | `cawnex-worker-{stage}`        | Crow execution (1 vCPU, 2GB, SPOT)       |
| **DynamoDB**        | `cawnex-{stage}`               | Main table (single-table design)         |
| **DynamoDB**        | `cawnex-events-{stage}`        | Wave event log                           |
| **S3**              | `cawnex-artifacts-{stage}`     | Repo snapshots, context files            |
| **S3**              | `cawnex-assets-{stage}`        | Human task file uploads                  |
| **EFS**             | `cawnex-repos-{stage}`         | Git worktrees (tenant-isolated)          |
| **SQS**             | `cawnex-tasks-{stage}`         | Task queue (reserved)                    |
| **KMS**             | `alias/cawnex-vault-{stage}`   | Secret encryption                        |
| **Cognito**         | Imported from AuthStack        | JWT authentication                       |

---

## Integration Endpoints

### Public (no auth)

| Method | Path      | Purpose                                                 |
| ------ | --------- | ------------------------------------------------------- |
| GET    | `/health` | Liveness check — returns `{status, stage}`              |
| GET    | `/config` | Client config — returns Cognito pool IDs, region, stage |

### Projects

| Method | Path                 | Purpose                                                 |
| ------ | -------------------- | ------------------------------------------------------- |
| POST   | `/projects`          | Create project (writes list entry + root snapshot)      |
| GET    | `/projects`          | List all projects for tenant                            |
| GET    | `/projects/{id}/hub` | Aggregated hub — project + docs + stats + waves + tasks |

### Documents (AI-guided)

| Method | Path                              | Purpose                                             |
| ------ | --------------------------------- | --------------------------------------------------- |
| PUT    | `/projects/{id}/documents/{type}` | Save document (vision/architecture/glossary/design) |
| GET    | `/projects/{id}/documents/{type}` | Get document (null if not saved)                    |

### Backlog (Milestones → Goals → MVIs)

| Method | Path                                 | Purpose                                    |
| ------ | ------------------------------------ | ------------------------------------------ |
| POST   | `/projects/{id}/milestones`          | Add milestone with goals                   |
| PUT    | `/projects/{id}/milestones`          | Replace all milestones                     |
| GET    | `/projects/{id}/milestones`          | Get milestones with MVI counts per goal    |
| GET    | `/projects/{id}/milestones/context`  | Get all 4 docs as planning context         |
| GET    | `/projects/{id}/goals/{gid}/context` | Get goal + siblings + docs + existing MVIs |
| POST   | `/projects/{id}/goals/{gid}/mvis`    | Save MVIs for goal (max 8h per MVI)        |
| GET    | `/projects/{id}/goals/{gid}/mvis`    | Get MVIs for goal                          |

### Waves (Execution)

| Method | Path                                         | Purpose                                        |
| ------ | -------------------------------------------- | ---------------------------------------------- |
| POST   | `/projects/{id}/waves`                       | Create wave from goal MVIs or ad-hoc directive |
| GET    | `/projects/{id}/waves`                       | List waves (sorted by created_at desc)         |
| GET    | `/projects/{id}/waves/{wid}`                 | Wave detail — MVIs + crows + human tasks       |
| POST   | `/projects/{id}/waves/{wid}/activate`        | Activate → queues MVIs → scales ECS worker     |
| POST   | `/projects/{id}/waves/{wid}/pause`           | Pause execution                                |
| POST   | `/projects/{id}/waves/{wid}/cancel`          | Cancel wave + non-terminal MVIs                |
| GET    | `/projects/{id}/waves/{wid}/events`          | Paginated event feed (limit, cursor)           |
| POST   | `/projects/{id}/waves/{wid}/mvis/{mid}/ship` | Ship MVI (must be ready_to_ship + can_ship)    |

### AI Chat

| Method | Path       | Purpose                                            |
| ------ | ---------- | -------------------------------------------------- |
| POST   | `/ai/chat` | Claude API proxy — tracks cost on project snapshot |

### Autopilot (Voice-driven project creation)

| Method | Path                       | Purpose                                                             |
| ------ | -------------------------- | ------------------------------------------------------------------- |
| POST   | `/projects/autopilot/chat` | Stateful Monarch chat — gathering → proposed → executing → complete |

### Human Tasks

| Method | Path                                           | Purpose                                   |
| ------ | ---------------------------------------------- | ----------------------------------------- |
| GET    | `/projects/{id}/human-tasks`                   | List tasks grouped by status              |
| GET    | `/projects/{id}/human-tasks/{htid}`            | Task detail with input schema             |
| POST   | `/projects/{id}/human-tasks/{htid}/respond`    | Submit response + optional steering       |
| POST   | `/projects/{id}/human-tasks/{htid}/upload-url` | Get presigned S3 upload URL (5min expiry) |

### Vault (Secrets)

| Method | Path                                         | Purpose                      |
| ------ | -------------------------------------------- | ---------------------------- |
| POST   | `/projects/{id}/vault/secrets`               | Store KMS-encrypted secret   |
| GET    | `/projects/{id}/vault/secrets`               | List metadata (never values) |
| DELETE | `/projects/{id}/vault/secrets/{name}`        | Remove secret                |
| PUT    | `/projects/{id}/vault/secrets/{name}/rotate` | Re-encrypt with new value    |

---

## How It Works

### 1. Autopilot Flow (Voice → Shipped Code)

```
User holds FAB → speaks "Build a URL shortener on AWS"
  │
  ▼ (SFSpeechRecognizer transcribes)
POST /projects/autopilot/chat { message: "Build a URL shortener on AWS" }
  │
  ▼ (Monarch asks 2-3 questions via Claude)
POST /projects/autopilot/chat { message: "Python, create new repo, with analytics" }
  │
  ▼ (Monarch proposes structured plan)
Response: { phase: "proposed", plan: { milestones, goals, mvis } }
  │
  ▼ (User taps "Launch")
POST /projects/autopilot/chat { action: "launch" }
  │
  ├─ Creates project (instant) → returns project_id
  └─ Writes MONARCH#task to DynamoDB
       │
       ▼ (DynamoDB Stream triggers Monarch Lambda)
  Monarch Lambda (async, ~60s):
    ├─ Generates vision document via Claude → emits event
    ├─ Generates architecture document → emits event
    ├─ Generates glossary document → emits event
    ├─ Generates design document → emits event
    ├─ Saves milestones + goals + MVIs → emits event
    ├─ Creates wave + activates → emits event
    └─ Scales ECS worker to 1
         │
         ▼ (Worker picks up planner crow)
  Worker ECS (continuous poll):
    ├─ Planner: breaks MVI into tasks → writes completion
    │    ▼ (Murder Lambda reacts)
    ├─ Implementer: writes code, commits, pushes → writes completion
    │    ▼ (Murder Lambda reacts)
    ├─ Reviewer: reviews code → approves or rejects
    │    ▼ (if rejected → Fixer → re-review loop)
    └─ MVI ready to ship → wave transitions to review
```

### 2. Crow Lifecycle (State Machine)

```
Planner (completed)
  ├─ has tasks → Implementer
  ├─ has human tasks → create HumanTask + Implementer (for non-blocked tasks)
  ├─ oversized tasks → SplitRequired (re-plan with split instructions)
  └─ no tasks → FailMVI

Implementer (completed) → Reviewer

Reviewer (completed)
  ├─ approved (no blocking issues) → MarkMVIReady
  ├─ rejected → Fixer
  └─ max fix cycles exceeded → FailMVI

Fixer (completed) → Reviewer (re-review)

Any crow (failed)
  ├─ retries < max → retry same crow type
  └─ retries exhausted → FailMVI
```

### 3. Wave Lifecycle

```
planning → approved → executing → review → delivered
                        │
                        ├─→ paused → executing (resume)
                        ├─→ steered → proposed/executing
                        └─→ cancelled

All MVIs terminal (ready_to_ship/shipped/failed) → wave auto-transitions to review
```

### 4. Murder Lambda Reactions

The Murder Lambda is triggered by DynamoDB Streams on every INSERT/MODIFY:

| Trigger                   | Action                                                 |
| ------------------------- | ------------------------------------------------------ |
| MVI status → `queued`     | Assign planner crow with instructions                  |
| Crow status → `completed` | Run state machine → assign next crow or mark MVI ready |
| Crow status → `failed`    | Retry or fail MVI                                      |
| Human task → `completed`  | Unblock dependent crows, resume execution              |
| All MVIs terminal         | Transition wave to `review`                            |

### 5. Worker Execution Loop

```python
while True:
    # Query GSI1 for DISPATCH#pending crows
    pending = query(GSI1PK="DISPATCH#pending")
    for crow in pending:
        # Claim: pending → running (conditional update)
        claim(crow)
        # Clone repo + checkout branch
        worktree = create_worktree(crow.repo, crow.branch)
        # Call Claude with instructions + repo context
        result = call_claude(crow.instructions, worktree_context)
        # Commit + push changes
        git_commit_and_push(worktree, result)
        # Write completion snapshot (triggers Murder Lambda)
        write_completion(crow, result)
    sleep(10)
```

---

## DynamoDB Schema

### Main Table — Single-Table Design

| PK                       | SK                              | Entity       | Purpose                     |
| ------------------------ | ------------------------------- | ------------ | --------------------------- |
| `T#{tenant}`             | `P#{project}`                   | ProjectEntry | Project list                |
| `T#{tenant}`             | `AUTOPILOT#{session}`           | Session      | Autopilot chat state        |
| `T#{tenant}#VAULT`       | `P#{project}#S#{name}`          | Secret       | Encrypted secrets           |
| `T#{tenant}#P#{project}` | `S#`                            | Snapshot     | Project root                |
| `T#{tenant}#P#{project}` | `DOC#{type}`                    | Document     | Vision/arch/glossary/design |
| `T#{tenant}#P#{project}` | `BACKLOG#milestones`            | Backlog      | Milestones + goals          |
| `T#{tenant}#P#{project}` | `BACKLOG#goal#{gid}#mvis`       | GoalMVIs     | MVIs per goal               |
| `T#{tenant}#P#{project}` | `MONARCH#task`                  | MonarchTask  | Async setup trigger         |
| `T#{tenant}#P#{project}` | `S#{wave}`                      | Snapshot     | Wave root                   |
| `T#{tenant}#P#{project}` | `S#{wave}#m{mvi}`               | Snapshot     | MVI under wave              |
| `T#{tenant}#P#{project}` | `S#{wave}#m{mvi}#cr_{type}_{n}` | Snapshot     | Crow under MVI              |
| `T#{tenant}#P#{project}` | `S#{wave}#m{mvi}#ht_{id}`       | Snapshot     | Human task                  |

**GSI1** (worker dispatch): `GSI1PK=DISPATCH#pending` → crows waiting for execution

### Events Table

| PK                                | SK                   | Purpose                 |
| --------------------------------- | -------------------- | ----------------------- |
| `T#{tenant}#P#{project}#W#{wave}` | `{timestamp}#{type}` | Wave events (live feed) |

**GSI1**: `T#{tenant}#P#{project}` → project-level event queries

**TTL**: `expires_at` (90 days dev, 365 days prod)

---

## Glossary

| Term           | Meaning                                                                          |
| -------------- | -------------------------------------------------------------------------------- |
| **Crow**       | Specialized AI agent with a defined role (planner, implementer, reviewer, fixer) |
| **Murder**     | Orchestrator Lambda that coordinates crow lifecycle via DynamoDB Streams         |
| **Monarch**    | Project setup agent — generates docs, plans milestones, launches first wave      |
| **Wave**       | Execution batch — a set of MVIs dispatched together with a budget                |
| **MVI**        | Minimum Valuable Increment — a 2-8 hour deliverable (the merge unit)             |
| **Nest**       | Git worktree where a crow works (isolated per execution)                         |
| **Blackboard** | Shared DynamoDB state that crows read/write                                      |
| **Human Task** | Work item requiring human input (secrets, approvals, design decisions)           |
| **Autopilot**  | Voice-driven project creation flow (speak → refine → launch)                     |

---

## Tech Stack

| Layer        | Technology                                                  |
| ------------ | ----------------------------------------------------------- |
| **iOS**      | Swift + SwiftUI (native)                                    |
| **API**      | Python 3.12 + FastAPI + Mangum (Lambda)                     |
| **AI**       | Claude (Haiku 4.5 for crows, via Anthropic OAuth)           |
| **Database** | DynamoDB (single-table + events table)                      |
| **Storage**  | S3 (assets + artifacts) + EFS (git repos)                   |
| **Compute**  | Lambda (API, Murder, Monarch, SSE) + ECS Fargate (Worker)   |
| **Auth**     | Cognito (JWT) + API Gateway authorizer                      |
| **Secrets**  | KMS (vault) + Secrets Manager (API keys)                    |
| **Infra**    | AWS CDK (TypeScript)                                        |
| **CI/CD**    | GitHub Actions (smart change detection + tag-based deploys) |

---

## Project Structure

```
cawnex/
├── apps/
│   ├── api/              # FastAPI Lambda — all REST endpoints
│   │   ├── src/routes/   # autopilot, projects, waves, documents, goals, etc.
│   │   ├── src/claude/   # Claude API client (OAuth)
│   │   ├── src/db/       # TenantDB (DynamoDB client)
│   │   └── tests/        # 80+ unit tests, 75%+ coverage
│   ├── worker/           # ECS Fargate — crow execution engine
│   │   ├── main.py       # Continuous poll loop
│   │   └── Dockerfile    # Python 3.12 slim + git
│   └── ios/              # SwiftUI native app
│       └── Cawnex/
│           ├── Features/ # Autopilot, Waves, MVI, Backlog, HumanTasks, etc.
│           ├── Core/     # Network, Auth, Navigation, Theme, Speech
│           └── Components/ # Reusable UI (FAB, cards, buttons, bars)
├── lambdas/
│   ├── murder/           # Crow orchestration (DynamoDB Stream)
│   │   └── src/murder/   # handler, reactor, state_machine, events, etc.
│   ├── monarch/          # Project setup agent (DynamoDB Stream)
│   │   └── src/monarch/  # handler, agent, documents, planner, wave_launcher
│   ├── worker/           # Shared worker library (crow execution)
│   ├── orchestration/    # Checker + Worker Scaler
│   └── sse/              # Server-Sent Events streaming
├── infra/
│   └── lib/cawnex-stack.ts  # CDK — all AWS resources
├── design/
│   └── cawnex.pen        # Pencil design file (all screens)
├── docs/
│   ├── design/           # Screen specs, architecture decisions
│   └── VISION.md         # Product vision
├── scripts/              # iOS config sync, deployment helpers
└── .github/workflows/    # CI/CD pipelines
```

---

<div align="center">

**Cawnex** — _Coordinated Intelligence_

Built with obsession by humans and crows.

</div>
