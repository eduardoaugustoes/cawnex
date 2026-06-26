# orchestrate — a self-walking, adaptive, analysis-first build pipeline

**Date:** 2026-06-26
**Status:** Design (approved in brainstorm; pending spec review)
**Author:** Eduardo Augusto

## 1. Purpose

A reusable, drop-in-any-repo orchestration. You give it one intent. It walks itself
through an **analysis-first** pipeline — research → innovation-scout → tradeoff analysis
→ validated plan → optional gated implementation — leaning on past decisions while
actively hunting for better solutions. As it works it emits **live, versioned artifacts**
(research brief, tradeoff decision matrix, decision record, diagrams, OpenAPI, UI mockups)
that are first-class shareable engineering knowledge, not just code.

The goal is to remove manual orchestration work: state intent once, watch artifacts build
live, trust that standards are enforced by the spine (not left to agent discretion).

### Relationship to cawnex's existing dark factory

Cawnex already runs a cloud dark factory (DDB-Streams Murder orchestrator; Planner →
Implementer → Reviewer → Fixer crows; four-altitude approval gates; Council deployed but
never fired; shipped PR #16 autonomously). `orchestrate` is the **local, founder-driven
counterpart**: the thing run by hand at the terminal for deep, adversarial,
artifact-emitting analysis on a single intent.

It is also a **prototype of cawnex's own flagged-but-unbuilt stages** — the Plan Adversary
and the deterministic verification gate were the top items in
`CAWNEX-BUILDS-ITSELF-PLAN.md`. `orchestrate` lets those ideas be dogfooded locally before
wiring them into the cloud Murder.

## 2. Evidence base (why this shape)

Two research passes (prior internal work + 2025–2026 industry literature) drove the design.
Key findings that are **load-bearing**:

- **Deterministic gates are the only trusted hard gate.** "Give Claude something that
  produces a pass or fail and the loop closes on itself." Standards must be executable
  (lint/typecheck/tests/`cdk synth`/schema-validation), wired as blocking checks — not
  advisory prose.
- **The verifier must be external to the implementer.** Intrinsic self-correction degrades
  accuracy (DeepMind, ICLR 2024). Grading is done by fresh-context adversary subagents
  and/or CI, never by the agent that wrote the code.
- **Adversary critics must be heterogeneous.** Homogeneous multi-agent debate fails to beat
  cheap self-consistency; the real gain is *model diversity* (arxiv 2502.08788). Critics run
  on a different model than the implementer, and a stage must beat self-consistency to justify
  its cost.
- **Agents fake gates 18–63% of the time** in coding settings (`sys.exit(0)` to fake passing
  tests; printing `PASS` to game substring matchers). Gates must be tamper-resistant.
- **Failure compounds super-linearly with task length** (METR: <10% success beyond ~4hr;
  doubling duration ≈ 4× failure). Short hops + checkpoint after every stage + hard caps.
- **Context rot starts before the window fills** (30–50% degradation). Each stage is a
  fresh-context subagent returning only its artifact/summary.
- **Don't optimize against a reasoning monitor** — it teaches obfuscated cheating. Monitors
  flag-and-halt; never used as a reward signal.
- **Autonomy works narrowly:** mechanical, well-scoped, well-tested work atop good infra
  (Spotify: 1000 PRs/10 days — but years of test infra, migrations only). The one gold-standard
  RCT (METR) found experienced devs got **19% slower** on their own mature repos while
  *believing* they were faster. → Analysis-first is the evidence-backed sweet spot;
  implementation is the smaller, human-reviewed tail.

## 3. Architecture

One JS `Workflow` script (`orchestrate.workflow.js`) is the **deterministic spine**, invoked
by a thin `/orchestrate "<intent>"` skill that handles the workflow opt-in. Claude agents are
the muscle inside each phase.

```
/orchestrate "intent"
        │
   Phase 0: CLASSIFY → work-type + profile + resolved hints + verify mechanism
        │             (THE one human gate: confirm once)
        ▼
   load history (memory + repo docs)  ──►  cascading hints injected into every agent
        │
   ┌─────────────────────── analysis-first heart ───────────────────────┐
   │ RESEARCH (deep-research fan-out, work-type scoped)                  │
   │ INNOVATION-SCOUT (adversarial to the inherited status quo)         │
   │ TRADEOFF ANALYSIS (decision matrix: options × criteria × scores)  ──► adversary fan-out
   │ WRITE-PLAN (validated plan)                                         ──► adversary fan-out
   └────────────────────────────────────────────────────────────────────┘
        │
   IMPLEMENT (optional per run; rules applied) ──► adversary fan-out + VERIFY (agent-runnable)
        │                                          loops until clean; hard cap → surface to human
        ▼
   artifacts streamed to docs/ and committed throughout
```

**Self-walking:** after the Phase 0 confirm, the run proceeds fully autonomously.
**Loop-until-clean:** each stage's adversary + gate pass can send the stage back for retries
(hard cap); on exhaustion it stops and surfaces to the human — never silent-pass.
**Default output is a decision, not a diff:** many runs stop at validated plan + decision
matrix + artifacts without writing code.

## 4. Adaptivity: classify + profiles

Phase 0 reads the intent, classifies the work-type, and proposes the profile + artifact set +
verify mechanism. The user confirms/adjusts **once**, then the run is autonomous.

Profiles: `ui` · `api` · `domain` · `data` · `infra` · `refactor`. Each profile is a lego in a
`PROFILES` map and declares a fixed contract (§6).

## 5. Hints & gates (cascading, two-tier)

Hints resolve at runtime via a cascade, merged in precedence order (later overrides earlier):

1. **Global** — `~/.claude/orchestrate/hints/*.md` (apply in any repo)
2. **Profile** — `~/.claude/orchestrate/hints/profiles/<type>.md`
3. **Project general** — `<repo>/.orchestrate/hints/*.md`
4. **Project override for type** — `<repo>/.orchestrate/hints/<type>.md`

Each hint file has two parts:

- **`## guidance` (soft):** injected into agent prompts. Both *references skills to invoke*
  (e.g. infra → invoke `cdk-bounded-context-stack` skill; enforce `STRICT-CODING-STANDARDS.md`)
  AND *restates a few critical must-not-violate rules inline* (so the adversary has hard checks
  even if a skill is skipped).
- **`## gates` (hard):** checks the **spine** runs before a stage may pass. Two kinds:
  - `type: command` — runnable assertion, exit code = pass/fail (objective: lint, typecheck,
    tests-touched, `cdk synth`, schema validation).
  - `type: judge` — a dedicated heterogeneous adversary agent rules pass/fail **with cited
    evidence**, for "did it really use pattern X" checks where no command exists.

Gates cascade exactly like hints (global ⊕ profile ⊕ project). A stage's gate opens only when
**both** the adversary verdict is clean **and** every hard gate passes.

### Evidence-hardened gate rules (baked into the spine)

| Rule | Evidence |
|---|---|
| Gates run in a sandbox the agent can't edit; diff scanned for cheats (`sys.exit`, hardcoded `PASS`, touched test files, rewritten git history) before any gate is trusted | reward hacking 18–63% |
| Adversary critics run on a *different model* than the implementer; a stage must beat self-consistency to justify its cost | homogeneous debate ≯ self-consistency |
| Each stage = fresh-context subagent returning only its artifact | context rot before window fills |
| Hard iteration cap per stage + explicit stop → surface to human (never silent-pass, never infinite loop) | super-linear failure with horizon |
| Reasoning monitor flags-and-halts, never used as a reward signal | optimizing against intent → hidden cheating |

## 6. Profile contract: emit + **mandatory verify**

**Invariant: no verify, no run.** A profile with no agent-runnable verify mechanism cannot
execute; the spine errors at Phase 0. "Every implementation must be verifiable by agents" is
enforced structurally. The implement→adversary gate **drives the artifact through its verify
tool** — the verdict is grounded in observed behavior, not a self-reported log.

| Profile | Design/emit tool | Verify mechanism (agent-runnable) |
|---|---|---|
| `ui` | **Pencil MCP** (`.pen` mockups) | **Chrome DevTools MCP** — load running UI, snapshot + console + a11y/lighthouse audit, assert elements present & interactive |
| `api` | OpenAPI emitter | spin endpoint locally → hit routes, validate responses against `openapi.yaml`; contract test |
| `domain` | class/sequence diagram | unit tests exercise modeled behavior; type-check; diagram-vs-code consistency judge |
| `data` | ER/schema + migration | run migration on scratch DB → query, assert schema; rollback test |
| `infra` | stack/arch diagram | `cdk synth`/`cdk diff` exit code + command gates (no raw exports, capability-registry used) |
| `refactor` | before/after + blast-radius map | existing test suite stays green + behavior-diff check (no observable change) |

Profile shape:

```js
PROFILES.ui = {
  workType: 'ui',
  hints:  ['global', 'profiles/ui', 'project/ui'],   // cascade
  emit:   ['spec', 'research-brief', 'tradeoffs', 'decision', 'pencil-mockup', 'component-tree'],
  verify: {                                           // MANDATORY, agent-runnable
    tool:   'chrome-devtools-mcp',
    method: 'load running UI → snapshot + console + a11y/lighthouse → assert',
    gate:   'no console errors; a11y AA; asserted elements present & interactive',
  },
}
```

Diagram default format is **mermaid** (cheap, versionable, renders in any markdown preview /
GitHub); `infra` may additionally export drawio. UI mockups use Pencil; OpenAPI viewable in any
Swagger UI. The optional rendered visual surface (Pencil/Chrome/Swagger) is opt-in per profile —
the spine never *blocks* on a GUI.

## 7. Memory & innovation layer

Bidirectional — "lean on history but find better":

- **Read (history in):** before research, load relevant prior decisions from the
  `~/.claude/.../memory/` system AND the repo's own decision-rich docs (cawnex: ARCHITECTURE,
  STRICT-CODING-STANDARDS, prior specs). Injected as a "prior-decisions" prompt fragment so the
  plan doesn't re-litigate settled choices.
- **Innovate (find better):** the innovation-scout pass is adversarial toward the inherited
  approach — "given the intent + latest practices, is there a materially better solution than
  history assumed? Cite evidence." Plugs into `deep-research`. Its proposals must survive the
  same adversary + gates as anything else.
- **Write (decision out):** at run end, write a memory file capturing the *decision and why*
  (not the code), feeding future runs. Fixes cawnex's flagged gap: "each wave starts cold; no
  learning loop."

The tension between respecting the past and finding better is a feature, resolved by the gates.

## 8. Run layout (versioned + autonomous)

Written to the repo and committed as it goes:

```
docs/orchestrate/<timestamp>-<slug>/
  00-classification.md      # work-type, profile, resolved hints, verify mechanism
  01-research-brief.md      # best practices + latest advances, cited (deep-research)
  02-innovation-scout.md    # challenges to the inherited approach
  03-tradeoffs.md           # decision matrix: options × weighted criteria × scores × recommendation
  04-decision.md            # chosen approach + why + what was rejected (→ memory)
  05-plan-final.md          # the written, adversary-cleared plan
  artifacts/
    openapi.yaml | class-diagram.mmd | mockup.pen | stack.mmd | ...
  adversary-log.md          # every fan-out round, every gate result, every retry
  verify-report.md          # what each verify tool observed (Chrome DevTools, cdk synth, ...)
```

`tradeoffs.md`, `decision.md`, `adversary-log.md`, and `verify-report.md` are the durable,
shareable engineering knowledge: what was considered, challenged, checked, and observed.

## 9. Spine emphasis: analysis-first

Research + tradeoff analysis + innovation-scouting are the **heart**; implementation is a
smaller, optional, hard-gated tail. The default product of a run is a **decision** (research
brief → tradeoff matrix → recommended approach), not a diff. This matches the evidence: the
planner/executor pattern's strongest results are on research/analysis; greenfield implementation
is where autonomy is weakest and human review is mandatory.

This brainstorm itself was the dry-run of the analysis-first spine (intent → deep-research
fan-out → adversarial findings → tradeoff-weighing → evidence-hardened decisions → this spec).

## 10. Components (units & boundaries)

| Unit | Responsibility | Depends on |
|---|---|---|
| `/orchestrate` skill | one-command entry; workflow opt-in; pass intent | Workflow tool |
| `orchestrate.workflow.js` (spine) | deterministic phase control, loops, caps, gate enforcement | profiles, hints resolver, gate runner |
| Classifier (Phase 0) | intent → work-type + profile + verify; the one human gate | PROFILES map |
| Hints resolver | cascade global ⊕ profile ⊕ project → merged prompt fragment + gate set | filesystem |
| Gate runner | run command/judge gates in tamper-resistant sandbox; verdict | sandbox, heterogeneous critic |
| Adversary fan-out | heterogeneous fresh-context critics per stage | different model |
| Artifact emitters | per-profile artifact production (Pencil, OpenAPI, mermaid, …) | profile tools/MCPs |
| Verify drivers | per-profile agent-runnable verification (Chrome DevTools, cdk synth, …) | profile MCPs/CLIs |
| Memory I/O | read prior decisions; write decision record | `~/.claude` memory, repo docs |

## 11. Scope / YAGNI

**In:** the spine, classifier + confirm-once, cascading hints + two-tier gates, evidence-hardened
gate rules, profile contract with mandatory verify, the six profiles (analysis path mandatory;
implementation path optional), memory I/O, run layout.

**Out (for now):** GUI canvas; cloud/background execution (this is local-terminal); replacing
the cawnex cloud Murder; cost-routed model dispatch (note it, don't build it); auto-merge.

## 12. Open questions for implementation planning

- Which model to use for heterogeneous critics vs the implementer (must differ).
- Minimal viable profile set for the first build (likely `refactor` + `api` given analysis-first
  emphasis and cawnex's needs).
- Exact gate command scripts for cawnex (`make lint`, `make typecheck`, tests-touched checker).
- How `/orchestrate` opts into the Workflow tool cleanly each run.
