# Cawnex — Technical Architecture

> AWS serverless, multi-tenant, .pen-native

---

## Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Compute (API)** | AWS Lambda + API Gateway v2 | Pay-per-request, scale to zero |
| **Compute (Workers)** | AWS Lambda (initially), ECS Fargate (when needed) | Start simple, graduate to Fargate for >15min tasks |
| **Database** | DynamoDB (single-table) | Serverless, multi-tenant isolation via partition keys, pay-per-request |
| **Queue** | SQS + DLQ | Task queue, replaces Redis Streams |
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
│                CloudFront (CDN + HTTPS)                    │
└──────────────────────────┬─────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│              API Gateway v2 (HTTP API)                     │
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
│  └────┬────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘     │
│       │           │            │             │            │
│       ▼           ▼            ▼             ▼            │
│  ┌─────────────────────────────────────────────────┐     │
│  │              Shared Python Packages              │     │
│  │  core (models, schemas) │ providers (BYOL)      │     │
│  │  git_ops (GitHub API)   │ pen (file operations)  │     │
│  └─────────────────────────────────────────────────┘     │
└──────────────────────────┬─────────────────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
     ┌──────────┐  ┌──────────┐  ┌──────────┐
     │ DynamoDB │  │    S3    │  │   SQS    │
     │ (data)   │  │ (files)  │  │ (queue)  │
     └──────────┘  └──────────┘  └────┬─────┘
                                      │
                                      ▼
                              ┌──────────────┐
                              │   Worker     │
                              │   Lambda     │
                              │              │
                              │  Murder      │
                              │  (orchestr.) │
                              │      │       │
                              │  ┌───┴────┐  │
                              │  │ Crows  │  │
                              │  └────────┘  │
                              └──────────────┘
```

---

## Multi-Tenant Isolation

Every piece of data is scoped to a tenant:

| Layer | Isolation Method |
|-------|-----------------|
| **DynamoDB** | Partition key prefix: `T#<tenant_id>` |
| **S3** | Key prefix: `tenants/<tenant_id>/` |
| **SQS** | Message attribute: `tenant_id` (single queue, filtered) |
| **Cognito** | Custom attribute: `custom:tenant_id` |
| **API** | JWT contains `tenant_id`, enforced on every request |

---

## DynamoDB — Single Table Design

### Table: `cawnex-{stage}`

| PK | SK | Entity | Example |
|----|-----|--------|---------|
| `T#<tid>` | `PROJECT#<pid>` | Project | Vision, name, status |
| `T#<tid>` | `PROJECT#<pid>#MILESTONE#<mid>` | Milestone | Description, order, progress |
| `T#<tid>` | `PROJECT#<pid>#TASK#<taskid>` | Task | Status, description, milestone ref |
| `T#<tid>` | `PROJECT#<pid>#EXECUTION#<eid>` | Execution | Status, crow, cost, duration |
| `T#<tid>` | `PROJECT#<pid>#EXECUTION#<eid>#EVENT#<ts>` | Event | Stream line (tool_use, output, etc.) |
| `T#<tid>` | `PROJECT#<pid>#REPO#<rid>` | Repository | GitHub URL, default branch |
| `T#<tid>` | `PROJECT#<pid>#WORKFLOW#<wid>` | Workflow | Pipeline steps |
| `T#<tid>` | `AGENT#<aid>` | Agent Definition | Crow config (prompt, model, tools) |
| `T#<tid>` | `LLMCONFIG` | LLM Config | Encrypted API keys, model preferences |
| `T#<tid>` | `PROFILE` | Tenant Profile | Name, plan, billing |
| `T#<tid>` | `PEN#<penid>` | Pen File Metadata | S3 key, name, project ref |
| `T#<tid>` | `PROJECT#<pid>#VISION_MSG#<ts>` | Vision Message | Chat history with Vision AI |

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

## SQS — Task Queue

**Queue:** `cawnex-tasks-{stage}`

Message format:
```json
{
  "tenant_id": "t_abc123",
  "project_id": "p_xyz",
  "task_id": "task_001",
  "workflow_id": "wf_code_shipping",
  "priority": "normal"
}
```

**DLQ:** `cawnex-tasks-dlq-{stage}` (3 retries, 14-day retention)

Visibility timeout: 30 minutes (Murder runs can be long)

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

**Key concepts:**
- `frame` = container with flexbox layout (vertical/horizontal/none)
- `$--varname` = design token variable reference
- `ref` = component instance (references a `reusable: true` component)
- `descendants` = property overrides on component instances
- `slot` = placeholder for children in container components
- `themes` = multi-axis theming (light/dark, compact/regular, etc.)

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

Full property mapping documented in `docs/pen-swiftui-mapping.md`.

---

## Worker Architecture

### Initially: Lambda

```
SQS → Lambda (Murder) → Crow (Anthropic SDK) → GitHub API → PR
```

Lambda limit: 15 minutes. Sufficient for simple tasks. Worker Lambda has higher memory (1-2 GB).

### Later: ECS Fargate

When tasks exceed 15 minutes or need persistent state:

```
SQS → Fargate Task (Murder) → Crow (long-running) → GitHub API → PR
```

Fargate: 1 vCPU, 2 GB RAM, SPOT in dev, on-demand in prod.

### Murder Pipeline

```
Task received
    ↓
Load workflow (e.g., Refine → Implement → Review → Document)
    ↓
For each step:
    ├── Select Crow (from agent config)
    ├── Create Nest (git worktree)
    ├── Inject context (vision, milestone, previous step output)
    ├── Execute Crow (Anthropic SDK + tools)
    ├── Stream events → DynamoDB + SSE
    ├── Handle errors (retry / skip / fail based on on_fail config)
    └── Pass output to next step
    ↓
Open PR (if implementation step succeeded)
    ↓
Record execution (cost, duration, outcome)
```

### Crow Runtime

Each Crow uses the Anthropic Python SDK with typed tools:

```python
client = anthropic.AsyncAnthropic(api_key=user_api_key)

# Tools: filesystem (read/write/list), shell (run commands), git (commit/branch/PR)
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
- CDK stack: DynamoDB + S3 + Cognito + Lambda + API GW
- Deploy empty API (health check endpoint)
- CI/CD: GitHub Actions → `cdk deploy`

### Increment 1 — Pen API
- Lambda functions for .pen CRUD
- S3 storage with tenant-scoped prefixes
- DynamoDB metadata (PK: `T#<tid>`, SK: `PEN#<penid>`)

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

### Increment 5 — Execution Engine
- SQS integration
- Murder orchestrator (Lambda)
- Single Crow (Dev Crow) with Anthropic SDK
- Event streaming (SSE via Lambda streaming response)

### Increment 6 — Full Pipeline
- Refine → Implement → Review → Document
- Multiple Crows
- GitHub PR integration
- Cost tracking

### Increment 7 — Production
- Custom domains (cawnex.ai API)
- Push notifications (APNs)
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
| Lambda (API + Worker) | ~$1-5 (pay per request) |
| DynamoDB | ~$1-5 (on-demand) |
| S3 | ~$0.50 (storage + requests) |
| SQS | ~$0 (free tier) |
| Cognito | ~$0 (free tier up to 50k MAU) |
| CloudFront | ~$1-2 |
| **Total** | **~$5-15/mo** |

Scales linearly with usage. No idle costs.
