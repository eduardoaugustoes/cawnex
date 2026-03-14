# 🏗️ Cawnex Architecture — Design Document

> Draft v0.1 — To be refined based on strategic decisions.

---

## Design Principles

1. **Start simple, evolve fast** — Subprocess with regex worked for months. We follow the same principle.
2. **Specialize everything** — Dedicated agents beat generic ones by an order of magnitude.
3. **Orchestration is the product** — Anyone can spawn an agent. The value is in coordinating them.
4. **BYOL (Bring Your Own LLM)** — We never pay for tokens. Users bring their own API key or subscription. See [byol.md](./byol.md).
5. **Issue-tracker agnostic** — Support Linear, GitHub Issues, Jira, GitLab Issues from day one.
6. **Git-native** — Everything goes through git. No magic. Worktrees for isolation.
7. **Observable by default** — Every action is streamed. Every cost is tracked.
8. **Human-in-the-loop, not human-in-the-way** — One approval point, not many.

---

## Proposed Architecture

```
┌─────────────────────────────────────────────────────┐
│                  INTEGRATIONS LAYER                  │
│                                                      │
│  Linear  GitHub Issues  Jira  GitLab  (webhooks)     │
│  Slack   Discord   Teams   Telegram  (notifications) │
│  GitHub  GitLab  Bitbucket           (git providers)  │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│                  THE MURDER (Core)                    │
│                                                      │
│  ┌─────────────┐ ┌──────────────┐ ┌──────────────┐  │
│  │  Webhook     │ │  Event Bus   │ │  Execution   │  │
│  │  Gateway     │ │  (Redis      │ │  Engine      │  │
│  │              │ │   Streams)   │ │              │  │
│  └─────────────┘ └──────────────┘ └──────────────┘  │
│                                                      │
│  ┌─────────────┐ ┌──────────────┐ ┌──────────────┐  │
│  │  Router      │ │  Context     │ │  PR Sync     │  │
│  │  (LLM-based) │ │  Manager     │ │  Manager     │  │
│  └─────────────┘ └──────────────┘ └──────────────┘  │
│                                                      │
│  ┌─────────────┐ ┌──────────────┐ ┌──────────────┐  │
│  │  Guard       │ │  Cost        │ │  Retry       │  │
│  │  (anti-      │ │  Tracker     │ │  Engine      │  │
│  │  hallucin.)  │ │              │ │              │  │
│  └─────────────┘ └──────────────┘ └──────────────┘  │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│                  CROW RUNTIME                        │
│                                                      │
│  Each crow (agent) runs as an isolated process:      │
│  • Claude Agent SDK instance                         │
│  • Git worktree (nest)                               │
│  • Role-specific system prompt                       │
│  • Streaming output → Event Bus → Dashboard          │
│                                                      │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐       │
│  │Refine  │ │Backend │ │Frontend│ │  QA    │ ...    │
│  │Crow    │ │Crow    │ │Crow    │ │ Crow   │        │
│  └────────┘ └────────┘ └────────┘ └────────┘        │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│                  THE ROOST (Dashboard)                │
│                                                      │
│  React + Vite + shadcn/ui                            │
│  Real-time via SSE                                   │
│  Sections: Dashboard, Executions, Agents,            │
│            Queue, Settings, Cost Analysis             │
└─────────────────────────────────────────────────────┘
```

---

## Key Simplifications vs. AgentOps

| AgentOps (Luiz)    | Cawnex (Our approach)                       | Rationale                                                                                                              |
| ------------------ | ------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| Kafka + Redis      | **Redis Streams only**                      | Simpler. Kafka is overkill for MVP. Redis Streams provides pub/sub + persistence. Migrate to Kafka if needed at scale. |
| MySQL + ClickHouse | **PostgreSQL only**                         | One DB to start. Postgres handles both OLTP and basic analytics. Add ClickHouse later.                                 |
| Custom CLI + Web   | **Web-first, CLI later**                    | Dashboard is the differentiator. CLI can be added in V2.                                                               |
| NLM-DFA routing    | **LLM-based routing (simpler)**             | Start with a Claude prompt that analyzes the issue and returns affected repos. Formalize into DFA later if needed.     |
| 7 agents           | **Start with 4**: Refinement, Dev, QA, Docs | Mobile + Security can be added later. Dev agent handles both backend + frontend initially.                             |
| GitLab only        | **GitHub first**                            | Larger market. Add GitLab later.                                                                                       |
| Linear only        | **GitHub Issues first**                     | Zero integration needed — same platform as git. Add Linear/Jira as plugins.                                            |
| Kubernetes deploy  | **Docker Compose for MVP**                  | Ship faster. K8s when there are actual users.                                                                          |

---

## Data Model (Draft)

### Core Entities

```
Organization
├── id, name, plan
├── repositories[]
├── agents[] (config)
├── integrations[] (Linear, Slack, etc.)
└── settings (LLM config, retry policy, etc.)

Repository
├── id, org_id, git_url, provider (github/gitlab)
├── default_branch
├── agent_config (CAWNEX.md — instructions for agents)
└── language, framework (auto-detected)

Issue
├── id, org_id, external_id (Linear/GH/Jira ID)
├── title, description, labels
├── source (linear/github/jira/manual)
├── status (pending/refining/approved/in_progress/completed/failed)
└── created_at, updated_at

Execution
├── id, issue_id, org_id
├── agent_type (refinement/dev/qa/docs/security)
├── repository_id
├── status (queued/running/completed/failed/cancelled)
├── worktree_path
├── pr_url
├── cost (tokens_in, tokens_out, total_usd)
├── duration_seconds
├── events[] (streaming log)
├── parent_execution_id (for sub-executions)
└── created_at, started_at, completed_at

Event (streaming log)
├── id, execution_id
├── type (planning/tool_use/output/error/peer_message)
├── content (text)
├── timestamp
└── metadata (tool name, file path, etc.)

Agent
├── id, org_id
├── type (refinement/dev/qa/docs/security)
├── status (ready/busy/idle/disabled)
├── system_prompt
├── model (opus/sonnet/haiku)
├── retry_policy
└── stats (total_executions, success_rate, avg_duration)
```

### State Machine — Execution

```
                    ┌──────────┐
                    │  QUEUED   │
                    └────┬─────┘
                         │ agent available
                         ▼
                    ┌──────────┐
              ┌────│ RUNNING   │────┐
              │    └────┬─────┘    │
              │         │          │
         timeout/   completed   hallucination
         error         │       detected
              │         ▼          │
              │    ┌──────────┐    │
              │    │COMPLETED │    │
              │    └──────────┘    │
              │                    │
              ▼                    ▼
         ┌──────────┐      ┌──────────┐
         │  FAILED   │      │CANCELLED │
         └────┬─────┘      └──────────┘
              │
              │ retryable?
              ▼
         ┌──────────┐
         │ RETRYING  │──→ QUEUED (re-enter)
         └──────────┘
```

### State Machine — Issue

```
  PENDING → REFINING → AWAITING_APPROVAL → APPROVED → IN_PROGRESS → COMPLETED
                                                                  ↘ FAILED
```

---

## API Design (Draft)

```
POST   /api/v1/webhooks/github       ← Receive GitHub webhooks
POST   /api/v1/webhooks/linear       ← Receive Linear webhooks
POST   /api/v1/webhooks/jira         ← Receive Jira webhooks

GET    /api/v1/executions             ← List executions (filterable)
GET    /api/v1/executions/:id         ← Execution detail
GET    /api/v1/executions/:id/events  ← SSE stream of events
POST   /api/v1/executions/:id/cancel  ← Cancel execution
POST   /api/v1/executions/:id/retry   ← Retry execution

GET    /api/v1/issues                 ← List issues
POST   /api/v1/issues                 ← Create issue manually
POST   /api/v1/issues/:id/approve     ← Approve refined issue
POST   /api/v1/issues/:id/reject      ← Reject refined issue

GET    /api/v1/agents                 ← List agents + status
PATCH  /api/v1/agents/:id             ← Update agent config

GET    /api/v1/dashboard/stats        ← Dashboard metrics
GET    /api/v1/dashboard/costs        ← Cost breakdown

GET    /api/v1/orgs/:id/settings      ← Org settings
PATCH  /api/v1/orgs/:id/settings      ← Update settings
```

---

## Deployment (MVP)

```yaml
# docker-compose.yml
services:
  api:
    build: ./apps/api
    ports: ["8000:8000"]
    depends_on: [db, redis]

  dashboard:
    build: ./apps/dashboard
    ports: ["3000:3000"]

  worker:
    build: ./apps/worker
    depends_on: [db, redis]
    # Runs crow (agent) executions

  db:
    image: postgres:16

  redis:
    image: redis:7
```

Later: Kubernetes + ArgoCD for production multi-tenant.
