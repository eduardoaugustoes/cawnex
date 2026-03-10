# 🐦 Agent Definitions — Cawnex

> Each crow has one job. Specialization is the product.

---

## MVP Agents (V1)

### 🔍 Refinement Crow

**Mission**: Transform a raw issue into a fully specified, actionable task.

**Input**: Issue title + description (from Linear/GitHub/Jira)

**Output**:
- Refined user story (As a..., I want..., So that...)
- Acceptance criteria (Given/When/Then)
- Technical notes (approach suggestions)
- Affected repositories list
- Estimated complexity (S/M/L/XL)

**Model**: Opus (needs deep reasoning)

**System Prompt Includes**:
- Repository structure knowledge (from CAWNEX.md files)
- API contracts between services
- Tech stack constraints
- Previous similar issues for context

**When it runs**: Immediately when issue enters the system.

**Outputs to**: Human (for approval) → then Orchestrator

---

### ⚙️ Dev Crow

**Mission**: Implement the solution in code.

**Input**: Approved user story + acceptance criteria + assigned repository

**Output**:
- Code changes in a worktree
- Passing tests (if test framework exists)
- Pull Request with descriptive title/body

**Model**: Opus (code generation needs highest quality)

**System Prompt Includes**:
- Repository-specific CAWNEX.md
- Language/framework conventions
- Existing code patterns (auto-detected)
- API contracts from other repos (shared by orchestrator)

**When it runs**: After human approves refined issue.

**Capabilities**:
- Read files, write files, execute shell commands
- Create git worktree
- Install dependencies
- Run tests
- Create and push branch
- Open Pull Request via GitHub API

**Guardrails**:
- Cannot push to main/master directly
- Cannot delete branches
- Cannot modify CI/CD config (security boundary)
- Max execution time: 15 minutes
- Max token budget per execution

**Note**: In MVP, one Dev Crow handles both backend and frontend. Split into Backend Crow + Frontend Crow in V2 when cross-repo coordination is needed.

---

### ✅ QA Crow

**Mission**: Review code against acceptance criteria and quality standards.

**Input**: Pull Request URL + original acceptance criteria

**Output**:
- Review result (approved/changes_requested)
- Comments on specific lines (if issues found)
- Summary of what was checked

**Model**: Sonnet (review is faster, less generation needed)

**Workflow**:
1. Get diff from main..HEAD
2. Review changed files against acceptance criteria
3. Run type checks (if applicable)
4. Check for common issues (security, performance, patterns)
5. Attempt to fix minor issues directly
6. Approve or request changes with specific feedback

**When it runs**: After Dev Crow opens PR.

**Guardrails**:
- Read-only access to main branch
- Can push fixes to the PR branch
- Cannot merge PRs (orchestrator handles merge)
- Max execution time: 5 minutes

---

### 📄 Docs Crow

**Mission**: Keep documentation in sync with code changes.

**Input**: Merged PR + diff + repository docs structure

**Output**:
- Updated documentation files
- New documentation if new features
- Commit directly to main (or separate PR if configured)

**Model**: Haiku (documentation is simpler, cost-effective)

**When it runs**: After PR is merged.

**What it updates**:
- README.md
- API documentation
- Configuration docs
- Changelog
- Architecture decision records

**Guardrails**:
- Can only modify documentation files (*.md, docs/*, etc.)
- Cannot modify source code
- Max execution time: 3 minutes

---

## V2 Agents (Post-MVP)

### ⚙️ Backend Crow (split from Dev)
- Focuses on server code, APIs, DB migrations
- Communicates API contracts to Frontend Crow

### 🖥️ Frontend Crow (split from Dev)
- Focuses on UI components, pages, styling
- Receives API contracts from Backend Crow

### 📱 Mobile Crow
- iOS/Android specific implementations
- React Native / Expo / Swift / Kotlin

### 🔒 Security Crow
- SAST/DAST scanning
- Dependency vulnerability checks
- Secret detection
- Security best practices review

### 📋 Planning Crow
- Breaks epics into smaller issues
- Estimates complexity
- Maps dependencies between issues
- Creates sprint plans

---

## Agent Configuration — CAWNEX.md

Each repository should have a `CAWNEX.md` file at the root:

```markdown
# CAWNEX.md — Repository Agent Instructions

## Repository
- **Name**: my-api
- **Type**: backend
- **Language**: Python 3.12
- **Framework**: FastAPI
- **Database**: PostgreSQL (via SQLAlchemy)
- **Test Framework**: pytest

## Structure
- `src/` — Source code
- `src/routes/` — API endpoints
- `src/models/` — Database models
- `src/services/` — Business logic
- `tests/` — Test files
- `docs/` — Documentation

## Conventions
- Use type hints everywhere
- All endpoints need input validation (Pydantic)
- All DB queries go through repository pattern
- Tests required for all new endpoints
- Use `ruff` for linting

## API Contracts
- Exports: `GET /api/v1/users`, `POST /api/v1/tasks`
- Consumes: auth-service `/api/v1/auth/verify`

## Do NOT
- Modify alembic migration files manually
- Change database schema without migration
- Use raw SQL queries
- Disable type checking
```

---

## Agent Communication Protocol (V1 — Simple)

In MVP, all communication goes through the orchestrator:

```
Dev Crow → (event) → Orchestrator → (event) → QA Crow
```

In V2, add peer-to-peer for cross-repo coordination:

```
Backend Crow ←→ Frontend Crow  (API contract sync)
```

### Message Schema (V1)

```json
{
  "type": "agent_message",
  "from": "dev-crow-backend",
  "to": "orchestrator",
  "execution_id": "exec_123",
  "payload": {
    "kind": "pr_ready",
    "pr_url": "https://github.com/org/repo/pull/42",
    "branch": "crow/LUI-19-api",
    "files_changed": 5,
    "tests_passed": true
  },
  "timestamp": "2026-03-10T12:00:00Z"
}
```

### Message Types

| Type | Direction | Description |
|------|-----------|-------------|
| `issue_assigned` | Orchestrator → Agent | Start working on this |
| `context_shared` | Orchestrator → Agent | Here's context from another agent |
| `pr_ready` | Agent → Orchestrator | PR created, ready for QA |
| `review_complete` | QA → Orchestrator | Approved or changes requested |
| `fix_applied` | Agent → Orchestrator | Applied fixes from review |
| `execution_complete` | Agent → Orchestrator | Done |
| `execution_failed` | Agent → Orchestrator | Failed with error |
| `heartbeat` | Agent → Orchestrator | Still alive (every 30s) |
