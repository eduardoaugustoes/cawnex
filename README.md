<div align="center">

# 🐦‍⬛ Cawnex

### Coordinated Intelligence

**Agent orchestration platform that turns a single issue into shipped, tested, documented code — without human intervention.**

*One caw. Seven agents. Zero bottlenecks.*

---

[Getting Started](#-getting-started) · [Architecture](#-architecture) · [Agents](#-the-7-agents) · [How It Works](#-how-it-works) · [CLI](#-cli) · [Why Cawnex](#-why-cawnex)

</div>

---

## 🧠 What is Cawnex?

In nature, crows don't work alone. They call to each other — **caw** — sharing what they've found, coordinating the hunt, solving problems no single bird could crack.

**Cawnex** does the same thing with AI agents.

You create an issue, and a coordinated murder of specialized agents — backend, frontend, QA, docs, security — ships it to production.

**~$1 per PR. No humans in the loop.**

```
Issue created → Agents coordinate → Code shipped → Team notified
```

## ✨ Features

- 🐦 **7 Specialized Agents** — Each agent has one mission. Specialization over generalization.
- 🔑 **BYOL (Bring Your Own LLM)** — Use your own API key or Claude Max subscription. No token limits. No artificial constraints.
- 🔄 **End-to-End Autonomous** — From issue to merge, zero human intervention required.
- 🌐 **Cross-Repo Coordinated** — Changes across multiple services stay consistent. Synchronized PRs.
- 📡 **Real-Time Streaming** — Watch every agent action live via SSE. No waiting for results.
- 🏢 **Multi-Tenant** — Complete isolation between organizations. Auto-routing webhooks.
- 🔁 **Smart Retry** — Failures are isolated. A frontend error doesn't block the backend.
- 🛡️ **Hallucination Detection** — Orchestrator monitors agent output and cancels if it drifts.
- 📊 **Cost Tracking** — Tokens, duration, cost per execution — all monitored automatically.
- 🤖 **Multi-LLM Support** — Anthropic, OpenAI, Google. Use different models per agent type.

## 🐦 The 7 Agents

| Agent | Role | What it does |
|-------|------|-------------|
| 🔍 **Refinement** | Analyst | Analyzes issues → generates full user stories with acceptance criteria and affected repos |
| ⚙️ **Backend** | Engineer | Writes server code, APIs, database migrations, business logic |
| 🖥️ **Frontend** | Engineer | Builds interfaces, components, and user experiences |
| 📱 **Mobile** | Engineer | Implements features in iOS/Android applications |
| ✅ **QA** | Reviewer | Validates code against acceptance criteria, approves or rejects PRs |
| 📄 **Docs** | Writer | Auto-updates documentation after every code change |
| 🔒 **Security** | Auditor | Scans for vulnerabilities, ensures conformity with best practices (SAST/DAST) |

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────┐
│                      LINEAR                          │
│            Issue created with label                  │
│                  → webhook fires                     │
└────────────────────┬─────────────────────────────────┘
                     │ webhook
                     ▼
┌──────────────────────────────────────────────────────┐
│          🐦‍⬛ THE MURDER (Orchestrator)                │
│                                                      │
│  • Receives events via Redis Streams                  │
│  • Analyzes issue type & affected repos              │
│  • Routes to correct agent(s)                        │
│  • Monitors streaming for hallucination              │
│  • Cancels if agent goes off-track                   │
│  • Coordinates synchronized PRs                      │
└──┬────┬────┬────┬────┬────┬────┬─────────────────────┘
   │    │    │    │    │    │    │
   ▼    ▼    ▼    ▼    ▼    ▼    ▼
┌──────────────────────────────────────────────────────┐
│              🐦 CROWS (Agents)                       │
│                                                      │
│  Each agent works in an isolated worktree (nest)     │
│  Agents communicate via NCP (caws)                   │
│  Parallel execution, shared context                  │
│                                                      │
│  Refinement → Backend ↔ Frontend ↔ Mobile            │
│                    ↓                                  │
│              QA → Docs → Security                    │
└────────────────────┬─────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────┐
│              GIT WORKFLOW                             │
│                                                      │
│  • Worktrees (nests) per agent — full isolation      │
│  • PRs synchronized across repos                     │
│  • Auto-merge after QA approval                      │
│  • Coordinated rollback on failure                   │
└────────────────────┬─────────────────────────────────┘
                     │
                     ▼
              Slack notification 🔔
```

### BYOL — Bring Your Own LLM

```
┌─────────────────────────────────────────┐
│  🔑 Connect your AI                     │
│                                          │
│  [Anthropic API Key]  ← recommended     │
│  [OpenAI API Key]                        │
│  [Google AI API Key]                     │
│                                          │
│  ── or ──                                │
│                                          │
│  [Claude Max Subscription]               │
│  Unlimited executions via Claude Code    │
└─────────────────────────────────────────┘
```

Your key. Your budget. Your rules. We handle the orchestration.

| BYOL Mode | How it works | Best for |
|-----------|-------------|----------|
| **API Key** | Direct SDK calls, precise token tracking | Low-medium volume |
| **Subscription** | Claude Code subprocess, unlimited | High volume / power users |

### Tech Stack

| Layer | Technology |
|-------|-----------|
| **AI Engine** | BYOL — Claude SDK (primary), GPT-4, Gemini (user's key) |
| **Backend** | Python 3.12 + FastAPI + SQLAlchemy (async) |
| **Database** | PostgreSQL (multi-tenant) |
| **Cache / Streams** | Redis (Streams for event bus, cache for state) |
| **Web App** | React + Vite + TypeScript + shadcn/ui |
| **iOS** | Swift + SwiftUI (full native) |
| **Android** | Kotlin + Jetpack Compose (full native) |
| **Issue Tracker** | GitHub Issues (webhook), Linear planned |
| **Git** | GitHub (worktrees per agent) |
| **API Contracts** | OpenAPI spec → generated clients (TS, Swift, Kotlin) |
| **Package Mgmt** | uv (Python), pnpm (Node) |
| **Infrastructure** | Docker Compose (MVP) → Kubernetes (scale) |
| **Notifications** | Slack, GitHub, Email |

## 📁 Project Structure

```
cawnex/
├── packages/
│   ├── core/           # SQLAlchemy models, Pydantic schemas, enums, DB session
│   ├── providers/      # BYOL abstraction (Anthropic, OpenAI, Google)
│   └── git_ops/        # Worktree, branch, PR management (GitPython + GitHub API)
├── apps/
│   ├── api/            # FastAPI — webhooks, REST, SSE streaming
│   ├── worker/         # The Murder (orchestrator) + Crows (agents)
│   ├── web/            # React + Vite + shadcn/ui
│   ├── ios/            # Swift + SwiftUI (full native)
│   └── android/        # Kotlin + Jetpack Compose (full native)
├── prompts/            # Agent system prompts (version-controlled)
├── specs/              # OpenAPI spec (single source of truth for all clients)
├── scripts/            # Dev tooling, migrations, seed data
├── tests/              # Integration + E2E tests
├── docs/
│   ├── research/       # Competitive analysis, transcript insights
│   ├── design/         # Architecture, agents, orchestration, BYOL, platform
│   └── roadmap/        # Phases, MVP scope, Milestone 0
├── docker-compose.yml  # PostgreSQL + Redis (dev)
├── pyproject.toml      # uv workspace root
└── CAWNEX.md           # Agent instructions (dogfooding)
```

## 🔄 How It Works

### The Loop

Every agent follows the same cognitive loop:

```
    ┌→ Perceive ──→ Reason ──→ Act ──→ Observe ─┐
    └────────────────────────────────────────────┘
```

1. **Perceive** — Read the environment: issue, code, context
2. **Reason** — Analyze and plan the best action
3. **Act** — Execute: write code, open PR, run tests
4. **Observe** — Verify the result, adjust if necessary

The cycle repeats until the objective is fully achieved — with optional human supervision at critical points.

### Flow: Issue → Production

```
1. 📋 Issue created in Linear (with agent label)
        │
2. ⚡ Webhook → Redis Stream → Orchestrator (The Murder)
        │
3. 🔍 Refinement Agent generates:
        • Full user story
        • Acceptance criteria
        • Technical notes
        • Affected repositories
        │
4. 🧑 HUMAN APPROVES (only intervention point)
        │
5. 🐦 Dev Agents work in PARALLEL:
        • Create worktrees (nests)
        • Read environment + context
        • Implement solution
        • Communicate via caws (agent-to-agent protocol)
        • Share API contracts between repos
        │
6. ✅ QA Agent reviews:
        • Diffs against acceptance criteria
        • Type checks
        • Approves or rejects
        │
7. 📄 Docs Agent updates documentation
        │
8. 🔒 Security Agent scans for vulnerabilities
        │
9. 🔀 Synchronized PRs merge together
        │
10. 🔔 Slack notification → Done
```

### Flow: PR → Merge

```
PR Opened → QA Reviews (acceptance criteria) → Auto-Merge → Slack Notification
```

The complete cycle — from issue to merge — happens without any engineer needing to intervene. The team is notified only at the end.

## 💻 CLI

```bash
$ cawnex init --repo github.com/myorg/api
✅ Repository connected

$ cawnex agents list

  🐦 refinement   ready
  🐦 backend      ready
  🐦 frontend     ready
  🐦 mobile       idle
  🐦 qa           ready
  🐦 docs         ready
  🐦 security     ready

$ cawnex issue LUI-19 --run

  ⚡ The Murder picked up LUI-19
  → Refinement: generating user story...
  → Backend: creating nest crow/LUI-19-api
  → Frontend: creating nest crow/LUI-19-web
  → QA: watching for PRs...

$ cawnex watch

  🐦 LUI-19 ████████████░░░░ 74%
     backend  ✅ completed (2m31s)
     frontend ⏳ implementing...
     qa       🔄 waiting for PRs
     docs     🔄 queued

$ cawnex roost

  📊 The Roost — Dashboard
  ┌─────────────┬──────────┬──────────┬──────────┐
  │ Executions  │ Success  │ PRs      │ Cost     │
  │ 174         │ 58.05%   │ 33       │ $57.29   │
  └─────────────┴──────────┴──────────┴──────────┘
```

### Cawnex Vocabulary

| Term | Meaning |
|------|---------|
| **Crows** | Agents — your AI workers |
| **The Murder** | Orchestrator — coordinates everything |
| **Nests** | Worktrees — isolated workspaces per agent |
| **Caws** | Agent-to-agent messages |
| **The Roost** | Dashboard — monitor everything |
| **Fallen Crow** 💀 | Failed execution |

## 💰 Real Numbers

| Metric | Value |
|--------|-------|
| Cost per execution | ~$0.15 - $0.96 |
| Cost per PR | ~$1.73 |
| QA review duration | ~2m 48s |
| Parallel vs sequential | 15 min vs 1h+ |
| Equivalent team size | 20-30 engineers |

## 🤔 Why Cawnex?

### Agents vs Skills

| | Skill | Agent |
|---|-------|-------|
| **Changes** | What you **know** | **Who** does the work |
| **Nature** | Packaged knowledge, passive | Autonomous entity with mission |
| **Analogy** | Excel — powerful, needs someone to open it | Analyst — uses Excel, decides when and how |

> *Skills amplify capabilities. Agents replace the need for a human to execute a task.*

### Key Lessons

- **Start simple** — A subprocess with regex worked in production for months before migrating to SDK
- **Feature flags for safe migration** — Never do big bang. Rollback per organization instantly.
- **Specialization > Generalization** — 7 specialized agents deliver far superior results to 1 generic agent

### Why the crow?

Crows are one of nature's most intelligent animals:
- 🧰 Use **tools** to solve problems
- 🗣️ **Communicate** complex information to each other
- 🤝 Work in **coordinated groups**
- 🧠 **Remember** and share knowledge across the group
- 🧩 Solve **multi-step puzzles** autonomously

That's literally what AI agents do.

## 📈 Evolution

```
Phase 1 — CLI          Phase 2 — SDK          Phase 3 — Migration     Phase 4 — Feature Flags
Claude CLI as           Agent SDK with          Strangler Fig:          Control per org
subprocess with         structured output,      new executions          with instant
regex parsing.          native metrics,         use SDK while           rollback.
Simple, functional,     and sub-agent           old ones stay           Safe migration,
but fragile at scale.   support.                on CLI.                 no big bang.
```

> *The most important lesson: start simple. The subprocess with regex worked in production for months before the migration to SDK.*

## 💰 Pricing

| Tier | Price | Includes |
|------|-------|---------|
| **Free** | $0/mo | 20 executions, 1 repo, 2 agents |
| **Pro** | $29/mo | Unlimited executions, 10 repos, 4 agents |
| **Team** | $99/mo | Unlimited repos, 7 agents, multi-repo sync, 5 seats |
| **Enterprise** | Custom | SSO, audit logs, SLA, on-prem |

*All tiers require BYOL. We charge for orchestration, not tokens.*

## 🚀 Roadmap

- [x] **Milestone 0 — "The Egg"** — Monorepo scaffold, DB models, Docker infra, first agent *(in progress)*
- [ ] **Phase 1 — "First Flight"** — Single agent, single repo, CLI proof (5 real issues → 3 merged PRs)
- [ ] **Phase 2 — "The Murder"** — Full pipeline (Refine → Dev → QA → Docs), dashboard, BYOL multi-provider
- [ ] **Phase 3 — "Migration"** — Multi-repo coordination, synchronized merges, GitHub App
- [ ] **Phase 4 — "The Roost"** — Multi-tenant SaaS, billing, native mobile apps, subscription relay
- [ ] **Phase 5 — "Evolved"** — Planning Agent, Skills Marketplace, ROI Dashboard

## 📄 License

MIT

---

<div align="center">

**🐦‍⬛ Cawnex** — *Coordinated Intelligence*

Built with obsession by humans and crows.

</div>
