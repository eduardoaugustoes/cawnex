# PR Actions — Approve, Reject, and Adversarial Steer

**Date:** 2026-05-15
**Status:** Draft — awaiting user review

## Problem

The PR Review screen in iOS shows the reviewer crow's verdict and the diff, but every action button is disabled placeholder UI: **Approve & Merge**, **Steer**, **Reject**, and **Ask about this PR** all have empty closures with `.disabled(true)` + `.opacity(0.4)`. The reviewer's "✅ APPROVED" verdict has nowhere to go. PR #16 (Cawnex's first real autonomous PR) is currently stranded because the founder cannot land it from the app.

Closing this loop also opens a strategic question: when a machine reviewer approves machine-written code, what does human-in-the-loop verification actually look like? Today, the founder reads the verdict and clicks a button. That's not verification — it's rubber-stamping. We want a **second, adversarial review layer** that the founder operates: an investigator who reads the PR with the assumption the reviewer was wrong.

This spec ships three things:

1. **Approve & Merge** — close the loop. `gh pr merge --rebase --delete-branch`, mark MVI as shipped in DDB, trigger wave-delivery check.
2. **Reject** — close the PR on GitHub with a reason, mark MVI as rejected.
3. **Steer** — open an adversarial Claude tool-use chat scoped to the PR. The model has read-only access to the codebase at the PR's head SHA. Its system prompt explicitly puts it in opposition to the reviewer's verdict. The chat is investigation-only: it cannot push code, post PR comments mid-chat, or trigger crows. The founder reads the chat, then decides Approve or Reject.

A fourth action, **GitHub** (open in Safari), needs no backend.

## Constraints

- **API runs on Lambda.** All four routes live there. Chat turns are HTTP POSTs, not long-lived connections — each turn fits in one Lambda invocation (Haiku 4.5, ~60s typical, well under the 15-minute cap).
- **iOS already has Cognito JWT auth** and reuses `APIClient` for all calls. No new auth surface.
- **Stream service from Phase 1-3 already runs on Fargate** and is the canonical place to push frames to iOS. Steer reuses it for streaming chat tokens.
- **GitHub token is in Secrets Manager** at `cawnex/dev/github-token` and the worker already has access. Extending API Lambda IAM to read it is one CDK line.
- **No new infrastructure category.** The whole feature reuses Lambda + DDB + SSE + Secrets Manager that already exist.

## Out of Scope

- **Push-fix from Steer.** Steer never mutates code. If the chat convinces the founder a fix is needed, that's a separate future action (Reject → human edits → re-run, or a future "Push Fix" button that triggers a Fixer crow). Not in this spec.
- **Rerun-MVI from Steer.** Same reasoning. Wave-state machinery, not chat-state.
- **Multi-user chat collaboration.** One founder per chat. No real-time co-editing.
- **Persistent token-stream replay.** If the user misses the streaming render, the persisted final message is what they get on reload.
- **Per-chat model selection.** Steer always uses Haiku 4.5.
- **GitHub PR comments mid-chat.** The Steer chat is private. The only place it leaks to GitHub is the auto-attached summary at merge time (see "Convo summary attached at merge").
- **Steer for non-Cawnex repos.** Initially the cloned repo lives at `/tmp/steer-{chat_id}` cloned from the same GitHub remote the worker uses.

---

## Architecture

```
                    ┌──────────────────────┐
                    │ iOS PRReviewScreen   │
                    │  • Approve & Merge   │
                    │  • Reject (sheet)    │
                    │  • Steer (chat)      │
                    │  • GitHub (browser)  │
                    └──────────┬───────────┘
                               │ HTTPS + Cognito JWT
                               ▼
        ┌──────────────────────────────────────────────┐
        │ API Lambda (apps/api)                        │
        │                                              │
        │  POST /prs/{n}/merge  ─────► gh pr merge     │
        │                              + DDB MVI→ship  │
        │                              + Murder reactor│
        │                                              │
        │  POST /prs/{n}/reject ─────► gh pr close     │
        │                              + DDB MVI→reject│
        │                                              │
        │  POST /prs/{n}/steer/chats         ──── DDB  │
        │       /chats/{c}/messages ─► Anthropic loop  │
        │                              (read/grep/sub) │
        │                                ─── SSE pub   │
        └──────────────────────────────────────────────┘
                               │
        ┌──────────────────────┴───────────────────────┐
        ▼                                              ▼
   ┌─────────┐                                   ┌──────────┐
   │ DynamoDB│                                   │  Stream  │
   │ (events,│                                   │  service │
   │ snaps,  │                                   │ (Fargate)│
   │ steer)  │                                   └─────┬────┘
   └─────────┘                                         │ SSE
                                                       ▼
                                            ┌──────────────────┐
                                            │ iOS chat renderer│
                                            └──────────────────┘
```

### Pieces

**Three new POST routes on API Lambda** under `apps/api/src/routes/pr_actions.py`:
- `POST /projects/{pid}/waves/{wid}/mvis/{mid}/prs/{n}/merge`
- `POST /projects/{pid}/waves/{wid}/mvis/{mid}/prs/{n}/reject`
- `POST /projects/{pid}/waves/{wid}/mvis/{mid}/prs/{n}/steer/chats` + `/chats/{c}/messages`

**A new `steer_chat` module** under `apps/api/src/steer/`:
- `chat_session.py` — DDB session/message CRUD
- `repo_clone.py` — `git clone --depth 1 --branch <pr_head_sha>` into `/tmp/steer-{chat_id}`
- `tools.py` — `read_file`, `grep_files`, `glob_files`, `submit_response`
- `loop.py` — Anthropic `messages.stream()` agentic loop, identical pattern to worker's implementer crow
- `system_prompt.py` — the adversarial instructions

**Stream service gains one new SSE event type**: `steer_message_delta`. The chat-id becomes part of the SSE topic so each chat is its own channel.

**iOS** gets:
- `Features/PR/PRReviewViewModel.swift` enriched with `merge()`, `reject(reason:)`, `openSteerChat()` methods
- `Features/PR/Steer/SteerChatScreen.swift` — chat UI with streaming render, concerns sidebar, suggested-question chips
- `Features/PR/Steer/SteerChatViewModel.swift` — chat state, message send, SSE consumer
- `Core/Network/APIPRActionsService.swift` — POST handlers for merge/reject
- `Core/Network/APISteerService.swift` — chat CRUD + SSE subscription via `EventStreamClient`

---

## The four actions

### 1. Approve & Merge

| Field | Value |
|---|---|
| Route | `POST /projects/{pid}/waves/{wid}/mvis/{mid}/prs/{n}/merge` |
| Body | `{}` (empty; chat-summary attachment is auto-derived) |
| Response | `{merged: true, sha: "abc...", mvi_status: "shipped", wave_status: "review"\|"delivered"}` |

**Flow:**

1. Validate caller has access to project (`get_tenant` dep + `TenantDB.read` on the MVI snapshot).
2. Confirm MVI is in `ready_to_ship`. Reject 409 otherwise — you can't approve an unready MVI.
3. **If any Steer chat exists for this PR** with `status="active"` and at least one `assistant` message: build a "Convo summary" markdown block from the chat (see "Convo summary attached at merge" below) and post it via `gh pr comment` *before* merge.
4. Call `gh pr merge {n} --rebase --delete-branch --repo {owner}/{repo}`. On non-zero exit, return 409 with stderr.
5. Update DDB MVI snapshot: `status: "shipped"`, `shipped_at: now()`, `merge_sha: <gh output>`.
6. Write `mvi_shipped` event to events table.
7. Trigger Murder reactor's wave-terminal check via `_maybe_transition_wave` (already exists for ship-mvi). If every MVI in the wave is terminal, wave transitions to `delivered`; otherwise wave stays in `review`.
8. Mark any active Steer chats for this PR as `closed`.

**Idempotency:** if PR is already merged on GitHub (gh returns specific code), treat as success and reconcile DDB. If MVI is already `shipped` in DDB, return 200 with current state — don't fail.

### 2. Reject

| Field | Value |
|---|---|
| Route | `POST /projects/{pid}/waves/{wid}/mvis/{mid}/prs/{n}/reject` |
| Body | `{reason: string (max 2000 chars), close_branch: bool (default true)}` |
| Response | `{rejected: true, mvi_status: "rejected"}` |

**Flow:**

1. Same auth + MVI-readiness check as merge.
2. Build a markdown rejection comment: `## Rejected by founder\n\n{reason}\n\n_(Steer chat summary attached when applicable)_`. Same conditional Steer-summary attachment as merge.
3. `gh pr comment` + `gh pr close --delete-branch` (if `close_branch`).
4. Update DDB MVI: `status: "rejected"`, `rejected_at: now()`, `rejection_reason: reason`.
5. Write `mvi_rejected` event.
6. Murder reactor checks if wave is now fully terminal.
7. Mark active Steer chats as `closed`.

**Idempotency:** if PR is already closed (gh exit code), reconcile and return 200.

### 3. Steer (the chat)

Two endpoints:

#### `POST /projects/{pid}/waves/{wid}/mvis/{mid}/prs/{n}/steer/chats`
Create a new chat session. Body empty. Returns:
```json
{
  "chat_id": "c1778890123",
  "sse_topic": "steer/c1778890123",
  "head_sha": "d204db2e2a..."
}
```

Pre-loads chat context (PR diff, reviewer outcome, implementer snapshot, project docs) into the chat session record but does NOT call Anthropic yet. The first turn happens when the user sends a message.

#### `POST /projects/{pid}/waves/{wid}/mvis/{mid}/prs/{n}/steer/chats/{chat_id}/messages`
Send a user message. Body:
```json
{"content": "string (max 4000 chars)"}
```

Synchronously persists the user message, kicks off the Anthropic loop (token deltas stream out via SSE on `steer/{chat_id}`), and returns 200 once the loop completes:
```json
{
  "user_message_id": "msg#0003",
  "assistant_message_id": "msg#0004",
  "tokens": {"input": 18420, "output": 1255},
  "submitted_response": {
    "summary": "The reviewer missed that...",
    "severity": "concern",
    "concerns": ["bare-except in project_state.py:127 swallows errors silently"]
  }
}
```

**Loop shape** (identical pattern to implementer crow's tool-use loop in `lambdas/worker/src/worker/claude.py`):

```python
client.messages.stream(
    model="claude-haiku-4-5-20251001",
    system=ADVERSARIAL_SYSTEM_PROMPT,
    messages=load_chat_history(chat_id) + [{"role": "user", "content": new_message}],
    tools=[READ_FILE, GREP_FILES, GLOB_FILES, SUBMIT_RESPONSE],
    max_tokens=8000,
)

# For each chunk:
#   - tool_use → execute tool against /tmp/steer-{chat_id}, feed tool_result back
#   - text_delta → publish steer_message_delta to SSE
#   - submit_response tool call → terminator, capture structured payload, exit loop
```

When `submit_response` is called, persist:
- The assistant message (role=assistant, content=concatenated text deltas, structured_response=tool_use input)
- All tool_use / tool_result pairs (role=tool_use / tool_result, content=serialized)
- Update chat's `tokens_used`

### 4. GitHub

iOS only. Tap → `UIApplication.shared.open(URL(string: pr.url)!)`. No backend.

---

## Steer chat data model

Three new SK patterns under existing project partition (`PK = T#{tenant}#P#{project_id}`):

### `STEER#{pr_id}#chat#{chat_id}` — chat session

```json
{
  "entityType": "SteerChat",
  "pr_id": "16",
  "wave_id": "w1778872378963",
  "mvi_id": "mvi2",
  "head_sha": "d204db2e2ac2dd56e2d3dc255882da1223de8426",
  "created_by": "user-001",
  "created_at": "2026-05-15T22:00:00Z",
  "status": "active",
  "tokens_used": {"input": 142000, "output": 8500},
  "expires_at": 1779494400,
  "concerns_total": 0
}
```

- `status`: `active` | `closed` | `budget_exhausted`
- `expires_at`: TTL — chat auto-archives 24h after last message
- `concerns_total`: denormalized count, summed across all `submit_response.concerns` so the sidebar can show a running total cheaply

### `STEER#{pr_id}#chat#{chat_id}#msg#{seq}` — chat message

```json
{
  "entityType": "SteerMessage",
  "role": "user" | "assistant" | "tool_use" | "tool_result" | "system",
  "content": "string",
  "ts": "2026-05-15T22:00:01Z",
  "tokens": {"input": 0, "output": 0},
  "tool_use": { "name": "read_file", "input": {...} },
  "tool_result": { "for_id": "toolu_...", "result_bytes": 4521, "truncated": false },
  "structured_response": { "summary": "...", "severity": "concern", "concerns": [...] },
  "error": null
}
```

`seq` is zero-padded monotonic (`0001`, `0002`, …) so DDB sort order = chronological. Tool messages persisted individually so the chat history reconstructs faithfully on reload.

### `STEER#{pr_id}#summary` — denormalized index

```json
{
  "entityType": "SteerSummary",
  "chat_count": 1,
  "last_chat_id": "c1778890123",
  "last_message_ts": "2026-05-15T22:00:34Z"
}
```

Single-row lookup for the PR Review screen to know "does this PR have a steer chat?" without scanning. Updated on chat-create + last-message-write.

---

## Convo summary attached at merge

When Approve & Merge or Reject runs and any Steer chat for this PR has at least one assistant message, **automatically attach a summary as a GitHub PR comment** before merging/closing.

### Why

The Steer chat is the founder's adversarial-verification record. If they engaged the chat and decided to merge, the artifact of that verification belongs in the PR's permanent record on GitHub — not just in DDB. Future maintainers reading the merged commit can see "the founder questioned X and Y before approving" without needing access to Cawnex.

### What the comment looks like

```markdown
## Founder verification (Cawnex Steer)

Reviewer verdict: ✅ Approved — "{first 200 chars of reviewer summary}"

The founder discussed this PR with Cawnex's adversarial Steer agent before merging. Highlights from the conversation:

**Concerns raised:** 2 (severity: 1 concern, 1 info)

- `project_state.py:127` — bare `except Exception` swallows errors silently. The reviewer did not flag this.
- `list_projects` — N+1 query, calls `compute_current_state` per project.

**Conversation summary** *(3 turns, 18.4k input / 1.3k output tokens)*

> Q: What's the worst case if compute_current_state throws?
> A: Currently all projects silently show `draft` with no log entry...

> Q: Should I fix that before merging?
> A: That's a judgment call. The bare-except predates this PR...

_Steer chats are read-only; the agent cannot modify code or post to GitHub mid-chat. This summary was auto-generated by Cawnex at merge time._
```

### Implementation

`apps/api/src/steer/summary.py:build_pr_comment(chat_id) → str`. Reads all messages for the chat, formats by role:
- User messages become `> Q: ...`
- Assistant messages (the structured `submit_response`) become `> A: {summary[:300]}`
- All `concerns` across all assistant messages are deduplicated and listed
- Token totals from chat session
- Hard cap: comment body truncated to 60kb (GitHub's limit is ~65k)

### Behavior matrix

| Scenario | Comment posted? |
|---|---|
| No Steer chat ever created | No |
| Chat created, never sent a message | No |
| Chat with 1+ assistant turns, then Approve & Merge | **Yes** |
| Chat with 1+ assistant turns, then Reject | **Yes** (under the rejection reason) |
| Multiple chats on same PR | Yes — the comment includes the **most recent** chat. Earlier chats are referenced as "N earlier chats — see Cawnex for full history." |
| `gh pr comment` fails | Log + continue with merge/reject. The merge is the load-bearing action; the comment is decoration. Failure does not block. |

---

## Failure modes

| Failure | What happens | Behavior |
|---|---|---|
| **iOS disconnects mid-stream** | SSE closes; Lambda has no signal | Lambda finishes the turn, persists. iOS on resume queries `GET /chats/{c}/messages?after={seq}` and renders what arrived |
| **User cancels intentionally** | `DELETE /chats/{c}/in_flight` (Phase 3) | Anthropic stream is cancelled mid-token. If `submit_response` already fired, message is complete. If mid-text, partial message persisted with `status: "cancelled"` |
| **Anthropic API error mid-turn** | Lambda catches, persists system message with `error` field set | iOS renders error bubble. User retries |
| **`gh pr merge` fails (conflicts, branch protection)** | Non-zero exit code | Return 409 with stderr. MVI stays `ready_to_ship` (no DDB mutation). iOS surfaces sheet: "Merge failed: {reason}. Open in GitHub to resolve manually" |
| **`gh pr close` fails** | Same | 502 with error. MVI stays `ready_to_ship` |
| **Tool call crashes** (e.g., read_file on nonexistent path) | Returns error string in `tool_result` | Model sees the error, recovers naturally |
| **Chat exceeds 250k input tokens** | `POST .../messages` returns 402 before calling Anthropic | iOS: "Chat budget exhausted — open a new chat" |
| **Lambda cold start + first clone** | ~10-12s first-turn latency | iOS shows "Investigating…" placeholder |
| **PR head SHA drifted since chat started** (someone pushed) | First read after detect → re-clone | Chat-level event `pr_branch_updated` sent to SSE; iOS surfaces "PR was updated" banner |
| **Multiple concurrent chats on same PR** | All allowed; each gets its own `chat_id` | iOS picker if `chat_count > 1`; default opens most recent |
| **`gh pr comment` fails during merge summary attach** | Logged | Merge continues; warn the user post-merge: "PR merged. Summary comment failed to post — see logs" |

---

## Budgets and rate limits

| Limit | Value | Env var |
|---|---|---|
| Per-chat input tokens | 250,000 | `STEER_CHAT_MAX_INPUT_TOKENS` |
| Per-chat output tokens | 50,000 | `STEER_CHAT_MAX_OUTPUT_TOKENS` |
| Per-turn output tokens | 8,000 | `STEER_TURN_MAX_OUTPUT_TOKENS` |
| Tool calls per turn | 30 | `STEER_TURN_MAX_TOOL_CALLS` |
| Active chats per user per project | 10 | `STEER_MAX_ACTIVE_CHATS_PER_PROJECT` |
| Chat TTL after last message | 24h | `STEER_CHAT_TTL_HOURS` |
| Message content max length (iOS-side) | 4,000 chars | iOS const |
| PR comment body max length | 60kb (60_000 bytes) | constant |

All numbers calibrated for Haiku 4.5 (200k context window). With project docs (~30k tokens) + reviewer outcome (~3k) + implementer outcome (~5k) + chat history, a 250k input budget supports ~6-8 substantive turns.

---

## Adversarial system prompt

```
You are a skeptical second reviewer for a pull request on the Cawnex project.

Your job is NOT to summarize the PR. Your job is to find what the first
reviewer missed. The first reviewer's verdict is in your context. Your
job is to be adversarial to that verdict: assume they were lazy, or
hurried, or fooled by surface-level correctness.

You have read-only tools to read any file, grep, or glob across the
codebase at the PR's head SHA. You cannot write, run, or execute
anything. You cannot post to GitHub. You can only investigate and report.

Operating rules:

1. Before answering ANY user question, read at least one file from the PR
   diff. Don't reason from filenames alone.
2. If the user asks "is this safe?", "did the reviewer miss anything?",
   or any variant, default to assuming YES — find specific evidence.
3. When you do find a concern, be specific: file path + line range + why
   it matters. "Error handling looks weak" is not useful. "In
   project_state.py:127, the bare `except Exception` swallows
   compute_current_state failures and silently returns 'draft', so
   anyone debugging will see no log line. This will mask future
   regressions" is useful.
4. If you genuinely can't find any concerns after investigation, say so
   plainly. Don't manufacture concerns. (severity=info, concerns=[])
5. You're talking to the founder. They wrote the spec. They know the
   codebase. Skip preamble. Don't explain what the PR does — they know.
   Lead with the answer.

You must end every turn with the `submit_response` tool call. Even a
single-sentence answer ends with submit_response.

Context loaded:
- PR #{pr_number} metadata (title, branch, head SHA, diff stats)
- The first reviewer's verdict and reasoning
- The implementer crow snapshot (instructions, files_changed,
  commit_message)
- All four project documents (vision, architecture, glossary, design)
- The current chat history (previous turns)
```

---

## Tools available to Steer

| Tool | Schema | Bounds |
|---|---|---|
| `read_file` | `{path: string}` | Returns up to 50KB. Truncated with marker if larger. Path must resolve inside `/tmp/steer-{chat_id}` — path-escape guarded |
| `grep_files` | `{pattern: string, path: string?}` | Ripgrep. Returns up to 100 matches |
| `glob_files` | `{pattern: string}` | Returns up to 200 paths |
| `submit_response` | `{summary: string, severity: "info"\|"concern"\|"blocker", concerns: string[]}` | **Terminator** — emit final structured response. `concerns` is the adversarial list of things-found (may be empty). `summary` is prose |

Path-escape guard: every tool input path is resolved against the worktree root via `Path(root).joinpath(input_path).resolve()`; if the result is not inside `root`, the tool returns an error.

---

## Phases

### Phase 1 — Approve & Merge + Reject

Smallest, ships first; immediately unblocks PR #16 and any future PRs.

1. New file `apps/api/src/routes/pr_actions.py` with the two routes.
2. New module `apps/api/src/github_actions.py` wrapping `subprocess.run` for `gh pr merge` and `gh pr close`. The Lambda already has the `gh` CLI in its layer (verify; install if not).
3. CDK: grant API Lambda read on `cawnex/dev/github-token` Secret.
4. Murder reactor's `_maybe_transition_wave` already handles wave-terminal; route just calls it via DDB Streams (existing path).
5. iOS: wire merge + reject buttons. Confirmation sheets. Error sheets.
6. Tests: route happy path, gh-failure 409, idempotency, wave-transition.

### Phase 2 — Steer chat (the meat)

1. DDB schema validation tests for `STEER#{pr_id}#chat#{c}`, `#msg#{seq}`, `#summary`.
2. `apps/api/src/steer/` module: `chat_session.py`, `repo_clone.py`, `tools.py`, `loop.py`, `system_prompt.py`, `summary.py`.
3. New routes `POST .../steer/chats` and `POST .../chats/{c}/messages`.
4. Stream service gains `steer_message_delta` event type. Per-chat SSE topic (`steer/{chat_id}`).
5. iOS: `SteerChatScreen`, `SteerChatViewModel`, `APISteerService`, suggested-question chips wired.
6. iOS PR Review screen: enable Steer button, show concerns sidebar with running tally, show "PR has N steer chats" badge.
7. Hook chat-closure into Phase 1's merge/reject (close active chats; attach summary).
8. Tests: tool-use loop, budget enforcement, mid-stream cancel, expired chat read-only.

### Phase 3 — Polish + observability

1. Mid-stream cancel via Anthropic stream cancellation (`DELETE /chats/{c}/in_flight`).
2. PR head SHA drift detection + re-clone.
3. Multi-chat picker UI in iOS.
4. CloudWatch metrics: chats started, concerns raised per chat, merge approval rate (with vs without prior chat), token cost per chat.
5. Per-project Steer cost dashboard.

---

## What we do NOT build

- **No code mutation from Steer.** No "push fix" button, no Fixer crow assignment from chat, no GitHub PR comments mid-chat. The chat is investigation-only.
- **No multi-user chat.** One founder per chat.
- **No token-stream replay.** If you missed the streaming render, you missed it. The persisted message is the truth.
- **No alternative model per chat.** Haiku 4.5 only.
- **No "approve from chat".** If the conversation convinces you to approve, you close the chat and click Approve & Merge. Single mutation point per action.
- **No bi-directional chat sync across devices in real time.** If you open the chat on iPad while iPhone is mid-turn, the iPad sees the chat history on load; new tokens stream only to the device that's actively connected.
- **No automated re-run of Steer when PR is updated.** Drift detection triggers a UI banner; the founder decides whether to start a new chat.

---

## Rejected alternatives

**Steer hosted on Worker (Fargate) instead of Lambda.** Worker would avoid Lambda's 15-min cap and the `/tmp` clone-on-cold-start. But Worker is currently zero-scaled when idle; first chat would trigger a ~60s Fargate cold start. Adds a new "Worker mode" (not executing waves but holding interactive chat). For v1, where PR review is a short-lived activity (minutes, not hours), Lambda is the right runtime. If usage explodes — many concurrent long chats — migrate to Worker; the chat session model in DDB is runtime-agnostic.

**Steer triggers a Fixer crow on user request.** Originally considered, then removed. The reason: the Cawnex Steer agent is structurally a *verification* mechanism, not an *editing* mechanism. Conflating the two muddies the chat's purpose ("am I investigating or am I rewriting?") and creates an attack surface (a malicious prompt convincing Steer to push bad code). Keeping Steer read-only is a stronger architectural promise. Push-fix can be a separate future action.

**Approve & Merge as a single endpoint that auto-decides squash vs rebase based on commit count.** Considered briefly. Rejected for explicitness — every project should pick one strategy and stick to it. We chose `--rebase --delete-branch`.

**Per-PR cost limits instead of per-chat.** Considered. Rejected because the natural reset is "open a new chat" — per-chat budget creates a clean retry path, per-PR limits create a frustrating "you've used up this PR's review budget" wall.

**Posting Steer comments to GitHub mid-chat (as the agent investigates).** Considered. Rejected because the chat is a working-thought process; only the conclusion (at merge time) belongs in the PR's permanent record.

---

## Open questions

None blocking. Phase 1 (merge + reject) is tightly scoped enough to start immediately. Phase 2 (Steer) is well-bounded enough to plan once Phase 1 ships.
