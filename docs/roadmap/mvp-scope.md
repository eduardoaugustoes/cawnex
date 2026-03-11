# 🎯 MVP Scope — What's In, What's Out

---

## MVP = Phase 0 + Phase 1

**One sentence**: A GitHub issue with label `cawnex` triggers an autonomous pipeline that refines, implements, reviews, and merges code in a single repository.

---

## ✅ IN (MVP)

### Agents
- Refinement Crow (issue → user story)
- Dev Crow (implement + open PR)
- QA Crow (review PR)
- Docs Crow (update docs post-merge)

### Orchestration
- Sequential pipeline (refine → dev → qa → docs)
- Human approval after refinement
- Guard system (token budget, time limit, loop detection)
- Smart retry (retryable failures only)
- Execution state machine

### Integration
- GitHub (webhooks + API for PRs)
- Single repo per issue

### Dashboard
- Executions list (status, duration, cost)
- Execution detail (streaming events)
- Basic stats (success rate, total cost)

### Infrastructure
- Docker Compose (local/VPS deployment)
- PostgreSQL + Redis
- SSE for real-time streaming

---

## ❌ OUT (Post-MVP)

| Feature | Why out | When |
|---------|---------|------|
| Multi-repo coordination | Complexity. Single repo first. | Phase 2 |
| Synchronized PR merge | Needs multi-repo first | Phase 2 |
| Linear/Jira integration | GitHub Issues is enough for MVP | Phase 2 |
| Multi-tenant | Single org first | Phase 3 |
| Authentication/billing | Self-hosted first | Phase 3 |
| Security Crow | Dev+QA+Docs covers 80% of value | Phase 3 |
| Mobile Crow | Backend+Frontend Crow handles most repos | Phase 3 |
| Backend/Frontend split | Single Dev Crow handles both initially | Phase 2 |
| CLI | Dashboard-first | Phase 4 |
| Skills Marketplace | Need users first | Phase 4 |
| Kubernetes | Docker Compose is fine for <100 executions/day | Phase 3 |
| Kafka | Redis Streams handles MVP traffic | Phase 4 |
| Browser testing | Advanced QA feature | Phase 4 |

---

## MVP User Story

```
As a developer,
I create a GitHub issue labeled "cawnex" in my repository,
And within minutes, I receive:
  1. A refined user story with acceptance criteria (for my approval)
  2. A Pull Request implementing the feature
  3. An automated QA review
  4. Updated documentation
Without writing a single line of code.
```

---

## MVP Success Metrics

| Metric | Target |
|--------|--------|
| End-to-end time (simple issue) | < 10 minutes |
| Success rate | > 60% |
| Cost per execution | < $2.00 |
| QA review time | < 3 minutes |
| Setup time (new repo) | < 5 minutes |

---

## MVP Monorepo Structure

```
cawnex/
├── README.md
├── docker-compose.yml
├── docs/
│   ├── research/          ← What we learned
│   ├── design/            ← How we're building
│   └── roadmap/           ← When we're building
├── apps/
│   ├── api/               ← FastAPI backend
│   │   ├── src/
│   │   │   ├── main.py
│   │   │   ├── routes/
│   │   │   │   ├── webhooks.py
│   │   │   │   ├── executions.py
│   │   │   │   ├── issues.py
│   │   │   │   └── dashboard.py
│   │   │   ├── models/
│   │   │   │   ├── execution.py
│   │   │   │   ├── issue.py
│   │   │   │   └── event.py
│   │   │   ├── services/
│   │   │   │   ├── orchestrator.py    ← The Murder
│   │   │   │   ├── router.py          ← LLM-based routing
│   │   │   │   ├── guard.py           ← Anti-hallucination
│   │   │   │   └── retry.py           ← Smart retry
│   │   │   ├── agents/
│   │   │   │   ├── base.py            ← Base crow class
│   │   │   │   ├── refinement.py
│   │   │   │   ├── dev.py
│   │   │   │   ├── qa.py
│   │   │   │   └── docs.py
│   │   │   └── integrations/
│   │   │       ├── github.py
│   │   │       └── notifications.py
│   │   ├── tests/
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   ├── dashboard/          ← React frontend
│   │   ├── src/
│   │   │   ├── pages/
│   │   │   │   ├── Dashboard.tsx
│   │   │   │   ├── Executions.tsx
│   │   │   │   ├── ExecutionDetail.tsx
│   │   │   │   └── Settings.tsx
│   │   │   ├── components/
│   │   │   └── lib/
│   │   ├── package.json
│   │   └── Dockerfile
│   └── worker/             ← Agent execution runtime
│       ├── src/
│       │   ├── main.py
│       │   ├── crow_runner.py
│       │   └── worktree_manager.py
│       ├── requirements.txt
│       └── Dockerfile
├── prompts/                ← Agent system prompts
│   ├── refinement.md
│   ├── dev.md
│   ├── qa.md
│   └── docs.md
└── scripts/
    ├── setup.sh
    └── seed.sh
```
