# Cawnex through the Dark-Factory Lens

**Date:** 2026-05-16
**Source corpus:** Background Agents research at `~/background-agents/transcripts/` — Ona Background Agents Summit (Day 1 + Day 2, Feb 2026) + Software Factory live-build (Apr/May 2026) + Stripe Minions blog. Specifically [Shardul Vaidya's "Dark Factories" talk](https://github.com/eduardoaugustoes/background-agents) and the convergent architecture across **Coinbase, Ramp, Stripe, Anthropic, and StrongDM**.

This doc compares Cawnex against the convergent dark-factory pattern those five companies independently arrived at. The point: if convergent design is real, the pattern is probably right, and the gaps between Cawnex today and that pattern are the work that turns Cawnex from "supervised single-thread agent" into "factory."

---

## The thesis to compare against

From Shardul's talk:

> *"Zero humans write code, zero humans review code. Coinbase, Ramp, Stripe, Anthropic, and StrongDM all came to the same pattern."*

Five companies that don't talk to each other built the same architecture:

1. **Orchestrator** decomposes one requirement into a DAG of parallel tasks
2. **Per-agent isolation** — sandbox + worktree per agent
3. **Verification gates** — three tiers (traditional, AI-native, formal), running in parallel
4. **Rework loop** — full failure context fed forward, not retried
5. **Cost-routed dispatch** — cheap models for trivial, frontier for hard
6. **"Crashing is a feature"** — agents are cattle, orchestrator is durable

Plus the framing: **verification is back pressure** — tests aren't "did it work?", they're "force the agent is required to listen to." The threshold between L2 and L4 autonomy isn't a better model; it's a verification system the model has to obey.

---

## How Cawnex scores

| Element | Grade | Why |
|---|---|---|
| Orchestrator (durable, stateless agents) | **B-** | Murder + Council shape is right, but no DAG-level parallelism *within* an MVI |
| Per-agent isolation (sandbox + worktree) | **C** | Stateless Worker, but no sandbox-per-crow; single Fargate task runs crows serially |
| Multi-tier verification | **D+** | Reviewer crow runs; Council designed-not-running; no deterministic test gate on crow output |
| Adversarial verification | **B** | Reviewer crow is adversarial-by-design; Steer chat (spec'd, not built) doubles down |
| Rework loop (not retry) | **B+** | Fixer + `_find_fix_history` threading is the right shape |
| Cost-routed dispatch | **F** | Single hardcoded model (`claude-haiku-4-5-20251001`) across all crow types |
| Crashing-is-a-feature reliability | **C** | Right architecture, wrong cycle time (hourly Checker for stale-claim recovery) |

**Overall: between L2 and L4 — closer to L2.** The shape is dark-factory-shaped. The execution is small-and-supervised.

---

## What already looks like a dark factory

Five things in Cawnex today that match the convergent pattern, ordered strongest-match-first.

### 1. Murder reactor as the durable orchestrator (strong match)

The DDB-Streams-triggered Lambda that dispatches the next crow is structurally identical to Shardul's `EventBridge + Step Functions` block in his AWS mapping. State lives in DDB; the orchestrator reads-decides-writes; agents are stateless consumers. Same pattern, different AWS primitive (we use Streams; he uses EventBridge).

What this gets us: a crash in the Worker doesn't lose the wave. Murder reconstructs everything from DDB on the next dispatch.

### 2. Reviewer + Fixer as adversarial pair (strong match)

Shardul calls for *two* adversarial agents per task: a **plan adversary** (reviews the orchestrator's DAG before tasks dispatch) and a **code adversary** (reviews the coder's output). Cawnex has the code adversary — the Reviewer crow — with rework via Fixer + fix-history threading. The plan-adversary slot is empty; Council is designed for it but hasn't been exercised on a real wave yet.

> *"The system is designed so the coder agent expects rejection."* — Shardul

The Reviewer crow's `outcome.approved=False` triggers a Fixer assignment in `react_to_crow_completion`. Identical pattern.

### 3. Wave/MVI/Crow snapshot rows as DAG nodes (medium match)

The data model already encodes "the orchestrator owns durable state, the agents read it." A wave's snapshot subtree IS a DAG — just one with a fixed shape (planner → implementer → reviewer → fixer×N) instead of an arbitrary one.

The right abstraction is there; the parallelism isn't. Today an 8-task planner output gets handed to one implementer that ships them as a bundle. A real dark factory would dispatch those as 8 parallel sub-tasks with merge-conflict awareness up front.

### 4. Approval gates at four altitudes (medium match — unique to Cawnex)

Most dark factories collapse to one human gate (PR merge). Cawnex has four: Milestone, Goal, MVI, PR. That's actually *more* human-in-the-loop than the convergent five, by design — which is appropriate for "founders, not engineering orgs."

Tradeoff: Cawnex is **deliberately L3, not L4**. The convergent five trust their verification gates enough to let the bot merge to main. Cawnex trusts its verification gates enough to let the founder *one tap*, then merge.

### 5. The append-only event log + SSE fanout (strong match)

DDB Streams → EventBridge Pipe → SQS → Stream Service is essentially a small Kafka. Every state transition is an event. Every event has a consumer. This is the **observability spine** Shardul says the convergent five all built — `CloudWatch + CloudTrail` in his AWS mapping, our events-table + SSE in ours.

What this gets us: live wave-execution view in iOS, audit log for compliance, and the substrate for cross-task review (a Phase 3 idea Shardul lists as aspirational).

---

## What's missing — in priority order

What would push Cawnex from L2-shaped to L4-shaped, ordered by impact:

### 1. Deterministic verification gate **inside** the Worker

The single biggest gap.

> *"Traditional tier verification — unit tests, property tests, mutation tests, lint. LLMs are trained on these, they understand the signal."* — Shardul

Today: implementer ships → CI runs after merge → if it fails, the next session's pre-commit hook catches it (as happened with PR #16's lint issues, fixed in `c5c2915`).

Dark factory: implementer ships → **inside the Worker, before the reviewer**, run the project's linter/typechecker/test-suite. Failures go to the Reviewer's `blocking_issues` and trigger Fixer rework. Tests serve **two functions**: gate ("does the code pass?") and back pressure ("what does failure teach the next attempt?"). Both matter. The second is the underrated one.

For Cawnex specifically: this is `black --check` + `flake8` + `mypy` + `pytest` run inside the Worker container against the implementer's worktree, with structured failure output threaded into the Reviewer's instructions. Maybe 100 lines of code. Massive jump in autonomy.

### 2. Cost-routed model dispatch

Today every crow type hardcodes `claude-haiku-4-5-20251001`. That's $1/M input across the board.

Stripe (the convergent five's most-mature) routes per task:
- Trivial transforms (rename, type addition) → cheap model
- Complex synthesis (new feature, multi-file design) → frontier model
- Adversarial review → cheap model (the gate value is in independence, not depth)

For Cawnex: planner = Sonnet 4.6 (worth the cost on harder decompositions); implementer = Haiku for trivial / Sonnet for complex (decision based on planner's task count or context token count); reviewer = Haiku; fixer = Sonnet (always — they're handling Reviewer's pushback, hard problems by definition); Council votes = Haiku majority + Opus for tie-breaker.

Wiring is straightforward — `lambdas/worker/src/worker/config.py:MODEL_CONTEXT_WINDOWS` already knows about all three models. The selection logic doesn't exist yet.

### 3. Council actually voting on real PRs

The Council spec exists. Six advisors with Security + Clarity vetoes. None has run on a dogfood wave. Adding `react_to_mvi_ready_to_ship` → trigger Council → Council either approves auto-merge or escalates to founder would be the single biggest jump in *autonomy*. Today the founder is the only gate above the Reviewer.

This is L4 territory: "let the bot merge if Council unanimously approves and no advisor used a veto." The convergent five all do this. Cawnex is one Lambda invocation away from offering it as an opt-in.

### 4. Per-crow sandbox

> *"Each crow gets its own EFS subdirectory. Two crows on the same MVI can run in parallel without stepping on each other."*

Today: one Worker task, one `/mnt/repos/T/{tenant}` mount. Crows run serially in the same Python process. Two parallel crows would share state.

Dark factory: each crow execution gets a per-run worktree (via `git worktree add` or Jujutsu) at a unique path, gets cleaned up after the crow completes. This is also what unblocks (1) — a sandboxed worktree is where you run lint and tests safely.

### 5. Sub-minute claim recovery

Worker crash mid-crow → crow row stays `claimed=true` → Checker Lambda sweeps it on **hourly** cron. That's not "crashing is a feature" — that's "crashing is a 60-minute incident."

> *"Reliability through statelessness, not durability. Agents are cattle. The orchestrator is the pet."* — Shardul

Fix: claim TTL via DDB conditional puts. Worker writes `claim_expires_at = now + 5min` on claim; renews it every 60s while alive; if the Worker dies, the next polling Worker sees the expired claim and takes over. No Checker Lambda involvement. Sub-minute recovery.

---

## The element that's distinctively Cawnex

One thing Cawnex has that the convergent five **deliberately don't**: **four altitudes of human approval gate**.

Most dark factories collapse human-in-the-loop to one decision: "merge or not, at PR time." Even that's increasingly optional (Stripe's "two-iteration CI cap" auto-merges if CI passes twice).

Cawnex's four gates (Milestone, Goal, MVI, PR) exist because the target user is the **solo founder**, not the engineering org. The founder needs to steer at strategy altitude (Milestone), scope altitude (Goal), unit-of-work altitude (MVI), and craft altitude (PR). The convergent five serve teams who've already aligned on strategy; their orchestrators only have to manage the craft.

This is the design tension Shardul calls out:

> *"You're no longer writing code, you're composing the factory that writes the code for you. You go from an engineer who super focuses on code to an engineer who focuses on how the system verifies and fact-checks that the code is correct."*

For Stripe, "composing the factory" is one person's full-time job per ~50 engineers it serves. For Cawnex, "composing the factory" *is the founder's job by definition* — and the four gates are how that composition gets done day-to-day.

So Cawnex is closer to **L3 by design**, not **L4 by limitation**. The right comparison isn't "Cawnex is missing what Stripe has." It's "Cawnex's L3 with four-altitude steering is a different shape than Stripe's L4 with one-altitude merge gate, for different users."

---

## What we'd build next, given this lens

In order of impact, repeating the priorities from above:

1. **Deterministic verification gate inside Worker** — would have caught PR #16's three lint issues before merge. ~1 day of work.
2. **Cost-routed dispatch** — meaningful cost reduction + better outputs on hard tasks. ~2 days.
3. **Council voting on real PRs** — biggest jump in autonomy. ~1 week (Council exists but is untested at integration scale).
4. **Per-crow sandbox** — unblocks parallel within-MVI execution + safer (1). ~3 days.
5. **Sub-minute claim recovery** — replaces hourly Checker. ~half a day.

Items (1), (2), and (5) together would move Cawnex from L2-shaped to L3.5. Items (3) and (4) would offer an explicit L4 opt-in: "let the bot ship this entire wave without me." That's the real dark-factory line.

---

## References

- `~/background-agents/transcripts/case-studies/dark-factory-convergent-architecture.md` — Shardul Vaidya's talk distilled
- `~/background-agents/transcripts/concepts/07-trust-and-verification.md` — back-pressure model, SAE levels, multi-LLM defense
- Cawnex's own architecture: [`docs/ARCHITECTURE.md`](ARCHITECTURE.md), [`docs/diagrams/cawnex-architecture.drawio`](diagrams/cawnex-architecture.drawio)
- The five published artifacts from the convergent companies — Stripe Minions blog (parts 1+2), Ramp Inspect, Coinbase posts, StrongDM digital-twin, Anthropic's Claude-Code-on-Claude-Code

---

## One-line takeaway

**Cawnex is dark-factory-shaped at the orchestrator and event-log layers, half-built at the verification and isolation layers, and deliberately different at the human-in-the-loop layer.** The work that turns it into a factory is the verification gate, not the orchestrator — and that work is closer than it looks.
