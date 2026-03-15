# Council Protocol — Advisory Decision-Making

> Intelligence without judgment is just computation.
> Judgment without multiple perspectives is just bias.
> The Council combines both.

---

## Problems Solved

| #   | Problem                                                               |
| --- | --------------------------------------------------------------------- |
| 17  | Separate intelligence (how) from judgment (what & why)                |
| 18  | Multiple perspectives catch blind spots                               |
| 19  | Advisors evolve with project maturity                                 |
| 20  | Decisions traceable (who voted what, why)                             |
| 21  | Disagreement is a feature — debate rounds, dissent, re-evaluation     |
| 22  | Resource discipline — max rounds, don't burn credits debating forever |

---

## The Six Advisors

| Advisor         | Lens                                 | Veto Power      | Example Concern                                    |
| --------------- | ------------------------------------ | --------------- | -------------------------------------------------- |
| **Security**    | Vulnerabilities, auth, data exposure | YES — can BLOCK | "No rate limiting on auth endpoint"                |
| **Quality**     | Patterns, tests, maintainability     | No              | "Test coverage below 60%"                          |
| **Performance** | Latency, cost, scalability           | No              | "N+1 query pattern detected"                       |
| **Market**      | Business value, user impact, timing  | No              | "Onboarding is higher priority than admin panel"   |
| **Maturity**    | Tech debt, stability, reliability    | No              | "This approach creates coupling we'll regret"      |
| **Clarity**     | Spec ambiguity, missing requirements | YES — can BLOCK | "Acceptance criteria are vague, will cause rework" |

**Two advisors have veto:** Security (can't ship vulnerable code) and Clarity (can't build against ambiguous specs). Others influence through scoring.

---

## When Council Convenes

### Yes — Council Needed

1. **Wave planning** — "What should be in the next wave?"
2. **Architecture decisions** — "REST vs GraphQL? Monolith vs microservices?"
3. **Priority conflicts** — "Two goals compete for the same wave, which first?"
4. **Escalation** — Murder hit a wall, needs judgment on how to proceed
5. **Human-requested** — Founder asks "should we pivot to B2B?"

### No — Council Skipped

- Routine task assignment (Murder handles this)
- Code review (Reviewer crow handles this)
- Bug fixes (straight to execution)

---

## The Voting Protocol

### Round 1: Independent Assessment

All 6 advisors run **in parallel** (6 Lambda calls). No advisor sees another's vote — prevents groupthink.

#### Input (per advisor)

```json
{
  "human_directive": "Ship onboarding in 2 weeks",
  "project_context": {
    "phase": "execution",
    "tech_stack": "FastAPI, DynamoDB, SwiftUI",
    "existing_code_summary": "...",
    "current_wave": "w002 (completed)"
  },
  "decision_needed": "What should Wave 3 contain?",
  "options": [
    { "id": "mvi_auth", "name": "Auth & JWT", "human_estimate": "3 days" },
    {
      "id": "mvi_onboarding",
      "name": "Onboarding flow",
      "human_estimate": "4 days"
    },
    {
      "id": "mvi_payment",
      "name": "Payment integration",
      "human_estimate": "5 days"
    }
  ],
  "project_memory": "...",
  "advisor_memory": "..."
}
```

#### Output (per advisor)

```json
{
  "advisor": "security",
  "scores": {
    "mvi_auth": 9,
    "mvi_onboarding": 6,
    "mvi_payment": 3
  },
  "recommendation": "Auth must come first — no rate limiting, no CSRF protection yet",
  "reasoning": "Payment without auth hardening is a liability. Auth MVI includes rate limiting which protects all subsequent endpoints.",
  "blockers": [
    "No rate limiting on POST /auth/sign-in",
    "CSRF tokens not implemented"
  ],
  "confidence": 0.85,
  "vote": "BLOCK",
  "suggested_crows": ["implementer", "tester", "security-auditor"],
  "estimated_effort": "medium"
}
```

#### Vote Types

| Vote                     | Meaning                       | Effect                                                            |
| ------------------------ | ----------------------------- | ----------------------------------------------------------------- |
| `APPROVE`                | No concerns, proceed          | Counts toward consensus                                           |
| `APPROVE_WITH_CONDITION` | Proceed if condition met      | Condition recorded, Monarch decides                               |
| `ABSTAIN`                | Not enough context to judge   | Ignored in tally                                                  |
| `BLOCK`                  | Hard stop — unacceptable risk | Only Security and Clarity can BLOCK. Forces debate or escalation. |

---

### Monarch Synthesis

The Monarch receives all 6 votes and:

1. **Checks for vetoes** — Security BLOCK or Clarity BLOCK stops everything
2. **Weighs scores by confidence** — a 0.9 confidence vote matters more than 0.4
3. **Identifies disagreements** — if Market says "ship now" but Security says "block", that's tension to resolve
4. **Makes a decision** OR **calls another round** OR **escalates to human**

#### Monarch Decision Output

```json
{
  "decision": "proceed_with_constraints",
  "wave_plan": ["mvi_auth", "mvi_onboarding"],
  "deferred": ["mvi_payment"],
  "reasoning": "Security BLOCK on payment is valid. Auth first hardens the foundation. Onboarding aligned with human directive. Payment deferred to Wave 4 after auth is shipped.",
  "ordering_constraints": [
    "Auth MVI must include rate limiting",
    "Add CSRF middleware before payment"
  ],
  "dissent_acknowledged": {
    "market": "Wanted payment in this wave for revenue. Acknowledged but security risk outweighs."
  },
  "confidence": 0.82,
  "action": "execute"
}
```

#### Monarch Actions

| Action     | When                                 | What happens                                   |
| ---------- | ------------------------------------ | ---------------------------------------------- |
| `execute`  | Consensus or Monarch confident       | Wave plan sent to Murder for execution         |
| `debate`   | Disagreement worth resolving         | Round 2 with full transparency                 |
| `escalate` | Can't resolve, human judgment needed | Notification sent to founder with full context |

---

### Round 2: Debate (if needed)

Triggered when Monarch sets `action: "debate"`. Advisors now receive **additional context**:

```json
{
  "round_1_votes": [ ... ],
  "monarch_synthesis": "Security raised a valid point about rate limiting. Can we resolve this without deferring payment?",
  "specific_question": "Can auth rate limiting be task #1 in the wave, unblocking payment to start after?"
}
```

Key differences from Round 1:

- Advisors see ALL Round 1 votes (full transparency)
- Advisors can **change their vote** based on new information
- Only advisors relevant to the disagreement need to vote (others can skip)

**Example resolution:**

```json
{
  "advisor": "security",
  "vote": "APPROVE_WITH_CONDITION",
  "condition": "Rate limiting must ship and pass tests before payment crow starts",
  "reasoning": "Ordering constraint resolves my concern. Rate limiter is a 2-hour task.",
  "confidence": 0.78,
  "changed_from": "BLOCK"
}
```

---

### Round 3: Final Call (rare)

If Round 2 doesn't resolve, one more round. Same format as Round 2 but with Round 2 results visible.

After Round 3, Monarch MUST either decide or escalate. No Round 4.

---

## Round Limits & Cost

```
Max rounds:     3 (hard limit — resource discipline)
Round 1:        All 6 advisors in parallel
Round 2:        Only disagreeing advisors (2-4 typically)
Round 3:        Only if still unresolved (rare, 1-3 advisors)
After 3 rounds: Monarch decides OR escalates to human
```

### Cost Model

| Scenario                        | Advisors  | Rounds | Cost        |
| ------------------------------- | --------- | ------ | ----------- |
| Consensus (typical)             | 6         | 1      | ~$0.09      |
| Minor disagreement              | 6 + 3     | 2      | ~$0.13      |
| Major disagreement              | 6 + 4 + 2 | 3      | ~$0.18      |
| Amortized per task (wave of 10) | —         | —      | ~$0.01-0.02 |

Each advisor call: ~$0.015 (Sonnet, ~2000 tokens in, ~500 out).

---

## Human Override

The founder can intervene at any point:

| Action              | Description                                              | Recorded As                                      |
| ------------------- | -------------------------------------------------------- | ------------------------------------------------ |
| **Override block**  | "Ship payment despite Security concern"                  | `human_override: { advisor_overridden, reason }` |
| **Request round**   | "Ask Security about OAuth token storage specifically"    | Triggers targeted Round 2                        |
| **Add constraint**  | "OK to payment but must add Stripe webhook verification" | `human_constraint: { text }`                     |
| **Dismiss advisor** | "Ignore Market for this wave, I know what to build"      | `advisor_dismissed: { advisor, reason }`         |
| **Force decision**  | "Build auth first, no debate needed"                     | `human_decision: { wave_plan, reasoning }`       |

### Override Record

```json
{
  "human_override": {
    "action": "override_block",
    "advisor_overridden": "security",
    "reason": "Founder accepted risk: rate limiting will be added in Wave 4",
    "timestamp": "2026-03-14T10:05:00Z"
  }
}
```

Overrides are critical training data — they teach the model where human judgment diverges from advisor recommendations.

---

## DynamoDB Storage

Council sessions are council-level snapshots in the recursive tree:

```
PK: T#{tenant}#P#{project}
SK: S#{wave_id}#council_{session_id}
```

### Full Council Snapshot

```json
{
  "PK": "T#acme#P#cawnex",
  "SK": "S#w003#council_001",
  "level": "council",
  "status": "completed",

  "ask": "What should Wave 3 contain?",
  "context": {
    "human_directive": "Ship onboarding in 2 weeks",
    "project_phase": "execution",
    "available_mvis": ["mvi_auth", "mvi_onboarding", "mvi_payment"]
  },

  "rounds": [
    {
      "round": 1,
      "votes": [
        {
          "advisor": "security",
          "vote": "BLOCK",
          "scores": { "mvi_auth": 9, "mvi_onboarding": 6, "mvi_payment": 3 },
          "reasoning": "Payment without auth hardening is a liability.",
          "blockers": ["No rate limiting", "No CSRF"],
          "confidence": 0.85,
          "suggested_crows": ["implementer", "tester", "security-auditor"]
        },
        {
          "advisor": "quality",
          "vote": "APPROVE",
          "scores": { "mvi_auth": 7, "mvi_onboarding": 8, "mvi_payment": 5 },
          "reasoning": "All three are well-specified. Auth tests should cover edge cases.",
          "confidence": 0.72
        },
        {
          "advisor": "performance",
          "vote": "APPROVE",
          "scores": { "mvi_auth": 6, "mvi_onboarding": 7, "mvi_payment": 8 },
          "reasoning": "No performance concerns at this stage.",
          "confidence": 0.68
        },
        {
          "advisor": "market",
          "vote": "APPROVE",
          "scores": { "mvi_auth": 5, "mvi_onboarding": 9, "mvi_payment": 8 },
          "reasoning": "Onboarding is highest priority for user acquisition. Payment enables revenue.",
          "confidence": 0.9
        },
        {
          "advisor": "maturity",
          "vote": "APPROVE",
          "scores": { "mvi_auth": 8, "mvi_onboarding": 6, "mvi_payment": 4 },
          "reasoning": "Auth is foundational. Three MVIs in one wave is aggressive but feasible.",
          "confidence": 0.65
        },
        {
          "advisor": "clarity",
          "vote": "APPROVE",
          "scores": { "mvi_auth": 8, "mvi_onboarding": 7, "mvi_payment": 7 },
          "reasoning": "All specs are clear. Payment has well-defined Stripe integration docs.",
          "confidence": 0.8
        }
      ],
      "consensus": false,
      "blocker": "security"
    },
    {
      "round": 2,
      "question": "Can auth rate limiting be task #1 in the wave, unblocking payment?",
      "votes": [
        {
          "advisor": "security",
          "vote": "APPROVE_WITH_CONDITION",
          "condition": "Rate limiting must ship before payment starts",
          "reasoning": "Ordering constraint resolves my concern. Rate limiter is a 2-hour task.",
          "confidence": 0.78,
          "changed_from": "BLOCK"
        },
        {
          "advisor": "market",
          "vote": "APPROVE",
          "reasoning": "Acceptable if payment ships in same wave.",
          "confidence": 0.88
        }
      ],
      "consensus": true
    }
  ],

  "decision": {
    "actor": "monarch",
    "action": "execute",
    "wave_plan": ["mvi_auth", "mvi_onboarding", "mvi_payment"],
    "ordering_constraints": [
      "mvi_auth MUST complete before mvi_payment starts"
    ],
    "reasoning": "Security concern resolved with ordering constraint. All three MVIs fit in 2-week directive.",
    "dissent_record": {
      "security_initial_block": "Rate limiting missing — resolved by making it prerequisite",
      "maturity_concern": "Three MVIs in one wave is aggressive — noted but within directive"
    },
    "confidence": 0.8
  },

  "cost": {
    "round_1": {
      "calls": 6,
      "tokens_in": 12000,
      "tokens_out": 3000,
      "credits": 0.09
    },
    "round_2": {
      "calls": 2,
      "tokens_in": 5000,
      "tokens_out": 1200,
      "credits": 0.04
    },
    "total_credits": 0.13
  },

  "created_at": "2026-03-14T10:00:00Z",
  "completed_at": "2026-03-14T10:00:45Z",
  "entityType": "Snapshot"
}
```

---

## Advisor Prompt Structure

Each advisor gets a layered system prompt:

```python
def build_advisor_prompt(advisor_type, org_id, project_id, decision_context):
    return [
        # Layer 1: Advisor identity and role (static, cached)
        load(f"prompts/advisors/{advisor_type}.md"),

        # Layer 2: Org standards (cached, rarely changes)
        load(f"dynasty/{org_id}/MEMORY.md"),

        # Layer 3: Project context (cached per project)
        load(f"dynasty/{org_id}/court/{project_id}/MEMORY.md"),

        # Layer 4: Advisor's own memory (evolves over time)
        load(f"dynasty/{org_id}/agents/{advisor_type}.md"),

        # Layer 5: Decision context (unique per session)
        decision_context
    ]
```

**Prompt caching:** Layers 1-3 rarely change → ~90% token discount on repeated calls. Layer 4 is small (~2000 tokens). Layer 5 is the only variable cost.

---

## Advisor Evolution

After each wave completes, the Monarch runs a **reflection step**:

```
Input:
  - Wave results (what shipped, what failed)
  - Council decisions that shaped this wave
  - Human overrides (where founder disagreed with council)
  - Outcomes (bugs reported? tests passing? user feedback?)

Output per advisor (0-3 learnings each):
  - security: "Rate limiting was valid — prevented DDoS during load testing"
  - market: "Founder prioritizes shipping over polish — adjust future scoring"
  - maturity: "Three MVIs per wave worked — threshold is higher than estimated"
  - quality: "FastAPI projects need explicit test for async middleware"
```

Learnings append to `dynasty/{org}/agents/{advisor_type}.md`. Pruned when over ~2000 token budget (old entries summarized).

### Evolution Example

**Month 1 — Security advisor memory:**

```
- Auth endpoints need rate limiting (learned from Wave 3 block)
```

**Month 3 — Security advisor memory:**

```
- Auth endpoints need rate limiting (learned from Wave 3 block)
- FastAPI CORS config must explicitly list allowed origins (Wave 7 vulnerability)
- DynamoDB IAM policies should use least-privilege per Lambda (Wave 9 audit)
```

**Month 6 — Security advisor memory (pruned):**

```
- This project uses FastAPI + DynamoDB. Key security patterns:
  - Rate limiting on all public endpoints (enforced since Wave 3)
  - Explicit CORS origin lists, never wildcard (learned Wave 7)
  - Least-privilege IAM per Lambda function (learned Wave 9)
  - JWT token rotation every 8 hours (established Wave 12)
- Founder tends to override security for shipping speed — flag high-risk items explicitly
```

---

## Execution Flow

```
Human directive arrives
    │
    ▼
Monarch decides: does this need Council?
    │
    ├── No (routine) → Murder dispatches directly
    │
    └── Yes (decision point) → Convene Council
         │
         ▼
    Round 1: 6 advisors in parallel (~$0.09, ~15 seconds)
         │
         ├── Consensus → Monarch executes
         │
         ├── Disagreement → Round 2 debate (~$0.04, ~10 seconds)
         │    │
         │    ├── Resolved → Monarch executes
         │    │
         │    └── Still stuck → Round 3 final call (~$0.03, ~8 seconds)
         │         │
         │         ├── Resolved → Monarch executes
         │         │
         │         └── Deadlock → Escalate to human
         │
         └── BLOCK (veto) → Debate or escalate
              │
              ├── Resolvable with constraint → Round 2
              │
              └── Fundamental disagreement → Escalate to human
```

---

## Training Data Value

Council sessions produce the richest training data in the system:

| Signal            | Training Value                                                   |
| ----------------- | ---------------------------------------------------------------- |
| Advisor scores    | Priority assessment across dimensions                            |
| Disagreements     | Where trade-offs exist between concerns                          |
| Resolution path   | How tensions get resolved (constraint, debate, override)         |
| Human overrides   | Where AI judgment diverges from human judgment                   |
| Outcomes          | Whether the decision led to good results (bugs, rework, success) |
| Advisor evolution | How specialized judgment improves with experience                |

A fine-tuned model trained on thousands of council sessions would learn to:

- Score priorities across multiple dimensions simultaneously
- Identify when security concerns are real vs overly cautious
- Predict which decisions founders typically override
- Suggest constraints that resolve disagreements without blocking

---

## Design Principles Summary

1. **Parallel, not sequential** — advisors are independent, no groupthink
2. **Max 3 rounds** — resource discipline, converge or escalate
3. **Two veto powers** — Security and Clarity can BLOCK, others influence through scoring
4. **Dissent preserved** — disagreement is recorded, not suppressed
5. **Human can override anything** — the system advises, never dictates
6. **Advisors evolve** — memory accumulates per advisor, pruned to token budget
7. **Cost-efficient** — ~$0.09 per consensus, ~$0.27 worst case, amortized across wave tasks
