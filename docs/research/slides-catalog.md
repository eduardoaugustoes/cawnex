# 🖼️ Slides Catalog — AgentOps Presentation

> 35+ slides captured from Luiz M. Couto's live presentation, March 9, 2026
> Platform: Gamma.app (gamma.app/docs/Agentes-de-IA-Autonomos-*)

---

## Slide Index

### Introductory / Conceptual

| # | Title | Key Content |
|---|-------|-------------|
| 1 | O que são Agentes de IA? | Percebe/Raciocina/Age, executa tarefas completas, funcionário autônomo |
| 2 | Agentes em Ação — Exemplos Reais 2026 | Coding (Claude Code, Devin, Copilot), DevOps (AWS Agent), Marketing (RevBridge + Thompson Sampling). 79% corporate adoption (Gartner) |
| 3 | Agentes vs Skills | Skill = what you KNOW (Excel). Agent = WHO does the work (Analyst). "Skills amplify capabilities. Agents replace the need for a human." |
| 4 | A Analogia Perfeita | Agents = Departments, Skills = Software (CRM, ERP), Agent decides WHEN to use which skill |
| 5 | O Loop do Agente | Perceive → Reason → Act → Observe → repeat. Human supervision optional at critical points |

### AgentOps Platform

| # | Title | Key Content |
|---|-------|-------------|
| 6 | AgentOps — A Solução | Orchestrates autonomous agents. Born from RevBridge's need. Flow: Issue → Code → PR → QA |
| 7 | O Desafio | Volume of issues (hundreds/sprint across 29 repos), manual code review, outdated documentation |
| 8 | Os 7 Agentes do AgentOps | Refinement, Backend, Frontend, Mobile, QA, Docs, Security |
| 9 | O que é o Claude Agent SDK? | SDK da Anthropic, structured output, native metrics, real-time streaming |
| 10 | Diferenciais do AgentOps | 7 specialized agents, E2E automatic, cross-repo coordinated, real-time streaming |
| 11 | Hierarquia de Execução | Coordinator → Dev → QA → Docs. Smart retry + real-time SSE dashboard |
| 12 | Fluxo — Da Issue ao Código | Issue created → Orchestrator → Refinement → Development. Linear webhook + intelligent routing |
| 13 | Fluxo — Do PR ao Merge | PR Opened → QA Reviews → Auto-Merge → Slack Notification. Zero human intervention |
| 14 | Arquitetura do AgentOps | Backend: FastAPI+MySQL+Redis. Frontend: React+Vite+shadcn. Motor: Claude SDK. Integrations: Linear, GitHub, GitLab, Slack |
| 15 | Cross-Repo — Mudanças Coordenadas | Problem: API change impacts backend+workflow+frontend. Solution: Coordinator creates execution per repo, synchronized PRs, coordinated rollback |
| 16 | Caso Real — RevBridge | 1 issue → Coordinator identifies 3 repos (mab-core, mab-workflow, frontend) → 3 coordinated executions → 3 synchronized PRs |
| 17 | Multi-Tenant | Complete isolation, OAuth auto-refresh (GitLab 2h expiry), intelligent webhooks auto-route by org |

### Evolution & Lessons

| # | Title | Key Content |
|---|-------|-------------|
| 18 | Do CLI ao SDK — Evolução | Phase 1: CLI+regex. Phase 2: Strangler Fig migration. Phase 3: Full SDK. Phase 4: Feature flags. "Subprocess with regex worked for months" |
| 19 | Lições Aprendidas | Start simple, feature flags for safe migration, specialization > generalization |

### Context & Impact

| # | Title | Key Content |
|---|-------|-------------|
| 20 | RevBridge — O Contexto | Marketing automation + IA, Thompson Sampling, 29 microservices, 160K+ lines |
| 21 | Impacto na RevBridge | 29 microservices (full cycle automated), 160K+ lines (auto-documented), 100% strategic focus |
| 22 | Próximos Passos | Planning Agent, ROI Dashboard, Skills Marketplace |
| 23 | Perguntas? | "Agents are present, not future. The question is WHEN and HOW your team will adopt them." |

### Live Demos

| # | Title | Key Content |
|---|-------|-------------|
| 24 | AgentOps Dashboard (demo) | 17 executions, 76.47% success, 2 PRs, $2.10 cost |
| 25 | AgentOps Dashboard (prod RevBridge) | 174 executions, 58.05% success, 33 PRs, $57.29 cost |
| 26 | Execution #197 detail | IAH-29 "personalized-devotionals", PR #9, QA agent, 64 events, 2m48s |
| 27 | Executions list | IAH-29 spawned: Backend, Mobile, Docs, QA (multiple), Refinement — all completed |
| 28 | Linear board (Task Manager) | LUI-19 Backlog, 14 Todo items, issues for CI/CD, CLAUDE.md, tests, pre-commit |
| 29 | Datadog Logs Control Center | 6M logs (5min window), 14 real errors, 265 active services, 0.00023% error rate |
| 30 | Claude Code v2.1.71 | Running on revbridge-devbox-vm, Opus 4.6 / Claude Max, ~/workspaces/full, ~10 tmux sessions |
| 31 | RBD Interactive Shell | Custom CLI: repos (infra, frontend, apis, library, auth, mab), scale, promote, diff, kubectl |

### External References

| # | Title | Key Content |
|---|-------|-------------|
| 32 | Google Cloud AI Agent Trends 2026 | Cover page — "AI agents are redefining business value in 2026" |
| 33 | Report intro | 3,466 enterprise decision makers surveyed, Google Cloud + DeepMind data |
| 34 | Report page 13 | Detailed section (content not fully visible) |

### Call Participants (visible)

- Victor Scarpa
- **Luiz M. Couto** (presenter)
- Juliano Dutra (co-founder HeavyBridge)
- Gustavo Toledo
- Kelvin Cleto
- Rafael Nascimento (co-founder HeavyBridge)
- Paulo Vitor S.
- Guilherme C.
- **Eduardo da S.** (user)
- +32/36 others

## Key Data Points Extracted from Slides

### Metrics
- **79%** corporate adoption of AI agents (Gartner 2026)
- **$0.15/exec** (demo) to **$0.96/exec** (production)
- **$1.73** average cost per PR
- **2m 48s** QA review duration
- **6M logs** in 5-minute window
- **265** active services monitored
- **0.00023%** error rate

### Architecture Confirmed
- FastAPI + MySQL + Redis (backend)
- React + Vite + shadcn/ui (frontend)
- Claude Agent SDK (AI engine)
- Linear + GitHub/GitLab + Slack (integrations)
- Kafka + Redis (message bus)
- Kubernetes + ArgoCD (infrastructure)
- Datadog (observability)
- ClickHouse (analytics)
