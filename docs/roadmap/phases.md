# 🗺️ Cawnex Roadmap — Phases

---

## Phase 0 — Foundation (Weeks 1-2)
> "The subprocess with regex that works"

### Goal
Get ONE agent executing ONE issue on ONE repo end-to-end.

### Deliverables
- [ ] Monorepo structure (`apps/api`, `apps/dashboard`, `apps/worker`)
- [ ] PostgreSQL schema (organizations, repos, issues, executions, events)
- [ ] Redis Streams setup (event bus)
- [ ] GitHub webhook receiver
- [ ] Single Dev Crow: takes issue → creates worktree → writes code → opens PR
- [ ] Basic execution tracking (start/complete/fail)
- [ ] CLI: `cawnex run <issue-url>`

### Not Yet
- No dashboard
- No multi-repo
- No QA/Docs agents
- No multi-tenant
- No routing (manual assignment)

### Success Criteria
Run `cawnex run https://github.com/org/repo/issues/1` and get a PR opened automatically.

---

## Phase 1 — The Core Loop (Weeks 3-5)
> "Issue to merged PR, autonomous"

### Goal
Complete autonomous pipeline: Refine → Develop → Review → Merge.

### Deliverables
- [ ] Refinement Crow (issue → user story + acceptance criteria)
- [ ] QA Crow (review PR against acceptance criteria)
- [ ] Docs Crow (update docs after merge)
- [ ] Human approval flow (webhook callback or dashboard button)
- [ ] Execution state machine (queued → running → completed/failed)
- [ ] SSE streaming (events in real-time)
- [ ] Basic dashboard (executions list + detail view)
- [ ] Guard system (token budget, time limit, loop detection)
- [ ] Smart retry (test failures → retry with error context)

### Not Yet
- No multi-repo coordination
- No synchronized PRs
- No multi-tenant
- Single LLM provider (Claude only)

### Success Criteria
Create a GitHub issue with label `cawnex` → Refinement generates story → Human approves → Dev implements → QA reviews → Auto-merge → Docs updated. Full cycle, single repo.

---

## Phase 2 — The Murder (Weeks 6-9)
> "Cross-repo coordination"

### Goal
Handle issues that affect multiple repositories with synchronized PRs.

### Deliverables
- [ ] LLM-based router (analyze issue → determine affected repos)
- [ ] Multi-repo execution (parallel dev agents per repo)
- [ ] Context sharing between agents (API contracts)
- [ ] Synchronized PR merge (all-or-nothing)
- [ ] Coordinated rollback on failure
- [ ] CAWNEX.md spec and auto-detection
- [ ] Dashboard v2 (stats, cost tracking, agent overview)
- [ ] Split Dev Crow → Backend Crow + Frontend Crow
- [ ] Webhook support for Linear (in addition to GitHub)

### Not Yet
- No multi-tenant
- No mobile agent
- No security agent
- No marketplace

### Success Criteria
Create one issue that affects backend + frontend → both repos get coordinated PRs → synchronized merge → no broken contracts.

---

## Phase 3 — Production Ready (Weeks 10-14)
> "Multi-tenant SaaS"

### Goal
Ship Cawnex as a product that other teams can use.

### Deliverables
- [ ] Multi-tenant architecture (org isolation)
- [ ] OAuth flow (GitHub App installation)
- [ ] User authentication (GitHub OAuth)
- [ ] Billing/usage tracking
- [ ] Security Crow (SAST/DAST)
- [ ] Mobile Crow
- [ ] Jira integration
- [ ] GitLab integration
- [ ] Slack/Discord notifications
- [ ] Deployment on AWS (ECS or K8s)
- [ ] Landing page on cawnex.ai
- [ ] Documentation site

### Success Criteria
External team installs Cawnex GitHub App → connects repos → creates issue → gets automated PR. We can bill them.

---

## Phase 4 — Scale (Months 4-6)
> "The Marketplace"

### Deliverables
- [ ] Planning Crow (epics → issues)
- [ ] Skills Marketplace (shareable agent configs)
- [ ] ROI Dashboard (time saved, cost per PR, quality metrics)
- [ ] Browser testing agent (E2E via Playwright)
- [ ] LLM-DFA router (formalized state machine)
- [ ] CLI v2 (`cawnex watch`, `cawnex agents`, `cawnex roost`)
- [ ] Kubernetes deployment with auto-scaling
- [ ] Kafka migration (if Redis Streams becomes bottleneck)
- [ ] Enterprise features (SSO, audit logs, compliance)

---

## Tech Stack Evolution

| Phase | Backend | Frontend | DB | Queue | Infra |
|-------|---------|----------|-----|-------|-------|
| 0 | FastAPI | — | PostgreSQL | Redis Streams | Docker local |
| 1 | FastAPI | React+Vite | PostgreSQL | Redis Streams | Docker Compose |
| 2 | FastAPI | React+Vite+shadcn | PostgreSQL | Redis Streams | Docker Compose |
| 3 | FastAPI | React+Vite+shadcn | PostgreSQL + Redis | Redis Streams | AWS ECS/K8s |
| 4 | FastAPI | React+Vite+shadcn | PostgreSQL + ClickHouse | Kafka + Redis | K8s + ArgoCD |

---

## Risk Matrix

| Risk | Impact | Probability | Mitigation |
|------|--------|------------|------------|
| LLM costs higher than expected | HIGH | MEDIUM | Token budgets per execution, model selection per agent type |
| Success rate too low (<50%) | HIGH | MEDIUM | Better system prompts, CAWNEX.md spec, guard system |
| GitHub API rate limits | MEDIUM | HIGH | Caching, GitHub App (higher limits), queuing |
| Agent hallucination at scale | HIGH | MEDIUM | Guard system, output validation, human escalation |
| Synchronized merge failures | HIGH | LOW | Pre-merge validation, fast revert, test in staging first |
| Redis Streams insufficient at scale | MEDIUM | LOW | Migration path to Kafka already designed |
| Competition (Devin, Copilot Workspace) | MEDIUM | HIGH | Focus on orchestration (multi-agent, multi-repo) — not single-agent coding |

---

## Competitive Landscape

| Product | What it does | Cawnex differentiator |
|---------|-------------|----------------------|
| **GitHub Copilot** | Code completion | Single file, no orchestration, no E2E |
| **Devin (Cognition)** | Autonomous dev agent | Single agent, no multi-repo coordination |
| **Cursor** | AI-powered IDE | IDE-bound, no CI/CD integration |
| **Codex (OpenAI)** | Code agent | Single repo, no orchestration |
| **Sweep** | AI PR agent | Limited to simple issues, no QA loop |
| **AgentOps (Luiz)** | Full orchestration | Internal tool, not available publicly |
| **Cawnex** | **Multi-agent orchestration** | **Multi-repo, synchronized PRs, specialized agents, issue-tracker agnostic** |

The gap in the market: **nobody offers multi-agent, multi-repo, orchestrated development as a product.** Luiz built it internally. Cawnex productizes it.
