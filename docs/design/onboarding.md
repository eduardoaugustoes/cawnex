# Onboarding — First-Run Wizard

The onboarding flow is the first thing a user sees after signup. It's a guided wizard that connects their infrastructure and configures Cawnex to work with their repos.

## Flow

```
Signup → Connect GitHub → Add LLM Key → Configure Workflow → Test Run → Dashboard
```

## Steps

### Step 1 — Connect GitHub

**Goal:** Link repos that Cawnex will operate on.

- OAuth App flow (or paste a PAT for CLI users)
- User selects which repos to connect
- Cawnex reads each repo's `CAWNEX.md` (if present) for project conventions
- Auto-detects: language, framework, test commands, branch strategy

**Data created:**
- `Repository` records with `github_full_name`, `clone_url`, `default_branch`
- Auto-populated `language`, `framework`, `cawnex_md`

**API:**
```
POST /api/v1/onboarding/github
  { "token": "ghp_...", "repos": ["owner/repo1", "owner/repo2"] }

→ { "connected": 2, "repositories": [...] }
```

### Step 2 — Add LLM Key

**Goal:** BYOL — user provides their own API key.

- Select provider: Anthropic (recommended), OpenAI, Google
- Paste API key
- Cawnex validates the key with a test call (1 token)
- Key is encrypted with Fernet and stored in `LLMConfig`
- Optional: set monthly budget limit

**Data created:**
- `LLMConfig` with `encrypted_api_key`, `provider`, `budget_limit_usd`

**API:**
```
POST /api/v1/onboarding/llm
  { "provider": "anthropic", "api_key": "sk-ant-...", "budget_limit_usd": 50.0 }

→ { "valid": true, "provider": "anthropic", "test_model": "claude-haiku-4-6" }
```

**Security:**
- API key never returned after submission
- Encrypted at rest with Fernet (key from `CAWNEX_FERNET_KEY` env var)
- Response shows `has_api_key: true` only

### Step 3 — Configure Agents

**Goal:** Choose which agents (crows) are active and customize their behavior.

**Default agents (created from templates):**
| Agent | Model | Tools | Enabled |
|-------|-------|-------|---------|
| Refinement | claude-opus-4-6 | filesystem, web_search | ✅ |
| Developer | claude-opus-4-6 | filesystem, shell, git, github | ✅ |
| QA Reviewer | claude-sonnet-4-6 | filesystem, shell, git | ✅ |
| Documentation | claude-haiku-4-6 | filesystem, git | ✅ |

**Customizable per agent:**
- Model (claude-opus-4-6 / claude-sonnet-4-6 / claude-haiku-4-6 / gpt-4o / etc.)
- System prompt (extend or replace)
- Tool packs (add/remove capabilities)
- Max execution time
- Max tokens per turn

**Data created:**
- `AgentDefinition` records (cloned from templates, tenant-scoped)

### Step 4 — Configure Workflow

**Goal:** Define the pipeline — which agents run in which order.

**Default workflow: "Code Shipping"**
```
Refine → [Human Approval] → Implement → Review → Document
```

**Customizable:**
- Step order (drag & drop on web)
- Which steps require human approval
- Error handling: retry / fail / skip / goto
- Trigger: which GitHub label activates the workflow (default: `cawnex`)
- Branch naming: `crow/{task_id}-{slug}` (customizable pattern)
- PR template: auto-populated with acceptance criteria + diff stats
- Auto-merge: enabled/disabled per workflow

**Data created:**
- `Workflow` + `WorkflowStep` records

### Step 5 — Configure Tools

**Goal:** Give agents the right capabilities for the project.

**Tool packs:**
| Pack | What it does | Default |
|------|-------------|---------|
| `filesystem` | Read/write/search files | All agents |
| `shell` | Run shell commands | Dev, QA |
| `git` | Branch, commit, push | Dev, QA, Docs |
| `github` | PR, issues, labels | Dev |
| `web_search` | Search the web | Refinement |

**Per-repo conventions (from `CAWNEX.md` or configured here):**
- Test command: `npm test`, `pytest`, `go test ./...`
- Lint command: `npm run lint`, `ruff check .`
- Build command: `npm run build`, `cargo build`
- Deploy hook: URL called after merge (optional)

### Step 6 — Test Run (Dry Run)

**Goal:** Validate the setup end-to-end before going live.

- User picks an existing GitHub issue (or creates a test one)
- Cawnex runs the full workflow in dry-run mode:
  - Refinement generates the brief (shown to user)
  - Developer creates a branch + writes code (diff shown, no PR created)
  - QA reviews (feedback shown)
  - Docs updates (diff shown)
- User sees: estimated cost, time, token usage
- If satisfied → activate, create the PR for real

**API:**
```
POST /api/v1/onboarding/test-run
  { "repo": "owner/repo", "issue_number": 42, "dry_run": true }

→ SSE stream of execution events
```

## Post-Onboarding

After completing the wizard:
1. GitHub webhook is registered on selected repos
2. User lands on The Roost (dashboard)
3. Any issue labeled `cawnex` triggers the workflow automatically
4. First real execution creates a PR and notifies via configured channels

## Web UI Screens

```
┌─────────────────────────────────────────────┐
│  🐦‍⬛ Welcome to Cawnex                       │
│                                             │
│  Let's set up your murder.                  │
│                                             │
│  ● Connect GitHub        ← current          │
│  ○ Add LLM Key                              │
│  ○ Configure Agents                         │
│  ○ Configure Workflow                       │
│  ○ Test Run                                 │
│                                             │
│  [Connect with GitHub]                      │
│  or paste a Personal Access Token           │
└─────────────────────────────────────────────┘
```

## Mobile Onboarding

iOS/Android follow the same flow but optimized for mobile:
- OAuth opens system browser → deep link back
- API key paste uses system clipboard
- Agent/workflow config uses bottom sheets
- Test run streams events in a timeline view
