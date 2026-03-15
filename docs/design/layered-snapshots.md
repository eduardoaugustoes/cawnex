# Layered Snapshots — Core Data Structure

> The data structure IS the algorithm.
> Like git's tree/blob/commit model made branches cheap and merging natural,
> our recursive snapshot model makes traceability, rewind, budget tracking,
> and training data generation fall out as natural byproducts.

---

## The Insight

Every level of the orchestration — wave, council, murder, crow — produces the same thing: a **snapshot** recording ask → reasoning → execution → outcome. These snapshots nest recursively, like directories in a file system.

---

## The 3D Matrix

Work can be visualized as a 3D matrix:

```
X axis: Features (auth, onboarding, payment)
Y axis: Concerns/perspectives (security, quality, performance, implementation)
Z axis: Time/waves (evolution)
```

Slicing this matrix answers different questions:

| Slice                               | Question Answered                       |
| ----------------------------------- | --------------------------------------- |
| Horizontal (top layer)              | What's the current state?               |
| Vertical (one feature, all waves)   | How did auth evolve over time?          |
| By concern (one column, all layers) | How has security improved across waves? |
| Peel a layer                        | Revert a wave's work                    |
| Sum through layers                  | Total budget spent on any dimension     |

---

## The Snapshot Primitive

Every snapshot at every level has the same shape:

```
Snapshot {
    ask              what was requested
    context          project phase, tech stack, existing code summary

    decisions [
        { advisor, score, reasoning, recommendation }    council votes
        { monarch, final_decision }                       monarch call
        { dissent: [...] }                                disagreements recorded
    ]

    cycles [                                              feedback loop
        {
            plan,
            tasks: [ { crow, input, output, git_diff } ],
            review: { approved, issues },
        }
        // rejected cycles preserved as context for next cycle
    ]

    git_commit       sha of the final approved code
    human_approved   bool
    cost             { tokens, credits, time }

    // long-term signal (updated retroactively)
    bugs_reported    count (updated weeks later)
    reverted         bool
    tech_debt        bool
    learning         extracted insight for memory
}
```

---

## Recursive Nesting

Snapshots nest — each level contains child snapshots of the level below:

```
Wave Snapshot
  ask: "Ship onboarding in 2 weeks"
  cost: sum of all council snapshots
  │
  ├── Council Snapshot
  │     ask: "Auth with OAuth or session-based?"
  │     decisions: [6 advisor votes + dissent]
  │     cost: sum of all murder snapshots
  │     │
  │     ├── Murder Snapshot (MVI)
  │     │     ask: "Implement OAuth auth endpoint"
  │     │     cost: sum of all crow snapshots
  │     │     │
  │     │     ├── Crow Snapshot (planner)
  │     │     │     ask: "Plan the OAuth implementation"
  │     │     │     cost: { tokens: 2500, credits: 0.04 }
  │     │     │
  │     │     ├── Crow Snapshot (implementer)
  │     │     │     ask: "Write token validation middleware"
  │     │     │     cost: { tokens: 5000, credits: 0.08 }
  │     │     │     git_commit: "abc123"
  │     │     │
  │     │     └── Crow Snapshot (reviewer)
  │     │           ask: "Review the implementation"
  │     │           outcome: { approved: true }
  │     │
  │     └── Murder Snapshot (another MVI)
  │           ...
  │
  └── Council Snapshot (another decision)
        ...
```

**Cost bubbles up automatically** — crow reports actual tokens, murder sums its crows, council sums its murders, wave sums its councils.

**Learning bubbles up selectively** — crow learns "async middleware pattern", murder learns "always run reviewer after implementer", council learns "security concerns on auth were valid".

**Rewind at any level** — revert a crow (redo one task), revert a murder (redo an MVI), revert a council (re-evaluate a decision), revert a wave (scrap the whole batch).

---

## Three Purposes Simultaneously

### 1. Operational

- Rewind to any snapshot at any level
- Budget tracking by summing layers
- Parallel MVIs as independent snapshot stacks
- State transitions tracked in snapshot history

### 2. Memory

- Agents learn from past snapshots in the same project
- Learnings extracted after each execution and wave
- Added to layered CLAUDE.md memory files
- Pruned to token budget when full

### 3. Training Data

Each snapshot is a complete training sample: ask + reasoning + code + outcome + human feedback.

**What makes this training data unique** (vs existing AI coding datasets):

| Existing Data           | Cawnex Snapshots                                            |
| ----------------------- | ----------------------------------------------------------- |
| Code only, no reasoning | Full reasoning chain (council votes, dissent, decisions)    |
| No outcome signal       | Human approved? Tests pass? Bugs later?                     |
| Single-shot             | Failed attempts alongside successful ones (correction data) |
| One perspective         | Multi-perspective judgment (security vs quality vs market)  |
| No feedback loop        | Long-term outcome signal (bugs reported weeks later)        |

---

## The Data Flywheel (Business Moat)

```
Day 1:    Uses off-the-shelf Claude, same as everyone
Month 6:  Thousands of ask→reasoning→code→outcome samples
Month 12: Fine-tune specialized models for code decision reasoning
Year 2:   Unreplicable dataset — requires orchestration + real projects
          + human feedback to produce
```

No competitor can replicate this dataset without building the same orchestration engine, running real projects through it, and collecting human feedback at every gate.

---

## MVI = Branch, Layer = Delta

The snapshot model maps cleanly to git:

- Each MVI works in its own **git branch** (isolation)
- Each layer is a **delta** on top of previous layers (efficient)
- Rewriting an MVI = delete the branch + new snapshot (no sibling impact)
- Wave completion = **synchronized merge** of all MVI branches

---

## DynamoDB Encoding

The recursive tree is encoded in the DynamoDB sort key using materialized paths:

```
PK: T#{tenant}#P#{project}
SK: S#{wave}                              → wave snapshot
SK: S#{wave}#{council}                    → council session
SK: S#{wave}#{council}#{murder}           → murder/MVI snapshot
SK: S#{wave}#{council}#{murder}#{crow}    → crow/task snapshot
```

Full tree for a wave = `SK begins_with S#{wave}` → one query, everything.

See `data-model-v2.md` for complete schema.
