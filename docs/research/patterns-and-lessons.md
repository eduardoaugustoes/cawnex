# 🧩 Patterns & Lessons Learned

> Extracted from Luiz's 26 years of experience + AgentOps production usage

---

## ✅ Patterns That Worked

### 1. Strangler Fig Migration
**Problem**: Moving from CLI to SDK all at once would break production.
**Solution**: New executions use SDK, old ones continue on CLI. Gradual migration.
**Lesson**: Never do big bang migrations. Feature flags per organization with instant rollback.

### 2. Specialization Over Generalization
**Problem**: One generic agent trying to do everything hallucinated and produced poor results.
**Solution**: 7 specialized agents, each with a single mission.
**Lesson**: "7 specialized agents deliver far superior results to 1 generic agent. Specialization allows more precise prompts and more predictable behaviors."

### 3. Start Simple
**Problem**: Temptation to build the perfect system from day one.
**Solution**: Started with subprocess calling Claude CLI, parsing output with regex.
**Lesson**: "The subprocess with regex worked in production for months before the SDK migration." Ship the simplest thing that works.

### 4. Worktrees for Agent Isolation
**Problem**: Multiple agents editing the same repo create conflicts.
**Solution**: Git worktrees — each agent gets a full isolated copy.
**Lesson**: Same result as monorepo, without the migration pain.

### 5. Synchronized PRs
**Problem**: Backend PR merges, breaks frontend contract.
**Solution**: Orchestrator holds all PRs until all are ready, then merges together.
**Lesson**: Cross-repo consistency requires atomic merges.

### 6. Human-in-the-Loop at ONE Point
**Problem**: Too many approval points slow everything down; zero approvals is risky.
**Solution**: Human approves only the refined user story. Everything after is autonomous.
**Lesson**: One well-placed checkpoint is better than many interruptions.

### 7. Smart Retry (Not Blind)
**Problem**: Blind retry wastes tokens and can compound errors.
**Solution**: Analyze execution tree, verify message interactions, retry only what makes sense.
**Lesson**: Each agent needs its own retry policy. Frontend failure shouldn't block backend.

### 8. Error → Claude → Fix → Deploy
**Problem**: Traditional debugging cycle is slow.
**Solution**: Copy error from Datadog → send to Claude → get fix → deploy.
**Lesson**: "Fix forward" is faster than rollback for most errors. Only do full rollback when truly broken.

### 9. Bot on Telegram for Mobile Approval
**Problem**: Need to approve PRs while driving/away from computer.
**Solution**: Telegram bot with Eleven Labs voice. Speak to approve/reject.
**Lesson**: Meet developers where they are. Not everything needs a web UI.

### 10. Agent.md Per Repository
**Problem**: LLM hallucinates without repo-specific context.
**Solution**: Each repo has a CLAUDE.md/Agent.md that describes its structure, patterns, and rules.
**Lesson**: "Without Agent.md in every repo, the agent starts hallucinating. You need to direct it."

---

## ❌ Anti-Patterns / Mistakes

### 1. Letting Agents Free-Form
**Problem**: Without architectural constraints, agents create code in multiple languages, inconsistent patterns.
**Result**: "If you leave them free, they'll code in whatever language they think is best for each problem."
**Fix**: Define stack constraints in Agent.md. Same DB, same patterns, same language per repo.

### 2. Trusting Junior + AI
**Problem**: Junior developers feel empowered by AI but lack production experience.
**Result**: "They can make MVPs but in production — security holes, DB issues, latency, queue breaks."
**Fix**: Senior oversight is still required. AI is "a super nerdy junior" — knows patterns but needs direction.

### 3. Infinite Agent Loops
**Problem**: Agents communicating with each other can enter infinite loops.
**Result**: Token burn without progress. One company spent $150K in tokens.
**Fix**: Orchestrator monitors and cancels. Set hard limits on conversation rounds.

### 4. Context Window Overflow
**Problem**: Long conversations cause context compaction, which loses information.
**Result**: Hallucination increases after compaction.
**Fix**: Anthropic extended to 1M tokens. Keep conversations focused. Use sub-agents for isolation.

### 5. Scaling Without Coordination
**Problem**: Early attempts had agents submitting PRs independently.
**Result**: Uncoordinated, unorchestrated PRs that broke things.
**Fix**: Only merge when ALL PRs and ALL tests pass. Orchestrator enforces this.

### 6. Each Microservice Does Its Own Thing
**Problem**: "Netflix-style" freedom where each service uses its own DB, language, patterns.
**Result**: "Doesn't work unless you have a million employees." Loses contract consistency.
**Fix**: Standardize stack across services. Same DB, same patterns, shared contracts.

### 7. Full Rollback as Default
**Problem**: Instinct to rollback everything when something breaks.
**Result**: Lose all changes, even good ones. Slow recovery.
**Fix**: Fix forward. Git overwrite to previous version only as last resort (~5 times total).

### 8. Big Bang SDK Migration
**Problem**: Switching everything to SDK at once.
**Result**: Risk of complete system failure.
**Fix**: Strangler Fig pattern. Gradual migration. Feature flags per org.

---

## 🧠 Mental Models

### AI = Super Nerdy Junior
> "A IA é um Júnior super nerd — sabe todos os padrões do projeto, sabe tudo que sabe, mas você tem que saber dar o rumo pra ela."

The AI knows all patterns, all best practices, all syntax. But without senior direction:
- It creates unnecessary abstractions
- It solves problems that don't exist
- It hallucinates when it runs out of known patterns
- It doesn't understand production trade-offs (latency, cost, scale)

### Agents = Departments
Each agent is like a company department:
- Has its own mission
- Has its own expertise
- Collaborates but doesn't step into others' territory
- Reports to the orchestrator (CEO)

### Skills = Corporate Software
Skills are like CRM, ERP, Excel:
- Any department can use them
- But none of them acts alone
- The agent (department head) decides WHEN to use which skill

### Orchestrator = CEO
- Doesn't write code itself
- Understands the big picture
- Delegates to specialists
- Monitors progress
- Makes go/no-go decisions
- Coordinates cross-department (cross-repo) initiatives

---

## 📏 Decision Framework

### When to Build vs. When to Use Existing

| Situation | Decision | Why |
|-----------|----------|-----|
| CLI tool for DevOps | Build custom (rbd) | Team-specific workflows |
| Message bus | Use Kafka + Redis | Don't reinvent |
| Agent orchestration | Build custom | Nothing existed that solved cross-repo |
| Observability | Use Datadog | Best-in-class, not worth rebuilding |
| Issue tracking | Use Linear | Integration via webhooks is enough |
| LLM | Use Claude SDK | Best quality + subscription model |
| Frontend | Build with React/Vite | Need custom dashboard |
| Git workflow | Build on worktrees | Git native, just needed orchestration layer |

### When to Use Bayesian Models vs. LLM

| Task | Choice | Reason |
|------|--------|--------|
| Campaign optimization | Bayesian (Thompson Sampling) | Statistical, needs real data, LLM hallucinates |
| Code generation | LLM (Claude) | Pattern recognition, language understanding |
| Issue routing | LLM (Claude via NLM-DFA) | Needs to understand natural language + code |
| A/B testing allocation | Bayesian | Mathematical optimization |
| Documentation | LLM (Claude) | Natural language generation |
| Anomaly detection | Bayesian / Classical ML | Statistical patterns |

Luiz's insight: "The LLM will try to answer, but without context it just responds something. For statistical optimization, use Bayesian models."

---

## 💰 Cost Analysis

### Their Numbers
- Anthropic Max subscription: ~R$2,000/month (~$400)
- 174 executions/week at ~$0.96/exec = ~$167/week = ~$668/month
- Total estimated: ~$1,000-1,100/month for the full AI engine

### vs. Human Equivalent
- 20-30 engineers × ~$8,000/month (Brazil average senior) = $160,000-240,000/month
- Even at 10 engineers: $80,000/month
- **ROI: 80-240x cost reduction**

### Key Insight
- Use subscription (Claude Max) instead of per-token API for high-volume workloads
- Per-token would cost significantly more at their volume
- "If I were using API tokens, it would be much more than $57"
