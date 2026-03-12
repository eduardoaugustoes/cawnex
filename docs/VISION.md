# Cawnex — Vision

> Coordinated Intelligence. From vision to velocity.

---

## What is Cawnex?

Cawnex is a multi-agent AI orchestration platform that turns a founder's vision into shipped outcomes — across software, content, data, infrastructure, or any other domain.

You describe what you want to build. Cawnex breaks it into milestones, generates tasks, assigns specialized AI agents ("Crows") organized into domain-specific "Murders", and delivers results. You stay in control — every task needs your approval before execution.

**One sentence:** Vision → Milestones → Goals → MVIs → Tasks → Murder → Crows → Outcomes → Shipped.

---

## Who is it for?

**Technical founder CEOs** who:
- Have a clear product vision but limited time to code everything themselves
- Want AI to handle the execution while they steer the direction
- Need to ship fast without hiring a team
- Want to maintain quality through automated review and human approval gates

---

## Core Principles

1. **Vision-driven** — Everything flows from the project vision. The AI understands your intent and works toward it.
2. **Human-in-the-loop, not human-in-the-way** — AI proposes, you approve. One approval point per task, not death by a thousand confirmations.
3. **Prepaid Credits** — Users purchase credits upfront. Credits bundle all costs (AI, repo, workflow, compute). No API key management, no token counting, no surprises. The internal cost breakdown is never exposed.
4. **Multi-tenant from day 1** — Safe data isolation between tenants at every layer.
5. **Orchestration is the product** — Anyone can spawn an agent. The value is coordinating them: routing, sequencing, context-sharing, result delivery across any domain.
6. **Domain-agnostic** — Cawnex is not a dev tool. It is a platform for orchestrating any AI workflow — software, editorial, social, infrastructure, data, or domains yet to be defined. The Murder pattern generalizes across all of them.
7. **Full native mobile** — iOS (Swift/SwiftUI) and Android (Kotlin/Compose). No cross-platform compromises.
8. **Observable by default** — Every action is streamed. Every cost is tracked. Every decision is auditable.
9. **ROI-transparent** — Every cost is shown in context. Users always see what they spent alongside what it would cost to hire humans for the same work. Cost is never displayed alone.

---

## Glossary

| Term | Meaning |
|------|---------|
| **Crow** | A specialized AI agent with a defined role, skill set, backstory, constraints, and a set of behavior states it moves through during execution (e.g., Scouting, Building, Hunting, Landed). Each Crow is assigned a model and works inside a Nest |
| **Backstory** | A Crow's personality narrative that shapes how it approaches problems and makes decisions. Configured per Crow |
| **Constraints** | Hard boundaries on a Crow that override all other instructions. Red-flagged in the UI to signal their severity |
| **Crow Behavior State** | The current activity of a Crow: Scouting, Planning, Building, Hunting, Reviewing, Documenting, or Landed |
| **Skill** | A reusable capability that defines what a Crow can do. Includes a name, description (critical for LLM tool selection), input parameter schema, behavior annotations (readOnly, destructive, idempotent), security permissions, execution config, and a test runner. Skills are managed in a library and attached to Murders to shape their capabilities |
| **Behavior Annotations** | Flags on a Skill describing its side-effect profile: Read Only (no mutations), Destructive (irreversible changes), Idempotent (safe to retry). Based on the MCP standard |
| **Murder** | A specialized flock of Crows tuned for a specific domain (e.g., Dev Murder, Editorial Murder). A Murder is the unit of orchestration — it decides dynamically which Crows to deploy and in what order based on blackboard state. Configured with a Murder Prompt, Crow Flow, Quality Gates, Escalation Rules, and Budget Limits |
| **Murder Type** | A named archetype of Murder configuration. Built-in types: Dev, Editorial, Social, Infra, Data. Users can define custom Murder Types by selecting Crows, configuring prompts and tools, and defining coordination patterns |
| **Murder Prompt** | System-level context injected into every Crow's prompt within a Murder. Provides shared instructions, domain knowledge, and project-specific guidance |
| **Crow Flow** | The suggested handoff chain between Crows in a Murder (e.g., Planner → Implementer → Reviewer). The Murder uses it as guidance but can deviate when context demands |
| **Quality Gates** | Automated checks that must pass before a Murder considers work done (e.g., CI passing, test coverage threshold, linting). Configured per Murder |
| **Escalation Rules** | Rules defining what happens when a Crow fails or gets stuck (e.g., retry count, fallback Crow, alert human). Configured per Murder |
| **Budget Limits** | Spending caps per Murder execution — max credits per task and per total execution run. Prevents runaway costs |
| **Nest** | An isolated git worktree where a Crow works |
| **Blackboard** | Shared state (DynamoDB) that a Murder and its Crows read and write during execution. Contains context, prior work, goals, and Crow reports. The coordination primitive that enables dynamic orchestration |
| **The Roost** | The dashboard / command center (iOS app + web) |
| **Project** | A top-level container with its own vision, milestones, repos, assigned Murders, and cost tracking |
| **Vision** | A conversational AI-refined description of what the project should become. Built through an AI-guided chat that asks structured questions and synthesizes answers into a standardized document |
| **AI-Guided Document** | A document created through conversational AI: the system asks targeted questions, the user answers, and the AI synthesizes responses into standardized sections. Used for Vision, Architecture, Glossary, and Design System documents |
| **Milestone** | A 3–6 month business achievement that changes the company's competitive position |
| **Goal** | A 2–6 week chunk decomposed from a milestone — a manageable slice of business value. Users can Approve, Steer, or Reject goals |
| **MVI** | Minimum Valuable Increment — a 2–5 day deliverable that is already a visible step forward. This is the merge set for PRs. Monitored via the MVI Blackboard |
| **Task** | An atomic unit of work estimated at ≤ 8 hours of human equivalent effort. If an agent generates a task estimated at > 8 hours, it must auto-split into smaller tasks. Human time estimates are sourced from a benchmark database, not AI estimation. A Murder executes it by dynamically coordinating its Crows |
| **Execution** | A single run of a Murder against a task |
| **MVI Blackboard** | The live execution monitor for an MVI. Shows task/PR status, active Crow states, a Live Feed of events, Merge Readiness checklist, cost/ROI, and the Ship action. The founder's real-time window into what the Murder is doing |
| **Live Feed** | A real-time stream of timestamped events on the MVI Blackboard — Crow state changes, Murder decisions, PR approvals, kickoffs. Displayed with a red LIVE badge during active execution |
| **Merge Readiness** | A checklist of prerequisites that must be satisfied before an MVI can be shipped: all PRs reviewed, CI passing, all tasks complete |
| **Ship** | The action of merging all approved PRs and closing an MVI. Only available when Merge Readiness is fully satisfied |
| **AI Verdict** | The Reviewer Crow's automated assessment of a PR. Includes a confidence level, key findings (green checks and amber warnings), and a summary. Displayed as the first card on the PR Review screen |
| **Plan vs Execution** | A comparison view on the PR Review screen showing each Crow's planned approach alongside what was actually built. Highlights deviations with Complexity Hints |
| **Complexity Hint** | An amber-flagged callout on the PR Review screen where execution deviated from the plan. Explains why the deviation happened and assesses risk |
| **Steer** | A user action that sends directional feedback to a Murder without rejecting the work outright. Available at Goal, MVI, and PR Review levels. The Murder incorporates the feedback and adjusts its approach |
| **Approve / Steer / Reject** | The three-action pattern available throughout the approval flow: Approve accepts work as-is, Steer sends feedback for adjustment, Reject cancels the work. Used on Goals, MVIs, Tasks, and PR Reviews |
| **Credits** | The platform's prepaid currency. Users purchase credits upfront; credits are spent as projects execute. Each credit bundles AI cost, repository infrastructure, workflow orchestration, and compute. The internal cost breakdown is never exposed to users |
| **ROI** | Return on Investment — always displayed as the ratio of AI cost (credits spent) vs human equivalent cost (from benchmark database). Shown at every level: Dashboard, Project Hub, Goal, MVI, Task, and Billing. Cost is never displayed alone |
| **Pipeline Bar** | A stacked horizontal bar visualizing the status distribution of tasks or MVIs: done (solid) / active (medium) / refined (light) / draft (faintest). Uses tones of the same color. Appears on Project Cards and the Backlog |
| **Marketplace** | A discovery area for community-shared Murder templates and Skill definitions. Appears on both the Murders and Skills tabs. Users can browse, preview, and install pre-built configurations |
| **Notification** | An actionable or informational card delivered to the founder. Two categories: Needs Action (approve/steer/reject inline) and Recent (navigable via deep link). Types include Task Approval, MVI Ready, Task Failed, MVI Shipped, Credits Low, and Vision Ready |
| **Tenant** | A company or user account. All data is isolated per tenant |
| **.pen** | Pencil's JSON-based design file format, used for design-as-code |

---

## The Flow

```
┌─────────────────────────────────────────────────────────┐
│                    FOUNDER (iOS App)                      │
│                                                           │
│  1. Create Project                                        │
│  2. Chat with Vision AI → define what to build            │
│  3. AI proposes Milestones → approve/edit/reject          │
│  4. AI decomposes Milestones into Goals → approve/edit    │
│  5. AI breaks Goals into MVIs → approve/edit              │
│  6. AI generates Tasks per MVI (each ≤ 8h human equiv,    │
│     auto-split if larger) → approve/edit                   │
│  7. Watch Crows execute in real-time                      │
│  8. Review PRs → merge from phone                         │
│  9. MVI complete → AI proposes next MVI                   │
└───────────────────────────┬─────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│              THE MURDER (Backend Orchestration)            │
│                                                           │
│  Receives approved task                                   │
│  → Reads blackboard state (context, prior work, goals)    │
│  → Decides which Crows to deploy and in what order        │
│  → Creates Nest (git worktree or workspace) per Crow      │
│  → Crows move through behavior states dynamically         │
│     (Scouting → Planning → Building → Hunting → Landed)   │
│  → Streams behavior state changes to iOS app (SSE)        │
│  → Murder evaluates Landed states → routes next Crow      │
│  → Reports cost, duration, outcome                        │
└─────────────────────────────────────────────────────────┘
```

### Detailed Task Lifecycle

```
AI generates task (from MVI)
    ↓
PENDING APPROVAL → push notification to founder
    ↓
Founder approves (or edits + approves, or rejects)
    ↓
QUEUED → enters SQS
    ↓
Murder picks up → reads blackboard → decides crow deployment strategy
    ↓
Crows activated — each moves through behavior states:
  Scouting  → exploring context, reading codebase/prior work
  Planning  → breaking down approach, creating strategy
  Building  → writing code, creating files, making changes
  Hunting   → looking for bugs, running tests, validating
  Reviewing → QA crow checking work, reading diffs
  Documenting → writing docs, updating references
  Landed    → done, waiting for Murder's next decision
    ↓
Murder evaluates Landed Crows → deploys next Crows or closes execution
    ↓
COMPLETED → outcome delivered, execution recorded
```

### Murder Types

A Murder is a specialized flock — not a generic orchestrator. Projects are assigned one or more Murders based on their domain needs.

| Murder Type | Purpose | Example Crows |
|-------------|---------|---------------|
| **Dev Murder** | Software development | Planner, Implementer, Reviewer, Fixer, Documenter |
| **Editorial Murder** | Book and content creation | Researcher, Outliner, Writer, Editor, Proofreader |
| **Social Murder** | Social media content | Content Creator, Visual Designer, Scheduler, Analyst |
| **Infra Murder** | DevOps and infrastructure | IaC Writer, Security Auditor, Cost Optimizer, Deployer |
| **Data Murder** | Data pipelines | Schema Designer, ETL Builder, Validator, Reporter |
| **Custom** | Any user-defined domain | Configured per project |

---

## Data Hierarchy

```
Tenant (company/user)
│
├── Project: "Cawnex"
│   ├── Vision: "Multi-agent platform that turns issues into PRs"
│   ├── Repositories: [github.com/user/cawnex]
│   ├── Murders:
│   │   ├── Dev Murder (Planner, Implementer, Reviewer, Fixer, Documenter)
│   │   └── Infra Murder (IaC Writer, Security Auditor, Deployer)
│   ├── Credit Budget: (allocated credits, spending limits per Murder)
│   └── Milestones:
│       ├── M1: "Foundation" (business achievement: platform can accept and process first task)
│       │   ├── Goal 1: "API Infrastructure" (2 weeks)
│       │   │   ├── MVI 1.1: "DynamoDB + S3 Core Storage"
│       │   │   │   ├── Task: "Create single-table DynamoDB schema" → COMPLETED (Dev Murder)
│       │   │   │   ├── Task: "Set up S3 tenant-scoped storage" → COMPLETED (Dev Murder)
│       │   │   │   └── Task: "Write integration tests" → COMPLETED (Dev Murder)
│       │   │   └── MVI 1.2: "REST API Endpoints"
│       │   │       ├── Task: "Build Pen API CRUD" → IN PROGRESS (Dev Murder)
│       │   │       └── Task: "Add API Gateway + Lambda" → PENDING APPROVAL (Infra Murder)
│       │   └── Goal 2: "Auth & Identity" (3 weeks)
│       │       └── MVI 2.1: "Cognito + Apple Sign In"
│       │           ├── Task: "Configure Cognito user pool" → QUEUED (Infra Murder)
│       │           └── Task: "Implement Apple Sign In flow" → QUEUED (Dev Murder)
│       └── M2: "Core Loop" (business achievement: first autonomous task execution)
│           └── ...
│
├── Project: "Calhou"
│   ├── Vision: "Modern quoting platform for aluminum window industry"
│   ├── Repositories: [calhou, calhou-api]
│   ├── Murders:
│   │   └── Dev Murder (Planner, Implementer, Reviewer)
│   └── ...
│
└── Project: "Client X"
    └── ...
```

---

## Screen Map (iOS App)

### Row 0 — Auth + Global Tabs
| Screen | Description |
|--------|-------------|
| S01 — Splash | Crow logo animation |
| S02 — Sign In | Apple Sign In + email/password (Cognito) |
| S10 — Dashboard | Project list with pipeline bars (done/active/refined/draft), budget widget (spent vs human equiv saved), sort/filter controls |
| S40 — Murders | All Murders with status, active crow count, current behavior states |
| S60 — Skills | Skill library — reusable capabilities assigned to Crows |
| S50 — Settings | Account, credits & billing, webhooks, API keys, notifications |

### Row 1 — Project + Settings Drill-In
| Screen | Description |
|--------|-------------|
| S12 — Project Hub | Central routing screen: stats row (progress, tasks, pending, ROI), document cards (Vision/Architecture/Glossary/Design System), backlog pipeline card, assigned murders, cost footer |
| S51 — Credits & Billing | ROI summary (multiplier + human equiv saved), credit balance, usage breakdown, purchase credits, transaction history |

### Row 2 — Documents (AI-Guided)
| Screen | Description |
|--------|-------------|
| S12a — Vision Document | Purple accent. AI-guided chat that builds a 6-section vision document through structured questions. AI asks → user answers → AI synthesizes into standardized sections |
| S12c — Architecture Document | Blue accent. 7-section technical architecture document. Same AI-guided flow |
| S12d — Glossary Document | Green accent. AI extracts terms from Vision + Architecture docs, user approves/edits each term |
| S12e — Design System Document | Orange accent. Visual sections with color swatches, typography preview, spacing. 5 sections |

### Row 3 — Backlog Drill-In
| Screen | Description |
|--------|-------------|
| S12b — Backlog | Milestone list with expandable goals. Each goal shows status chip, description, counts. "+ Add Goal" and "+ Milestone" actions |
| S12f — Goal Detail | MVI cards with progress, task counts, ROI per MVI. Murder assignment. Approve/Steer/Reject flow |
| S12g — MVI Task Review | Task list with crow assignments (model per crow), human estimate per task (max 8h), Approve/Steer/Reject per task |
| S13b — MVI Blackboard | Live execution monitor: tasks & PRs with status, murder decisions, crow reports, blackboard events stream, merge readiness checklist, ship button |

### Row 4 — Deprecated
Old screens kept for reference (S03a-c Onboarding, S20 Approvals, S30 Live, S11 Project Home)

---

## Design System Components

### Foundation Tokens
| Token | Light | Dark | Type |
|-------|-------|------|------|
| `--background` | #F5F5F5 | #0A0A0A | color |
| `--card` | #FFFFFF | #1A1C1E | color |
| `--card-foreground` | #1A1C1E | #FFFFFF | color |
| `--primary` | #7C3AED | #9F67FF | color (crow purple) |
| `--primary-foreground` | #FFFFFF | #FFFFFF | color |
| `--muted` | #F0F0F0 | #2D2F31 | color |
| `--muted-foreground` | #6B7280 | #9CA3AF | color |
| `--border` | #E5E5E5 | #404244 | color |
| `--destructive` | #EF4444 | #EF4444 | color |
| `--success` | #22C55E | #22C55E | color |
| `--warning` | #F59E0B | #F59E0B | color |
| `--info` | #3B82F6 | #3B82F6 | color |
| `--font-primary` | Inter | Inter | string |
| `--font-mono` | JetBrains Mono | JetBrains Mono | string |
| `--radius-sm` | 4 | 4 | number |
| `--radius-m` | 8 | 8 | number |
| `--radius-lg` | 16 | 16 | number |
| `--radius-pill` | 9999 | 9999 | number |

### Reusable Components
| Component | Variants | Used in |
|-----------|----------|---------|
| **ProjectCard** | with milestone progress, active task count | S10 |
| **MilestoneRow** | pending, in progress, completed — contains Goals | S11, S13 |
| **GoalCard** | pending, in progress, completed — shows MVI progress count | S13 |
| **MVICard** | task/PR status, merge readiness indicator | S13, S13b |
| **TaskCard** | pending approval, approved, executing, completed, failed | S20, S21, S13b |
| **CrowBadge** | scouting, planning, building, hunting, reviewing, documenting, landed, idle, failed | S40, S41, S31 |
| **MurderCard** | idle, active, error — shows Murder Type, active crow count, current behavior states | S40, S11 |
| **StatusPill** | queued, running, completed, failed, cancelled, pending | S30, S13 |
| **CostLabel** | dollar amount, token count | S31, S11 |
| **ApproveRejectBar** | approve + reject buttons, with swipe gesture | S21, S22, S23, M01 |
| **ExecutionCard** | compact (list), expanded (detail) | S30 |
| **StreamLine** | tool_use, output, error, planning, peer_message | S31, S32 |
| **RepoChip** | connected, syncing, error | S11, S52 |
| **MetricCard** | number, percentage, mini chart | S11 |
| **WorkflowStep** | crow behavior state block, with crow icon + behavior label + status | S41, S31 |
| **VisionBubble** | user message, AI message, suggestion (with approve/reject) | S12 |
| **EmptyState** | no data, error, loading, first-time | All screens |
| **LLMKeyInput** | API key field + test button + status indicator | S51, S03 |
| **NavBar** | bottom tab bar (5 tabs) with badge counts | Global |

---

## Pricing

Cawnex uses a **prepaid credits model**. Users purchase credits upfront and spend them as projects execute. Platform pricing covers AI costs, repository infrastructure, workflow orchestration, and compute — the internal cost breakdown is not exposed to users.

| Visible to User | Internal to Cawnex |
|---|---|
| Credits purchased | Revenue |
| Credits spent per project | AI + repo + workflow + infra costs + margin |
| Human equivalent saved | Benchmark DB calculation |
| ROI multiplier | spent vs saved ratio |

---

## Competitive Position

| | Copilot | Cursor | Devin | Lovable | **Cawnex** |
|---|---------|--------|-------|---------|-----------|
| Multi-agent | ❌ | ❌ | ❌ | ❌ | ✅ |
| Multi-repo sync | ❌ | ❌ | ❌ | ❌ | ✅ |
| Vision → Tasks → Outcomes | ❌ | ❌ | Partial | ❌ | ✅ |
| Human approval flow | ❌ | ❌ | ❌ | ❌ | ✅ |
| Prepaid credits (no API keys) | ❌ | ❌ | ❌ | ❌ | ✅ |
| Native iOS app | ❌ | ❌ | ❌ | ❌ | ✅ |
| Customizable Murder Types | ❌ | ❌ | ❌ | ❌ | ✅ |
| Multi-domain (dev, editorial, infra…) | ❌ | ❌ | ❌ | ❌ | ✅ |
| Price | $10-19 | $20-40 | $500 | $20-50 | **Prepaid credits** |

---

## What Cawnex is NOT

- **Not a code editor** — we don't compete with Cursor or Copilot
- **Not a single-agent builder** — we orchestrate multiple specialized agents organized into Murders
- **Not a dev-only tool** — Murders work across software, content, data, infra, and any custom domain
- **Not an LLM provider** — we never host models, users bring their own
- **Not a project management tool** — we provide the backlog structure (Milestone → Goal → MVI → Task) but focus on AI-driven execution and ROI transparency
