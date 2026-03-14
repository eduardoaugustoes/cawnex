# 📝 Transcript Analysis — Luiz M. Couto (HeavyBridge/AgentOps)

> Source: Founder-to-Founder mentorship session, ~1h51m
> Date: March 9, 2026
> Participants: ~42 people (Victor Scarpa, Luiz M. Couto, Juliano Dutra, Gustavo Toledo, Kelvin Cleto, Eduardo, Rafael Nascimento, Paulo Vitor, Guilherme, +32 others)

---

## 🧑‍💼 About Luiz M. Couto

- **26 years in tech**: Microsiga → TOTVS → Track Center → Amazon AWS → Hard Rock startup → CTO Banco Digio/Bradesco
- Professor at USP, PhD in computational dynamics
- All 14 AWS certifications
- Co-founded **HeavyBridge** with Juliano and Rafa (~mid 2025)
- Self-described "Anthropic fanboy" — focused on security

## 🏢 HeavyBridge / RevBridge

- **Product**: Marketing automation platform with AI at the core
- **Algorithm**: Thompson Sampling (Bayesian multi-armed bandit) for campaign optimization
- **Scale**: 29 microservices, 160K+ lines of code in production
- **Team**: 4 people total (2 senior devs)
- **Equivalent team**: Would need 20-30 engineers for 1 year to build the same manually
- **Infrastructure**: Kubernetes, ArgoCD (GitOps), Datadog (800B+ logs)

## 🤖 AgentOps — The System

### Origin

Born from RevBridge's real need: scale development without scaling the team proportionally. Started as CLI experiments, evolved into a full orchestration platform.

### The 7 Agents

1. **Refinement** — Analyzes and refines requirements before any code is written
2. **Backend** — Server code, APIs, business logic (FastAPI/Python)
3. **Frontend** — Interfaces, components, UX (React/Vite/shadcn)
4. **Mobile** — iOS/Android features
5. **QA** — Validates acceptance criteria, approves/rejects PRs
6. **Docs** — Auto-updates documentation after every code change
7. **Security** — SAST/DAST vulnerability scanning, best practices

### Orchestrator ("The Murder")

- Receives events via **Kafka**
- Uses **NLM-DFA** (LLM + Deterministic Finite Automaton) to understand logical flow across repositories
- Based on a pen-testing research paper (Shannon-based implementation)
- Routes issues to correct agent(s) — Backend, Frontend, or Mobile
- Monitors agent streaming output for **hallucination detection**
- Cancels execution if agent drifts off-track
- Coordinates **synchronized PRs** across multiple repos

### Communication

- Agents communicate via **Kafka + Redis**
- Real-time streaming via **SSE (Server-Sent Events)** to dashboard
- Agent-to-agent messages ("caws") share context and coordinate

### Git Workflow

- Each agent creates a **worktree** (not a feature branch)
- Worktrees provide full isolation — agents don't interfere with each other
- PRs are synchronized across repos — all merge together or none do
- Coordinated rollback on failure
- GitOps: everything goes through git, IAC applied via ArgoCD

### Smart Retry

- Not blind retry — understands the execution tree
- Verifies if there was an interaction between messages
- Uses context and docs to determine if retry makes sense
- Each agent has its own retry policy
- A frontend error doesn't block the backend

## 📊 Real Production Numbers

### Demo environment (Task Manager project)

- 17 executions (7 days)
- 76.47% success rate
- 2 PRs created
- $2.10 total cost (~$0.15/exec)

### Production (RevBridge)

- 174 executions (7 days)
- 58.05% success rate
- 33 PRs created
- $57.29 total cost (~$0.96/exec)
- 1 currently running
- 57 failed (learning/iterating)

### QA Performance

- Execution #197: 2m 48s for full QA review
- Tasks: get diff, review against acceptance criteria, TypeScript check, fix issues, deliver result
- Compare: 30+ minutes for a human reviewer

## 🔧 Tech Stack (Confirmed)

| Component     | Technology                                                   |
| ------------- | ------------------------------------------------------------ |
| AI Engine     | Claude Agent SDK (Anthropic) — Opus 4.6 complex, Haiku light |
| Backend       | FastAPI + Python                                             |
| Database      | MySQL (primary), PostgreSQL (some services)                  |
| Cache         | Redis                                                        |
| Message Bus   | Kafka (real-time events), Redis (queues)                     |
| Analytics DB  | ClickHouse                                                   |
| Frontend      | React + Vite + shadcn/ui                                     |
| Infra         | Kubernetes + ArgoCD + IAC                                    |
| Observability | Datadog                                                      |
| Issue Tracker | Linear                                                       |
| Git           | GitLab (primary), GitHub (some projects)                     |
| Notifications | Slack                                                        |
| Custom CLI    | `rbd` — scale, promote, diff, commit, kubectl wrapper        |
| Auth          | OAuth with auto-refresh (GitLab tokens expire every 2h)      |

## 🧠 Key Technical Insights

### NLM-DFA (Critical Architecture Piece)

- Uses LLM with natural language to understand the "logical flow" inside an application
- Based on a pen-testing paper that used LLM-DFA for repository analysis
- The orchestrator uses this to understand how changes in one repo affect others
- Without this, coordinating 29 repos would be impossible
- Luiz: "The NLM-DFA is what allowed me to use the LLM to understand the logical flow inside the application"

### The "Debozo" Technique

- Repeat the prompt 2x in the same context
- Claims 70-80% more consistency in responses
- Used in critical prompts where accuracy matters

### Hallucination Prevention

- Orchestrator monitors streaming output in real-time
- Detects when agent starts creating things that "don't make sense"
- Auto-cancels execution when hallucination detected
- Luiz experienced this: "The AI started creating things that made no sense, started solving problems that didn't exist"

### Worktrees vs Feature Branches

- Almost migrated to monorepo (came very close one night)
- Decided worktrees give the same isolation benefit
- Each agent gets an "org tree" — a copy of the repo
- Agents work in parallel without interference
- Result would be identical to monorepo approach

### CLI → SDK Evolution (Strangler Fig Pattern)

1. **Phase 1**: Claude CLI as subprocess, parsing output with regex
2. **Phase 2**: Gradual migration — new executions use SDK, old ones stay on CLI
3. **Phase 3**: Full SDK with structured output, native metrics, sub-agent support
4. **Phase 4**: Feature flags per organization with instant rollback

- Key lesson: "The subprocess with regex worked in production for months"

### Subscription vs API Tokens

- Uses Anthropic Max subscription (~R$2000/month)
- Much cheaper than per-token API billing at their volume
- Allows running multiple Claude sessions simultaneously

### Junior + AI = Danger

- Junior devs feel empowered but create solutions that break in production
- "They can make MVPs but when it goes to production — security issues, DB problems, latency, queues breaking"
- Need senior experience to guide the AI effectively
- Luiz's analogy: "AI is a super nerdy junior — knows all patterns but you need to give it direction"

### Rollback Stories

- Had to do full rollback ~5 times
- Worst case: scaled up, lost DB connection overnight, massive error logs
- Strategy: `git reset` to last working version, investigate later
- CLI can do automated rollback
- "I never do full rollback, I do a git overwrite to the previous version"

## 💬 Notable Quotes

> "Se eu não tivesse toda a experiência com o Uber, eu também não conseguiria" (Without all my Uber experience, I couldn't have done this either)

> "A IA é um Júnior super nerd — sabe todos os padrões do projeto, mas você tem que saber dar o rumo pra ela" (AI is a super nerdy junior — knows all patterns but you need to give it direction)

> "Comece simples. O subprocess com regex funcionou por meses" (Start simple. The subprocess with regex worked for months)

> "Especialização supera generalização. 7 agentes especializados entregam resultados muito superiores a 1 agente genérico" (Specialization beats generalization)

> "Os agentes começaram a se falar... aí você fala, cara, aí acabou, perdeu o controle" (The agents started talking to each other... and you think, man, you've lost control)

> "Eu nunca conheci alguém que tá trabalhando com um nível similar ao meu" (I've never met anyone working at a similar level to mine)

## 🔗 Tools & References Mentioned

- **Claude Agent SDK** — Anthropic's official framework
- **Claude Code v2.1.71** — CLI tool, Opus 4.6 / Claude Max
- **Claude Remote Execution** — Access Claude Code via web from anywhere
- **Linear** — Issue tracking / sprint management
- **Datadog** — Full observability platform
- **Pencil.dev** — MCP for UI prototyping, connects to Claude for visual validation
- **OpenClaw** — Mentioned by a participant (Eduardo?) as similar concept
- **NLM-DFA paper** — Pen-testing research that inspired orchestrator architecture
- **Eleven Labs** — TTS for Telegram bot (voice interaction while driving)

## 🎯 Their Roadmap (Next Steps)

1. **Planning Agent** — Break epics into smaller issues with estimates and dependencies
2. **ROI Dashboard** — Time saved, cost per execution, code quality metrics
3. **Skills Marketplace** — Shareable skills between organizations
4. **Browser Testing Agent** — Chrome instance for frontend E2E testing (already experimenting)

## ⚠️ Known Limitations (from their experience)

- Success rate ~58% in production (still improving)
- 57 failed executions in 7 days (learning/iterating)
- Agents can enter infinite conversation loops (burn tokens without progress)
- Context compaction causes hallucination (why Anthropic extended to 1M tokens)
- Cannot fully replace human review for complex architectural decisions
- Junior developers cannot effectively manage the system
- Kafka was partially replaced — some things moved to Redis
- Multi-repo coordination is the hardest problem they solved
