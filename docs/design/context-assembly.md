# Context Assembly — What Each Crow Receives

> Problem #8: Scoped context, not full repo every time.
> Each crow gets exactly what it needs — no more, no less.

---

## The 5-Layer Prompt

Every crow receives the same 5 layers. Content differs by crow type.

```
Layer 1: Identity       WHO you are        (static per crow type, cached)
Layer 2: Dynasty        ORG standards      (cached, shared across all crows)
Layer 3: Project        PROJECT context    (cached, project-specific)
Layer 4: Specialization LEARNINGS          (evolves, crow-type-specific)
Layer 5: Task           WHAT to do         (unique per invocation)
```

Layers 1-3 hit prompt cache (~90% token discount). Layer 4 is small (~2000 tokens). Layer 5 is the variable cost.

---

## Context by Crow Type

### Planner Crow

Sees the big picture. Never writes code.

**Identity prompt:**

```
You are a Planner crow. You break work into tasks.
Output structured JSON with tasks, each ≤8 hours human equivalent.
Never write code. Never implement. Only plan.
```

**Task context (Layer 5):**

| Included                                                | Why                                   |
| ------------------------------------------------------- | ------------------------------------- |
| MVI description and acceptance criteria                 | What to plan for                      |
| File tree of the repo (full listing, no contents)       | Understand project structure          |
| Key files: README, package.json, configs                | Understand tech stack and conventions |
| Existing test structure (what's tested, what's not)     | Know where tests need to be added     |
| Previous planner outputs for this project (from memory) | Avoid repeating past mistakes         |

| NOT Included        | Why                                         |
| ------------------- | ------------------------------------------- |
| Full source code    | Planner doesn't need implementation details |
| Git history         | Not relevant to planning                    |
| Other MVIs' details | Scope isolation                             |

**Token budget:** ~10K in, ~2K out

**Output contract:**

```json
{
  "tasks": [
    {
      "name": "Token validation middleware",
      "description": "Create async middleware for JWT validation",
      "human_estimate_hours": 4,
      "files_to_read": ["src/auth/jwt.py", "src/middleware/__init__.py"],
      "files_to_modify": [
        "src/middleware/auth.py",
        "tests/test_auth_middleware.py"
      ],
      "acceptance_criteria": [
        "Validates JWT on protected routes",
        "Returns 401 with clear error"
      ]
    }
  ],
  "context_files": ["src/config.py", "src/models/user.py"],
  "summary": "3 tasks, estimated 12 hours human equivalent"
}
```

---

### Implementer Crow

Sees specific files from the plan. Not the full repo.

**Identity prompt:**

```
You are an Implementer crow. You write production-quality code.
Follow the project's conventions. Write tests for new code.
Output JSON with file changes: {path, action, content}.
Only modify files relevant to your task.
```

**Task context (Layer 5):**

| Included                                                      | Why                                  |
| ------------------------------------------------------------- | ------------------------------------ |
| Task description from planner                                 | What to implement                    |
| Acceptance criteria                                           | Definition of done                   |
| Specific files to read (from planner's `files_to_read[]`)     | Understand existing code             |
| Specific files to modify (from planner's `files_to_modify[]`) | Know what to change                  |
| Content of those files (full source)                          | Need actual code to modify           |
| Related test files                                            | Write tests alongside implementation |
| Previous implementation attempts (if retry)                   | Don't repeat failed approach         |

| NOT Included             | Why                             |
| ------------------------ | ------------------------------- |
| Full file tree           | Planner already scoped the work |
| Files outside task scope | Avoid accidental changes        |
| Other tasks' details     | Scope isolation                 |
| Git history              | Not relevant to implementation  |

**Token budget:** ~30K in, ~8K out

**Output contract:**

```json
{
  "changes": [
    {
      "path": "src/middleware/auth.py",
      "action": "create",
      "content": "full file content..."
    },
    {
      "path": "tests/test_auth_middleware.py",
      "action": "create",
      "content": "full file content..."
    }
  ],
  "commit_message": "feat: add JWT token validation middleware",
  "summary": "Created async token validation with 94% test coverage"
}
```

---

### Reviewer Crow

Sees only what changed. Judges, never writes code.

**Identity prompt:**

```
You are a Reviewer crow. You review code changes for quality,
security, performance, and correctness against acceptance criteria.
Output JSON verdict: {approved, issues[], suggestions[], summary}.
Also output plan_vs_execution comparing what was planned vs what was built.
You do NOT write code. You judge code.
```

**Task context (Layer 5):**

| Included                                            | Why                          |
| --------------------------------------------------- | ---------------------------- |
| Original task description and acceptance criteria   | Judge against intent         |
| Planner's plan (what was supposed to happen)        | Plan-vs-execution comparison |
| Git diff (what actually changed)                    | The thing being reviewed     |
| Changed files (full content of modified files only) | Context around the diff      |
| Test results (pass/fail summary)                    | Quality signal               |
| Previous review feedback (if re-review after fix)   | Track improvement            |

| NOT Included         | Why                           |
| -------------------- | ----------------------------- |
| Unchanged files      | Noise — focus on what changed |
| Full repo tree       | Not relevant to review        |
| Other tasks' changes | Scope isolation               |

**Token budget:** ~15K in, ~2K out

**Output contract:**

```json
{
  "approved": false,
  "issues": [
    "No test for token expiration edge case",
    "Missing rate limit header"
  ],
  "suggestions": [
    "Consider using a decorator pattern for cleaner middleware chain"
  ],
  "summary": "Implementation is solid but missing edge case test coverage.",
  "plan_vs_execution": [
    {
      "step": 1,
      "crow": "planner",
      "plan": "Create Zod validation schemas",
      "executed": "Created Zod schemas for registration, login, and profile",
      "deviation": null
    },
    {
      "step": 2,
      "crow": "implementer",
      "plan": "Add validation middleware",
      "executed": "Added validation + refactored error handler",
      "deviation": "Deviated: refactored existing error handler. Low risk, improves consistency."
    }
  ],
  "confidence": "high",
  "findings": [
    { "text": "Zod schemas with proper error messages", "type": "check" },
    { "text": "Email regex doesn't match RFC 5322", "type": "warning" }
  ]
}
```

---

### Fixer Crow

Sees the reviewer's feedback and current code. Makes minimal targeted changes.

**Identity prompt:**

```
You are a Fixer crow. You fix specific issues identified by the Reviewer.
Make minimal, targeted changes. Do not refactor beyond what's needed.
Do not change code that the Reviewer did not flag.
Output JSON with file changes, same format as Implementer.
```

**Task context (Layer 5):**

| Included                                         | Why                          |
| ------------------------------------------------ | ---------------------------- |
| Original task description                        | Context for the fix          |
| Reviewer's issues[] (specific problems)          | Exactly what to fix          |
| Reviewer's suggestions[] (optional improvements) | Nice-to-haves if feasible    |
| Current file contents (post-implementation)      | Code to modify               |
| Git diff from implementation                     | Understand what was changed  |
| Test results (which tests fail and why)          | Fix failing tests            |
| Previous fix attempts (if retry #2+)             | Don't repeat same failed fix |

| NOT Included    | Why                                          |
| --------------- | -------------------------------------------- |
| Full repo       | Fixer works on specific files only           |
| Planner's plan  | Fixer works from reviewer feedback, not plan |
| Unrelated files | Scope isolation                              |

**Token budget:** ~20K in, ~4K out

---

### Documenter Crow

Sees what shipped, not how it was built.

**Identity prompt:**

```
You are a Documenter crow. You update project documentation
to reflect shipped changes. Update README, API docs, changelog.
Write clear, concise docs for end users and developers.
Do not explain implementation details unless they affect the API contract.
```

**Task context (Layer 5):**

| Included                                         | Why                              |
| ------------------------------------------------ | -------------------------------- |
| MVI summary (what was delivered)                 | What to document                 |
| Git diff summary (files changed, not full diff)  | Scope of changes                 |
| Existing docs: README.md, API docs, CHANGELOG.md | What to update                   |
| PR descriptions from shipped tasks               | Human-readable summaries         |
| Acceptance criteria                              | What the user-facing behavior is |

| NOT Included           | Why                                                  |
| ---------------------- | ---------------------------------------------------- |
| Full source code       | Documenter writes about behavior, not implementation |
| Test files             | Not relevant to docs                                 |
| Implementation details | Users don't need to know internals                   |
| Reviewer feedback      | Internal process, not docs                           |

**Token budget:** ~10K in, ~4K out

---

### Council Advisors

Each advisor gets lens-specific context for decision-making.

**Shared identity pattern:**

```
You are the {advisor_type} advisor. You evaluate decisions through
the lens of {lens_description}.
{veto_clause if applicable}
Output JSON: {scores, reasoning, blockers[], vote, confidence}.
```

**Advisor-specific context:**

| Advisor         | Extra Context                                                                                              | NOT Included                       |
| --------------- | ---------------------------------------------------------------------------------------------------------- | ---------------------------------- |
| **Security**    | Auth/security implementation summary, known vulnerabilities (from memory), OWASP guidelines for tech stack | Business metrics, UI details       |
| **Quality**     | Test coverage stats, linting results, code complexity metrics                                              | Business metrics, security details |
| **Performance** | Endpoint latency data, DB query patterns, caching config                                                   | Auth details, UI details           |
| **Market**      | Human directive, project phase, competitor context (from memory)                                           | Source code, infra details         |
| **Maturity**    | Tech debt notes (from memory), dependency versions, refactoring history                                    | Business metrics, security details |
| **Clarity**     | Acceptance criteria, spec documents, glossary                                                              | Source code, infra details         |

**Token budget per advisor:** ~5K in, ~1K out

---

## Context Assembly Algorithm

```python
def assemble_context(crow_type, task, wave, project, dynasty):
    """Murder assembles this before dispatching a crow."""

    # Layer 1: Identity (static, from prompts/ directory)
    identity = load_prompt(f"prompts/crows/{crow_type}.md")

    # Layer 2: Dynasty standards (cached, rarely changes)
    dynasty_context = load_memory(f"dynasty/{dynasty.id}/MEMORY.md")

    # Layer 3: Project context (cached per project)
    project_context = load_memory(
        f"dynasty/{dynasty.id}/court/{project.id}/MEMORY.md"
    )

    # Layer 4: Specialization memory (evolves)
    specialization = load_memory(
        f"dynasty/{dynasty.id}/agents/{crow_type}.md"
    )

    # Layer 5: Task-specific context (unique per invocation)
    task_context = build_task_context(crow_type, task, wave, project)

    # Assemble with cache boundaries
    return {
        "system": [identity, dynasty_context, project_context, specialization],
        "user": task_context,
    }


def build_task_context(crow_type, task, wave, project):
    """Build Layer 5 — the variable part, scoped per crow type."""

    if crow_type == "planner":
        return {
            "mvi": task.mvi_description,
            "acceptance_criteria": task.acceptance_criteria,
            "file_tree": gather_file_tree(project.repo),
            "key_files": read_key_files(project.repo),
            "test_structure": summarize_tests(project.repo),
        }

    elif crow_type == "implementer":
        plan = get_planner_output(task)
        return {
            "task": task.description,
            "acceptance_criteria": task.acceptance_criteria,
            "files_to_read": read_files(plan.files_to_read),
            "files_to_modify": read_files(plan.files_to_modify),
            "related_tests": read_test_files(plan.files_to_modify),
            "previous_attempts": get_previous_attempts(task),
        }

    elif crow_type == "reviewer":
        plan = get_planner_output(task)
        impl = get_implementer_output(task)
        return {
            "task": task.description,
            "acceptance_criteria": task.acceptance_criteria,
            "plan": plan.summary,
            "git_diff": impl.git_diff,
            "changed_files": read_changed_files(impl),
            "test_results": impl.test_results,
            "previous_reviews": get_previous_reviews(task),
        }

    elif crow_type == "fixer":
        review = get_reviewer_output(task)
        impl = get_implementer_output(task)
        return {
            "task": task.description,
            "issues": review.issues,
            "suggestions": review.suggestions,
            "current_files": read_changed_files(impl),
            "git_diff": impl.git_diff,
            "test_failures": impl.test_failures,
            "previous_fixes": get_previous_fixes(task),
        }

    elif crow_type == "documenter":
        return {
            "mvi_summary": task.mvi_summary,
            "diff_summary": task.diff_summary,
            "existing_docs": read_doc_files(project.repo),
            "pr_descriptions": task.pr_descriptions,
            "acceptance_criteria": task.acceptance_criteria,
        }
```

---

## Context Flow Through the Pipeline

```
                    Planner
                    sees: file tree + key files
                    produces: plan (tasks, files_to_read, files_to_modify)
                        │
                        ▼
                    Implementer
                    sees: plan + specific files from plan
                    produces: code changes + git diff
                        │
                        ▼
                    Reviewer
                    sees: plan + diff + changed files + acceptance criteria
                    produces: verdict + issues + plan-vs-execution
                        │
                    ┌───┴───┐
                    │       │
                approved  rejected
                    │       │
                    │       ▼
                    │   Fixer
                    │   sees: reviewer issues + current files + diff
                    │   produces: targeted fixes
                    │       │
                    │       └──► Reviewer (re-review)
                    │
                    ▼
                Documenter
                sees: MVI summary + diff summary + existing docs
                produces: updated docs
```

Each step passes **artifacts forward**, not raw context. The planner's output tells the implementer which files to read. The implementer's diff tells the reviewer what changed. The reviewer's issues tell the fixer what's wrong.

This is the **scoped context chain** — each crow gets exactly what it needs from the previous step's output.

---

## Large Repo Strategy

For repos with hundreds of files, the planner can't read everything.

### Tiered File Reading

```
Tier 1 — Always included (cheap):
  - File tree (just paths, no content)
  - README.md
  - package.json / pyproject.toml / Cargo.toml
  - Config files: tsconfig.json, .env.example
  - CLAUDE.md (if present)

Tier 2 — Included if small:
  - Entry points: main.py, app.ts, index.html
  - Directory READMEs
  - Schema files: schema.prisma, models.py

Tier 3 — On-demand (planner requests):
  - Planner output includes "context_files" it wants to read
  - Murder reads them and passes to implementer
  - NOT sent back to planner (avoid round-trip)
```

### Token Budget Guards

```
Max context per crow type:
  Planner:      15K tokens input
  Implementer:  40K tokens input
  Reviewer:     20K tokens input
  Fixer:        25K tokens input
  Documenter:   15K tokens input
  Advisor:       8K tokens input

If context exceeds budget:
  1. Summarize large files (first 100 + last 50 lines)
  2. Truncate file tree to relevant directories
  3. Omit test files if not directly relevant
  4. Reference S3 for full content (crow can request via tool)
```

---

## Token Budget Summary

| Crow                 | Input    | Output   | Cost (Sonnet) | Cost (Opus) |
| -------------------- | -------- | -------- | ------------- | ----------- |
| Planner              | ~10K     | ~2K      | ~$0.06        | ~$0.30      |
| Implementer          | ~30K     | ~8K      | ~$0.21        | ~$1.05      |
| Reviewer             | ~15K     | ~2K      | ~$0.08        | ~$0.38      |
| Fixer                | ~20K     | ~4K      | ~$0.12        | ~$0.60      |
| Documenter           | ~10K     | ~4K      | ~$0.09        | ~$0.45      |
| **Full pipeline**    |          |          | **~$0.56**    | **~$2.78**  |
| Council (6 advisors) | ~5K each | ~1K each | **~$0.09**    | **~$0.45**  |

With prompt caching on layers 1-3 (~90% discount), actual cost is ~40-60% of these estimates.

---

## Prompt Caching Strategy

```
┌─────────────────────────────────────────────┐
│ CACHE BLOCK (layers 1-3, rarely changes)    │
│                                             │
│ Layer 1: Crow identity prompt               │
│ Layer 2: Dynasty MEMORY.md                  │
│ Layer 3: Project MEMORY.md                  │
│                                             │
│ Cache hit rate: ~90%                        │
│ Token discount: ~90%                        │
├─────────────────────────────────────────────┤
│ EPHEMERAL (layers 4-5, changes per call)    │
│                                             │
│ Layer 4: Specialization memory (~2K tokens) │
│ Layer 5: Task context (varies by crow type) │
│                                             │
│ Always full price                           │
└─────────────────────────────────────────────┘
```

Layers 1-3 are sent as the `system` prompt (cacheable). Layers 4-5 are sent as the `user` message.

---

## Design Principles

1. **Scoped, not full** — each crow gets only what it needs
2. **Artifacts forward** — each step's output becomes the next step's input
3. **Planner decides scope** — it identifies which files matter, implementer reads only those
4. **Reviewer never sees full repo** — only the diff and changed files
5. **Fixer works from feedback** — reviewer issues, not the original plan
6. **Token budgets enforced** — hard limits per crow type, summarize if exceeded
7. **Prompt caching on stable layers** — 90% discount on identity + org + project context
8. **Large repos handled gracefully** — tiered file reading, on-demand context
