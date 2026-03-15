# Screen Query Analysis — S33 Task Detail & S34 PR Review

> DynamoDB single-table mapping for task and PR review screens.
> Table: `cawnex` with recursive snapshots. PK = `T#{tenant_id}#P#{project_id}`, SK = `S#{path}` where path = `wave#council#murder#crow`.

---

## 1. Screen Purposes

- **S33 — Task Detail:** Single task deep-dive showing estimates, implementation steps, acceptance criteria, assigned crow, and PR link.
- **S34 — PR Review:** AI-guided PR review with plan vs execution comparison, verdict, conversational Q&A, and approve/steer/reject actions.

---

## 2. Data Needed

### S33 — Task Detail

| Field                    | Type     | Example                                                  |
| ------------------------ | -------- | -------------------------------------------------------- |
| task.name                | string   | "RBAC middleware"                                        |
| task.status              | enum     | completed, in_progress, pending_approval, queued, failed |
| task.description         | string   | "Create NestJS guard..."                                 |
| task.humanEstimate       | string   | "6h"                                                     |
| task.aiCost              | currency | $2.40                                                    |
| task.roi                 | number   | 42                                                       |
| task.assignedCrow        | object   | {name, role, model, behaviorState}                       |
| task.implementationSteps | array    | [{text, completed}]                                      |
| task.acceptanceCriteria  | array    | [{text, passed}]                                         |
| task.pr                  | object   | {title, branch, number, status}                          |

### S34 — PR Review

| Field           | Type     | Example                                   |
| --------------- | -------- | ----------------------------------------- |
| pr.title        | string   | "Add input validation..."                 |
| pr.branch       | string   | "feat/input-validation"                   |
| pr.status       | enum     | ready, changes_requested, merged          |
| pr.mviRef       | string   | "MVI 1.2"                                 |
| pr.taskRef      | string   | "Input Validation"                        |
| pr.creditsCost  | number   | 12                                        |
| pr.aiMinutes    | number   | 8                                         |
| pr.filesChanged | number   | 6                                         |
| pr.linesAdded   | number   | 142                                       |
| pr.linesRemoved | number   | 23                                        |
| verdict         | object   | {status, confidence, summary, findings[]} |
| planVsExecution | array    | [{crowName, role, plan, executed, hint?}] |
| askChips        | string[] | suggested questions                       |
| conversation    | array    | [{role, content, riskBadge?}]             |

---

## 3. DynamoDB Queries

### Snapshot Path Convention

The SK path `S#{wave}#{council}#{murder}#{crow}` forms a hierarchy. A task lives at the crow level — it is the unit of work a specific crow executes within a murder, within a wave.

### S33 — Task Detail

**Primary read: Get task snapshot**

| Purpose  | PK                             | SK                                                     | Operation |
| -------- | ------------------------------ | ------------------------------------------------------ | --------- |
| Get task | `T#{tenant_id}#P#{project_id}` | `S#{wave_id}#M#{murder_id}#C#{crow_id}#TASK#{task_id}` | `GetItem` |

The task snapshot contains: name, status, description, humanEstimate, aiCost, assignedCrow, implementationSteps, acceptanceCriteria, and a `prRef` pointer.

**Secondary read: Get PR summary (for the PR card at bottom)**

| Purpose    | PK                             | SK                                                 | Operation |
| ---------- | ------------------------------ | -------------------------------------------------- | --------- |
| Get PR ref | `T#{tenant_id}#P#{project_id}` | `S#{wave_id}#M#{murder_id}#C#{crow_id}#PR#{pr_id}` | `GetItem` |

Only needs `{title, branch, number, status}` — the lightweight fields embedded in the task snapshot are sufficient. No separate query needed if PR metadata is denormalized into the task record.

### S34 — PR Review

**Primary read: Get PR record with verdict and plan-vs-execution**

| Purpose          | PK                             | SK                                                 | Operation                               |
| ---------------- | ------------------------------ | -------------------------------------------------- | --------------------------------------- |
| Get PR detail    | `T#{tenant_id}#P#{project_id}` | `S#{wave_id}#M#{murder_id}#C#{crow_id}#PR#{pr_id}` | `GetItem`                               |
| Get conversation | `T#{tenant_id}#P#{project_id}` | `CONV#PR#{pr_id}#MSG#{timestamp}`                  | `Query` (begins_with `CONV#PR#{pr_id}`) |

**Write operations:**

| Purpose          | PK                             | SK                                | Operation                      |
| ---------------- | ------------------------------ | --------------------------------- | ------------------------------ |
| Approve PR       | `T#{tenant_id}#P#{project_id}` | `EVT#{ulid}`                      | `PutItem` (event: pr_approved) |
| Steer PR         | `T#{tenant_id}#P#{project_id}` | `EVT#{ulid}`                      | `PutItem` (event: pr_steered)  |
| Reject PR        | `T#{tenant_id}#P#{project_id}` | `EVT#{ulid}`                      | `PutItem` (event: pr_rejected) |
| Add chat message | `T#{tenant_id}#P#{project_id}` | `CONV#PR#{pr_id}#MSG#{timestamp}` | `PutItem`                      |

---

## 4. Task-to-Crow Snapshot Mapping

A task is a crow-level snapshot. The hierarchy:

```
PK: T#acme#P#cawnex
  SK: S#W01                              ← wave snapshot (status, task count)
  SK: S#W01#COUNCIL#vote_001             ← council decision for this wave
  SK: S#W01#M#dev                        ← murder snapshot (crow roster, flow state)
  SK: S#W01#M#dev#C#planner#TASK#t001    ← planner's task snapshot
  SK: S#W01#M#dev#C#impl#TASK#t001       ← implementer's task snapshot (same task, different crow)
  SK: S#W01#M#dev#C#reviewer#TASK#t001   ← reviewer's task snapshot
```

The **task entity** (t001) flows through multiple crow snapshots as it progresses through the murder's crow flow (planner -> implementer -> reviewer). Each crow writes its own snapshot under its own SK prefix, recording what it did for that task.

**S33 reads the "current" task snapshot** — the latest crow that touched this task. The API resolves which crow-level snapshot to return by checking the task's current execution step (stored in the murder-level snapshot or via a GSI on `task_id + status`).

Alternatively, a **task-level summary record** can be maintained:

```
SK: S#W01#M#dev#TASK#{task_id}   ← denormalized task summary (updated after each crow step)
```

This avoids the client needing to know which crow currently owns the task.

---

## 5. PR Data Storage

PR data is stored as a **separate snapshot record**, not embedded in the task. Rationale:

1. PR has its own lifecycle (created, reviewed, merged/rejected) independent of the task.
2. S34 needs rich PR data (verdict, plan-vs-execution, conversation) that would bloat the task record.
3. Multiple screens reference the same PR (S32 task list, S33 PR card, S34 full review).

```
PK: T#acme#P#cawnex
  SK: S#W01#M#dev#C#impl#PR#14           ← PR created by implementer crow
      Attributes:
        title, branch, number, status
        creditsCost, aiMinutes, filesChanged, linesAdded, linesRemoved
        prUrl (GitHub link)
        taskRef (back-pointer to task)
        mviRef (back-pointer to MVI)

  SK: S#W01#M#dev#C#reviewer#PR#14       ← reviewer crow's verdict on this PR
      Attributes:
        verdict: {status, confidence, summary, findings[]}
        reviewedAt, reviewDurationMs
```

**The task record holds a lightweight `pr` object** `{title, branch, number, status}` as a denormalized reference — enough for S33's PR card. S34 fetches the full PR and reviewer records.

---

## 6. Plan vs Execution: Reading Planner vs Implementer Snapshots

The `planVsExecution` array on S34 is assembled by reading multiple crow-level snapshots for the same task:

```
Step 1 — Planner:
  Read: SK: S#W01#M#dev#C#planner#TASK#t001
  Extract: plan (planner's output = task breakdown, instructions)

Step 2 — Implementer:
  Read: SK: S#W01#M#dev#C#impl#TASK#t001
  Extract: executed (what the implementer actually did, diff summary)
  Extract: hint (if implementer deviated from plan, explanation)

Step 3 — Reviewer:
  Read: SK: S#W01#M#dev#C#reviewer#TASK#t001
  Extract: verdict, findings
```

**Assembly strategy:** The API handler queries all crow snapshots for a given task within a murder using `begins_with`:

```
Query:
  PK = T#acme#P#cawnex
  SK begins_with S#W01#M#dev#C#
  FilterExpression: contains(SK, 'TASK#t001')
```

Or more efficiently, the PR record itself stores the pre-assembled `planVsExecution` array — written by the reviewer crow when it completes its review. The reviewer crow has access to the planner's plan and the implementer's output as part of its review context (passed by Murder), so it can emit the comparison as a structured artifact.

**Recommended approach:** Store `planVsExecution` directly on the reviewer's PR snapshot. It is written once at review time and read many times by S34. Avoids multi-record fan-out on every S34 render.

---

## 7. Steer/Reject: Triggering a New Cycle

When the human taps **Steer** or **Reject** on S34:

### Steer Flow

1. **Write event:** `PutItem` with SK `EVT#{ulid}`, type `pr_steered`, payload = human feedback text.
2. **Murder receives event** (via DynamoDB Stream or direct invocation).
3. **Murder creates a new crow snapshot** under the same murder, same wave:
   ```
   SK: S#W01#M#dev#C#fixer#TASK#t001#R2    ← retry 2, fixer crow
   ```
   The `#R{n}` suffix distinguishes retry cycles. The fixer crow receives:
   - Original plan (from planner snapshot)
   - Previous implementation (from implementer snapshot)
   - Human feedback (from the steer event)
   - Review findings (from reviewer snapshot)
4. **Fixer crow executes**, pushes new commits to the same branch, updates the PR.
5. **New reviewer snapshot** is written: `SK: S#W01#M#dev#C#reviewer#TASK#t001#R2`
6. **Task summary record updated** with new status, new PR snapshot version.

### Reject Flow

1. **Write event:** `PutItem` with SK `EVT#{ulid}`, type `pr_rejected`.
2. **Murder marks the task as rejected** in the task summary record.
3. **PR is closed** (GitHub API call).
4. **Murder may re-plan** — creating a new task under the same MVI, or escalating to the Monarch if the rejection implies a scope change.

### Key Point

New crow snapshots are always **appended** under the same murder prefix — never overwritten. This gives full audit trail:

```
S#W01#M#dev#C#impl#TASK#t001       ← first attempt
S#W01#M#dev#C#reviewer#TASK#t001   ← first review (rejected)
S#W01#M#dev#C#fixer#TASK#t001#R2   ← second attempt (after steer)
S#W01#M#dev#C#reviewer#TASK#t001#R2 ← second review (approved)
```

---

## 8. Conversation Storage for AI Chat

S34 has an AI chat where the human asks questions about the PR ("Why was the error handler changed?"). This is stored separately from crow snapshots:

```
PK: T#acme#P#cawnex
SK: CONV#PR#14#MSG#2026-03-14T10:32:00.000Z
    Attributes:
      role: "user"
      content: "Why was the error handler refactored?"
      timestamp: 2026-03-14T10:32:00.000Z

SK: CONV#PR#14#MSG#2026-03-14T10:32:01.500Z
    Attributes:
      role: "assistant"
      content: "The implementer noticed that..."
      riskBadge: {label: "Low risk", color: "green"}
      timestamp: 2026-03-14T10:32:01.500Z
```

**Query pattern:**

```
Query:
  PK = T#acme#P#cawnex
  SK begins_with CONV#PR#14#MSG#
  ScanIndexForward = true  (chronological order)
```

**Why separate from snapshots:**

- Conversations are user-initiated, not part of the orchestration pipeline.
- They grow unboundedly (user can ask many questions).
- They use a different SK prefix (`CONV#`) to avoid polluting the snapshot namespace (`S#`).
- The `askChips` (suggested questions) are stored on the PR record itself — they are generated once by the reviewer crow.

---

## 9. Real-Time Needs

### S33 — Task Detail

**Minimal real-time needs.** Task detail is mostly a read-once screen. However, if the user is viewing a task that is currently `in_progress`:

- **SSE connection** from S32 (MVI Blackboard) can update task status when navigating back.
- No dedicated SSE for S33 — the user navigates back to S32 which has its own SSE stream.

### S34 — PR Review

**SSE required for two scenarios:**

1. **AI conversation streaming:** When the user asks a question, the AI response streams token-by-token via SSE. The conversation endpoint:

   ```
   POST /prs/:id/chat → returns SSE stream
   ```

   The client renders tokens as they arrive, then persists the complete message to DynamoDB when the stream ends.

2. **PR status updates:** If the PR is being re-reviewed after a steer (crow is actively working), SSE pushes:
   - Crow behavior state changes ("Fixer: building" -> "Fixer: pushing")
   - New verdict when reviewer completes
   - PR status transitions (changes_requested -> ready)

**SSE connection pattern:**

```
GET /projects/:projectId/prs/:prId/stream
Headers: Authorization: Bearer {jwt}

Events:
  event: chat_token
  data: {"token": "The implementer"}

  event: verdict_updated
  data: {"status": "approved", "confidence": "high"}

  event: crow_state
  data: {"crow": "fixer", "state": "pushing"}
```

### Summary of Real-Time by Screen

| Screen | SSE | Purpose                                                   |
| ------ | --- | --------------------------------------------------------- |
| S33    | No  | Static read; parent S32 handles updates                   |
| S34    | Yes | AI chat streaming + PR status during active review cycles |
