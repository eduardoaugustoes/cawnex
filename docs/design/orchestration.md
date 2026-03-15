# Orchestration Engine — Design Index

> From idea to software, guided by human direction.
> A murder of crows, guided by a monarch, advised by a council,
> building what humans envision.

---

## Design Documents

Read in this order for full context:

### 1. Foundation

| Doc | What It Covers |
|-----|----------------|
| [orchestration-problems.md](orchestration-problems.md) | **22 core problems** the engine must solve. Every component traces back here. |
| [layered-snapshots.md](layered-snapshots.md) | **Core data structure** — recursive snapshots that serve operational, memory, and training data purposes simultaneously. The 3D matrix (features x concerns x time). |
| [agent-memory.md](agent-memory.md) | **How agents learn** — layered CLAUDE.md pattern (not RAG). Three memory layers: dynasty, project, specialization. |

### 2. Data Model

| Doc | What It Covers |
|-----|----------------|
| [data-model-v2.md](data-model-v2.md) | **DynamoDB schema** — partition patterns, SK patterns, GSIs, snapshot primitive, materialized views, size estimates. |
| [screen-queries-all.md](screen-queries-all.md) | **Access patterns per screen** — every iOS screen mapped to exact PK/SK queries. |
| [decisions-log.md](decisions-log.md) | **Architecture Decision Records** — DynamoDB over MongoDB, CLAUDE.md over RAG, dual hierarchy, materialized views, config vs snapshot. |

### 3. Protocols

| Doc | What It Covers |
|-----|----------------|
| [council-protocol.md](council-protocol.md) | **Advisory decision-making** — 6 advisors, parallel voting, max 3 debate rounds, Security+Clarity veto, dissent recording, human override. |
| [wave-lifecycle.md](wave-lifecycle.md) | **State machine** — 11 wave states, 9 MVI states, pause/steer/budget enforcement, ordering constraints, wave-to-wave continuity. |
| [context-assembly.md](context-assembly.md) | **Prompt engineering** — 5-layer prompt, scoped context per crow type, artifact chain, prompt caching, large repo strategy. |

### 4. Per-Screen Deep Dives

| Doc | Screens |
|-----|---------|
| [screen-queries-s01-s02.md](screen-queries-s01-s02.md) | Splash, Sign In |
| [screen-queries-s11.md](screen-queries-s11.md) | Create Project |
| [screen-queries-s24-s30-s31.md](screen-queries-s24-s30-s31.md) | Backlog, Milestone, Goal |
| [screen-queries-s32.md](screen-queries-s32.md) | MVI Blackboard (most critical) |
| [screen-queries-s33-s34.md](screen-queries-s33-s34.md) | Task Detail, PR Review |
| [screen-queries-s40-s41-s42.md](screen-queries-s40-s41-s42.md) | Murders, Crows |
| [screen-queries-s70.md](screen-queries-s70.md) | Notifications |

### 5. Legacy (superseded)

| Doc | Status |
|-----|--------|
| [orchestration.md](orchestration.md) | V1 orchestration spec. Superseded by this design system. Retained for reference. |
| [agents.md](agents.md) | V1 agent specs. Crow types and behavior states still relevant. |
| [architecture.md](architecture.md) | V1 design architecture. DynamoDB blackboard pattern still foundational. |

---

## The Hierarchy

```
Human (founder)
  sets directive, approves, steers, rejects
       |
Dynasty (org/tenant)
  org-wide standards, policies, memory
       |
Monarch (per project)
  strategic decisions, convenes council, plans waves
       |
Council (6 advisors)
  Security, Quality, Performance, Market, Maturity, Clarity
  parallel voting, max 3 debate rounds, 2 veto powers
       |
Murder (execution orchestrator)
  dispatches crows, judges output, manages retries
  stream-triggered state machine (POC5 pattern)
       |
Crows (specialist workers)
  Planner, Implementer, Reviewer, Fixer, Documenter
  each in isolated git worktree (POC6 pattern)
```

---

## The Loop

```
Human sets directive
  -> Monarch + Council plan wave
    -> Human approves
      -> Murder dispatches crows
        -> Guards enforce limits
          -> Work gets done, PR created
            -> Human reviews
              -> Ship -> next wave -> loop
```

Each cycle produces:
- **Code** — merged to main
- **Learnings** — added to agent memory
- **Training data** — ask + reasoning + code + outcome
- **Cost tracking** — bubbled up through snapshot tree

---

## Key Principles

1. **The data structure IS the algorithm** — recursive snapshots make traceability, rewind, and budget tracking automatic
2. **Scoped context, not full repo** — each crow gets only what it needs
3. **Human controls, AI advises** — approval gates at every level, steer/pause/reject anytime
4. **Disagreement is a feature** — council dissent is preserved, not suppressed
5. **Resource discipline** — budgets, limits, max rounds at every layer
6. **Agents get smarter** — memory accumulates, advisors evolve, training data compounds
7. **Config vs snapshot** — mutable templates frozen at execution start
8. **Write-time aggregation** — materialized views via Streams, not query-time fan-out

---

## Guard System

### Detection Strategies

| Guard | What It Catches | Action |
|-------|----------------|--------|
| Token budget | Agent consuming too many tokens | Warn at 80%, cancel at 100% |
| Time limit | Agent taking too long | Hard cancel (planner: 5m, dev: 15m, QA: 5m, docs: 3m) |
| Scope boundary | Agent modifying files outside its area | Warn or cancel |
| Output coherence | Solving problems not in the issue | Cancel |
| Loop detection | >3 similar outputs in sequence | Cancel |

### Retry Engine

| Failure Type | Retryable? | Strategy |
|-------------|------------|----------|
| LLM timeout | Yes | Retry with same context |
| LLM rate limit | Yes | Exponential backoff |
| Git conflict | Yes | Pull latest, rebase, retry |
| Test failure | Yes | Send error to agent, ask for fix |
| QA rejection | Yes | Send feedback to fixer crow |
| Hallucination detected | No | Cancel, notify human |
| Token budget exceeded | No | Cancel, notify human |
| Repeated failure (>3x) | No | Cancel, escalate to human |

### Max Retries by Crow Type

| Crow | Max Retries | Backoff |
|------|-------------|---------|
| Planner | 2 | None |
| Implementer | 3 | Linear (1m, 2m, 3m) |
| Reviewer | 2 | None |
| Fixer | 3 | Linear |
| Documenter | 1 | None |

---

## Cost Model

| Component | Cost | Notes |
|-----------|------|-------|
| Council session (consensus) | ~$0.09 | 6 Sonnet calls |
| Council session (3 rounds) | ~$0.27 | Worst case |
| Full crow pipeline | ~$0.56 (Sonnet) / ~$2.78 (Opus) | Planner + Implementer + Reviewer + Documenter |
| With prompt caching | ~40-60% of above | Layers 1-3 cached at 90% discount |
| Infrastructure (MVP) | ~$10-25/month | DynamoDB on-demand + Lambda |

---

## DynamoDB Schema (Summary)

```
6 partition patterns:
  T#{tenant}#P#{project}       snapshots, events, docs, memory
  T#{tenant}#PROJECTS          project list
  T#{tenant}#DYNASTY           org config (murders, skills)
  T#{tenant}#NOTIFICATIONS     cross-project inbox
  T#{tenant}#BILLING           credits, rollups
  MARKETPLACE                  global templates

1-2 GSIs:
  DISPATCH#{status}            worker pickup
  T#{tenant}#W#{wave}          wave-to-MVI lookup (optional)

5 materialized views (Streams-powered):
  SUMMARY                      project summary for Dashboard
  HUB                          project hub for S12
  Milestone/Goal counters      planning hierarchy
  ROLLUP#CURRENT               billing aggregates
  unread_notification_count    badge count
```

Full schema: [data-model-v2.md](data-model-v2.md)
