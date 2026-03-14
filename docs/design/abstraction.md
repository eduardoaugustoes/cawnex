# 🧬 Abstraction Layer — Domain-Agnostic Agent Orchestration

> Cawnex is not a code shipping tool. It's an **agent orchestration platform**.
> Code is the first use case. Not the only one.

---

## The Shift

### Before (Coupled)

```
Issue → Refinement Crow → Dev Crow → QA Crow → Docs Crow → Merged PR
```

Every concept was code-specific:

- "Issue" (GitHub)
- "Crow" (hardcoded agent types)
- "PR" (git)
- "Worktree" (git)
- "Merge" (git)
- Tools: read_file, write_file, shell, git

### After (Decoupled)

```
Task → Agent Pipeline → Artifacts
```

Generic concepts that work for ANY domain:

| Coupled (before)             | Decoupled (after)                    | Examples                                                           |
| ---------------------------- | ------------------------------------ | ------------------------------------------------------------------ |
| Issue                        | **Task**                             | GitHub issue, book brief, research question, marketing campaign    |
| Crow (Dev/QA/Docs)           | **Agent** (configurable)             | Code writer, book author, researcher, editor, reviewer, translator |
| PR                           | **Artifact**                         | Pull request, document, report, image, dataset, email draft        |
| Worktree                     | **Workspace**                        | Git worktree, temp directory, cloud storage folder, Google Doc     |
| Merge                        | **Deliver**                          | Git merge, publish, email send, upload, deploy                     |
| GitHub webhook               | **Trigger**                          | Webhook, schedule, API call, chat message, file upload             |
| Git tools                    | **Tool Pack**                        | Git pack, file pack, web pack, writing pack, data pack             |
| Refinement → Dev → QA → Docs | **Workflow** (configurable pipeline) | Code workflow, writing workflow, research workflow                 |

---

## Core Abstractions

### 1. Task (replaces Issue)

A **Task** is any unit of work that enters the system.

```python
class Task:
    id: int
    tenant_id: int
    title: str
    description: str
    source: TaskSource        # github, linear, jira, manual, api, chat, schedule
    source_ref: str           # external ID (issue #, brief ID, etc.)
    source_url: str           # link back to origin
    workflow_id: int          # which pipeline to run
    status: TaskStatus        # pending → refining → approved → in_progress → completed
    context: dict             # arbitrary metadata (repo info, book genre, target audience...)
    artifacts: list[Artifact] # outputs produced
```

### 2. Agent (replaces Crow)

An **Agent** is a configurable autonomous worker. NOT hardcoded types.

```python
class AgentDefinition:
    id: int
    tenant_id: int
    name: str                 # "Code Developer", "Book Author", "QA Reviewer"
    slug: str                 # "code-dev", "book-author", "qa-reviewer"
    description: str
    system_prompt: str        # The agent's personality and instructions
    model: str                # "claude-opus-4-6", "gpt-4.1"
    tool_packs: list[str]     # ["git", "filesystem", "shell"] or ["writing", "web_search"]
    max_tokens: int
    max_time_seconds: int
    retry_policy: dict        # {max_retries: 2, backoff: "linear"}
```

Users CREATE their own agents. We provide templates:

```yaml
# Template: Code Developer
name: Code Developer
system_prompt: prompts/code-dev.md
tool_packs: [git, filesystem, shell, github]
model: claude-opus-4-6

# Template: Book Chapter Writer
name: Chapter Writer
system_prompt: prompts/book-writer.md
tool_packs: [filesystem, web_search, writing]
model: claude-opus-4-6

# Template: Research Analyst
name: Research Analyst
system_prompt: prompts/researcher.md
tool_packs: [web_search, filesystem, data_analysis]
model: claude-opus-4-6
```

### 3. Tool Pack (replaces hardcoded tools)

A **Tool Pack** is a pluggable set of capabilities an agent can use.

```python
class ToolPack:
    slug: str                 # "git", "filesystem", "web_search", "writing"
    name: str
    description: str
    tools: list[ToolDef]      # List of tool definitions (name, description, parameters)
```

#### Built-in Tool Packs

| Pack              | Tools                                                               | Use Cases                           |
| ----------------- | ------------------------------------------------------------------- | ----------------------------------- |
| **filesystem**    | read_file, write_file, list_dir, delete_file, move_file             | Universal — every agent needs files |
| **shell**         | run_command (sandboxed)                                             | Code agents, devops                 |
| **git**           | clone, branch, commit, push, diff, worktree_create, worktree_delete | Code agents                         |
| **github**        | create_pr, merge_pr, comment_pr, create_issue, read_issue           | Code workflow                       |
| **web_search**    | search, fetch_url, extract_content                                  | Research, writing                   |
| **writing**       | create_document, append_section, format_markdown, word_count        | Book writing, content               |
| **data**          | read_csv, query_db, generate_chart, analyze                         | Data/research agents                |
| **communication** | send_email, send_slack, send_notification                           | Delivery agents                     |
| **storage**       | upload_s3, download_s3, list_bucket                                 | Cloud storage                       |

#### Custom Tool Packs (V2)

Users can define their own tool packs — functions the agent can call that hit user-defined APIs.

### 4. Workflow (replaces hardcoded pipeline)

A **Workflow** defines the sequence of agents and decision points.

```python
class Workflow:
    id: int
    tenant_id: int
    name: str                 # "Code Shipping", "Book Writing", "Research"
    slug: str
    description: str
    steps: list[WorkflowStep] # Ordered pipeline
    trigger: TriggerConfig    # What starts this workflow
```

```python
class WorkflowStep:
    order: int
    agent_id: int             # Which agent runs this step
    name: str                 # "Refine", "Implement", "Review"
    input_from: str           # "task" | "previous_step" | "step:<name>"
    requires_approval: bool   # Human checkpoint?
    on_reject: str            # "retry" | "fail" | "goto:<step>"
    on_fail: str              # "retry" | "fail" | "skip"
    condition: str            # Optional: only run if condition met
```

#### Example: Code Shipping Workflow

```yaml
name: Code Shipping
trigger: { source: github, event: issue_labeled, label: cawnex }
steps:
  - name: Refine
    agent: refinement-agent
    input_from: task
    requires_approval: true
    on_reject: fail

  - name: Implement
    agent: code-dev-agent
    input_from: previous_step
    on_fail: retry

  - name: Review
    agent: qa-reviewer-agent
    input_from: previous_step
    on_reject: goto:Implement # Send back with feedback

  - name: Document
    agent: docs-agent
    input_from: previous_step
    on_fail: skip
```

#### Example: Book Writing Workflow

```yaml
name: Book Writing
trigger: { source: manual }
steps:
  - name: Outline
    agent: book-outliner
    input_from: task
    requires_approval: true

  - name: Research
    agent: research-analyst
    input_from: previous_step
    on_fail: retry

  - name: Write Chapter
    agent: chapter-writer
    input_from: previous_step
    requires_approval: false

  - name: Edit
    agent: editor-agent
    input_from: previous_step
    on_reject: goto:Write Chapter

  - name: Format
    agent: formatter-agent
    input_from: previous_step
    on_fail: skip
```

#### Example: Research Workflow

```yaml
name: Deep Research
trigger: { source: api }
steps:
  - name: Scope
    agent: scope-analyst
    input_from: task
    requires_approval: true

  - name: Gather
    agent: web-researcher
    input_from: previous_step

  - name: Analyze
    agent: data-analyst
    input_from: previous_step

  - name: Synthesize
    agent: report-writer
    input_from: previous_step

  - name: Review
    agent: fact-checker
    input_from: previous_step
    on_reject: goto:Gather
```

### 5. Artifact (replaces PR)

An **Artifact** is any output produced by a workflow.

```python
class Artifact:
    id: int
    execution_id: int
    artifact_type: str        # "pull_request", "document", "report", "dataset"
    title: str
    content: str              # Or reference to file
    url: str                  # Link to artifact (PR URL, doc URL, file URL)
    metadata: dict            # Type-specific data
```

Artifact types:

- `pull_request` → {pr_number, repo, branch, diff_stats}
- `document` → {format: "markdown", word_count, sections}
- `report` → {format: "pdf", pages, charts}
- `dataset` → {format: "csv", rows, columns}
- `email_draft` → {to, subject, body}

### 6. Workspace (replaces Worktree)

A **Workspace** is the isolated environment where an agent works.

```python
class Workspace:
    type: str                 # "git_worktree", "temp_dir", "cloud_storage"
    path: str                 # Local path or remote URI
    cleanup_policy: str       # "on_complete", "on_approve", "manual"
```

- Code agents → git worktree
- Writing agents → temp directory
- Data agents → temp directory + cloud storage
- Research agents → temp directory

### 7. Trigger (replaces GitHub Webhook)

A **Trigger** is what starts a workflow.

```python
class TriggerConfig:
    source: str               # "github", "linear", "jira", "api", "schedule", "chat"
    event: str                # "issue_labeled", "issue_created", "manual", "cron"
    filters: dict             # {label: "cawnex"}, {priority: "high"}, etc.
```

---

## What Changes in the Codebase

### Models (packages/core)

| Current                | Change To                                | Impact                                                                                            |
| ---------------------- | ---------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `Issue` model          | **`Task`** model                         | Rename + add `workflow_id`, `context` (JSON), remove git-specific fields                          |
| `Execution` model      | Keep but generalize                      | Remove `pr_url`, `pr_number`, `worktree_path`, `branch_name` → move to `Artifact` and `Workspace` |
| `ExecutionEvent` model | Keep as-is                               | Already generic ✅                                                                                |
| `Tenant` model         | Keep as-is                               | Already generic ✅                                                                                |
| `LLMConfig` model      | Keep as-is                               | Already generic ✅                                                                                |
| `Repository` model     | Becomes optional **`TaskSource`** config | Not all tasks come from repos                                                                     |
| —                      | Add **`AgentDefinition`** model          | Configurable agents                                                                               |
| —                      | Add **`Workflow`** model                 | Configurable pipelines                                                                            |
| —                      | Add **`WorkflowStep`** model             | Pipeline steps                                                                                    |
| —                      | Add **`Artifact`** model                 | Output tracking                                                                                   |
| —                      | Add **`ToolPack`** registry              | Available tool packs                                                                              |

### Enums

| Current                                   | Change To                                              |
| ----------------------------------------- | ------------------------------------------------------ |
| `AgentType` (hardcoded: DEV, QA, DOCS...) | Remove — agents are user-defined via `AgentDefinition` |
| `IssueStatus`                             | Rename to **`TaskStatus`**                             |
| `IssueSource`                             | Rename to **`TaskSource`**                             |
| `ExecutionStatus`                         | Keep as-is ✅                                          |
| `EventType`                               | Keep as-is ✅                                          |
| —                                         | Add **`ArtifactType`**                                 |
| —                                         | Add **`WorkspaceType`**                                |
| —                                         | Add **`TriggerSource`**                                |

### Worker (apps/worker)

| Current Plan                            | Change To                                                                                  |
| --------------------------------------- | ------------------------------------------------------------------------------------------ |
| `crows/dev.py`, `crows/qa.py`, etc.     | **`agent_runner.py`** — generic runner that loads `AgentDefinition` + attaches `ToolPack`s |
| `murder.py` (hardcoded pipeline)        | **`orchestrator.py`** — reads `Workflow` definition, executes steps in order               |
| `tools/filesystem.py`, `tools/shell.py` | **`tool_packs/filesystem.py`**, `tool_packs/git.py`, etc. — pluggable                      |
| `prompts/dev.md`, `prompts/qa.md`       | **`templates/`** — agent templates users can start from                                    |

### API

| Current               | Change To                                                      |
| --------------------- | -------------------------------------------------------------- |
| `/issues`             | **`/tasks`**                                                   |
| `/issues/:id/approve` | **`/tasks/:id/approve`**                                       |
| `/webhooks/github`    | **`/triggers/github`** (+ `/triggers/linear`, `/triggers/api`) |
| —                     | Add **`/agents`** CRUD (create/configure agents)               |
| —                     | Add **`/workflows`** CRUD (create/configure pipelines)         |
| —                     | Add **`/artifacts`** (list outputs)                            |

### Naming

| Current | Change To               | Reasoning                                              |
| ------- | ----------------------- | ------------------------------------------------------ |
| Crow    | **Agent**               | Generic. "Crow" stays as fun branding but not in code. |
| Murder  | **Orchestrator**        | Generic. "The Murder" is marketing, not architecture.  |
| Nest    | **Workspace**           | Generic.                                               |
| Caw     | **Message** / **Event** | Generic.                                               |
| Roost   | **Dashboard**           | Generic.                                               |

**The crow naming stays in branding, docs, and UI.** But the code is domain-agnostic.

---

## What DOESN'T Change

- **BYOL** — still user brings their own LLM ✅
- **Multi-tenant** — still scoped to organizations ✅
- **Guard system** — hallucination/budget/time limits apply to ANY agent ✅
- **Retry engine** — works for any workflow step ✅
- **Event streaming** — SSE/WebSocket works for any execution ✅
- **Provider abstraction** — Claude/OpenAI/Gemini still pluggable ✅

---

## The Code Workflow as a Template

The original "code shipping" becomes a **workflow template** — pre-installed, ready to use:

```yaml
# templates/workflows/code-shipping.yaml
name: Code Shipping
description: "Issue → Refine → Implement → Review → Merge → Document"
trigger:
  source: github
  event: issue_labeled
  filters:
    label: cawnex
agents:
  - slug: refinement
    template: templates/agents/refinement.yaml
  - slug: developer
    template: templates/agents/developer.yaml
  - slug: reviewer
    template: templates/agents/reviewer.yaml
  - slug: documenter
    template: templates/agents/documenter.yaml
steps:
  - name: Refine
    agent: refinement
    requires_approval: true
  - name: Implement
    agent: developer
  - name: Review
    agent: reviewer
    on_reject: goto:Implement
  - name: Document
    agent: documenter
    on_fail: skip
```

Users can:

1. Use this template as-is (most common)
2. Modify it (change models, add agents)
3. Create entirely new workflows (book writing, research, etc.)

---

## Why This Matters

1. **Market is 100x bigger** — not just dev teams, but writers, researchers, marketers, analysts
2. **Defensibility** — generic orchestration platform vs. another "AI coder"
3. **Revenue** — more use cases = more users = more subscriptions
4. **Composability** — users build workflows we never imagined
5. **Dogfooding** — we use code workflow to build Cawnex, but the platform itself is generic

---

## Migration Plan

Since we're at Step 2 (models just created), the cost of changing is LOW:

1. ✅ Rename `Issue` → `Task` in models
2. ✅ Add `AgentDefinition`, `Workflow`, `WorkflowStep`, `Artifact` models
3. ✅ Generalize `Execution` (remove git-specific fields → Artifact)
4. ✅ Update enums
5. ✅ Update schemas
6. ✅ Restructure worker: `crows/` → `tool_packs/` + generic `agent_runner.py`
7. ✅ Update API routes: `/issues` → `/tasks`, add `/agents`, `/workflows`
8. ⬜ Create code-shipping workflow template (preserves original functionality)
9. ⬜ Continue building Steps 3-11 with new abstractions
