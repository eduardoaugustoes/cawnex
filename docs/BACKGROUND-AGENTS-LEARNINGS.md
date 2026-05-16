# Background Agents Corpus — Learnings for Cawnex

**Date:** 2026-05-16
**Source:** Full read of `~/background-agents/transcripts/` — 27 docs, ~4,700 lines, distilling 28+ talks across the Ona Background Agents Summit (Day 1 + Day 2, Feb 2026), the Software Factory live-build (Apr/May 2026), and the Stripe Minions blog.

**Companion doc:** [`DARK-FACTORY-COMPARISON.md`](DARK-FACTORY-COMPARISON.md) covers the architectural lens (Shardul Vaidya's "Dark Factories" talk, the convergent five). This doc covers the **10 other case studies and 12 concept lenses** — the human-role / context-engineering / rollout / trust-mechanism stuff the dark-factory lens doesn't address.

If you only have time for one of these two docs, read this one. The dark-factory comparison is the architecture; this one is the system-around-the-architecture, which is where most companies fail.

---

## The four lenses that reframe Cawnex

The corpus has a dozen recurring frames. Four of them are *directly load-bearing* for what Cawnex should do next.

### 1. "The agent is a perpetual new hire" — and your documentation is its onboarding

> *"The agent is a perpetual new hire. As anything changes within your company, it will begin with a new fresh session each time. It doesn't know how certain things work. Yes, it can find them out, but it really comes down to you and your team on correctly documenting and building a system around this."* — Cole Murray (OpenInspects)

This mental model became canonical across both summit days. Will adopted it in the Day 2 wrap. Lawrence extended it to cross-agent collaboration. **It's the most useful single frame in the corpus.**

What it means for Cawnex specifically:

| What Cawnex has today | What "perpetual new hire" implies it should have |
|---|---|
| `lambdas/worker/src/worker/context.py` injects project docs into every crow | A `cawnex.md`-equivalent **inside the user's project** that describes their codebase conventions to crows |
| `MemoryStore` reads/writes per-agent learnings to DDB (`MEM#agent#{type}`) | A founder-facing UI to **edit** the AI's onboarding material between waves |
| Council and crow prompts get vision/architecture/glossary/design docs | A way for the founder to **author the onboarding deliberately**, not as a one-time spec exercise |

The product reframe: **Cawnex's value to a founder isn't "AI ships PRs." It's "Cawnex teaches the AI your codebase, persistently, across runs."** The founder isn't a user — they're an onboarding director.

This reframes the iOS UX. The four approval gates (Milestone/Goal/MVI/PR) aren't just approval — **they're training data the founder is producing**. Every steer, every reject, every reason should feed back into the AI's understanding of the project.

### 2. Patrick Debois's CDLC — Context Development Lifecycle

> *"Context is the fuel. We talk a lot about coding agents — yes, they're great as the engine — but context is the fuel."* — Patrick Debois (Tessl)

Patrick (the DevOps movement originator from 2009) named what every successful team is doing implicitly. Five stages modeled on the SDLC:

| Stage | What it means | Cawnex's current implementation |
|---|---|---|
| **Generate** | Create context: prompts, agents.md, MCP, specs | Document chat screens (vision/architecture/glossary/design) — **strong** |
| **Evaluate** | Test the context works: LLM-as-judge, eval suites, lint structure of skills | Council (designed, not exercised) — **gap** |
| **Distribute** | Share + version skills, signed packages | No registry — **gap** |
| **Observe** | Learn from real runs: agent session logs, production errors fed back | Events table + crow snapshots — **strong substrate** |
| **Enable** | The human harness: multiplayer mode, context retros, skill curation | Four-altitude approval gates — **uniquely strong** |

**The gap is Evaluate.** Cawnex generates context but doesn't lint it, score it, or version it. The founder writes a vision doc; nobody runs adversarial questions against it; nobody checks if the spec is too thin (which the Software Factory team identified as their **single biggest learning**: thin specs cascade into UI bugs).

Patrick's also-proposed new productivity metric:
> *"It is about how many hops, how many retries does the agent do to do a better job at things."*

Tool calls per session. **Forget PRs/day; count agent loops.** Cawnex's events table already has the data; nothing surfaces it.

### 3. Cloudflare's codecs — "engineers don't trust AI opinions"

The cleanest single statement of how AI-system trust is built:

> *"Engineers don't trust AI opinions. They just trust clear findings tied to standards that we agreed upon."* — Rajesh Bhatia (Cloudflare)

Cloudflare's 18-month arc to 93% R&D adoption pivoted on this. The AI reviewer went from "ignored opinions" to "trusted findings" the moment they codified the standards it cited.

**Applies recursively to Cawnex's founder.** Right now the iOS PR Review screen shows the reviewer crow's verdict as prose:

> "✅ APPROVED. This change correctly implements the core MVI: enriching existing project responses with a computed current_state field. All five modified files work together properly. Key strengths: (1) compute_current_state is a clean, pure function with comprehensive unit tests…"

That's an *opinion*. The founder has no way to know if the reviewer is right.

What Cloudflare did: the reviewer cites a rule. *"This violates `engineering-codex/error-handling.md` line 14 — bare except blocks must log."* Now the founder reads the rule once, agrees with it once, and **trusts every future review that cites that rule**.

What Cawnex needs: **a per-project `codex.md` that the reviewer crow is required to cite.** Maybe generated from the founder's design doc. Maybe iteratively built up across waves. The reviewer's verdict becomes "I checked sections A, B, C of your codex; here are the violations." Way more trustworthy than prose.

### 4. "Go where the pain lives" — Cawnex's user is a founder, not an engineering org

> *"Don't promise an engineer the world when you give them a platform. Give them a valuable use case because you have to go to where the pain lives."* — Nikhil Ramakrishnan (Uber)

The most-quoted line of the summit. Day 2 called it the rollout-strategy line of the conference.

**The convergent five all solved toil first**, not feature work:

- Uber's Minion handles validation around small fixes (tests, dependency checks, "does this break anything?") — **not features**
- Stripe's Minions started on the documentation site, then expanded
- Genentech started with the ops bot (Sentry triage), then the dev bot
- Software Factory's most-valuable single automation was the **PR Shepherd** that re-evaluates stuck PRs

**Cawnex started at the hardest end** — feature work end-to-end. That's why runs 1-5 all failed in different ways. The solo founder Cawnex targets resembles small-team profiles (Genentech's 4 engineers, Software Factory's 2-host team), not Stripe's eng org. **The first Crow type founders should successfully run isn't the full implementer.** It should be a "dependency upgrader" or "docs updater" or "test writer." Same architecture, narrower scope, much higher first-week success rate.

This is a **product positioning question**, not an engineering question. The current Cawnex pitch — "AI ships MVIs end-to-end" — frames the hardest use case as the first one. The corpus says: start narrower, build trust, expand.

---

## Five other concepts worth keeping in mind

Less load-bearing but useful frames:

### 5. "Verification is back pressure" — Stripe's 2-CI-iteration cap as a primitive

Stop thinking of tests as "did it work?" — start thinking of them as **force the agent is required to listen to.** Stripe's 2-CI-iteration cap (agent fixes failures, second iteration fixes residual, hit 2 → escalate to human) is the operational variant. The cap itself is back pressure — forces the agent to be careful early.

Cawnex has `FIX_CYCLE_LIMIT` already. It's the right primitive. What's missing is the **deterministic gate that triggers it inside the Worker**, not just the cap once it's triggered.

### 6. "Rewrite agent state for humans" — Lawrence Jones at incident.io

Lawrence found that exposing the agent's internal investigation summaries directly to humans read like "AI slop." Fix: a separate summarization layer specifically for human consumption.

Cawnex shows raw crow `outcome.summary` text on the iOS Wave Execution live feed, PR Review verdict, and MVI Detail screen. Run-6's PR comment was 350+ words of *"1. **compute_current_state function**: Pure function that…"* That's not how a human would write that comment.

**Cawnex needs a "human summarizer" pass** that takes the crow's structured outcome and produces tight, scannable summaries for the iOS UI. One-prompt change in the worker; massive UX upgrade.

### 7. "MCP is the UI between agents" — Lawrence Jones again

The biggest single conceptual contribution from Day 2:

> *"The MCP contract that you have between your agents has become an extremely important UI in a way that many APIs perhaps weren't before."*

Implication for Cawnex: when the Steer chat lands (Phase 2 of the PR Actions spec), its tools (read_file, grep_files, glob_files, submit_response) **are the UI between the founder's chat agent and the codebase**. The tool descriptions need to be written for *another agent* to read, not for humans. Same discipline as documenting an API for external consumers.

This isn't urgent yet; flagging for when Phase 2 ships.

### 8. The opinionated-stack-helps-AI insight — Monzo

> *"We can say, here are 3,000 examples of how we write code here at Monzo. Don't go and invent a new way."* — Suhail Patel

Heavy convention enforcement (one HTTP library, one auth pattern, codegen, static analysis) *helps* AI agents. Pattern density is signal.

Counter-implication for Cawnex's user: **founders with messy codebases will get worse Cawnex outputs than founders with opinionated stacks.** Worth noting in the onboarding — if the codebase is inconsistent, Cawnex will produce inconsistent code. The Genentech corollary: generic skills help; over-specific debugging skills hurt agents 2×. **Teach the agent what to look at, not what to look for.**

### 9. The "perpetual new hire" extension — Will (Day 2 keynote)

Combining concept 1 with Lawrence's MCP-as-UI insight:

> *"Every AI agent is effectively an engineer that you're onboarding on day one. They're only as smart as the things that you give them access to instantly."*

If you substitute "other agent" for "engineer," the framing holds for cross-agent collaboration too. Worth keeping in mind when Cawnex's Steer chat starts talking to the reviewer's outcome, or when the Council reads the implementer's snapshot — those are agent-to-agent onboardings.

### 10. "Hope is the strategy" on ROI — Suhail (Monzo)

> *"I would be skeptical of any organization right now who claims that they have a perfect answer to this. A significant amount of the dollars that we are spending is experimentation."*

The most honest line of the summit on ROI. DORA metrics break under AI. PRs/sprint is meaningless. Outcome-based pricing is structurally impossible because model releases reset calibration.

What does this mean for Cawnex's pricing and reporting? **The ROI screen the iOS app shows should be honest.** Today the dashboard surfaces "human equivalent saved" — which is *exactly* the kind of fabricated ROI Suhail warns about. Replace it with **customer-visible outcome velocity**: how many MVIs shipped this week vs last, time-to-ship per MVI, founder hours not spent reviewing. Honest proxies, not invented dollars.

---

## What I'd amend in the dark-factory comparison

Three things [`DARK-FACTORY-COMPARISON.md`](DARK-FACTORY-COMPARISON.md) under-covers:

### A. The rework loop isn't just "retry with context" — it's "escalate to a stronger model"

The convergent pattern is more than "feed failure context forward." It's that the **Fixer crow should be a stronger model than the Implementer**, because by the time we're invoking it, the easier model has already produced something the Reviewer rejected. The rework loop's value comes from *different* compute, not *retried* compute.

Cawnex's Fixer today uses the same model as the Implementer (Haiku 4.5 across the board). Wrong shape.

### B. The four-altitude gates map onto CDLC "Enable"

The dark-factory doc frames Cawnex's four gates as "deliberately L3, not L4." Truer framing: Cawnex's four gates are **the Enable stage of context-engineering at four different altitudes** (strategy / scope / unit / craft). That's a positive design choice for the founder user, not a deficit relative to L4 engineering orgs.

### C. The user isn't "shipping PRs" — they're "becoming a factory architect"

> *"You're no longer writing code, you're composing the factory that writes the code for you. You go from an engineer who super focuses on code to an engineer who focuses on how the system verifies and fact-checks."* — Shardul Vaidya

The corpus's strongest unspoken truth: **the user is becoming a factory architect, not a code author.** Stripe, Cloudflare, Genentech all describe this explicitly. **Cawnex's iOS UX should make this explicit** — the founder is *training the AI on their company*, not just consuming PRs. Right now the iOS UX frames the founder as a consumer of PRs; the corpus says they should be framed as a producer of context.

---

## Specific things to build in Cawnex, ranked by leverage

After the full corpus read, the priority list shifts from the dark-factory doc's version. New ordering:

### 1. Codex file the reviewer must cite (1 day)
Per-project `cawnex.md` or `codex.md` listing the founder's agreed-upon rules. Reviewer crow's `submit_result` schema gains a `cited_rules: list[str]` field. Verdict prose is replaced (or supplemented) with the rule citations.

**Cloudflare codecs pattern applied to Cawnex.** Biggest single trust unlock. The founder gains the ability to *configure* what the Reviewer cares about, beyond what the prompt says.

### 2. Pre-merge verification gate inside the worker (1 day)
Already in the dark-factory doc. `black + flake8 + mypy + pytest` (or whatever the project's stack uses) runs against the implementer's worktree before the reviewer sees the diff. Failures = Fixer rework with structured back-pressure. Would have caught PR #16's 3 lint issues.

### 3. Human summarizer pass on every crow outcome (half a day)
Add a `summarize_for_human` step at the end of every worker run. Takes the structured outcome and produces a 1-sentence headline + 3-bullet impact + (optional) concerns. Replaces the verbose raw `outcome.summary` text in iOS.

**Generalizable to MVI completion summaries, wave delivery summaries, and the Phase 2 Steer chat's PR comments.** Biggest UX win.

### 4. Cost-routed model dispatch (2 days)
Planner = Sonnet 4.6. Implementer = Haiku for trivial / Sonnet for complex (based on planner's task count). Reviewer = Haiku. **Fixer = Sonnet always.** Council votes = Haiku majority + Opus tie-breaker.

The framework knows about all three models (`MODEL_CONTEXT_WINDOWS`); just needs selection logic. Real cost savings + qualitatively better outputs on hard tasks.

### 5. Spec-quality pre-flight check (3 days)
Before a wave activates, an adversarial agent reviews the MVI's spec. Tries to interpret it ambiguously vs correctly; differences become "this spec is unclear about X." Returns structured concerns. The founder steers the spec before any tokens are burned on actual implementation.

**This is the single biggest source of wasted work** in the corpus, per Software Factory's Day 10 retro: thin specs cascade into UI bugs. The Stripe Minions talk reveals an unspoken pre-step: real Stripe usage starts with a **deep-search agent** that scopes feasibility before kicking off the actual Minion. Cawnex should have the same pre-step.

### 6. Context editing UI in iOS (1 week, biggest *product* unlock)
The founder needs to be able to edit the AI's onboarding between waves. Today the vision/architecture/glossary/design docs are write-once-via-chat. They should be **continuously edited based on what the founder learned from the last wave's reviewer findings**.

This is the "context retro" pattern from Patrick's CDLC. There's no UI for it. Building it is the biggest single move toward **the founder-as-onboarding-director framing** above.

---

## The reframing change I'd make to Cawnex's marketing / vision

The corpus consistently says: **the durable advantage isn't speed of generation — it's speed of response to a customer-cited need.**

- Cloudflare's codecs: respond to engineer feedback by updating a rule, not by retraining a model
- Stripe's blueprints: respond to repeated patterns by codifying them as deterministic nodes
- Genentech's hourly ticket pickups: respond in an hour to whatever's prioritized, day after day
- Harvey's "apps on the fly": agent generates a UI to do similar work *next time*

Cawnex's pitch today is *"ship MVIs."* That's a generation-speed pitch. **The more durable pitch is *"respond to your customer's feedback in 5 days, every day."*** The factory's value isn't the first 10 features — it's the next 100 customer requests.

For the iOS UX specifically: the **"Needs Your Input"** section on Project Hub is actually the most important screen in the product. Right now it's empty most of the time. Filling it with *customer feedback to triage* (not just MVIs awaiting approval) would close the production-to-planning loop Software Factory called out as the most-valuable single addition — and gives the founder a recurring reason to open the app.

---

## Two product-level moves the corpus suggests

These are bigger than feature requests — they're shape changes for what Cawnex is.

### 1. Cawnex is dual-product: harness + factory

Stripe, Cloudflare, Monzo, Uber all reached the same build-vs-buy answer: **build the harness, buy the foundation.** "Own the Chrome" — what they call the interface layer.

Cawnex today is doing both at once: building the harness (Crow types, Council, blueprints) *and* building the runtime (Murder reactor, Worker, SSE stream). That's defensible early. As Cawnex matures, the **harness** is where the founder's unique value lives (their codex, their conventions, their MCP servers). The **runtime** becomes commodity infrastructure.

Implication: the iOS app's primary surface should be **the harness**, not the runtime. Today the dashboard shows wave executions (runtime). Tomorrow it should show codex coverage, agent memory diffs, skill evolution (harness).

### 2. Cawnex's user is a small team, even if it's solo

The corpus's pattern: Genentech (4 engineers), Software Factory (2 hosts), Calhou (1 founder + AI). These are **small teams operating like medium teams** by virtue of agent leverage. The Software Factory case study makes this explicit:

> *"The right environment will probably foster the right talent. Right now as a software engineer with all the bots, a lot of agents helping us in the background, I can independently debug complex genomic issues. I spend less time debugging — more time to build."* — Shio-Chen Kwak

Cawnex's pricing should match. **Cawnex isn't priced per-seat for one founder** — it's priced per "1 founder + 4 agents" team. The product should support multiple "operators" (the founder, the AI Reviewer, the AI Planner, the AI Implementer) and give the founder a way to see what each is doing at any moment.

---

## What's *not* worth building from this corpus

Some things the corpus describes well but don't fit Cawnex's user:

- **Cross-organization agent handoff** (Lawrence Jones's frontier) — Cawnex is single-tenant single-project, federated trust isn't a problem yet
- **Multi-user collaborative sessions** (Harvey Spectre) — founders are solo by definition
- **Self-evolving skill loops** (Genentech) — too sophisticated for the user; risk of drift is real
- **Enterprise IDP / Backstage equivalent** — relevant when Cawnex supports projects with 10+ services; not for the solo founder

These are *all* good ideas, just not for Cawnex's current user. Worth re-reading the corpus when Cawnex starts serving 5-person teams.

---

## References

- `~/background-agents/transcripts/` — full corpus, 27 docs, ~4,700 lines
- [`DARK-FACTORY-COMPARISON.md`](DARK-FACTORY-COMPARISON.md) — companion doc, architectural lens
- [`docs/ARCHITECTURE.md`](ARCHITECTURE.md), [`docs/diagrams/cawnex-architecture.drawio`](diagrams/cawnex-architecture.drawio) — Cawnex's current shape

---

## One-line takeaway

**The dark-factory architecture is necessary but not sufficient. What separates *successful* dark-factory teams from their architectural twins is how well they teach the AI about their codebase — and Cawnex's user (the founder) is exactly the person who should be doing that teaching, deliberately, as the product's primary activity.** The next product surface to build is the one that makes context-authoring a first-class activity rather than a hidden side effect of approval gates.
