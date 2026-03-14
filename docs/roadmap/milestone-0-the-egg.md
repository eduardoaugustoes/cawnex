# 🥚 Milestone 0 — The Egg

> **Goal**: Prove that a multi-agent orchestration system can take a GitHub issue and produce a merged PR — autonomously.
>
> **Duration**: 2 weeks
> **Infra**: Current VPS (4 cores, 16GB RAM, Ubuntu 24.04)
> **LLM**: Your Anthropic API key (BYOL)
> **Output**: A working script that dogfoods on the Cawnex repo itself

---

## Success Criteria

```
1. Create GitHub issue on cawnex repo with label "cawnex"
2. System reads issue, generates refined user story
3. Human approves (Y/n in terminal)
4. System creates worktree, implements code, opens PR
5. System reviews PR against acceptance criteria
6. If approved → auto-merge
7. System updates docs
```

**If this works → Cawnex is alive.** Everything after is scaling.

---

## Prerequisites

| Need                      | Status | Action                        |
| ------------------------- | ------ | ----------------------------- |
| Docker on VPS             | ❌     | Install                       |
| Anthropic API key         | ❓     | User provides                 |
| GitHub PAT (repo scope)   | ❓     | User provides or use existing |
| PostgreSQL                | ❌     | Via Docker                    |
| Redis                     | ❌     | Via Docker                    |
| Python 3.12               | ✅     | Already installed             |
| Node 22                   | ✅     | Already installed             |
| `uv` (Python pkg manager) | ❌     | Install                       |

---

## Steps

### Step 1 — Environment Setup

**Time: 1-2 hours**

```
1.1  Install Docker + Docker Compose
1.2  Install uv (Python package manager)
1.3  Create .env with:
     - ANTHROPIC_API_KEY
     - GITHUB_TOKEN (PAT with repo scope)
     - ENCRYPTION_KEY (generated)
     - DATABASE_URL
     - REDIS_URL
1.4  docker-compose up (PostgreSQL + Redis)
1.5  Verify: psql connects, redis-cli pings
```

**Done when**: `docker ps` shows postgres + redis running.

---

### Step 2 — Python Workspace + Core Models

**Time: 2-3 hours**

```
2.1  Initialize uv workspace (pyproject.toml)
2.2  Create packages/core:
     - Base SQLAlchemy model (TenantMixin, TimestampMixin)
     - Tenant model (id, name, llm_provider, encrypted_api_key)
     - Repository model (id, tenant_id, github_url, default_branch)
     - Issue model (id, tenant_id, external_id, title, description, status)
     - Execution model (id, issue_id, agent_type, status, cost, duration)
     - Event model (id, execution_id, type, content, timestamp)
     - Enums (AgentType, ExecutionStatus, IssueStatus, Provider)
     - Pydantic schemas for all models
2.3  Create packages/core/db.py (async engine, session factory)
2.4  Alembic init + first migration (create all tables)
2.5  Run migration: tables exist in PostgreSQL
```

**Done when**: `alembic upgrade head` succeeds, tables visible in psql.

---

### Step 3 — BYOL Provider Abstraction

**Time: 2-3 hours**

```
3.1  Create packages/providers:
     - Base protocol: generate(), stream(), run_agent()
     - AnthropicProvider: wraps Claude SDK
       - Support for tool use (file read/write, shell, git)
       - Streaming output
       - Token counting + cost calculation
     - Factory: get_provider(tenant) → Provider
3.2  Create packages/providers/budget.py:
     - Token counter
     - Cost estimator (input/output tokens × price)
     - Budget guard (check before execution)
3.3  Test: call Claude with a simple prompt, get response
3.4  Test: call Claude with tools (read file, write file), verify tool use works
```

**Done when**: `python -m pytest tests/test_provider.py` passes — Claude responds and uses tools.

---

### Step 4 — Git Operations Library

**Time: 2-3 hours**

```
4.1  Create packages/git-ops:
     - worktree.py: create_worktree(repo, branch) → path
     - worktree.py: delete_worktree(path)
     - branch.py: create_branch(name), push(remote)
     - pr.py: create_pr(title, body, head, base) via GitHub API
     - pr.py: merge_pr(pr_number, method="squash")
     - pr.py: get_pr_diff(pr_number) → string
     - diff.py: get_worktree_diff() → string
4.2  Test on cawnex repo itself:
     - Create worktree "test-nest"
     - Create a test file
     - Commit + push
     - Create PR
     - Delete worktree
     - Close PR (cleanup)
```

**Done when**: Test PR appears on github.com/eduardoaugustoes/cawnex and is cleaned up.

---

### Step 5 — Dev Crow (First Agent)

**Time: 3-4 hours**

```
5.1  Create apps/worker/crows/base.py:
     - BaseCrow class
     - Tool registration (read_file, write_file, list_files, shell, search)
     - Execution lifecycle (start → run → complete/fail)
     - Event streaming (log each action to DB)
5.2  Create apps/worker/crows/dev.py:
     - System prompt from prompts/dev.md
     - Receives: issue title, description, repo path, CAWNEX.md content
     - Creates worktree
     - Implements code changes
     - Runs tests (if test framework detected)
     - Commits + pushes
     - Opens PR
     - Returns: PR URL, files changed, cost
5.3  Create prompts/dev.md:
     - Role definition
     - Repo context injection ({{cawnex_md}})
     - Rules (no direct push to main, follow patterns, write tests)
5.4  Test: give Dev Crow a simple issue manually
     - "Add GET /health endpoint that returns {status: ok, version: 0.1.0}"
     - Verify: PR appears with working code
```

**Done when**: Dev Crow creates a real PR on the cawnex repo from a manual issue input.

---

### Step 6 — Refinement Crow

**Time: 2-3 hours**

```
6.1  Create apps/worker/crows/refinement.py:
     - Reads issue title + description
     - Reads CAWNEX.md for repo context
     - Generates:
       • Refined user story (As a... I want... So that...)
       • Acceptance criteria (Given/When/Then)
       • Technical notes
       • Affected files estimate
       • Complexity estimate (S/M/L/XL)
     - Returns structured JSON
6.2  Create prompts/refinement.md
6.3  Test: feed a vague issue → get structured output
     - Input: "add health check"
     - Output: full story with criteria
```

**Done when**: Vague issue → structured, actionable user story.

---

### Step 7 — QA Crow

**Time: 2-3 hours**

```
7.1  Create apps/worker/crows/qa.py:
     - Receives: PR URL + acceptance criteria
     - Gets PR diff
     - Reviews each file against criteria
     - Checks for:
       • Acceptance criteria met
       • Code quality (patterns, naming)
       • Type hints present
       • Tests added (if required)
       • No scope creep (extra unrelated changes)
     - Returns: approved/rejected + comments
7.2  Create prompts/qa.md
7.3  Test: review the PR from Step 5
     - Should approve (if criteria met) or reject with specific feedback
```

**Done when**: QA Crow reviews a real PR and gives structured approve/reject.

---

### Step 8 — Docs Crow

**Time: 1-2 hours**

```
8.1  Create apps/worker/crows/docs.py:
     - Receives: merged PR diff + repo docs structure
     - Identifies what documentation needs updating
     - Updates relevant .md files
     - Commits directly to main (or opens small PR)
8.2  Create prompts/docs.md
8.3  Test: after merging health check PR, verify docs updated
```

**Done when**: Docs auto-update after a merge.

---

### Step 9 — The Murder (Orchestrator)

**Time: 3-4 hours**

```
9.1  Create apps/worker/murder.py:
     - Full pipeline: Refine → Approve → Dev → QA → Merge → Docs
     - State machine: tracks execution status transitions
     - Event logging: every step logged to DB
     - Error handling: catch failures, log, mark execution as failed
9.2  Create apps/worker/guard.py:
     - Token budget check (before each crow)
     - Time limit (15 min max per execution)
     - Loop detection (3+ similar outputs → cancel)
9.3  Create apps/worker/retry.py:
     - QA rejects → send feedback to Dev Crow → retry (max 2)
     - LLM timeout → retry with same context
     - Git conflict → pull + rebase + retry
9.4  Wire up: Redis Streams consumer
     - Worker polls queue
     - Picks up execution request
     - Dispatches to Murder
     - Murder runs the full pipeline
```

**Done when**: Full pipeline runs end-to-end from Redis queue trigger.

---

### Step 10 — GitHub Webhook + API

**Time: 2-3 hours**

```
10.1  Create apps/api/main.py (FastAPI app)
10.2  Create routes:
      - POST /webhooks/github (receive issue events)
      - GET /executions (list)
      - GET /executions/:id (detail with events)
      - POST /issues/:id/approve (human approval)
      - GET /health
10.3  Webhook handler:
      - Receives "issues" event with label "cawnex"
      - Creates Issue record in DB
      - Creates Execution record
      - Pushes to Redis Streams queue
      - Worker picks up → Murder runs
10.4  Set up GitHub webhook on cawnex repo:
      - URL: https://<vps-ip-or-ngrok>/webhooks/github
      - Events: Issues
      - Secret: shared secret for verification
10.5  ngrok or Cloudflare Tunnel for webhook delivery
```

**Done when**: Create issue on GitHub → webhook fires → execution starts → PR created.

---

### Step 11 — The Proof 🥚→🐣

**Time: 1 day**

```
11.1  Create 5 real issues on github.com/eduardoaugustoes/cawnex:

      Issue #1 (Easy):
      "Add GET /health endpoint"
      Returns API status, DB connection, Redis connection, version.

      Issue #2 (Easy):
      "Add execution list endpoint with pagination"
      GET /executions?page=1&limit=20, return total count + items.

      Issue #3 (Medium):
      "Add SSE endpoint for execution events"
      GET /executions/:id/events streams events in real-time.

      Issue #4 (Medium):
      "Add budget guard that pauses when monthly limit reached"
      Check budget before each crow execution. Notify if 80%/100%.

      Issue #5 (Hard):
      "Add tenant settings endpoint with BYOL configuration"
      CRUD for tenant LLM settings. Encrypt API key. Test connection.

11.2  Run each issue through the full pipeline
11.3  Track results:
      - Success/fail per issue
      - Time per execution
      - Cost per execution
      - Retry count
      - Quality of generated code (manual review)

11.4  Document results in docs/results/milestone-0.md
```

**Done when**: At least 3 of 5 issues produce merged PRs with working code.

---

## Step Summary

| Step   | What                  | Time  | Dependency       |
| ------ | --------------------- | ----- | ---------------- |
| **1**  | Environment setup     | 1-2h  | None             |
| **2**  | Core models + DB      | 2-3h  | Step 1           |
| **3**  | BYOL provider         | 2-3h  | Step 1           |
| **4**  | Git operations        | 2-3h  | Step 1           |
| **5**  | Dev Crow              | 3-4h  | Steps 2, 3, 4    |
| **6**  | Refinement Crow       | 2-3h  | Step 3           |
| **7**  | QA Crow               | 2-3h  | Steps 3, 4       |
| **8**  | Docs Crow             | 1-2h  | Steps 3, 4       |
| **9**  | Murder (Orchestrator) | 3-4h  | Steps 5, 6, 7, 8 |
| **10** | API + Webhooks        | 2-3h  | Step 9           |
| **11** | The Proof             | 1 day | Step 10          |

```
              Step 1 (env)
              /    |    \
         Step 2  Step 3  Step 4
            \      |      /
             \     |     /
        Step 6  Step 5  Step 7  Step 8
           \      |      /      /
            \     |     /      /
              Step 9 ←────────
                |
              Step 10
                |
              Step 11 🐣
```

**Total estimated time: ~30-40 hours of work over 2 weeks.**

---

## Deliverables

| Deliverable                   | Description                                   |
| ----------------------------- | --------------------------------------------- |
| `packages/core/`              | Models, schemas, enums, DB setup              |
| `packages/providers/`         | BYOL abstraction (Anthropic first)            |
| `packages/git-ops/`           | Worktree, branch, PR management               |
| `apps/worker/`                | 4 crows + Murder orchestrator + Guard + Retry |
| `apps/api/`                   | FastAPI with webhooks + basic endpoints       |
| `prompts/`                    | 4 agent system prompts                        |
| `docker-compose.yml`          | PostgreSQL + Redis + API + Worker             |
| `CAWNEX.md`                   | Agent instructions for self-work              |
| `docs/results/milestone-0.md` | Proof results with metrics                    |

---

## Risk Mitigation

| Risk                                                 | Mitigation                                              |
| ---------------------------------------------------- | ------------------------------------------------------- |
| Claude Agent SDK doesn't support needed tools        | Fall back to raw tool_use API (manual tool definitions) |
| Webhook delivery fails (VPS not publicly accessible) | Use ngrok or Cloudflare Tunnel                          |
| Dev Crow generates bad code                          | QA Crow catches it → retry loop (max 2)                 |
| Success rate < 50%                                   | Iterate on prompts, add more context in CAWNEX.md       |
| Docker uses too much RAM                             | Limit container memory, reduce worker concurrency to 1  |

---

## After The Egg Hatches

```
Milestone 0: The Egg       ← YOU ARE HERE
Milestone 1: The Hatchling ← Dashboard + multi-repo
Milestone 2: The Fledgling ← SaaS + multi-tenant + billing
Milestone 3: The Flight    ← iOS + Android + App Store
Milestone 4: The Murder    ← Skills marketplace + enterprise
```

---

## iOS Build Solution

For when we reach Milestone 3:

| Option                         | Cost                      | Setup Time     | Best For                  |
| ------------------------------ | ------------------------- | -------------- | ------------------------- |
| **Mac Mini M2** (buy)          | ~$600 one-time            | 1 day          | Long-term, full control   |
| **MacStadium** (cloud Mac)     | ~$50-80/mo                | 1 hour         | No hardware, instant      |
| **AWS EC2 Mac**                | ~$1.20/hr                 | 1 hour         | CI/CD bursts, pay-per-use |
| **Codemagic** (CI only)        | Free tier / $75/mo        | 30 min         | Just builds, no dev       |
| **GitHub Actions macOS**       | Free (public) / $0.08/min | Already set up | CI only                   |
| **BYOD** (your iPhone + Mac)   | $0                        | 0              | If you have one           |
| **Device farm** (AWS/Firebase) | ~$0.17/min                | 1 hour         | Testing on real devices   |

**Recommendation**:

- **Dev**: MacStadium or BYOD Mac for Xcode development
- **CI/CD**: GitHub Actions macOS runners (free for public repos)
- **Testing**: Firebase Test Lab ($0 for 10 devices/day on Spark plan)

Not a blocker. We solve this in Milestone 3, not now.
