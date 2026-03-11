# ❓ Gaps & Open Questions

> Things we don't know yet, need to research, or need to decide differently for Cawnex.

---

## 🔴 Critical Unknowns (Must Resolve Before Building)

### 1. NLM-DFA Implementation
**What we know**: Uses LLM + Deterministic Finite Automaton to understand cross-repo flow.
**What we don't know**:
- The specific research paper Luiz referenced (pen-testing + Shannon-based)
- How the state machine is defined (manually? auto-generated from code?)
- What states/transitions exist
- How it maps an issue to affected repositories
- Is this a custom model or a prompt engineering pattern?

**Action**: Research NLM-DFA papers. Check arxiv for LLM + DFA + pen-testing papers. May be related to "LLM-guided program analysis" or "LLM-augmented formal methods."

### 2. Agent-to-Agent Communication Protocol
**What we know**: Agents "talk to each other" via Kafka/Redis. One agent asks its peer if it needs anything.
**What we don't know**:
- Message schema/format
- How agents discover each other
- What triggers peer communication
- How conflicts are resolved (two agents modify same file)
- Is it request/response or pub/sub?

**Action**: Design our own protocol. Start simple (orchestrator-mediated), add peer-to-peer later.

### 3. Hallucination Detection Algorithm
**What we know**: Orchestrator monitors streaming and cancels when agent hallucinates.
**What we don't know**:
- How is "hallucination" defined programmatically?
- Is it rule-based (detecting nonsensical outputs) or LLM-based (a judge model)?
- What thresholds trigger cancellation?
- How does it distinguish between creative solutions and hallucination?

**Action**: Research hallucination detection in agentic systems. Consider using a lightweight "judge" model.

### 4. Execution State Machine
**What we know**: Executions go through states (visible in dashboard: Running, Completed, Failed, Blocked).
**What we don't know**:
- Complete state diagram
- Transition triggers
- What "Blocked" means exactly (awaiting human response?)
- How timeout is handled

**Action**: Define our own state machine based on observed states + logical inference.

---

## 🟡 Important Unknowns (Can Be Designed Independently)

### 5. Kafka Topic Structure
**What we know**: Events flow through Kafka between orchestrator and agents.
**What we don't know**:
- Topic naming convention
- Partition strategy (per agent? per repo? per org?)
- Consumer group configuration
- Retention policy

**Action**: Design based on best practices. Topic per event type is standard.

### 6. OAuth Token Refresh Mechanism
**What we know**: GitLab tokens expire every 2h, auto-refreshed without user interruption.
**What we don't know**:
- Where tokens are stored (Redis? Vault? DB?)
- Refresh flow (background job? on-demand?)
- How multi-tenant token isolation works

**Action**: Standard OAuth2 refresh token flow. Store in Redis with TTL.

### 7. Worktree Management
**What we know**: Each agent creates a git worktree for isolation.
**What we don't know**:
- Naming convention
- Cleanup strategy (when are worktrees deleted?)
- How many can run simultaneously
- Disk space management

**Action**: Design cleanup policy. Worktrees are cheap but accumulate.

### 8. Cost Tracking Implementation
**What we know**: Dashboard shows cost per execution, per agent, per time period.
**What we don't know**:
- How Claude SDK costs are calculated (tokens? time? subscription amortization?)
- How infrastructure costs are attributed per execution
- Storage format

**Action**: Claude SDK provides token counts. Calculate cost = tokens × price_per_token.

---

## 🟢 Nice to Know (For Later)

### 9. Custom CLI (`rbd`) Implementation
**What we know**: Interactive shell with git ops, kubectl, scale, promote.
**What we don't know**:
- Language (Python? Go? Bash?)
- How `scale` interacts with Kubernetes
- Watcher implementation

**Action**: Low priority for MVP. Build CLI later.

### 10. Datadog Integration Details
**What we know**: Logs, KPIs, error tracking, custom dashboard.
**What we don't know**:
- Which APM libraries
- Custom metrics definitions
- Alert configuration

**Action**: Start with simpler observability (structured logs + Grafana), upgrade to Datadog later.

### 11. "Debozo" Technique
**What we know**: Repeat prompt 2x in same context → 70-80% more consistency.
**What we don't know**:
- Exact implementation (duplicate system prompt? repeat user message?)
- In which scenarios it's used
- Any research backing this up

**Action**: Test independently. May be related to self-consistency prompting research.

### 12. Browser Testing Agent
**What we know**: Luiz is experimenting with Chrome instance for frontend E2E testing. Uses Claude to generate test scripts → executes → screenshots → validates.
**What we don't know**:
- Integration with existing QA agent
- Browser automation framework (Playwright? Puppeteer?)
- How visual regression is detected

**Action**: Add to roadmap V2. Not MVP.

---

## 🤔 Strategic Questions for Cawnex

### Differentiation
1. AgentOps is internal to HeavyBridge — should Cawnex be a **SaaS product** from day one?
2. Luiz mentioned wanting to create a "Skills Marketplace" — should Cawnex beat him to it?
3. Their success rate is 58% — can we get to 80%+ with better guardrails?
4. They use Linear — should Cawnex be **issue-tracker agnostic** (Linear, Jira, GitHub Issues)?
5. Their custom CLI is powerful — should Cawnex's CLI be a first-class citizen or web-first?

### Build vs. Buy vs. Fork
1. **Orchestrator**: Must build (core IP)
2. **Agent runtime**: Use Claude Agent SDK? Or abstract to support multiple LLMs?
3. **Dashboard**: Build (core UX differentiator)
4. **Git integration**: Build on top of `simple-git` / `isomorphic-git`?
5. **Message bus**: Kafka? Or start with Redis Streams (simpler)?
6. **Observability**: Build basic → integrate with existing tools later?

### Pricing Model
1. Luiz uses subscription — should Cawnex charge per execution? Per PR? Per agent?
2. How to handle LLM costs (pass-through? flat fee? tiered?)
3. Free tier to drive adoption?

### Open Source Strategy
1. Fully open source (like OpenClaw)?
2. Open core (free agents, paid orchestrator)?
3. Closed source SaaS?
4. Open source now, monetize later?
