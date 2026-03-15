# Architecture Decisions Log

> Key decisions made during orchestration engine design, with reasoning and alternatives considered.

---

## ADR-001: DynamoDB Single Table (not MongoDB, not PostgreSQL)

**Date:** 2026-03-14
**Status:** Accepted

**Decision:** Use DynamoDB single-table design with recursive snapshots.

**Why:**

- Zero idle cost (pre-revenue product)
- POC5+6 already proved the pattern works
- DynamoDB Streams is the backbone (Murder triggers, materialized views, SSE, notifications)
- Multi-tenant isolation via partition keys is a security guarantee, not application-level enforcement
- Recursive snapshots map to SK paths, every screen renders in 1-4 queries

**Alternatives considered:**

| Option        | Pros                                                                           | Cons                                                           | Verdict                                |
| ------------- | ------------------------------------------------------------------------------ | -------------------------------------------------------------- | -------------------------------------- |
| MongoDB       | Document model maps naturally to snapshots, rich queries, aggregation pipeline | Operational overhead, cost, no native Lambda integration       | Good but not justified at MVP          |
| PostgreSQL    | Full SQL, JSONB columns, strong consistency                                    | Schema migrations, vertical scaling limits, Aurora min ~$50/mo | Overkill for key-value access patterns |
| GraphQL + DDB | Schema-as-contract, subscriptions, nested queries                              | Extra layer, N+1 risk, one client doesn't justify              | Deferred to future                     |

**Future trigger:** Re-evaluate when web/Android clients need a shared API layer (GraphQL).

---

## ADR-002: Layered Markdown Memory (not RAG)

**Date:** 2026-03-14
**Status:** Accepted

**Decision:** Agent memory uses layered markdown files (CLAUDE.md pattern) with token budgets, not RAG.

**Why:**

- Memory is small (dozens of learnings, not millions of documents)
- Context window is large enough to hold all relevant memory
- RAG adds vector DB, embedding pipeline, retrieval tuning — unnecessary infrastructure
- Prompt caching makes memory essentially free (90% discount on stable layers)
- If memory grows too large, summarization beats search

**Future trigger:** If a single memory file consistently exceeds 4000 tokens after pruning, consider splitting into retrieval-based lookup.

---

## ADR-003: Dual Hierarchy (Planning + Execution)

**Date:** 2026-03-14
**Status:** Accepted

**Decision:** Planning hierarchy (Milestone → Goal → MVI) and execution hierarchy (Wave → Council → Murder → Crow) are stored as separate SK prefixes. MVI bridges them.

**Why:**

- Planning and execution are orthogonal — a wave can pull MVIs from different goals/milestones
- A milestone can span multiple waves
- The MVI is the join point (belongs to one Goal, executes in one Wave)
- Separate prefixes allow planning screens to query directly without traversing execution tree

**Schema:**

```
Planning:  S#PLAN#MS#{ms}#GL#{gl}#MVI#{mvi}
Execution: S#{wave}#{council}#{murder}#{crow}
```

---

## ADR-004: Materialized Views via Streams (not query-time aggregation)

**Date:** 2026-03-14
**Status:** Accepted

**Decision:** Dashboard, Project Hub, milestone counters, billing rollups, and notification badge count are materialized as denormalized records updated by DynamoDB Streams Lambdas.

**Why:**

- Dashboard (S10) and Project Hub (S12) are high-frequency read paths
- Query-time aggregation across hundreds of snapshots is untenable
- Stream Lambdas are simple increment/decrement logic
- Materialized records make screens load in 1-2 queries regardless of data volume

**5 materialized views:**

1. `SUMMARY` per project (S10 Dashboard)
2. `HUB` per project (S12 Project Hub)
3. Counters on milestone/goal items (S24/S30/S31)
4. `ROLLUP#CURRENT` in billing partition (S61)
5. `unread_notification_count` on dynasty META (S70 badge)

---

## ADR-005: Config vs Snapshot Separation

**Date:** 2026-03-14
**Status:** Accepted

**Decision:** Murder and Skill configs are mutable templates in the DYNASTY partition. When execution starts, config is frozen into the execution snapshot.

**Why:**

- Editing a murder config mid-execution would cause inconsistency
- Frozen snapshot makes executions reproducible
- Config changes affect future executions only
- Audit trail: can always see which config version produced which results

---

## ADR-006: Council with Two Veto Powers

**Date:** 2026-03-14
**Status:** Accepted

**Decision:** 6 advisors, parallel voting, max 3 debate rounds. Only Security and Clarity have BLOCK (veto) power.

**Why:**

- Security can't be overridden by popularity — vulnerable code must not ship
- Clarity prevents building against ambiguous specs (causes rework)
- Other concerns (quality, performance, market, maturity) influence through scoring but shouldn't block execution
- Max 3 rounds prevents endless debate (~$0.27 worst case)
- Human can override any block with recorded reasoning
