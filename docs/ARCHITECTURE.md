# Cawnex — Technical Architecture

> AWS serverless, multi-tenant, blackboard-driven orchestration

---

## Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Compute (API)** | AWS Lambda + API Gateway v2 | Pay-per-request, scale to zero |
| **Compute (Workers)** | AWS Lambda (initially), ECS Fargate (when needed) | Start simple, graduate to Fargate for >15min tasks |
| **Database** | DynamoDB (single-table) | Serverless, multi-tenant isolation via partition keys, pay-per-request |
| **Storage** | S3 | .pen files, artifacts, worktree snapshots. S3-compatible abstraction (R2/Tigris swappable) |
| **Auth** | Cognito | Apple Sign In + email/password, JWT, built-in user management |
| **CDN** | CloudFront | HTTPS termination, API caching where appropriate |
| **IaC** | CDK (TypeScript) | In monorepo, deployed via GitHub Actions |
| **iOS** | Swift 6 + SwiftUI | Native, no cross-platform |
| **Android** | Kotlin + Jetpack Compose | Native (future) |
| **Web** | React + Vite | Admin/ops dashboard (secondary) |
| **LLM** | BYOL via Anthropic SDK | Users provide API keys, we use `anthropic.AsyncAnthropic` |
| **Git** | GitHub API + worktrees | PRs, branches, code review |

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│                     iOS App (SwiftUI)                     │
│                                                            │
│  Vision Chat │ Approvals │ Live Stream │ Crows │ Settings  │
└──────────────────────────┬─────────────────────────────────┘
                           │ HTTPS
                           ▼
┌──────────────────────────────────────────────────────────┐
│          CloudFront → API Gateway v2 (HTTP API)           │
│                                                            │
│  /projects  /milestones  /tasks  /executions  /vision      │
│  /agents    /workflows   /repos  /auth       /pens         │
└──────────────────────────┬─────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│                Lambda Functions (Python 3.12)              │
│                                                            │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐     │
│  │ API     │ │ Vision   │ │ Pen API  │ │ Webhook  │     │
│  │ Handler │ │ Chat     │ │ Handler  │ │ Handler  │     │
│  └─────────┘ └──────────┘ └──────────┘ └──────────┘     │
└──────────────────────────┬─────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
     ┌──────────────┐           ┌──────────┐
     │   DynamoDB   │           │    S3    │
     │  (data +     │           │ (files)  │
     │  blackboard) │           └──────────┘
     └──────┬───────┘
            │ DynamoDB Streams
            ▼
     ┌──────────────┐
     │   Murder     │ ◄── Judge + Dispatcher (never a worker)
     │   Lambda     │
     │              │
     │  Reads blackboard state
     │  Decides next action
     │  Assigns crows
     │  Approves / rejects
     └──────┬───────┘
            │ Invokes
            ▼
     ┌──────────────┐
     │ Crow Lambdas │ ◄── Workers (Planner, Implementer, Reviewer, etc.)
     │              │
     │  Reads task from blackboard
     │  Executes (LLM + tools)
     │  Writes results to blackboard
     └──────────────┘
```

---

## Blackboard Pattern — Orchestration

The **blackboard** is a shared DynamoDB state that all agents (Murder + Crows) read and write to. It replaces message queues (SQS/Redis/Kafka) as the coordination mechanism.

### How It Works

1. **Trigger**: GitHub webhook / API call creates an Execution in DynamoDB
2. **Murder wakes up** (via DynamoDB Streams) → reads the blackboard → decides what to do
3. Murder writes a **CrowTask** to the blackboard → assigns a crow
4. **Crow Lambda fires** (via DynamoDB Streams on the new task) → reads its assignment → executes → writes a **CrowReport** back to the blackboard
5. **Murder wakes up again** (stream event from the report) → reads the report → decides next action
6. Repeat until all work is done
7. Murder writes final **approval or rejection** to the blackboard

### Murder — The Judge

Murder is **never a worker**. It never writes code, creates plans, or produces artifacts. It only:

- **Reads** the blackboard (execution state, crow reports, context)
- **Decides** what needs to happen next:
  - "This issue needs a plan" → assigns **Planner Crow**
  - "Plan looks good, time to implement" → assigns **Implementer Crow**
  - "Code is done, needs review" → assigns **Reviewer Crow**
  - "Needs documentation" → assigns **Documentation Crow**
  - "This output is bad" → **rejects** with specific feedback, reassigns the same or different crow
  - "Everything looks good" → **approves**, triggers PR merge
- **Writes** decisions (go / no-go / rerun with instructions) to the blackboard

Murder is a lightweight Lambda — mostly reads state, calls an LLM for judgment, writes a decision. Fast and cheap.

### Crows — The Workers

Each crow is a **specialist** that receives a task and produces a result:

| Crow | Role | Input | Output |
|------|------|-------|--------|
| **Planner** | Breaks issue into implementation plan | Issue + vision + context | Structured plan (steps, files, approach) |
| **Implementer** | Writes code | Plan + repo context | Code changes, commits |
| **Reviewer** | Reviews code for quality/correctness | Code diff + acceptance criteria | Review verdict + feedback |
| **Documenter** | Writes/updates docs | Code changes + project context | Documentation changes |
| **Fixer** | Addresses review feedback | Review comments + code | Fixed code |

Crows don't know about each other. They read their task from the blackboard, execute, and write results back. Murder coordinates everything.

### Execution Lifecycle

```
GitHub Issue
    │
    ▼
┌─────────────────────────────────────────────┐
│ Execution created (status: pending)          │
│ DynamoDB Stream fires → Murder Lambda        │
└──────────────────────┬──────────────────────┘
                       ▼
              Murder: "Needs a plan"
              → writes CrowTask (planner)
                       │
                       ▼ (Stream fires → Crow Lambda)
              Planner Crow executes
              → writes CrowReport (plan)
                       │
                       ▼ (Stream fires → Murder Lambda)
              Murder: reads plan
              → GO: "Plan approved, implement it"
              → writes CrowTask (implementer)
                  ── or ──
              → NO-GO: "Plan is weak, redo with notes"
              → writes CrowTask (planner, with feedback)
                       │
                       ▼ (Stream fires → Crow Lambda)
              Implementer Crow executes
              → writes CrowReport (code changes)
                       │
                       ▼ (Stream fires → Murder Lambda)
              Murder: "Code done, needs review"
              → writes CrowTask (reviewer)
                       │
                       ▼ ...
              Review → Murder approves or sends to Fixer
                       │
                       ▼
              Murder: "All good"
              → writes final approval
              → triggers PR merge
              → Execution status: completed
```

### CrowTask — What Murder Assigns

```json
{
  "execution_id": "exec_abc123",
  "step": 2,
  "crow": "implementer",
  "action": "implement",
  "task_description": "Implement the auth flow as described in the plan",
  "acceptance_criteria": [
    "Apple Sign In integration works",
    "JWT tokens returned on success",
    "Error handling for denied/cancelled"
  ],
  "context": {
    "vision": "Project vision summary...",
    "milestone": "Milestone 1: Auth + Onboarding",
    "previous_reports": [ /* Planner's report */ ],
    "murder_notes": "Follow the plan exactly. Use Cognito SDK, not raw HTTP."
  },
  "repo": {
    "url": "github.com/user/repo",
    "branch": "cawnex/exec_abc123",
    "base_branch": "main"
  },
  "constraints": {
    "max_tokens": 100000,
    "timeout_seconds": 600,
    "budget_usd": 2.00
  }
}
```

### CrowReport — What Crows Return

```json
{
  "execution_id": "exec_abc123",
  "step": 2,
  "crow": "implementer",
  "outcome": "completed",
  "summary": "Implemented Apple Sign In with Cognito integration",
  "criteria_results": [
    { "criterion": "Apple Sign In integration works", "pass": true, "detail": "Using ASAuthorizationController" },
    { "criterion": "JWT tokens returned on success", "pass": true, "detail": "Access + refresh tokens from Cognito" },
    { "criterion": "Error handling for denied/cancelled", "pass": true, "detail": "Handles .cancelled, .failed, .notHandled" }
  ],
  "artifacts": {
    "branch": "cawnex/exec_abc123",
    "files_changed": ["Sources/Auth/AppleSignIn.swift", "Sources/Auth/CognitoClient.swift"],
    "commit_sha": "a1b2c3d"
  },
  "cost": {
    "tokens_in": 12500,
    "tokens_out": 8300,
    "usd": 0.42
  },
  "context_for_next": "Auth flow complete. CognitoClient exposes `signIn()` and `refreshToken()` methods."
}
```

### Why Blackboard, Not Message Queues

| Concern | Blackboard (DynamoDB) | Message Queue (SQS/Kafka) |
|---------|----------------------|--------------------------|
| **State** | Single source of truth — everyone reads/writes same place | State split between queue + DB, must sync |
| **Visibility** | Full execution history queryable at any time | Messages consumed and gone |
| **Coordination** | DynamoDB Streams trigger next step automatically | Need separate routing logic |
| **Debugging** | Read the blackboard to see exactly what happened | Need to reconstruct from logs |
| **Cost** | DynamoDB Streams: free with the table | SQS: cheap but another service to manage |
| **Simplicity** | One data store for everything | Two systems (queue + state store) |

---

## Multi-Tenant Isolation

Every piece of data is scoped to a tenant:

| Layer | Isolation Method |
|-------|-----------------|
| **DynamoDB** | Partition key prefix: `T#<tenant_id>` |
| **S3** | Key prefix: `tenants/<tenant_id>/` |
| **Cognito** | Custom attribute: `custom:tenant_id` |
| **API** | JWT contains `tenant_id`, enforced on every request |
| **Blackboard** | Execution records include `tenant_id`, crows only see their tenant's data |

---

## DynamoDB — Single Table Design

### Table: `cawnex-{stage}`

| PK | SK | Entity | Description |
|----|-----|--------|-------------|
| `T#<tid>` | `PROJECT#<pid>` | Project | Vision, name, status |
| `T#<tid>` | `PROJECT#<pid>#MILESTONE#<mid>` | Milestone | Description, order, progress |
| `T#<tid>` | `PROJECT#<pid>#TASK#<taskid>` | Task | Status, description, milestone ref |
| `T#<tid>` | `PROJECT#<pid>#REPO#<rid>` | Repository | GitHub URL, default branch |
| `T#<tid>` | `PROJECT#<pid>#WORKFLOW#<wid>` | Workflow | Pipeline steps |
| `T#<tid>` | `PROJECT#<pid>#VISION_MSG#<ts>` | Vision Message | Chat history with Vision AI |
| `T#<tid>` | `AGENT#<aid>` | Agent Definition | Crow config (prompt, model, tools) |
| `T#<tid>` | `LLMCONFIG` | LLM Config | Encrypted API keys, model preferences |
| `T#<tid>` | `PROFILE` | Tenant Profile | Name, plan, billing |
| `T#<tid>` | `PEN#<penid>` | Pen File Metadata | S3 key, name, project ref |

#### Blackboard Records (Execution State)

| PK | SK | Entity | Description |
|----|-----|--------|-------------|
| `T#<tid>#EXEC#<eid>` | `META` | Execution | Status, issue ref, timestamps, final verdict |
| `T#<tid>#EXEC#<eid>` | `PLAN` | Plan | Planner's structured plan, Murder's approval/rejection |
| `T#<tid>#EXEC#<eid>` | `STEP#<seq>#TASK` | CrowTask | What Murder assigned to the crow |
| `T#<tid>#EXEC#<eid>` | `STEP#<seq>#REPORT` | CrowReport | What the crow produced |
| `T#<tid>#EXEC#<eid>` | `STEP#<seq>#DECISION` | Murder Decision | Go / no-go / rerun + feedback |
| `T#<tid>#EXEC#<eid>` | `EVENT#<ts>` | Event | Fine-grained stream (tool calls, output, errors) |

### GSI1 — Query by status across projects
| GSI1PK | GSI1SK | Use case |
|--------|--------|----------|
| `T#<tid>#STATUS#pending_approval` | `<created_at>` | Approval queue |
| `T#<tid>#STATUS#running` | `<started_at>` | Active executions |
| `T#<tid>#STATUS#completed` | `<completed_at>` | Recent completed |

### GSI2 — Admin / cross-tenant
| GSI2PK | GSI2SK | Use case |
|--------|--------|----------|
| `PLAN#pro` | `T#<tid>` | All pro tenants |
| `EXECUTION#<date>` | `T#<tid>#<eid>` | Global execution log |

---

## S3 Structure

```
cawnex-artifacts-{stage}-{account}/
├── tenants/
│   └── <tenant_id>/
│       ├── pens/
│       │   ├── <pen_id>.pen          # .pen JSON files
│       │   └── <pen_id>.thumb.png    # Generated thumbnails (future)
│       ├── worktrees/
│       │   └── <execution_id>/       # Worktree snapshots
│       └── artifacts/
│           └── <execution_id>/       # Build artifacts, logs
└── tmp/                               # Ephemeral (7-day lifecycle)
```

---

## Auth Flow (Cognito)

```
iOS App → Apple Sign In → Cognito User Pool → JWT (access + refresh)
                                                    │
                                                    ▼
                                            API Gateway
                                            (JWT authorizer)
                                                    │
                                                    ▼
                                              Lambda
                                              (extracts tenant_id from JWT)
```

---

## Pen API (Lambda)

.pen files are Pencil's JSON-based design format. Cawnex stores them on S3 with metadata in DynamoDB.

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/pens` | Create a new .pen file |
| `GET` | `/pens` | List .pen files (for tenant) |
| `GET` | `/pens/{id}` | Get .pen file metadata + signed S3 URL |
| `PUT` | `/pens/{id}` | Update .pen file |
| `DELETE` | `/pens/{id}` | Delete .pen file |

### .pen File Format

.pen files are JSON documents describing a scene graph:

```json
{
  "version": "2.8",
  "themes": { "Mode": ["light", "dark"] },
  "variables": {
    "--primary": { "type": "color", "value": "#7C3AED" },
    "--radius-m": { "type": "number", "value": 8 }
  },
  "children": [
    {
      "type": "frame",
      "id": "screen1",
      "layout": "vertical",
      "children": [...]
    }
  ]
}
```

**Node types:** `frame`, `group`, `rectangle`, `ellipse`, `line`, `polygon`, `path`, `text`, `icon_font`, `ref`, `note`, `prompt`, `context`

### .pen → SwiftUI Rendering

The iOS app renders .pen files natively as SwiftUI views:

| .pen type | SwiftUI |
|-----------|---------|
| `frame` (vertical) | `VStack` |
| `frame` (horizontal) | `HStack` |
| `frame` (none) | `ZStack` |
| `text` | `Text` |
| `rectangle` | `RoundedRectangle` |
| `ellipse` | `Ellipse` |
| `image` | `AsyncImage` |
| `icon_font` | `Image(systemName:)` (SF Symbols) |
| `path` | `Path` (from SVG geometry) |
| `ref` | Rendered component with overrides |
| Variables (`$--name`) | `@Environment` theme resolution |
| Themes (light/dark) | `@Environment(\.colorScheme)` |

---

## Real-Time Updates (iOS)

DynamoDB Streams → Murder/Crow writes to blackboard → Stream triggers a **Notifier Lambda** → pushes to **API Gateway WebSocket** → iOS app receives live execution updates.

No polling. The blackboard drives everything, including the UI.

---

## Worker Architecture

### Initially: Lambda

```
DynamoDB Stream → Murder Lambda → writes CrowTask → Stream → Crow Lambda → writes CrowReport → Stream → Murder Lambda → ...
```

Lambda limit: 15 minutes. Sufficient for most tasks. Worker Lambda: 1-2 GB memory.

### Later: ECS Fargate

When tasks exceed 15 minutes:

```
Murder detects long task → starts Fargate Task instead of Lambda
Fargate Crow executes → writes report to DynamoDB blackboard
Murder picks up via Stream as usual
```

Fargate: 1 vCPU, 2 GB RAM, SPOT in dev, on-demand in prod. Same blackboard protocol — only the compute changes.

### Crow Runtime

Each Crow uses the Anthropic Python SDK with typed tools:

```python
client = anthropic.AsyncAnthropic(api_key=user_api_key)

response = await client.messages.create(
    model=agent_config.model,
    system=agent_config.system_prompt,
    tools=tool_pack,
    messages=[{"role": "user", "content": task_description}]
)
```

**Tool packs:**
- `filesystem`: read_file, write_file, list_files, search
- `shell`: run_command (sandboxed)
- `git`: commit, create_branch, create_pr, diff

---

## Build Order (Increments)

### Increment 0 — AWS Foundation
- CDK stack: DynamoDB (with Streams enabled) + S3 + Cognito + Lambda + API GW
- Deploy empty API (health check endpoint)
- CI/CD: GitHub Actions → `cdk deploy`

### Increment 1 — Pen API
- Lambda functions for .pen CRUD
- S3 storage with tenant-scoped prefixes
- DynamoDB metadata

### Increment 2 — iOS App (parallel)
- Xcode project setup
- .pen → SwiftUI renderer
- Auth flow (Cognito + Apple Sign In)
- Pen file browser UI

### Increment 3 — Observability
- Status endpoint (environment, services, queue depth)
- Project + Milestone + Task CRUD
- Dashboard data endpoints

### Increment 4 — Vision AI
- Vision chat endpoint (streaming)
- AI-generated milestones and tasks
- Approval flow (approve/reject/edit)

### Increment 5 — Blackboard + Murder
- DynamoDB Streams integration
- Murder Lambda (judge + dispatcher)
- Planner Crow (first crow)
- Blackboard records (CrowTask / CrowReport / Decision)

### Increment 6 — Full Crow Pipeline
- Implementer, Reviewer, Documenter, Fixer crows
- End-to-end: issue → plan → implement → review → docs → PR
- Cost tracking per execution

### Increment 7 — Production
- Custom domains (cawnex.ai API)
- Push notifications (APNs)
- WebSocket real-time updates
- Billing integration
- Landing page

---

## Security

| Concern | Approach |
|---------|----------|
| API keys (BYOL) | Encrypted at rest (KMS), never logged, never sent to Cawnex servers |
| Tenant isolation | Partition key enforcement, S3 prefix policies, JWT validation |
| Auth | Cognito JWT, short-lived access tokens, refresh rotation |
| Code execution | Sandboxed worktrees, no host access, time/cost limits |
| Network | HTTPS everywhere, VPC for Fargate (when added) |
| Secrets | AWS Secrets Manager for infra secrets |

---

## Cost Model (AWS)

At low scale (dogfooding):

| Service | Estimated Monthly |
|---------|------------------|
| Lambda (API + Murder + Crows) | ~$1-5 (pay per request) |
| DynamoDB (+ Streams) | ~$1-5 (on-demand, streams free) |
| S3 | ~$0.50 (storage + requests) |
| Cognito | ~$0 (free tier up to 50k MAU) |
| CloudFront | ~$1-2 |
| **Total** | **~$5-15/mo** |

Scales linearly with usage. No idle costs.
