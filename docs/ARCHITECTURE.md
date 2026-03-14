# Cawnex — Technical Architecture

> AWS serverless, multi-tenant, MCP-native, blackboard-driven orchestration

---

## Stack

| Layer                 | Technology                                        | Why                                                                                        |
| --------------------- | ------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| **Compute (API)**     | AWS Lambda + API Gateway v2                       | Pay-per-request, scale to zero                                                             |
| **Compute (Workers)** | AWS Lambda (initially), ECS Fargate (when needed) | Start simple, graduate to Fargate for >15min tasks                                         |
| **Database**          | DynamoDB (single-table)                           | Serverless, multi-tenant isolation via partition keys, pay-per-request                     |
| **Storage**           | S3                                                | .pen files, artifacts, worktree snapshots. S3-compatible abstraction (R2/Tigris swappable) |
| **Auth**              | Cognito                                           | Apple Sign In + email/password, JWT, built-in user management                              |
| **CDN**               | CloudFront                                        | HTTPS termination, API caching where appropriate                                           |
| **IaC**               | CDK (TypeScript)                                  | In monorepo, deployed via GitHub Actions                                                   |
| **iOS**               | Swift 6 + SwiftUI                                 | Native, no cross-platform                                                                  |
| **Android**           | Kotlin + Jetpack Compose                          | Native (future)                                                                            |
| **Web**               | React + Vite                                      | Admin/ops dashboard (secondary)                                                            |
| **LLM**               | BYOL via Anthropic SDK                            | Users provide API keys, we use `anthropic.AsyncAnthropic`                                  |
| **Git**               | GitHub API + worktrees                            | PRs, branches, code review                                                                 |

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
│  /projects  /milestones  /goals  /mvis  /tasks  /executions │
│  /vision  /agents  /murders  /workflows  /repos  /auth  /pens │
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

A **Murder** is a specialized orchestrator tuned for a domain. Different Murder types have different crow compositions and different judgment patterns:

| Murder Type   | Crow Set                                               |
| ------------- | ------------------------------------------------------ |
| **Dev**       | Planner, Implementer, Reviewer, Fixer, Documenter      |
| **Editorial** | Researcher, Outliner, Writer, Editor, Proofreader      |
| **Social**    | Content Creator, Visual Designer, Scheduler, Analyst   |
| **Infra**     | IaC Writer, Security Auditor, Cost Optimizer, Deployer |

Murder is **never a worker**. It never writes code, creates plans, or produces artifacts. It only:

- **Reads** the blackboard (execution state, crow reports, context)
- **Decides** dynamically which crow(s) to activate next — there is no fixed pipeline. Murder can run multiple crows simultaneously (e.g., Implementer + Documenter in parallel).
- **Writes** decisions (go / no-go / rerun with instructions / MVI_READY) to the blackboard

Murder operates at two scopes:

- **Within an MVI (crow coordination)**: coordinates the crow cycle for each individual PR, deploying whichever crows its judgment determines are needed. Murder reads the MVI Blackboard, assigns CrowTasks, evaluates CrowReports, and decides go/no-go/rerun.
- **At the Goal level (MVI coordination)**: when an MVI completes, Murder checks the Goal-level blackboard to determine whether completed MVIs affect in-progress MVIs. It arbitrates cross-MVI dependencies — if context from MVI 1.1 needs to be injected into MVI 1.2, Murder handles that injection at this level before activating MVI 1.2's crow cycle.

Murder never unilaterally merges an MVI. It only declares readiness and waits for human approval.

Murder is a lightweight Lambda — mostly reads state, calls an LLM for judgment, writes a decision. Fast and cheap.

### Crows — The Workers

Each crow is a **specialist** that receives a task and produces a result. The crow set below is the **Dev Murder** configuration — other Murder types have different crow compositions.

#### Dev Murder — Crow Set

| Crow            | Role                                  | Input                           | Output                                   |
| --------------- | ------------------------------------- | ------------------------------- | ---------------------------------------- |
| **Planner**     | Breaks issue into implementation plan | Issue + vision + context        | Structured plan (steps, files, approach) |
| **Implementer** | Writes code                           | Plan + repo context             | Code changes, commits                    |
| **Reviewer**    | Reviews code for quality/correctness  | Code diff + acceptance criteria | Review verdict + feedback                |
| **Documenter**  | Writes/updates docs                   | Code changes + project context  | Documentation changes                    |
| **Fixer**       | Addresses review feedback             | Review comments + code          | Fixed code                               |

Crows don't know about each other. They read their task from the blackboard, execute, and write results back. Murder coordinates everything.

#### Crow Behavior States

Crows don't follow fixed pipeline steps. Each crow operates in a behavioral state that is tracked on the blackboard:

| State           | Description                                                |
| --------------- | ---------------------------------------------------------- |
| **scouting**    | Exploring context, reading codebase, gathering information |
| **planning**    | Breaking down the approach, structuring work               |
| **building**    | Writing code, content, or other artifacts                  |
| **hunting**     | Looking for bugs, running tests, validating output         |
| **reviewing**   | Checking work quality against acceptance criteria          |
| **documenting** | Writing or updating documentation                          |
| **landed**      | Work complete, waiting for Murder's next decision          |

### Execution Lifecycle

Murder does not follow a fixed pipeline. It reads the blackboard and decides dynamically at every step.

```
Trigger (GitHub Issue / API call)
    │
    ▼
┌─────────────────────────────────────────────┐
│ Execution created (status: pending)          │
│ DynamoDB Stream fires → Murder Lambda        │
└──────────────────────┬──────────────────────┘
                       │
    ┌──────────────────▼──────────────────────┐
    │              Murder reads blackboard      │
    │              → decides which crow(s)      │
    │                to activate                │
    │              → can activate multiple      │
    │                crows in parallel          │
    └──────────────────┬──────────────────────┘
                       │ writes CrowTask(s) to blackboard
                       ▼
    ┌──────────────────────────────────────────┐
    │  Crow Lambda(s) fire (Stream event)       │
    │  Each crow:                               │
    │    → reads its task                       │
    │    → executes (LLM + tools)               │
    │    → transitions through behavior states  │
    │      (scouting → building → landed, etc.) │
    │    → writes CrowReport to blackboard      │
    └──────────────────┬───────────────────────┘
                       │ Stream event → Murder Lambda
                       ▼
    ┌──────────────────────────────────────────┐
    │  Murder reads reports                     │
    │  → GO: activate next crow(s)              │
    │  → NO-GO: rerun same crow with feedback   │
    │  → DONE: write final approval             │
    └──────────────────┬───────────────────────┘
                       │
              repeat until done
                       │
                       ▼
              Murder: "All good"
              → writes final approval
              → triggers PR merge (Task level)
              → Execution status: completed
                       │
                       ▼ (when all Tasks in MVI are completed)
              Murder: checks MVI merge_readiness
              → all PRs approved?
              → YES: writes MVI_READY to blackboard
              → Founder approves merge set
              → MVI status: completed
```

### MCP — The Communication Protocol

Murder and Crows communicate via **Model Context Protocol (MCP)** using Streamable HTTP transport. This replaces custom JSON contracts with an open standard.

**Murder = MCP Client.** Connects to crow endpoints, discovers tools, calls them.
**Crows = MCP Servers.** Each crow exposes its skills as MCP tools.

```
Murder (MCP Client)                    Crow (MCP Server)
      │                                      │
      │── initialize ──────────────────────→ │
      │←── capabilities ───────────────────── │
      │                                      │
      │── tools/list ──────────────────────→ │
      │←── [plan, implement, review, ...] ── │
      │                                      │
      │── tools/call("implement", {          │
      │     repo: "user/repo",               │
      │     task: "Add health endpoint",     │
      │     context: { vision, plan, ... }   │
      │   }) ─────────────────────────────→  │
      │                                      │
      │   (crow executes: calls LLM,         │
      │    reads/writes files, commits)      │
      │                                      │
      │←── result: {                         │
      │     outcome: "completed",            │
      │     summary: "Created /health...",   │
      │     branch: "cawnex/exec_abc",       │
      │     files_changed: [...],            │
      │     cost: { tokens, usd }            │
      │   } ──────────────────────────────── │
```

### Three Building Blocks

| Concept            | What It Is                                                            | How It Works                                                                                                                                |
| ------------------ | --------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| **Skills**         | Tool packs (collections of MCP tools)                                 | `filesystem` = read_file + write_file + list_files. `git` = commit + branch + create_pr. Users can create custom skills.                    |
| **Agents (Crows)** | MCP servers loaded with skills + system prompt + model                | Each crow is a Lambda running an MCP server. Its tools come from its assigned skills. Users configure crows in the app (S42).               |
| **Murders**        | MCP clients that orchestrate agents via tool discovery + LLM judgment | Murder connects to crows, discovers their tools, decides which to call based on blackboard state. Users configure murders in the app (S41). |

### Why MCP

- **Open standard** — not a proprietary protocol; ecosystem of tools and clients
- **Dynamic discovery** — Murder doesn't hardcode what crows can do; it asks via `tools/list`
- **Pluggable** — add a new crow with new skills, Murder discovers it automatically
- **User-extensible** — users can create their own skills (MCP tools) and crows (MCP servers)
- **Streamable HTTP** — works natively behind API Gateway → Lambda

### Blackboard Records

Murder writes **task assignments** to the blackboard before calling a crow via MCP. Reports are written after execution. Murder writes **decisions** after judging.

The blackboard is the audit trail. MCP is the live communication channel.

```json
// Task assignment (Murder writes before MCP call)
{
  "PK": "T#tid#EXEC#e1", "SK": "STEP#02#TASK",
  "crow": "implementer",
  "mcp_tool": "implement",
  "mcp_input": { "repo": "user/repo", "task": "...", "context": {} },
  "constraints": { "max_tokens": 100000, "timeout_seconds": 600, "budget_usd": 2.00 }
}

// Report (written after MCP tool call returns)
{
  "PK": "T#tid#EXEC#e1", "SK": "STEP#02#REPORT",
  "outcome": "completed",
  "summary": "Implemented health endpoint",
  "artifacts": { "branch": "cawnex/exec_e1", "files_changed": [], "commit_sha": "a1b2c3d" },
  "cost": { "tokens_in": 12500, "tokens_out": 8300, "usd": 0.42 }
}

// Decision (Murder writes after judging the report)
{
  "PK": "T#tid#EXEC#e1", "SK": "STEP#02#DECISION",
  "verdict": "approve",
  "reason": "Code meets all acceptance criteria",
  "next_action": "assign_reviewer"
}
```

### Why Blackboard, Not Message Queues

| Concern          | Blackboard (DynamoDB)                                                             | Message Queue (SQS/Kafka)                                     |
| ---------------- | --------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| **State**        | Single source of truth — everyone reads/writes same place                         | State split between queue + DB, must sync                     |
| **Visibility**   | Full execution history queryable at any time                                      | Messages consumed and gone                                    |
| **Coordination** | DynamoDB Streams trigger next step automatically                                  | Need separate routing logic                                   |
| **Debugging**    | Read the blackboard to see exactly what happened                                  | Need to reconstruct from logs                                 |
| **Cost**         | DynamoDB Streams: free with the table                                             | SQS: cheap but another service to manage                      |
| **Simplicity**   | One data store for everything                                                     | Two systems (queue + state store)                             |
| **Scoping**      | Natural isolation via partition keys — each MVI's data lives in its own key space | Requires explicit topic/queue-per-scope routing configuration |

---

## Blackboard Scoping

The blackboard is not a single flat namespace. It is scoped at four levels, forming a hierarchy that mirrors the data hierarchy:

```
Project Blackboard     (read-only aggregation — what the iOS dashboard shows)
  └── Milestone Blackboard  (progress tracking — % complete across goals)
       └── Goal Blackboard  (coordination checkpoint — cross-MVI dependencies)
            └── MVI Blackboard  (ACTIVE WORKSPACE — where crows read/write)
                 └── Task records  (individual crow assignments + reports)
```

### MVI Blackboard — Active Workspace

This is where Murder and crows coordinate during execution. All crow activity is scoped to a single MVI's blackboard. Crows only ever read and write their own MVI's data — they never see another MVI's records.

The MVI Blackboard contains:

| Record type          | Description                                            |
| -------------------- | ------------------------------------------------------ |
| **CrowTasks**        | Murder's assignments to individual crows               |
| **CrowReports**      | What each crow produced (artifacts, verdicts, context) |
| **Murder Decisions** | Go / no-go / rerun with feedback                       |
| **Events**           | Fine-grained stream: tool calls, LLM output, errors    |
| **Merge readiness**  | Computed from Task and PR states — all PRs approved?   |

### Goal Blackboard — Coordination Checkpoint

When an MVI completes, Murder evaluates the Goal-level blackboard before activating the next MVI:

- Do the completed MVIs affect any in-progress or pending MVIs?
- Are there cross-MVI dependencies that need resolving?
- Does context from MVI 1.1 (e.g., a new API contract) need to be injected into MVI 1.2's CrowTask?

Murder arbitrates at this level when MVIs within the same Goal produce conflicting outcomes or shared context that downstream MVIs must consume.

### Milestone and Project Blackboards — Read-Only Aggregations

No crow writes directly to these levels. They are computed roll-ups that aggregate MVI blackboard states:

| Level         | What it aggregates                                                   |
| ------------- | -------------------------------------------------------------------- |
| **Milestone** | Progress % across Goals and MVIs, cost totals, active crow counts    |
| **Project**   | Milestone completion, overall merge readiness, total execution costs |

The iOS app's Project Home screen reads the project-level aggregation to display progress, active crows, and pending approvals.

---

## Multi-Tenant Isolation

Every piece of data is scoped to a tenant:

| Layer          | Isolation Method                                                          |
| -------------- | ------------------------------------------------------------------------- |
| **DynamoDB**   | Partition key prefix: `T#<tenant_id>`                                     |
| **S3**         | Key prefix: `tenants/<tenant_id>/`                                        |
| **Cognito**    | Custom attribute: `custom:tenant_id`                                      |
| **API**        | JWT contains `tenant_id`, enforced on every request                       |
| **Blackboard** | Execution records include `tenant_id`, crows only see their tenant's data |

---

## Data Hierarchy

```
Project
  └── Milestone  (3-6 month business achievement — changes competitive position)
       └── Goal   (2-6 week decomposition of the milestone)
            └── MVI  (2-5 day minimum deliverable — THIS is the merge set)
                 └── Task  (≤8h human equiv atomic unit → PR, auto-split if larger)
```

The **MVI is the merge set**. All PRs from Tasks within an MVI are merged together as a coherent increment. An MVI delivers visible value on its own.

### Concrete Example

```
Project: Cawnex iOS App

└── Milestone: Auth + Onboarding
     └── Goal: Functional Apple Sign In
          └── MVI: Complete login flow with session persistence
               ├── Task: Implement ASAuthorizationController
               ├── Task: Integrate Cognito with Apple token
               └── Task: Persist refresh token in Keychain
```

---

## DynamoDB — Single Table Design

### Table: `cawnex-{stage}`

| PK        | SK                                                                  | Entity            | Description                                                             |
| --------- | ------------------------------------------------------------------- | ----------------- | ----------------------------------------------------------------------- |
| `T#<tid>` | `PROJECT#<pid>`                                                     | Project           | Vision, name, status                                                    |
| `T#<tid>` | `PROJECT#<pid>#MILESTONE#<mid>`                                     | Milestone         | Description, order, progress                                            |
| `T#<tid>` | `PROJECT#<pid>#MILESTONE#<mid>#GOAL#<gid>`                          | Goal              | Description, milestone ref, target impact                               |
| `T#<tid>` | `PROJECT#<pid>#MILESTONE#<mid>#GOAL#<gid>#MVI#<mvid>`               | MVI               | Value, increment, verification, merge readiness                         |
| `T#<tid>` | `PROJECT#<pid>#MILESTONE#<mid>#GOAL#<gid>#MVI#<mvid>#TASK#<taskid>` | Task              | Status, description, PR ref, `human_hours_estimate` (from benchmark DB) |
| `T#<tid>` | `PROJECT#<pid>#REPO#<rid>`                                          | Repository        | GitHub URL, default branch                                              |
| `T#<tid>` | `PROJECT#<pid>#WORKFLOW#<wid>`                                      | Workflow          | Murder configuration (type, crow set, judgment preferences)             |
| `T#<tid>` | `PROJECT#<pid>#VISION_MSG#<ts>`                                     | Vision Message    | Chat history with Vision AI                                             |
| `T#<tid>` | `MURDER#<mid>`                                                      | Murder            | Name, type, crow configuration, status                                  |
| `T#<tid>` | `AGENT#<aid>`                                                       | Agent Definition  | Crow config (prompt, model, tools, parent murder ref)                   |
| `T#<tid>` | `LLMCONFIG`                                                         | LLM Config        | Encrypted API keys, model preferences                                   |
| `T#<tid>` | `PROFILE`                                                           | Tenant Profile    | Name, plan, billing                                                     |
| `T#<tid>` | `PEN#<penid>`                                                       | Pen File Metadata | S3 key, name, project ref                                               |

#### MVI — Record Fields

| Field              | Type     | Description                                   |
| ------------------ | -------- | --------------------------------------------- |
| `value`            | string   | Expected business value statement             |
| `increment`        | string   | What will be implemented in this MVI          |
| `verification`     | string[] | Verifiable success criteria                   |
| `status`           | enum     | `draft` \| `active` \| `completed`            |
| `merge_readiness`  | computed | Are all Task PRs ready to merge?              |
| `requirement_type` | enum     | `functional` \| `operational` \| `efficiency` |
| `value_score`      | number   | Fibonacci — relative business impact          |

#### Blackboard Records (Execution State)

Each Execution belongs to an MVI. The partition key `T#<tid>#EXEC#<eid>` carries implicit MVI context via the `META` record, which stores the `mvi_id` field. To query all blackboard records for a specific MVI, filter executions by `mvi_id` using GSI1 (`T#<tid>#MVI#<mvid>#EXEC`). Crows receive their `execution_id` from Murder and only ever access the partition belonging to their assigned execution — they never query across MVI boundaries.

| PK                   | SK                    | Entity          | Description                                            |
| -------------------- | --------------------- | --------------- | ------------------------------------------------------ |
| `T#<tid>#EXEC#<eid>` | `META`                | Execution       | Status, `mvi_id`, issue ref, timestamps, final verdict |
| `T#<tid>#EXEC#<eid>` | `PLAN`                | Plan            | Planner's structured plan, Murder's approval/rejection |
| `T#<tid>#EXEC#<eid>` | `STEP#<seq>#TASK`     | CrowTask        | What Murder assigned to the crow                       |
| `T#<tid>#EXEC#<eid>` | `STEP#<seq>#REPORT`   | CrowReport      | What the crow produced                                 |
| `T#<tid>#EXEC#<eid>` | `STEP#<seq>#DECISION` | Murder Decision | Go / no-go / rerun + feedback                          |
| `T#<tid>#EXEC#<eid>` | `EVENT#<ts>`          | Event           | Fine-grained stream (tool calls, output, errors)       |

### GSI1 — Query by status across projects

| GSI1PK                                    | GSI1SK           | Use case                    |
| ----------------------------------------- | ---------------- | --------------------------- |
| `T#<tid>#STATUS#pending_approval`         | `<created_at>`   | Approval queue              |
| `T#<tid>#STATUS#running`                  | `<started_at>`   | Active executions           |
| `T#<tid>#STATUS#completed`                | `<completed_at>` | Recent completed            |
| `T#<tid>#MVI_STATUS#active`               | `<created_at>`   | Active MVIs in tenant       |
| `T#<tid>#MVI_STATUS#completed`            | `<completed_at>` | MVIs ready for merge review |
| `T#<tid>#PROJECT#<pid>#MVI_STATUS#active` | `<created_at>`   | Active MVIs by project      |

### GSI2 — Admin / cross-tenant

| GSI2PK             | GSI2SK          | Use case             |
| ------------------ | --------------- | -------------------- |
| `PLAN#pro`         | `T#<tid>`       | All pro tenants      |
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

| Method   | Path         | Description                            |
| -------- | ------------ | -------------------------------------- |
| `POST`   | `/pens`      | Create a new .pen file                 |
| `GET`    | `/pens`      | List .pen files (for tenant)           |
| `GET`    | `/pens/{id}` | Get .pen file metadata + signed S3 URL |
| `PUT`    | `/pens/{id}` | Update .pen file                       |
| `DELETE` | `/pens/{id}` | Delete .pen file                       |

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

| .pen type             | SwiftUI                           |
| --------------------- | --------------------------------- |
| `frame` (vertical)    | `VStack`                          |
| `frame` (horizontal)  | `HStack`                          |
| `frame` (none)        | `ZStack`                          |
| `text`                | `Text`                            |
| `rectangle`           | `RoundedRectangle`                |
| `ellipse`             | `Ellipse`                         |
| `image`               | `AsyncImage`                      |
| `icon_font`           | `Image(systemName:)` (SF Symbols) |
| `path`                | `Path` (from SVG geometry)        |
| `ref`                 | Rendered component with overrides |
| Variables (`$--name`) | `@Environment` theme resolution   |
| Themes (light/dark)   | `@Environment(\.colorScheme)`     |

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
- Project + Milestone + Goal + MVI + Task CRUD (full hierarchy)
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

### Increment 6 — Full Dev Murder

- Implementer, Reviewer, Documenter, Fixer crows
- End-to-end execution: Murder reads blackboard, dispatches crows dynamically
- Cost tracking per execution

### Increment 7 — Production

- Custom domains (cawnex.ai API)
- Push notifications (APNs)
- WebSocket real-time updates
- Billing integration
- Landing page

---

## Security

| Concern          | Approach                                                            |
| ---------------- | ------------------------------------------------------------------- |
| API keys (BYOL)  | Encrypted at rest (KMS), never logged, never sent to Cawnex servers |
| Tenant isolation | Partition key enforcement, S3 prefix policies, JWT validation       |
| Auth             | Cognito JWT, short-lived access tokens, refresh rotation            |
| Code execution   | Sandboxed worktrees, no host access, time/cost limits               |
| Network          | HTTPS everywhere, VPC for Fargate (when added)                      |
| Secrets          | AWS Secrets Manager for infra secrets                               |

---

## Cost Model (AWS)

At low scale (dogfooding):

| Service                       | Estimated Monthly               |
| ----------------------------- | ------------------------------- |
| Lambda (API + Murder + Crows) | ~$1-5 (pay per request)         |
| DynamoDB (+ Streams)          | ~$1-5 (on-demand, streams free) |
| S3                            | ~$0.50 (storage + requests)     |
| Cognito                       | ~$0 (free tier up to 50k MAU)   |
| CloudFront                    | ~$1-2                           |
| **Total**                     | **~$5-15/mo**                   |

Scales linearly with usage. No idle costs.

---

## Task Estimation & ROI Model

### Task Estimation Rule

Every task must be estimable at **≤ 8 hours of human equivalent work**. If an agent generates a task estimated at > 8 hours, it **must auto-split** into smaller tasks until each is within the limit.

Human time estimates come from a **benchmark database** — not AI guessing. The database maps task types, complexity, and tech stack to historical human effort data. This ensures consistent, trustworthy estimates across all projects.

### Cost Model — What Users See vs Internal

| Layer                | Visible to User           | Internal to Cawnex                                         |
| -------------------- | ------------------------- | ---------------------------------------------------------- |
| **Platform cost**    | Credits spent             | AI + repository + workflow + infrastructure costs + margin |
| **Human equivalent** | "~$14k saved"             | Calculated from benchmark DB: `Σ(task_hours × dev_rate)`   |
| **ROI multiplier**   | "78x"                     | `human_equivalent / platform_cost`                         |
| **Dev rate**         | Configurable ($35-$75/hr) | Used for human equiv calculation only                      |

### ROI Display Tiers

Cost is **never shown alone**. Every cost display includes the human equivalent for context.

| Level                 | What's shown                                                                     |
| --------------------- | -------------------------------------------------------------------------------- |
| **Dashboard**         | Spent vs Saved stacked bar per project                                           |
| **Project Hub**       | ROI stat + "AI spend · human saved" footer                                       |
| **Goal Detail**       | Per-MVI: ROI multiplier, AI cost vs human equiv                                  |
| **MVI Task Review**   | Per-task: human hours, human cost, ROI multiplier                                |
| **Credits & Billing** | ROI summary card, total multiplier, total human equiv, execution time comparison |

### Pricing Flows Bottom-Up

```
Task (≤8h human equiv from benchmark DB)
  → MVI (sum of task estimates)
    → Goal (sum of MVI estimates)
      → Milestone (sum of goal estimates)
        → Project (sum of milestone estimates)
```

Platform cost is tracked from actual usage. Human equivalent is calculated from the benchmark database. The ratio between them is the ROI multiplier.
