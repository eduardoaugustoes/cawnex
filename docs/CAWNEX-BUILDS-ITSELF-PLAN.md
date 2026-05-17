# Cawnex Builds Itself — Staged Evolution Plan

**Status:** Strategic plan, agreed 2026-05-16. **Stage 4 (Council) is the chosen next stage**, locked 2026-05-16 after running a theoretical Council on the architecture choice.
**Companion docs:** [DARK-FACTORY-COMPARISON.md](DARK-FACTORY-COMPARISON.md) (the audit) · [BACKGROUND-AGENTS-LEARNINGS.md](BACKGROUND-AGENTS-LEARNINGS.md) (frames from the convergent five) · [diagrams/cawnex-architecture.drawio](diagrams/cawnex-architecture.drawio) Tabs 6 & 8 (visual)

## The reframe

After auditing Cawnex against the convergent dark-factory pattern, the temptation was to optimize what we have: parallelize implementers, cost-route models, harden the verification gate, switch to per-crow worktrees. That work is real but it's **fine-tuning that arrived from analysis, not from problems**.

The actual question is much simpler: **can Cawnex build itself end-to-end yet, and what's the next thing in the way of that?**

PR #16 was the first autonomous merge — but it was a one-off heroic. The loop that produced it has missing links, not slow links. This document captures the staged evolution plan to close the loop, in dependency order.

Optimizations (parallelism, cost-routing, sandboxing, claim-TTL recovery) are deferred until the loop closes. Then their value is measurable instead of speculative.

## The loop, as it stands today

What a fully autonomous wave requires, and where each step actually sits:

| Step | State | Gap |
|---|---|---|
| 1. Static context (Vision/Arch/Glossary/Design) | ✅ Exists | Frozen at project setup — never updated as the system evolves |
| 2a. Planner emits plan | ✅ Planner crow runs | Outputs a flat list, not a graph; no spec-quality check up front |
| 2b. **Plan adversary** | ❌ Doesn't exist | Bad plans go straight to expensive crow execution |
| 3. Crow execution | ✅ Implementer → Reviewer → Fixer works | Run-6 shipped a real PR |
| 4a. Reviewer crow | ✅ Adversarial-by-design | Works |
| 4b. **Council vote** | ❌ Designed in `council-protocol.md`, never run | Every PR escalates to the founder; no auto-merge tier |
| 4c. Founder gate | ✅ Approve/Reject buttons wired | Works |
| 5. **Observability for humans** | ⚠️ SSE works, CloudWatch exists | But no human-readable timeline of what the crow actually did |
| 6. **Learning loop** | ❌ Doesn't exist | Each wave starts cold; no memory of what failed last time |

**Four missing links** (plan adversary, council, human-readable observability, learning loop) plus **one rotting link** (static context that drifts from reality).

## The five stages, in dependency order

Each stage is the minimum to unblock the next. Each ends with Cawnex doing more of itself than before.

> **Note on build order:** The stages are listed below in the *dependency* order I originally proposed (1→5). The chosen *build* order is now Stage 4 first — see [Order of operations](#order-of-operations-updated-2026-05-16) below for the locked sequence and the reasoning for the re-order. Stages 1-3 and 5 remain in this document as future work whose ordering will be re-evaluated after Stage 4 ships.

---

### Stage 1 — Living context

**Today:** Vision/Arch/Glossary/Design written once at project setup, never touched again. Every crow run downstream reads docs that may be months out of date.

**Stage 1:** After every shipped MVI, a small Monarch operation re-reads the diff + the existing docs, and proposes updates. The founder approves/rejects the doc-update like any other change (uses the existing four-altitude approval pattern).

**Why first:** every subsequent crow run reads these docs. If they drift from reality, every plan/review/fix downstream is working from a lie. Cole Murray's "perpetual new hire" frame from `BACKGROUND-AGENTS-LEARNINGS.md` — documentation *is* agent onboarding.

**Result:** the system's understanding of itself stays current.

**Estimate:** ~2 days.

---

### Stage 2 — Plan adversary

**Today:** Planner emits N tasks → Implementer immediately burns tokens. Run-1 through Run-5 (see `BACKGROUND-AGENTS-LEARNINGS.md` for the failure log) each cost real money before anyone caught the bad plan.

**Stage 2:** Between Planner and Implementer, a Plan Adversary crow runs. Reads the plan + the (now-living) docs and asks: *Is this spec thin? Are there hidden dependencies? Will these tasks step on each other? What's missing?* Either approves, or rejects with structured feedback that goes back to Planner.

**Why second:** needs the docs from Stage 1 to do its job. And it's the highest-leverage gate — every bad plan caught here saves an Implementer + Reviewer + Fixer + Founder-attention cost downstream.

**Result:** plans get sharper before they're expensive.

**Estimate:** ~3 days.

---

### Stage 3 — Observability for humans

**Today:** SSE pushes wave-state updates. CloudWatch has crow logs. But there's no human-readable timeline of *what the crow was thinking* at any point.

**Stage 3:** A Human Summarizer crow runs after every crow finishes, takes the structured outcome, and produces: 1-line headline + 3 key decisions + any concerns. Stored in DDB events table, streamed via SSE to a "Wave timeline" view in iOS. Lawrence Jones's separate-layer-for-humans pattern from the IO transcript.

**Why third:** Stages 1+2 just added two more places things can go wrong. The founder needs to *see* them before they can trust them. Also unblocks faster prompt iteration (we can read what crows are actually doing without grepping CloudWatch).

**Result:** founder can watch Cawnex build, not just watch a progress bar.

**Estimate:** ~3 days.

---

### Stage 4 — Council *(LOCKED — chosen as the next stage)*

**Today:** Every PR escalates to the founder via the four-altitude approval gates. The Council Lambda is spec'd in `docs/design/council-protocol.md` and deployed, but has never voted on a real wave. The founder gate is on every PR's critical path; Cawnex's velocity equals founder-tap velocity.

**Why Stage 4 first (re-ordered from original 1→5 sequence):** Stages 1-3 *improve* the existing loop. Stage 4 *changes the loop's topology* — the founder stops being on every PR's critical path. It's also the stage that most directly demonstrates the dark-factory thesis (multi-perspective autonomy), it activates infrastructure that's already deployed but silent, and it unlocks the four-altitude gates the rest of the design depends on.

**Stage 4 outcome:** 6 tool-equipped advisors vote independently on every PR. Reviewer's verdict, the diff, planner intent, MVI spec, and project docs go into a packet; each advisor then *investigates the codebase through their own lens* using scoped tools (read_file, grep, list_directory, git_log_for_file) against the EFS-mounted working tree. Security + Clarity have veto power per the existing council-protocol spec. Outcomes are stored as `CouncilDecision` rows with full `investigation_trace` for auditability.

#### Locked architectural decisions

These were debated in a theoretical Council run on 2026-05-16 and are not re-litigated without explicit cause:

1. **Tool-equipped, not packet-only.** Each advisor calls tools to investigate independently. Packet-only Council is theater — six advisors reading the same prose produce correlated votes, not multi-perspective review. Tools produce genuine diversity by letting each lens pursue its own line of investigation.

2. **Dedicated `cawnex-council-${stage}` Fargate service (Option B).** Not the existing Worker (Option A). Council runs on a *new* Fargate task definition with a *separate* IAM role that has DDB read-only, EFS read-only, Anthropic key only — **no GitHub token, no S3 write, no ECS scaling permissions.** This was a Security-and-Architecture-vetoed decision against running Council in Worker:
   - **Security veto:** credential co-residency with code that has `git push` rights is the wrong threat model. Council advisors read potentially-hostile PR content; they must not share a process with merge-capable secrets.
   - **Architecture veto:** Worker is single-responsibility ("execute one crow run, exit"). Overloading it with the 6-way Council fan-out makes the task a grab-bag and forces every Council change to redeploy Worker.

3. **All 6 advisors run as parallel asyncio tasks within a single Fargate process.** Not 6 separate Fargate tasks, not 6 Lambda invocations, not a single Claude conversation with 6 personas. Each advisor opens its own Anthropic API conversation (`client.messages.stream(...)`), gets its own context window, runs its own tool-use loop. `asyncio.gather(..., return_exceptions=True)` orchestrates the six. Per-advisor failure is isolated; one crashing advisor doesn't kill the vote.

4. **EFS mounted read-only at the same path as Worker** (`/mnt/repos/T/{tenant}/{repo}`). **No advisor ever clones.** The working tree is left at PR head commit by the Reviewer crow that just ran; all six advisors share that filesystem read-only. Tool calls (read_file, grep) hit local EFS, completing in milliseconds rather than seconds.

5. **Per-advisor scoped tool palettes.** Not a flat "all advisors get all tools" — each role gets the tools its investigation actually needs, scoped by path where appropriate:

   | Advisor | Tools | Scope notes |
   |---|---|---|
   | Security | read_file, grep, list_directory, git_log_for_file | All paths |
   | Architecture | read_file, grep, list_directory, find_imports | All paths |
   | Clarity | read_file, grep | All paths |
   | Performance | read_file, grep, git_log_for_file | All paths |
   | UX | read_file, grep | Scoped to `apps/ios/...` and string files |
   | Cost | read_file, grep, list_directory | Scoped to `infra/...` |

6. **Hard caps:** 15 tool calls per advisor, 180s wall-clock per advisor. Hitting the cap is itself a finding — "this PR is too complex to evaluate in 15 calls" produces an abstain vote and a signal to escalate.

7. **No write tools, no recursive tools, ever.** Advisors investigate; they don't modify. No tool that calls Anthropic again (no sub-agent recursion — the path to runaway cost).

8. **Investigation trace is part of the vote record.** Every `AdvisorVote` includes which tools were called with what arguments. Founder-facing iOS view (Layer B) can show "Security read these 4 files, grep'd for `tenant_id`, found the missing filter on line 42." Vetoes without traces are not credible; vetoes with traces are.

#### Three-layer delivery

Layer A ships first; B and C iterate after we have data.

**Layer A — Tool-equipped Council fires and stores decisions** (~7-8 days)

- New CDK resources: `cawnex-council-${stage}` TaskDefinition + Service (0.5 vCPU / 1 GB), `CouncilServiceSG`, EFS read-only access point, dedicated task role
- New `apps/council/` package: Dockerfile, requirements.txt, `main.py`, 6 advisor system prompts, scoped tool implementations
- Murder reactor extended: when Reviewer crow writes its verdict, reactor writes a `COUNCIL#{vote_id}` row that triggers the new service via `ecs:UpdateService`
- New DDB SK pattern: `P#{proj}#COUNCIL#{wave}#{mvi}#{pr}#{ts}` for `CouncilDecision` rows including `votes[]` with `investigation_trace`
- The legacy `cawnex-council-${stage}` Lambda is deleted from CDK in the same pass
- **End of Layer A:** Council fires on every PR. Decisions are stored. Merge path is unchanged — founder still gates everything. We now have a parallel decision stream to compare to founder calls.

**Layer B — iOS surface for Council verdicts** (~3 days)

- PR Review screen learns to render the Council panel: per-advisor vote, concerns, veto status, "view investigation" affordance
- Tap-through view shows the investigation_trace as a readable timeline
- Founder still decides; Council informs

**Layer C — Graduated auto-merge** (~1 week + observation window)

- After 20+ PRs of observing Council match founder calls, enable auto-merge when: Council unanimous Yes + no vetoes + Reviewer approved + PR meets risk profile (size, scope, paths)
- Quarantine zones: auth, billing, IAM, schema migrations never auto-merge regardless of Council vote
- Per-project founder toggle (auto-merge off by default)
- Notification on every auto-merge with one-tap revert
- Self-throttling: if founder overrides >X% of Council calls in rolling window, auto-merge pauses

#### Cost of execution

- Anthropic API tokens: ~$0.21 per Council vote (6 advisors × ~$0.035 each at Haiku 4.5 pricing, ~18K input + ~3.3K output per advisor including tool-call rounds)
- Fargate compute: ~$0.0014 per vote on-demand, ~$0.0004 on Spot (0.5 vCPU / 1 GB for ~3 minutes including cold start)
- EFS / DDB / CloudWatch: pennies/month at any volume we'll see in the next 6 months
- One-time engineering: ~7-8 days for Layer A
- Ongoing operational tax: ~2 hrs/month for the new service's monitoring/deploys

#### What Layer A does *not* depend on

Layer A ships value with just the Reviewer's verdict + diff + planner intent + MVI spec + project docs in the packet. It does *not* depend on:

- Stage 1 (living context) — current frozen docs are good enough to start
- Stage 2 (plan adversary) — Reviewer's blocking_issues are sufficient input signal
- Stage 3 (human summarizer) — Layer B builds its own iOS-facing view

When Stages 1-3 ship, they enrich the packet and make Council votes higher-signal. But Council fires meaningfully from day one.

**Result:** the founder gate stops being on every PR's critical path. Element 4 of the dark-factory matrix (rework loop) graduates toward L4 with auto-merge. The first genuinely L4 cell in the Cawnex platform.

**Total estimate:** ~3 weeks across Layers A + B + C (with observation window between B and C).

---

### Stage 5 — Learning loop

**Today:** Each wave starts with frozen docs. Each crow run starts with no memory of last run's failures.

**Stage 5:** After every wave, a Monarch operation writes a structured "what we learned" snapshot — common mistakes, patterns that worked, prompts that misfired. Future planner/implementer/reviewer prompts read this. The system gets better at building itself the more it builds itself.

**Why last:** needs Stages 1-4 because the learning is over *what the system actually did*, which requires structured outcomes (4) which require human-readable summaries (3) which require good plans (2) which require living context (1).

**Result:** the dark-factory promise of "each cycle teaches the next."

**Estimate:** ~1 week to scaffold; value compounds over months.

---

## What this plan deliberately excludes

These are real improvements, but they're optimizations of a loop that doesn't fully close yet. Defer until the staged plan is delivered.

| Excluded work | Why deferred |
|---|---|
| Parallelization (DAG-level, parallel implementers) | Premature. The serial loop must close first. |
| Cost-routed model dispatch (Sonnet/Haiku per crow type) | Optimization. Becomes obvious once the loop has observability. |
| Per-crow worktrees (vs. tenant-shared) | Required only when we want parallel implementers. |
| Claim-TTL → sub-minute recovery (vs. hourly Checker) | Operational. The hourly cron is fine until throughput matters. |
| Deterministic verification gate (lint/test in Worker) | Real gap, but the audit gap. Plan-adversary is the bigger lever right now. |
| Murder/Crow CI/CD pipeline fix (task #18) | Worker deploys by hand today; still works. Not blocking. |
| GITHUB_TOKEN unsafeUnwrap → runtime fetch | Security cleanup, not loop-blocker. |

## Order of operations *(updated 2026-05-16)*

**Locked next stage: Stage 4, Layer A.**

The original plan put Stages 1-3 before Stage 4 because each stage produces signal that *enriches* Council inputs. That reasoning still holds for Layer C (graduated auto-merge), which benefits massively from richer packets. But Layer A — Council fires and stores decisions, founder still gates — ships meaningful value with just today's signal (Reviewer verdict + diff + planner intent + MVI spec + project docs), and it activates dead infrastructure that's already deployed.

The locked sequence:

1. **Stage 4 Layer A** — Council fires on every PR, decisions stored. Founder still gates. (~7-8 days)
2. **Stage 4 Layer B** — iOS surface for Council verdicts; founder sees the multi-perspective analysis. (~3 days)
3. **Observation window** — 20+ PRs of comparing Council calls to founder calls. (~2-4 weeks elapsed, low active work)
4. **Stage 4 Layer C** — Graduated auto-merge with quarantine zones and per-project toggles. (~1 week)

After Stage 4 ships end-to-end, re-evaluate. The remaining stages (1: Living context, 2: Plan adversary, 3: Human summarizer, 5: Learning loop) likely re-order based on what Council's investigation_traces reveal about which signal is most valuable to enrich next.

The "build the smallest stage first to validate the staging approach itself" principle still applies — but Layer A is now that smallest validating slice, not Stage 1.

## Success criteria (what "Cawnex builds itself" means at the end)

When Stages 1-5 are delivered:

1. A founder asks for feature X via iOS chat.
2. Planner produces a plan grounded in **current** docs (Stage 1).
3. Plan Adversary catches thin specs before they're expensive (Stage 2).
4. Crows execute; their work is **visible in human terms** as they go (Stage 3).
5. Reviewer + Council decide what auto-merges; only the hard calls escalate (Stage 4).
6. After ship, docs update themselves, lessons learned go into the prompt library (Stages 1 + 5).
7. Next wave starts smarter than the previous.

That is the loop. Everything else — parallelism, cost-routing, sandboxes, observability scaling — is fine-tuning on top of a closed loop.
