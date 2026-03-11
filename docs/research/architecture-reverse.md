# 🏗️ Architecture Reverse Engineering — AgentOps

> Reconstructed from transcript, slides, and live demos. Confidence levels noted.

---

## System Overview

```
                        ┌─────────────┐
                        │   LINEAR    │ ← Issue tracker (source of truth)
                        │  (webhook)  │
                        └──────┬──────┘
                               │ HTTP webhook
                               ▼
                        ┌─────────────┐
                        │    KAFKA    │ ← Event bus (real-time)
                        │   (topic)   │
                        └──────┬──────┘
                               │ consume
                               ▼
┌──────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR                           │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │   NLM-DFA    │  │  Hallucin.   │  │  PR Sync      │  │
│  │  (routing)   │  │  Detection   │  │  Manager      │  │
│  └──────────────┘  └──────────────┘  └───────────────┘  │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │  Agent Pool  │  │  Smart       │  │  Context       │  │
│  │  Manager     │  │  Retry       │  │  Sharing       │  │
│  └──────────────┘  └──────────────┘  └───────────────┘  │
└──────┬───────┬───────┬───────┬───────┬───────┬───────┬───┘
       │       │       │       │       │       │       │
       ▼       ▼       ▼       ▼       ▼       ▼       ▼
    ┌─────┐┌─────┐┌─────┐┌─────┐┌─────┐┌─────┐┌─────┐
    │Refin││Back ││Front││Mobil││ QA  ││Docs ││Secur│
    │ment ││end  ││end  ││e    ││     ││     ││ity  │
    └──┬──┘└──┬──┘└──┬──┘└──┬──┘└──┬──┘└──┬──┘└──┬──┘
       │       │       │       │       │       │       │
       ▼       ▼       ▼       ▼       ▼       ▼       ▼
    ┌─────────────────────────────────────────────────────┐
    │                    GIT (GitLab)                      │
    │  Worktrees (isolated) → PRs (synchronized) → Merge  │
    └─────────────────────────────────────────────────────┘
       │                                              │
       ▼                                              ▼
    ┌──────────┐                              ┌──────────┐
    │ DATADOG  │                              │  SLACK   │
    │ (observe)│                              │ (notify) │
    └──────────┘                              └──────────┘
```

## Component Breakdown

### 1. Entry Point — Linear Webhook
**Confidence: HIGH** (confirmed in slides + demo)

- Issues are created in Linear with specific labels
- Labels signal to AgentOps that the task should be handled autonomously
- Webhook fires on issue state change (e.g., moved to "In Progress")
- The webhook payload goes to Kafka

### 2. Message Bus — Kafka + Redis
**Confidence: HIGH** (confirmed in transcript)

- **Kafka**: Primary event streaming between orchestrator and agents
  - "Absolutely instantaneous" — Luiz's words
  - Used for real-time coordination
  - Originally tried Confluent, ended up using Kafka directly
- **Redis**: Queue management, caching
  - Built custom BRX queue system
  - Some things moved from Kafka to Redis over time
  - "Kafka ficou meio de lado" — some functions migrated to Redis

**Unknown**: Exact topic structure, partition strategy, consumer groups

### 3. Orchestrator
**Confidence: MEDIUM-HIGH** (described verbally, partially shown)

#### NLM-DFA Router
- Uses LLM + Deterministic Finite Automaton
- Understands logical flow inside applications
- Based on a pen-testing research paper (Shannon-based implementation)
- Paper used NLM-DFA to understand code flow for vulnerability testing
- Luiz adapted it for cross-repo orchestration
- Determines which repos are affected by an issue
- Routes to correct agent(s): Backend, Frontend, Mobile

**Unknown**: Exact paper reference, implementation details, state machine definition

#### Hallucination Detection
- Monitors agent streaming output in real-time
- Detects when agent creates things that "don't make sense"
- Can auto-cancel execution
- Uses context and previous messages to verify coherence

**Unknown**: Detection algorithm, thresholds, what triggers cancellation

#### PR Synchronization Manager
- Ensures PRs across repos are merged together
- "Only closes when all PRs and all tests are closed"
- Coordinated rollback if any PR fails

**Unknown**: Exact mechanism — likely uses Kafka events to track PR states

#### Smart Retry
- Not blind retry — uses execution tree analysis
- Verifies interaction between agent messages
- Each agent has its own retry policy
- Isolated: frontend failure doesn't block backend

**Unknown**: Retry limits, backoff strategy, how it determines "retryable"

### 4. Agents (Claude Agent SDK)
**Confidence: HIGH** (confirmed in slides + demo + transcript)

Each agent is a Claude Agent SDK instance with:
- **System prompt**: Role-specific instructions (CLAUDE.md / Agent.md per repo)
- **Tools**: Git operations, file system, shell commands
- **Context**: Issue description, acceptance criteria, repo structure
- **Worktree**: Isolated copy of the repo

#### Agent Lifecycle
```
1. Orchestrator creates execution
2. Agent receives: issue context + repo assignment + acceptance criteria
3. Agent creates worktree (isolated workspace)
4. Agent enters loop: Perceive → Reason → Act → Observe
5. Agent outputs: code changes, PR, test results
6. Streaming: every action visible in real-time via SSE
7. Completion: signals orchestrator
```

#### Agent Communication
- Agents can communicate with each other ("caws")
- Peer-to-peer protocol via Kafka/Redis
- Example from transcript: "My agent said: 'Let me check if my peer needs anything.' And it waits for the response."
- Orchestrator mediates when needed

**Unknown**: Message schema, how peers discover each other, conflict resolution

### 5. Git Workflow — Worktrees
**Confidence: HIGH** (confirmed explicitly)

- **Worktrees, NOT feature branches**
- Each agent gets a `git worktree` — a full copy of the repo at a specific point
- Agents work in completely isolated environments
- No interference between parallel agents
- Luiz almost migrated to monorepo but realized worktrees give same result
- Worktree naming convention likely: `crow/<issue-id>-<type>`

### 6. Frontend — AgentOps Dashboard
**Confidence: HIGH** (shown live)

- **React + Vite + shadcn/ui**
- Real-time updates via **SSE (Server-Sent Events)**
- Sections: Dashboard, Create Issue, Executions, Agents, Queue, Webhooks, Settings
- Dashboard shows: Total Executions, Success Rate, PRs Created, Cost, Running, Queue, Failed, Blocked
- Execution detail: Agent Output (events timeline), Details (dates, duration, issue link), Related Executions
- Execution list: filterable by agent type, status, labels

### 7. Backend — FastAPI
**Confidence: HIGH** (confirmed in slides)

- **FastAPI + Python**
- **MySQL** for persistence
- **Redis** for caching and queues
- Endpoints for: execution management, agent coordination, webhook reception, SSE streaming

### 8. Observability — Datadog
**Confidence: HIGH** (shown live)

- Dashboard: "RevBridge Platform - Logs Control Center"
- KPIs: Total Logs, Real Errors, ddtrace Noise, No Pipeline %, Active Services, Error Rate
- Production numbers: 6M logs (5min), 14 errors, 265 services, 0.00023% error rate
- Errors copied → sent to Claude → fixed → deployed

### 9. Custom CLI — `rbd`
**Confidence: HIGH** (shown live)

```
RBD Interactive Shell
├── Git & Deploy
│   ├── diff [repo]      — Changes dev → prod
│   ├── commit            — Auto commit & push
│   ├── promote [repo]    — Promote to prod
│   ├── sync-branch [repo]— Merge main → develop
│   ├── st [repo|all]     — Git status
│   ├── pull [repo|all]   — Git pull
│   ├── fetch [all]       — Git fetch & update notifications
│   └── push              — Git push
├── Environment
│   ├── dev               — Switch to dev
│   ├── prod              — Switch to prod
│   ├── open <target>     — Open ArgoCD/Datadog/GitLab
│   └── ci [svc]          — Show pipelines
├── Other
│   ├── notify [status]   — Watcher status & debug
│   ├── notify refresh    — Force refresh local changes
│   ├── notify restart    — Restart background watcher
│   ├── k <args>          — Run kubectl
│   ├── !<cmd>            — Run shell command
│   ├── clear             — Clear screen
│   └── quit              — Exit
└── Repos: infra, frontend, apis, library, auth, mab
```

### 10. Multi-Tenancy
**Confidence: MEDIUM** (described in slides, not shown in depth)

- Complete org isolation — data, credentials, executions never mix
- OAuth with automatic refresh (GitLab tokens expire every 2h)
- Webhooks auto-identify source organization
- Route execution to correct context without manual config
- Feature flags per organization for safe rollout

## Data Flow — Complete Issue Lifecycle

```
1. Developer creates issue in Linear with label "agent"
   └→ Linear fires webhook

2. Webhook → Kafka topic (issue.created)
   └→ Orchestrator consumes event

3. Orchestrator:
   a. Reads issue content
   b. NLM-DFA analyzes affected repos (e.g., mab-core, mab-workflow, frontend)
   c. Creates execution record in MySQL
   d. Spawns Refinement Agent

4. Refinement Agent:
   a. Reads issue + repo structure
   b. Generates: user story, acceptance criteria, technical notes, repo mapping
   c. Publishes result → Kafka
   d. Status: "awaiting-approval"

5. Human reviews & approves (ONLY human touchpoint)
   └→ Status change triggers next phase

6. Orchestrator spawns Dev Agents (parallel):
   a. Backend Agent → creates worktree, implements API changes
   b. Frontend Agent → creates worktree, implements UI changes
   c. (Mobile Agent if needed)
   d. Agents communicate via Kafka for API contract alignment

7. Dev Agents complete → each opens PR
   └→ PRs tracked by orchestrator

8. Orchestrator spawns QA Agent:
   a. Gets diff from main..HEAD
   b. Reviews against acceptance criteria
   c. Runs type checks
   d. Fixes minor issues
   e. Approves or rejects

9. If approved → Docs Agent updates documentation

10. If approved → Security Agent runs SAST/DAST

11. All checks pass → Orchestrator triggers synchronized merge
    └→ All PRs merge together

12. Slack notification sent to team

13. If any step fails:
    a. Smart Retry evaluates if retryable
    b. If not → coordinated rollback
    c. Notification with error details
```

## Confidence Summary

| Component | Confidence | Source |
|-----------|-----------|--------|
| 7 agents + roles | ✅ HIGH | Slides + transcript |
| Claude Agent SDK | ✅ HIGH | Slides + demo |
| FastAPI + MySQL + Redis | ✅ HIGH | Slides |
| React + Vite + shadcn | ✅ HIGH | Demo |
| Kafka + Redis messaging | ✅ HIGH | Transcript |
| Linear integration | ✅ HIGH | Demo |
| Worktrees (not branches) | ✅ HIGH | Transcript (explicit) |
| Synchronized PRs | ✅ HIGH | Slides + transcript |
| Datadog observability | ✅ HIGH | Demo |
| NLM-DFA routing | ⚠️ MEDIUM | Transcript only, no implementation details |
| Hallucination detection | ⚠️ MEDIUM | Transcript only |
| Agent-to-agent comms | ⚠️ MEDIUM | Mentioned but not detailed |
| Multi-tenant architecture | ⚠️ MEDIUM | Slides only |
| Smart retry logic | ⚠️ MEDIUM | Described verbally |
| OAuth refresh mechanism | 🔻 LOW | Mentioned in slide, no details |
| Kafka topic structure | 🔻 LOW | Inferred, not confirmed |
| Execution state machine | 🔻 LOW | Partially visible in demo |
