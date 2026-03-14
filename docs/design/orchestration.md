# 🎭 Orchestration — The Murder

> The orchestrator is the product. Everything else is a commodity.

---

## Core Responsibility

The Murder (orchestrator) is the central brain that:

1. **Receives** events (issue created, PR opened, review completed)
2. **Routes** to the correct agent(s)
3. **Monitors** agent execution in real-time
4. **Coordinates** multi-repo changes
5. **Enforces** synchronized merges
6. **Handles** failures and retries

---

## Routing Logic

### V1 — LLM-Based Router (Simple)

For MVP, routing is a single Claude call:

```
System: You are a router. Given an issue and a list of repositories with their CAWNEX.md
files, determine which repositories are affected and what type of agent is needed.

Respond in JSON:
{
  "affected_repos": ["repo-a", "repo-b"],
  "agent_assignments": [
    {"repo": "repo-a", "agent_type": "dev", "reason": "API endpoint change"},
    {"repo": "repo-b", "agent_type": "dev", "reason": "Frontend component update"}
  ],
  "cross_repo_dependencies": [
    {"from": "repo-a", "to": "repo-b", "type": "api_contract"}
  ]
}
```

**Model**: Sonnet (routing is classification, not generation)
**Cost**: Minimal — one call per issue

### V2 — LLM-DFA Router (Advanced)

Formalize the routing into a state machine:

- States: issue types × repo combinations
- Transitions: based on code analysis results
- LLM determines the current state and valid transitions
- More deterministic, fewer hallucination risks

---

## Execution Flow

```python
async def handle_issue(issue: Issue):
    # 1. Refine
    refined = await run_crow("refinement", issue)
    await notify_human(refined)
    await wait_for_approval(refined)

    # 2. Route
    plan = await route_issue(refined)

    # 3. Execute dev crows in parallel
    dev_tasks = []
    for assignment in plan.agent_assignments:
        task = run_crow("dev", refined, assignment.repo)
        dev_tasks.append(task)

    dev_results = await asyncio.gather(*dev_tasks)

    # 4. QA review each PR
    qa_tasks = []
    for result in dev_results:
        if result.pr_url:
            task = run_crow("qa", refined, result.pr_url)
            qa_tasks.append(task)

    qa_results = await asyncio.gather(*qa_tasks)

    # 5. All approved? Merge together
    if all(r.approved for r in qa_results):
        await synchronized_merge(dev_results)
        # 6. Docs update
        await run_crow("docs", refined, merged_prs)
        await notify_team("completed", issue)
    else:
        # Handle rejections
        await handle_qa_rejection(qa_results, dev_results)
```

---

## Synchronized Merge Strategy

The hardest problem. AgentOps's key innovation.

### The Problem

- Backend PR changes API contract
- Frontend PR depends on new API
- If backend merges first and frontend fails → broken state
- If frontend merges first → broken state (API doesn't exist yet)

### The Solution

```
1. All PRs created and reviewed ✅
2. All PRs pass CI ✅
3. Orchestrator verifies no conflicts between PRs
4. Merge ALL PRs in rapid succession (within seconds)
5. If any merge fails → revert all others
```

### Implementation (V1 — GitHub API)

```python
async def synchronized_merge(results: list[DevResult]):
    # Pre-check: all PRs mergeable?
    for r in results:
        status = await github.get_pr_status(r.pr_url)
        if not status.mergeable:
            raise MergeBlockedError(f"PR {r.pr_url} not mergeable")

    # Atomic-ish merge
    merged = []
    try:
        for r in results:
            await github.merge_pr(r.pr_url, method="squash")
            merged.append(r)
    except Exception as e:
        # Rollback: revert merged PRs
        for r in merged:
            await github.revert_merge(r.pr_url)
        raise SynchronizedMergeError(str(e))
```

**Note**: Not truly atomic (GitHub API doesn't support transactions). But fast enough for most cases. True atomicity would require a git-level solution.

---

## Guard — Anti-Hallucination

### Detection Strategies

#### 1. Output Coherence Check

Monitor streaming output for:

- Solving problems not mentioned in the issue
- Creating files in unexpected locations
- Installing dependencies not related to the task
- Repetitive loops (agent doing the same thing multiple times)

#### 2. Scope Boundary Check

- Count files changed vs. expected scope
- Flag if agent modifies files outside its assigned area
- Alert if agent tries to change CI/CD or security config

#### 3. Token Budget Guard

- Set max tokens per execution
- Warn at 80% budget
- Cancel at 100%

#### 4. Time Guard

- Set max execution time per agent type
- Refinement: 5 min, Dev: 15 min, QA: 5 min, Docs: 3 min

#### 5. Conversation Loop Detector

- Track if agent is repeating similar messages
- If >3 similar outputs in sequence → cancel
- This prevents the infinite loop problem Luiz mentioned

### Implementation (V1)

```python
class Guard:
    def __init__(self, execution: Execution):
        self.max_tokens = execution.agent.token_budget
        self.max_time = execution.agent.time_limit
        self.output_history = []

    async def check_event(self, event: Event) -> GuardAction:
        self.output_history.append(event)

        # Token budget
        if self.tokens_used > self.max_tokens:
            return GuardAction.CANCEL

        # Time limit
        if self.elapsed > self.max_time:
            return GuardAction.CANCEL

        # Loop detection (simple: similarity of last 3 outputs)
        if len(self.output_history) >= 3:
            if self._is_loop(self.output_history[-3:]):
                return GuardAction.CANCEL

        # Scope check (files outside expected area)
        if event.type == "file_write":
            if not self._in_scope(event.metadata.file_path):
                return GuardAction.WARN

        return GuardAction.CONTINUE
```

---

## Retry Engine

### Decision Matrix

| Failure Type           | Retryable? | Strategy                         |
| ---------------------- | ---------- | -------------------------------- |
| LLM timeout            | ✅ Yes     | Retry with same context          |
| LLM rate limit         | ✅ Yes     | Exponential backoff              |
| Git conflict           | ✅ Yes     | Pull latest, rebase, retry       |
| Test failure           | ✅ Yes     | Send error to agent, ask for fix |
| QA rejection           | ✅ Yes     | Send feedback to dev agent       |
| Hallucination detected | ❌ No      | Cancel, notify human             |
| Token budget exceeded  | ❌ No      | Cancel, notify human             |
| Repeated failure (>3x) | ❌ No      | Cancel, escalate to human        |
| Auth failure           | ❌ No      | Notify admin                     |

### Max Retries by Agent Type

| Agent      | Max Retries | Backoff             |
| ---------- | ----------- | ------------------- |
| Refinement | 2           | None (fast retry)   |
| Dev        | 3           | Linear (1m, 2m, 3m) |
| QA         | 2           | None                |
| Docs       | 1           | None                |

---

## Context Sharing Between Agents

### What Gets Shared

| From                    | To                                                    | Context Shared |
| ----------------------- | ----------------------------------------------------- | -------------- |
| Refinement → Dev        | Full user story, acceptance criteria, technical notes |
| Orchestrator → Dev      | Other repos' CAWNEX.md (API contracts)                |
| Dev → QA                | PR URL, acceptance criteria, what was implemented     |
| QA → Dev (on rejection) | Specific feedback, failing checks                     |
| Dev → Docs              | Merged PR diff, what changed and why                  |

### Context Format

```json
{
  "issue": {
    "title": "...",
    "refined_story": "...",
    "acceptance_criteria": ["..."],
    "technical_notes": "..."
  },
  "repository": {
    "name": "...",
    "cawnex_md": "...",
    "structure": "..."
  },
  "related_repos": [
    {
      "name": "other-repo",
      "api_contracts": "...",
      "recent_changes": "..."
    }
  ],
  "execution_history": [
    {
      "agent": "refinement",
      "output_summary": "..."
    }
  ]
}
```
