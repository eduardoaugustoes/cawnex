# Cawnex Architecture V2 — Coordinated Intelligence

> From idea to software, guided by human direction.

## Core Philosophy

```
Dynasty  → org/tenant (all projects)
Court    → Monarch + Council (project decisions)
Murder   → execution orchestrator
Crows    → specialist workers

Within each Court:
Crows    → intelligence (know HOW to do)
Council  → judgment (know WHAT matters)
Monarch  → direction (knows WHERE to go)
Human    → steers the Monarch
```

Agents have intelligence but no judgment. The council has judgment but no authority.
The Monarch has authority but follows human direction. The human sets the course.

---

## Hierarchy

```
┌─────────────────────────────────────────────────────┐
│                      HUMAN                           │
│              (founder / product owner)               │
│                                                      │
│  Manages Dynasty, steers projects via directives:   │
│    "MVP mode, ship onboarding in 2 weeks"            │
│    "Pivot to B2B, pause consumer features"           │
│    "Focus on security before launch"                 │
└────────────────────────┬────────────────────────────┘
                         │ manages
                         ▼
┌─────────────────────────────────────────────────────┐
│                     DYNASTY                          │
│                 (org/tenant level)                   │
│                                                      │
│  Contains multiple Courts (projects):                │
│    • Court: Cawnex (directive: "Build Sprint 1")    │
│    • Court: Mobile App (directive: "Ship MVP")      │
│    • Court: Analytics (directive: "Add reports")    │
│                                                      │
│  Sets org-wide policies:                             │
│    • Tech stack standards (TypeScript, CDK)         │
│    • Security requirements (OWASP, auth patterns)   │
│    • Code quality rules (testing, reviews)          │
└────────────────────────┬────────────────────────────┘
                         │ each project has a
                         ▼
┌─────────────────────────────────────────────────────┐
│                      COURT                           │
│              (project-level decisions)               │
│                                                      │
│  Monarch + Council for one specific project         │
└────────────────────────┬────────────────────────────┘
                         │ directive per project
                         ▼
┌─────────────────────────────────────────────────────┐
│                     MONARCH                          │
│              (strategic decision maker)              │
│                                                      │
│  - Internalizes human directives                     │
│  - Convenes council when decisions are needed        │
│  - Makes final call after hearing votes              │
│  - Organizes work into Waves                         │
│  - Escalates to human when uncertain                 │
│                                                      │
│  System prompt includes:                             │
│    - Current directive from human                    │
│    - Project phase (vision/strategy/execution)       │
│    - Budget and timeline constraints                 │
│    - History of past decisions and outcomes          │
└────────────────────────┬────────────────────────────┘
                         │ convenes
                         ▼
┌─────────────────────────────────────────────────────┐
│                     COUNCIL                          │
│              (advisory board, parallel)              │
│                                                      │
│  🛡️  Security    — vulnerabilities, auth, data       │
│  📐 Quality     — patterns, tests, maintainability  │
│  ⚡ Performance — latency, cost, scalability        │
│  📈 Market      — business value, user impact, GTM  │
│  🧱 Maturity    — tech debt, stability, reliability │
│  🔍 Clarity     — spec ambiguity, missing reqs      │
│                                                      │
│  Each advisor:                                       │
│    - Scores tasks/priorities (1-10)                  │
│    - Recommends which crows to recruit               │
│    - Flags blockers from their perspective           │
│    - Provides reasoning                              │
│                                                      │
│  Special powers:                                     │
│    - Security has VETO on critical vulnerabilities   │
│    - Clarity can BLOCK tasks with ambiguous specs    │
└────────────────────────┬────────────────────────────┘
                         │ votes + recommendations
                         ▼
┌─────────────────────────────────────────────────────┐
│                     MURDER                           │
│              (execution orchestrator)                │
│                                                      │
│  - Receives Monarch's execution plan                 │
│  - Dispatches tasks to crows via blackboard          │
│  - Manages parallel execution within a wave          │
│  - Handles retries, errors, escalation               │
│  - Reports wave completion to Monarch                │
│                                                      │
│  Does NOT make strategic decisions.                  │
│  Executes the plan faithfully.                       │
└────────────────────────┬────────────────────────────┘
                         │ tasks
                         ▼
┌─────────────────────────────────────────────────────┐
│                      CROWS                           │
│              (specialist workers)                    │
│                                                      │
│  🐦 Vision       — project brief, personas, flows   │
│  🐦 Architect    — tech stack, data models, APIs    │
│  🐦 Planner      — break work into tasks            │
│  🐦 Implementer  — write code, commit, push         │
│  🐦 Reviewer     — review diffs, approve/reject     │
│  🐦 Tester       — write tests, run tests           │
│  🐦 Designer     — UI specs, component design       │
│  🐦 DevOps       — infra, CI/CD, deployment         │
│  🐦 Docs         — API docs, guides, changelog      │
│  🐦 Researcher   — market analysis, benchmarks      │
│  🐦 Custom...    — user-defined specialists         │
│                                                      │
│  Each crow:                                          │
│    - Has a specialized system prompt                 │
│    - Receives scoped context (not full repo)         │
│    - Returns structured output (artifacts)           │
│    - Is stateless (context comes from Murder)        │
└─────────────────────────────────────────────────────┘
```

---

## Dynasty Structure

A Dynasty represents one organization/tenant and contains multiple Courts (projects):

```
Dynasty: "Acme Corp"
├── Court: "Cawnex"
│     ├── Monarch (directive: "Build Sprint 1: foundation + context")
│     ├── Council (Security, Quality, Market, Performance, Maturity, Clarity)
│     ├── Murder → dispatching Wave 2 tasks
│     └── Crows → implementing, reviewing, testing
│
├── Court: "Calhou" 
│     ├── Monarch (directive: "MVP quoting calculator")
│     ├── Council (same advisors, different project context)
│     ├── Murder → executing Wave 1
│     └── Crows → building calculator features
│
└── Court: "Mobile App"
      ├── Monarch (directive: "Ship onboarding flow")
      ├── Council
      └── Murder → idle, waiting for wave approval
```

**Dynasty-level inheritance:**

```
Dynasty policy: "TypeScript, vitest, CDK, OWASP top 10, DRY principles"
     ↓ inherited by all Courts
Court/Cawnex:   "Build orchestration platform" + dynasty policies
Court/Calhou:   "Build quoting calculator" + dynasty policies  
```

Each Court operates independently but shares dynasty standards. The human can:
- Set dynasty-wide policies (affect all projects)
- Steer individual Monarchs with project-specific directives
- Move resources between Courts as priorities shift

---

## Waves — Deliverable Units of Work

Work is organized into **Waves**: coherent, deliverable batches of tasks.

```
Human: "MVP. Focus onboarding. Ship in 2 weeks."
                    │
                    ▼
             Monarch + Council
                    │
                    ▼
        ┌─────────────────────────┐
        │ Wave 1 (Week 1)        │
        │  ✅ Auth básico         │
        │  ✅ Onboarding flow     │
        │  ✅ Core feature        │
        ├─────────────────────────┤
        │ Wave 2 (Week 2)        │
        │  ⬜ Payment             │
        │  ⬜ Notifications       │
        │  ⬜ Polish              │
        ├─────────────────────────┤
        │ Deferred (post-MVP)    │
        │  💤 Performance tuning  │
        │  💤 100% test coverage  │
        │  💤 Admin dashboard     │
        └─────────────────────────┘
```

### Wave Lifecycle

```
PLANNING → APPROVED → EXECUTING → REVIEW → DELIVERED
                ↑                     │
                │    human steers     │
                └─────────────────────┘
```

1. **PLANNING** — Monarch + Council create the wave (tasks, crows, order)
2. **APPROVED** — Human reviews and approves (or edits) the wave
3. **EXECUTING** — Murder dispatches crows, tasks run in parallel where possible
4. **REVIEW** — Wave complete, human reviews deliverables (PRs, docs, designs)
5. **DELIVERED** — Merged, shipped. Monarch plans next wave.

At ANY point, human can:
- **Steer**: "change direction, focus on X instead"
- **Pause**: "stop, let me think"
- **Inject**: "add this urgent task to current wave"
- **Skip**: "defer this wave, move to next"

---

## Project Phases

Each project progresses through phases. The council adapts its lens per phase.

### Phase 1 — Vision (idea → structure)

```
Input:  "I want to build a food delivery app"
Output: PROJECT_BRIEF.md, personas, user flows, KPIs

Crows:  Vision, Architect, Researcher (parallel)
Council focus: Clarity (is the idea well-defined?), Market (viable?)
Human:  Approves the brief
```

### Phase 2 — Strategy (structure → plan)

```
Input:  Approved PROJECT_BRIEF.md
Output: Milestones, design system, infra plan, timeline

Crows:  Milestone, Designer, Infra (parallel)
Council focus: Market (right priorities?), Maturity (realistic?)
Human:  Approves milestones and roadmap
```

### Phase 3 — Planning (plan → backlog)

```
Input:  Approved milestones
Output: Tasks with acceptance criteria, deps, estimates

Crows:  TaskBreaker, QA, Security (parallel per milestone)
Council focus: Clarity (specs clear?), Security (reqs covered?)
Human:  Approves backlog, may reprioritize
```

### Phase 4 — Execution (backlog → code)

```
Input:  Approved tasks (wave by wave)
Output: PRs, tests, docs

Crows:  Implementer, Tester, Reviewer (per task)
Council focus: Quality, Security, Performance
Human:  Reviews PRs or trusts auto-merge (confidence-based)
```

### Phase 5 — Evolution (continuous)

```
Input:  Running product, new issues, feedback
Output: Bug fixes, improvements, refactors

Crows:  Monitor, Refactorer, Docs
Council focus: Maturity (tech debt), Performance (scaling)
Human:  Steers priorities as business evolves
```

---

## Decision Protocol

### When to use each level

| Decision Type | Who Decides | Example |
|---------------|-------------|---------|
| Next step in active task | Murder alone | "implementer done → send to reviewer" |
| Which task to execute next | Council + Monarch | "auth or onboarding first?" |
| Milestone/wave planning | Council + Monarch + Human approval | "what's in Wave 1?" |
| Architecture/direction change | Council + Monarch + Human approval | "switch from REST to GraphQL" |
| Emergency (security/prod) | Security advisor VETO → Monarch auto-acts | "critical vulnerability found" |

### Council Voting Process

```
1. Monarch convenes council with:
   - Current directive
   - Project context
   - Decision needed

2. All advisors run in PARALLEL (6 Lambda calls)
   Each returns:
   - scores: {task_id: 1-10}
   - reasoning: "why"
   - recommended_crows: ["implementer", "tester"]
   - blockers: ["auth has no rate limiting"]
   - confidence: 0.0-1.0

3. Monarch receives all votes
   - Weighs by confidence and directive alignment
   - Security VETO overrides all
   - Clarity BLOCK prevents ambiguous tasks from starting
   - Makes final decision with reasoning

4. Decision recorded in blackboard for audit trail
```

### Cost Model

```
Council session (6 advisors + monarch):  ~$0.09
Amortized per task (wave of 10 tasks):   ~$0.01/task
Crow execution:                          ~$0.01-0.15/task
Total per task:                          ~$0.02-0.16

vs manual developer time:               $50-200/task
```

---

## Communication Protocol

### Task Contract (Murder → Crow)

```json
{
  "PK": "EXEC#abc",
  "SK": "STEP#02#TASK",
  "version": "1",
  "crow": "implementer",
  "instructions": "Implement GET /health endpoint",
  "context": {
    "type": "implement",
    "project_brief": "...",
    "plan": "...",
    "files_to_read": ["lambdas/poc5-api/handler.py"],
    "files_to_modify": ["lambdas/poc5-api/handler.py"],
    "include_tree": false,
    "include_diff": false
  },
  "repo": "owner/repo",
  "branch": "cawnex/exec_abc",
  "status": "pending"
}
```

### Report Contract (Crow → Murder)

```json
{
  "PK": "EXEC#abc",
  "SK": "STEP#02#REPORT",
  "version": "1",
  "outcome": "completed",
  "crow": "implementer",
  "outputs": {
    "files_changed": ["lambdas/poc5-api/handler.py"],
    "diff_summary": "+45 -0 lines",
    "commit_sha": "abc123",
    "pr_url": "https://github.com/...",
    "artifacts": {
      "code_diff": "..."
    }
  },
  "cost": "0.006",
  "duration_ms": 30000,
  "tokens": {"in": 2000, "out": 500}
}
```

### Context by Phase

| Crow | Gets | Doesn't get |
|------|------|-------------|
| Planner | file tree + key files + issue | diff (doesn't exist yet) |
| Implementer | specific files (from plan) + plan | full repo |
| Reviewer | git diff + changed files + plan | full repo |
| Fixer | diff + review issues + files | full repo |
| Tester | changed files + plan + existing tests | full repo |

Murder assembles context intelligently based on crow type and phase.

---

## Context Hierarchy

Inspired by Claude Code's CLAUDE.md pattern, applied to multi-tenant SaaS:

```
S3 or DynamoDB:

  /dynasty/{org_id}/
      CLAUDE.md                     ← dynasty-wide standards
      
  /dynasty/{org_id}/court/{project_id}/
      CLAUDE.md                     ← project context + architecture
      VISION.md                     ← project vision
      ROADMAP.md                    ← milestones + timeline
      
  /dynasty/{org_id}/court/{project_id}/agents/
      monarch.md                    ← monarch directive + personality
      council/
          security.md               ← security advisor prompt
          quality.md                ← quality advisor prompt
          ...
      crows/
          implementer.md            ← implementer prompt + rules
          reviewer.md               ← reviewer prompt + rules
          custom_crow.md            ← user-defined specialist
```

When dispatching a crow, the system prompt is assembled in layers:

```python
system = [
    load("dynasty/{org}/CLAUDE.md"),                        # dynasty standards
    load("dynasty/{org}/court/{proj}/CLAUDE.md"),           # project context
    load("dynasty/{org}/court/{proj}/agents/crows/{crow}.md"),  # crow specialization
]
# + Prompt Caching on dynasty + court layers (90% discount)
```

---

## Data Model

### DynamoDB — Single Table

```
PK                          SK                      Data
─────────────────────────── ─────────────────────── ────────────
DYNASTY#org1                META                    name, plan, settings
DYNASTY#org1                COURT#proj1             name, phase, monarch_directive
COURT#proj1                 VISION                  brief, personas, flows
COURT#proj1                 MILESTONE#m1            name, goals, wave
COURT#proj1                 TASK#t001               title, milestone, status, wave
COURT#proj1                 TASK#t002               ...
EXEC#exec1                  META                    court, repo, issue, branch
EXEC#exec1                  STEP#01#TASK            crow, instructions, context
EXEC#exec1                  STEP#01#REPORT          outcome, artifacts, cost
EXEC#exec1                  COUNCIL#vote            advisor_votes, monarch_decision
WAVE#w1                     META                    court, phase, status
WAVE#w1                     TASK#t001               ref to task
WAVE#w1                     TASK#t002               ref to task
```

### GSIs

- **GSI1**: `dynasty_id + court_id` → list courts per dynasty
- **GSI2**: `court_id + wave_id` → list tasks per wave  
- **GSI3**: `status + created_at` → find pending/active work

---

## Autonomy Gradient

```
┌─────────────────────────────────────────────────────┐
│  Confidence   │  Behavior                            │
├───────────────┼──────────────────────────────────────┤
│  🟢 High      │  Auto-merge, notify human            │
│  🟡 Medium    │  Create PR, request human review     │
│  🔴 Low       │  Stop and ask human                  │
├───────────────┼──────────────────────────────────────┤
│  🚨 VETO      │  Security blocker → halt everything  │
└───────────────┴──────────────────────────────────────┘

Confidence increases with:
  - Tests passing
  - Reviewer approved
  - Similar to previously accepted PRs
  - Project maturity (many successful waves)
  - Clear spec (Clarity advisor scored high)

Confidence decreases with:
  - New/unfamiliar patterns
  - Multiple reviewer rejections
  - Security flags
  - Ambiguous requirements
```

---

## Scaling Path

| POC | What | Status |
|-----|------|--------|
| **6** | Worker Lambda + EFS + git | ✅ Done |
| **7** | Context contract (Murder assembles context per phase) | Next |
| **8** | Parallel execution (Murder dispatches N tasks) | |
| **9** | Crow registry (rookery) + discovery | |
| **10** | Council (6 advisors + Monarch) | |
| **11** | Waves (deliverable batches + human approval) | |
| **12** | Vision→Strategy→Planning phases | |
| **13** | Autonomy gradient (confidence-based auto-merge) | |
| **14** | Custom crows (user-defined specialists) | |

---

## The Loop

```
Human steers
    → Monarch directs
        → Council judges
            → Murder dispatches
                → Crows execute
                    → Wave delivered
                        → Human reviews
                            → Human steers → ...
```

Each cycle makes the system smarter:
- Council learns which priorities led to good outcomes
- Monarch learns which directives work for this project
- Crows improve via better context and prompt refinement
- Human trusts more → autonomy increases

---

*"A murder of crows, guided by a monarch, advised by a council, 
building what humans envision."*
