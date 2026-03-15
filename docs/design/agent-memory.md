# Agent Memory — Layered CLAUDE.md Pattern

> Agents get smarter over time without starting from zero each execution.
> Not RAG. Not a database. Just curated markdown files with token budgets.

---

## The Problem

Every time a crow executes, it starts from scratch. It doesn't know:

- "Last time we changed auth middleware, tests broke because of X"
- "This project uses camelCase and pytest"
- "The founder hates verbose PRs"

Without memory, the system repeats the same mistakes and ignores hard-won learnings.

---

## Three Memory Layers

### 1. Dynasty Memory (org-wide)

```
Storage: /dynasty/{org}/MEMORY.md
Scope:   All projects, all crows in this org
Content: Tech stack standards, founder preferences, org policies
Example: "Always use TypeScript strict mode. Founder prefers short PR descriptions."
```

### 2. Project Memory (per project)

```
Storage: /dynasty/{org}/court/{project}/MEMORY.md
         /dynasty/{org}/court/{project}/conventions.md
         /dynasty/{org}/court/{project}/mistakes.md
Scope:   All crows working on this project
Content: Codebase patterns, architecture decisions, past mistakes
Example: "FastAPI middleware needs async pattern. DynamoDB uses single-table design."
```

### 3. Specialization Memory (per crow type, cross-project)

```
Storage: /dynasty/{org}/agents/{crow_type}.md
Scope:   All instances of this crow type, across all projects
Content: Learnings specific to this role
Example: (reviewer) "PRs touching both API and frontend need extra scrutiny"
         (security) "FastAPI projects commonly miss rate limiting on auth"
```

---

## Context Assembly

When Murder dispatches a crow, it loads memory into the system prompt:

```python
system_prompt = [
    load("prompts/crows/{crow_type}.md"),              # identity (static)
    load("dynasty/{org}/MEMORY.md"),                    # org standards (cached)
    load("dynasty/{org}/court/{project}/MEMORY.md"),    # project learnings (cached)
    load("dynasty/{org}/agents/{crow_type}.md"),        # specialization (evolves)
]
# + Prompt caching on layers 1-3 (~90% discount)
```

---

## How Memory Grows

### After Each Execution (Murder reflection)

```
Murder reads:  execution trace (what happened, what failed, what succeeded)
Murder asks:   "What should we remember for next time?"
Claude output: 0-3 learnings
Murder writes: append to appropriate memory file
```

### After Each Wave (Monarch reflection)

```
Monarch reads: all wave executions + council decisions + human feedback
Monarch asks:  "What should each advisor and project remember?"
Claude output: project-level and specialization-level learnings
Monarch prunes: remove outdated entries, keep files under token budget
```

---

## Token Budget & Pruning

Each memory file has a ~2000 token budget. When full:

1. Old entries get summarized (3 similar learnings → 1 consolidated entry)
2. Outdated entries removed (if the codebase changed and the learning no longer applies)
3. Most impactful entries preserved (learnings that prevented bugs or saved time)

### Evolution Example

**Month 1 — Security advisor memory:**

```
- Auth endpoints need rate limiting (learned from Wave 3 block)
```

**Month 3 — Security advisor memory:**

```
- Auth endpoints need rate limiting (Wave 3)
- FastAPI CORS must explicitly list origins (Wave 7 vulnerability)
- DynamoDB IAM: least-privilege per Lambda (Wave 9 audit)
```

**Month 6 — Security advisor memory (pruned & summarized):**

```
This project uses FastAPI + DynamoDB. Key security patterns:
- Rate limiting on all public endpoints (enforced since Wave 3)
- Explicit CORS origin lists, never wildcard (Wave 7)
- Least-privilege IAM per Lambda (Wave 9)
- JWT rotation every 8 hours (Wave 12)
- Founder tends to override security for speed — flag high-risk items explicitly
```

---

## Human Can See and Edit Memory

Memory files are just markdown. The iOS app (Settings) shows them. The founder can:

- Read what the AI has learned about their project
- Edit entries ("actually, we switched from REST to GraphQL")
- Delete entries ("this is no longer relevant")
- Add entries ("always use UTC timestamps")

---

## Why Not RAG

| Concern           | RAG                                             | CLAUDE.md Pattern                 |
| ----------------- | ----------------------------------------------- | --------------------------------- |
| Memory size       | Millions of documents                           | Dozens of learnings               |
| Infrastructure    | Vector DB, embedding pipeline, retrieval tuning | Markdown files in S3              |
| Relevance         | Needs similarity search                         | All memory fits in context window |
| Cost              | Embedding + storage + retrieval per query       | Zero (included in prompt, cached) |
| Accuracy          | Can retrieve irrelevant results                 | Curated, always relevant          |
| Growth management | Index grows unbounded                           | Token budget with pruning         |

**If memory ever gets too large for context, summarization is the answer, not search.**

---

## DynamoDB Storage

```
Per-project memory:
  PK: T#{tenant}#P#{project}
  SK: MEM#{level}#{topic}

Dynasty memory:
  PK: T#{tenant}#DYNASTY
  SK: MEM#dynasty#{topic}
  SK: MEM#agent#{crow_type}
```

Also stored in S3 as markdown files for prompt assembly:

```
s3://cawnex-memory/{tenant}/dynasty/MEMORY.md
s3://cawnex-memory/{tenant}/court/{project}/MEMORY.md
s3://cawnex-memory/{tenant}/agents/{crow_type}.md
```

DynamoDB is the source of truth. S3 is the read cache for Lambda prompt assembly.
