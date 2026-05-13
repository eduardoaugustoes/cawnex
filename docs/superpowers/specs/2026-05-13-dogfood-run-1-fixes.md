# Dogfood run 1 — fix bundle before run 2

**Run:** Wave `w1778712620964`, project `cawnex-e26784`, dev stage, 2026-05-13 22:50–22:56 UTC.
**Outcome:** Full crow chain ran (planner + implementer + 3× reviewer + 2× fixer). MVI auto-failed at FIX_CYCLE_LIMIT=2 because the implementer deleted the production `TenantDB` class and the fixer couldn't recover. PR #15 opened, must be closed without merge.
**Cost:** ~$0.30 real (Anthropic Console ground truth). Cawnex reported $0.886 because of bug #4 below.

This brief lists every fix worth shipping before the next dogfood attempt. Each section is sized to fit one MVI (~2–6h human-equivalent) and is independent — they can dispatch in parallel or in the order suggested.

The goal of this brief is not "ship all of these." The goal is: **the next session reading this brief should be able to choose 3–5, plan them as MVIs in Cawnex's backlog, and dispatch them with confidence that the factory has been hardened enough that the dispatch itself isn't the experiment.**

The fixes are grouped by what they unblock. Fix #1 unblocks every future run. Fixes #2–#4 keep the loop honest about what it's doing. Fixes #5–#6 are the ones that would have prevented run 1's specific failure. Fixes #7+ are hygiene.

---

## Fix 1 — Project create must require + validate a GitHub repo

**Why now:** Run 1 attempt 1 died because the Cawnex project was created without a `repo` value. The project root record had `repo: NULL`; Wave inherited `""`; Murder crashed on contract violation with no UI signal. Required two manual interventions: a DDB `update-item` to patch the project record, and a wave cancel to abandon the dead run. Every new Cawnex project today will repeat this.

**Where:**
- API: `apps/api/src/routes/projects.py` — the create-project endpoint must reject 422 on missing/empty `repo`.
- Validate the repo string is `owner/repo` shape (regex `^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$`) — empty + bad shapes both fail.
- iOS: `Features/Project/...` create-project screen must present a "GitHub repository (owner/repo)" field marked required with inline validation matching the API's regex.
- Optional bonus: API does a HEAD `https://api.github.com/repos/{repo}` with the stage's PAT and surfaces 404 / 403 as a "We can't see this repo with the factory's GitHub credentials" error before accepting the project.

**Acceptance:** Creating a Cawnex project with empty/malformed `repo` returns 422 from API and shows inline error in iOS. Creating with a valid `owner/repo` persists `repo` to both `T#{tenant}|P#{project_id}` ProjectEntry and `T#{tenant}#P#{project_id}|S#` root snapshot.

**Out of scope:** GitHub App onboarding (covered separately by `2026-05-13-github-app-onboarding-design.md`); we're just doing the PAT-era guard rail.

---

## Fix 2 — Wave activate must refuse empty repo with 409

**Why now:** Defence in depth. Even with Fix 1 in place, a legacy project could exist with `repo: ""`. Today the wave-activate route happily flips MVIs to `queued` and lets Murder crash. Should return 409 with a clear error.

**Where:** `apps/api/src/routes/waves.py:316 activate_wave`. After loading the wave item, also load the project record (`db.get_item(sk=f"P#{project_id}")`) and refuse activation if `project.get("repo", "")` is empty.

**Acceptance:** Activating a wave under a project with no `repo` returns 409 `{detail: "Project has no GitHub repo — set one in project settings before launching a wave."}`. iOS surfaces the message as a sheet-level error, not an alert.

---

## Fix 3 — Murder failure must write an iOS-visible event

**Why now:** Run 1 attempt 1's Murder crash was completely invisible to the founder. The wave sat "Executing" with `wave_activated` + `worker_warming` events in the live feed, but Murder was in a CloudWatch crash loop. No `mvi_failed` event. No "blocker detected." The founder has no UI breadcrumb that the run is dead.

**Where:** `lambdas/murder/src/murder/handler.py` `lambda_handler` exception handler. When `react_to_mvi_queued` raises (most importantly `ContractViolation`), write a `mvi_failed` event to `cawnex-events-{stage}` keyed `T#{tenant}#P#{project}#W#{wave_id}` with message describing the failure cause. Then transition the MVI to `failed` so it stops re-firing the stream.

Also: when Murder's contract validator rejects a write, the stream record will retry forever by default. Configure the event-source-mapping with a finite `MaximumRetryAttempts` (e.g. 3) and a DLQ.

**Acceptance:**
1. Force a contract violation (e.g. POST a queued MVI with `repo: ""` directly to DDB). Within 5s, the iOS Wave Execution live feed shows a red event `"MVI failed: repo is required"`.
2. The MVI item transitions to `status: failed` after first failure; Murder doesn't retry indefinitely.
3. CloudWatch shows a single error log, not a crash-loop stream.

---

## Fix 4 — Cost math: derive prices from deployed model, capture cache tokens, persist model field

**Why now:** Run 1's Wave Execution UI showed budget `$0.886 / $20.00` spent. Actual Anthropic Console billing for the same window: ~$0.30. Cawnex over-reports ~3× because:
- `worker/config.py:29-30` hardcodes Sonnet-4 prices (3 / 15 microdollars per token in/out)
- Deployed model is Haiku 4.5 (`cawnex-stack.ts:518` `ANTHROPIC_MODEL` override) at ~1× / 5× microdollars
- `worker/claude.py:85-86` captures only `input_tokens` + `output_tokens`; throws away `cache_creation_input_tokens` and `cache_read_input_tokens`
- `ClaudeResult.model` is populated but `executor.py:271-276` drops it from the persisted `Cost` record

Trust collapses if the budget dashboard lies — and it already lies.

**Where:**
1. `worker/claude.py:ClaudeResult` add `cache_creation: int` and `cache_read: int` fields; populate from `response.usage.cache_creation_input_tokens or 0` / `cache_read_input_tokens or 0`.
2. `worker/models.py:Cost` add `model: str` and `cache_creation`/`cache_read` token counts.
3. `worker/cost.py:calculate_credits(usage, model)` accept a model id; look up prices from a per-model table.
4. New module `worker/pricing.py`:
   ```python
   # Microdollars per token. Sourced from console.anthropic.com/settings/pricing on YYYY-MM-DD.
   PRICES = {
       "claude-haiku-4-5-20251001":  {"in": 1, "out": 5, "cache_write": 1, "cache_read": 0},
       "claude-sonnet-4-20250514":   {"in": 3, "out": 15, "cache_write": 4, "cache_read": 0},
       # Add models as deployed.
   }
   ```
   Round numbers above are placeholders — pull current real per-model prices from the Anthropic Console pricing page at fix time and write the source date in a comment.
5. Executor passes `claude_result.model` and the cache token counts into `Cost.from_*` so the persisted snapshot includes them.
6. iOS Wave Execution screen optional: if `cache_*` > 0, surface "saved $X via cache hits" next to the spent line.

**Acceptance:**
1. Run a smoke crow on Haiku 4.5. The crow's `cost.credits` matches `tokens_in × 1 + tokens_out × 5` (or whatever the actual current Haiku price table is), not the Sonnet number.
2. `cost` record in DDB has a `model` field with the value used.
3. Comparing wave.budget.spent against the Anthropic Console for the same window agrees within 5%.
4. If `ANTHROPIC_MODEL` env is changed without code change, prices follow the model automatically.

**Out of scope:** Enabling prompt caching itself (separate decision). This fix just makes the accounting *correct* when caching is enabled.

---

## Fix 5 — Planner and implementer must actually read the spec when listed in `context_files`

**Why now:** The MVI directive included `Spec: docs/superpowers/specs/2026-05-13-project-state-readout-design.md`. The planner correctly added the spec path to task 1's `context_files`. But:
- Planner's `gather_planner_context` walks the file tree and reads only the first 30 alphabetical files (`context.py:40`). The spec lives at `docs/superpowers/specs/2026-05-13-...md` — alphabetically late. Planner never read spec content.
- Implementer's `gather_implementer_context` is *supposed* to read every file in `files_to_read` + `files_to_modify`. The aggregated top-level `context_files` did include the spec. But the total `context_gathered` chars logged was only 9,673 — the 18KB spec almost certainly was not in that buffer. Implementer hallucinated DB methods that don't exist, `ProjectState` values that don't match Cawnex's data model, and deleted `TenantDB`.

**Diagnosis tasks:**
1. Reproduce by running a smoke test crow that lists a known spec path in `context_files` and log every file path `_read_file_safe` returns non-None for. Confirm whether the spec path is actually being attempted and what it returns.
2. Check: does `executor.py:223 _gather_context` for IMPLEMENTER receive the *top-level* `instructions_data["context_files"]` correctly? (`executor.py:217-221` parses `instructions` JSON — verify the planner's payload structure round-trips.)
3. Check `_read_file_safe` for silent failures other than size: encoding issues, path resolution, worktree-relative-path bugs.

**Fix tasks:**
1. Both `gather_planner_context` and `gather_implementer_context` must *always* read any markdown file under `docs/superpowers/specs/` plus any path explicitly named in the directive. Add a heuristic: if the directive text contains `Spec: <path>` or `spec: <path>`, the path is added to `files_to_read` regardless of what the planner said.
2. Planner gets a separate context-gathering pass that prioritizes files mentioned in the directive — those should land in the first 30, not random alphabetical files.
3. Log `files_read` (the list of actual paths read) in the `context_gathered` event so we can verify post-hoc what was in the prompt.

**Acceptance:**
1. Smoke test: run a planner crow with directive `Refactor X. Spec: docs/superpowers/specs/SOMESPEC.md`. The planner's logged `files_read` includes the spec path. Total `chars` ≥ size of spec.
2. The corresponding implementer's logged `files_read` includes the spec path.
3. Re-run the project-state-readout MVI manually with these fixes; the planner's outcome.tasks must reference at least 2 specific identifiers from the actual spec (not generic invented ones like `ProjectState.PLANNING`).

---

## Fix 6 — Reviewer must receive spec + planner outcome in its context

**Why now:** The reviewer surprised us positively — git diff alone was enough to catch "TenantDB deleted." But the reviewer rejected for *structural* destruction; it couldn't judge *semantic* correctness against the spec because the spec wasn't in its prompt. Reviewer's `gather_reviewer_context` gives only git diff + ≤10 changed-file contents.

If a future implementer produces structurally-clean but semantically-wrong code (e.g. adds a `state` field but computes it from wrong source data), the reviewer will rubber-stamp.

**Where:**
1. `worker/context.py:gather_reviewer_context` accept the planner's `outcome.tasks` and the directive-cited spec path; read both into the prompt.
2. `murder/src/murder/context_builder.py:_build_reviewer_instructions` (the function exists, currently only injects `planner_outcome` tasks list) must also embed the spec path under a `## Spec` heading so the reviewer can verify acceptance criteria against it.

**Acceptance:** A smoke reviewer crow's prompt includes the spec file contents and the planner's task list. Reviewer can quote specific spec requirements in its decision.

---

## Fix 7 — iOS LIVE badge must actually be live (wire SSE consumer)

**Why now:** The SSE Lambda at `lambdas/sse/handler.py` is deployed, wired to a Lambda Function URL, validates Cognito JWTs, and polls the events table at 1s intervals streaming SSE chunks. It is **orphaned**: zero iOS consumer. iOS `WaveExecutionViewModel.swift:69` runs a `Timer.scheduledTimer(withTimeInterval: 3.0)` REST poll, which Apple suspends on background. Founder must leave and return to the screen to see new state. The "LIVE" badge is a lie.

**Where:**
1. New iOS service `Features/Waves/SSEWaveEventStream.swift` consuming `URLSession.shared.bytes(for:)` against the SSE Lambda Function URL. Parse SSE-framed events; emit to the existing event-list observable.
2. `WaveExecutionViewModel` start the SSE subscription in `load()` instead of the Timer poll. Keep Timer as fallback when SSE returns non-200 or disconnects.
3. Handle Lambda's 14-minute SSE duration cap (`sse/handler.py:23 MAX_DURATION`) — when stream ends client-side, reconnect.
4. Surface a real disconnected indicator when SSE is not connected (badge stays grey instead of "LIVE").

**Acceptance:**
1. Activate a wave. Live feed updates appear in iOS within ≤2s of being written to the events table.
2. Background the app for 30s; foreground it. Events that arrived during background appear immediately on foregrounding (SSE reconnect catches up).
3. Cut network mid-wave. Badge changes from "LIVE" to a reconnecting indicator. When network returns, badge returns to LIVE and missed events appear.

**Out of scope:** Replacing the events-table-with-DDB-stream backbone with an EventBridge or AppSync subscription model. That's its own bigger architectural call.

---

## Fix 8 — GSI1 ghost-crow cleanup on status transition

**Why now:** Before run 1 attempt 2's wave, the Worker was poll-cycling for 15+ minutes on a `cr_plan_01` from project `caioo-653d43` showing as `DISPATCH#pending` in GSI1 but returning `already claimed` on conditional update. Probably a partial-failure leftover. Every 10 seconds wastes a Fargate poll + a DDB query. Permanent noise.

**Where:**
1. Audit `worker/blackboard.py:conditional_status_update` and `executor.py` writes — when transitioning `pending → running` and then `running → completed/failed`, ensure the GSI1 attributes (`GSI1PK = "DISPATCH#pending"`) are cleared from the item. PutItem with the completed snapshot at `worker/handler.py:140` should already drop GSI1PK if the new item doesn't set it — verify.
2. One-shot cleanup: scan GSI1 for entries where the underlying item is no longer `pending`; clear them. Probably a 50-line ops script committed to `lambdas/worker/scripts/`.

**Acceptance:**
1. After a crow transitions to completed, GSI1 query `PK = DISPATCH#pending` no longer returns it.
2. Run the cleanup script against dev — Worker poll's `pending_count` drops to 0 when no real work is queued.

---

## Fix 9 — iOS backlog-MVI tap routes correctly

**Why now:** `apps/ios/Cawnex/Cawnex/Core/Network/APIMVIService.swift:224 findWaveForMVI` only succeeds if the MVI is already inside a Wave. Tapping a backlog MVI throws `Could not find a wave containing this MVI` — a worse-than-useless error because the right action ("add this MVI to a wave") isn't reachable from that screen.

**Where:**
1. `Features/Backlog/...` MVI-list tap target should route to an MVI edit/preview screen scoped to the *backlog* item, not the wave Blackboard screen.
2. That edit/preview screen should have a "Launch as Wave" button that deep-links into WaveLaunch pre-filling Goal + this MVI + a default directive of the MVI name.
3. Alternative: the Blackboard screen, on `findWaveForMVI` failure, offers a "This MVI isn't in a wave yet — add to a new wave?" affordance instead of an error.

**Acceptance:** Tap a backlog MVI under any Goal → reach a meaningful screen with at least one path forward (edit, delete, or launch as wave).

---

## Optional fixes worth picking up if cycles allow

These were observed but lower priority than 1–9:

- **F10:** Plan-MVIs guided chat flow — JSON leakage, no recovery, state-loss on background. Big surface-area fix. Workaround documented in [[cawnex-plan-mvis-flow-broken]].
- **F11:** Goal-card MVI counter is stale on Launch Wave picker (shows "0 MVIs" for goals that have MVIs). Caching bug in the goals list endpoint or iOS-side state.
- **F12:** Directive field required on Launch Wave even when launching one named MVI. Default the directive to the MVI name when `mvi_ids.length == 1`.
- **F13:** Doc synthesizer says "vision document" for all doc types ([[cawnex-doc-synthesizer-bug]]).
- **F14:** iOS chat input silent ~7500 char truncation ([[cawnex-ios-chat-input-cap]]).
- **F15:** Two parallel Monarchs ([[cawnex-has-two-monarchs]]) — promote MCP-on-production-Monarch, archive `mcp-monarch/`.
- **F16:** Spurious `{{secret:name}}` template-resolution false positives. Tighten the regex.
- **F17:** `auto_mode` defaults to `"off"` — Council never fires for new projects. Consider defaulting to `"supervised"` so Council runs with founder approval gates.

---

## Suggested ordering for the next run

If we want one more dogfood attempt before broader rework, the minimum-viable bundle is **Fix 1 + Fix 2 + Fix 3 + Fix 5 + Fix 6**. That gives:
- Project create won't accept a bad config (Fix 1)
- Wave activate won't try to dispatch a bad config (Fix 2)
- Failures are visible to the founder (Fix 3)
- The implementer actually reads the spec (Fix 5)
- The reviewer can validate output against the spec (Fix 6)

That leaves cost-math (Fix 4) and SSE (Fix 7) as honesty fixes — important but not blocking another factory run. They go in the next batch.

Fixes 1, 2, 3 are small API/handler patches (~2h each).
Fix 4 is a medium refactor (~4h).
Fix 5 is the diagnostic-heavy one (~4–6h).
Fix 6 is small (~2h).
Fix 7 is a small-medium iOS task (~4h).
Fix 8 is small (~2h + ops script).
Fix 9 is iOS navigation (~3h).

Approx total for the recommended bundle: **~16h** human-equivalent. With Cawnex AI factory's actual implementer cost: probably $5–15 of Anthropic spend if it works, more if it loops.

---

## Operating-log seed for the next session

The next Claude session reading this brief should also consult these memory files for context:

- `cawnex-dogfood-run-1-findings.md` — the first attempt (the contract-violation crash)
- `cawnex-dogfood-run-2-findings.md` — the second attempt (the failed PR run that produced 14 more findings)
- `cawnex-dogfood-runway.md` — the original Milestone-1 setup and intent
- `cawnex-plan-mvis-flow-broken.md` — yesterday's planning friction findings

These are private to Eduardo's Claude memory; this brief in the repo is the public-to-Claude-sessions version.
