# Agent Isolation Hardening — Design Spec

**Date:** 2026-08-28
**Status:** Ready for implementation
**Origin:** Security audit of LLM isolation boundaries (this repo, 2026-08-28). Every finding below was verified by executing it, not by reading alone. Reproductions are recorded inline.

---

## 1. Problem statement

Cawnex runs LLM-driven "crows" that read a customer repo and emit code changes, plus a "council" of six LLM advisors that review the result. The isolation model is **capability-based, not permission-based**: the model is given a small set of hand-written tools rather than a general agent harness with permission prompts.

That core decision is sound and must be preserved. The defects are *inconsistencies in enforcing it* — the read path is contained, the write path is not; the worker's tools are scoped, the council's are not; the safety gate fails open rather than closed.

### 1.1 What is already correct (do not regress)

These are load-bearing and must survive every change in this spec:

- The model has **no shell, no network, no write tool**. Its entire surface is `read_file`, `glob_files`, `grep_files`, `list_dir` (`lambdas/worker/src/worker/tools.py:419`) plus a `submit_result` terminator.
- Mutations are **data, not actions**: the model returns a `changes` array; host code applies it (`lambdas/worker/src/worker/git_ops.py:137`).
- `tool_choice={"type": "any"}` (`lambdas/worker/src/worker/claude.py:281`) forces server-side schema validation of the terminator payload.
- **The merge gate is genuinely well built.** No `merge_pr` exists anywhere in `lambdas/`; merging lives only behind authenticated API routes gated on `status == "ready_to_ship"` (`apps/api/src/routes/pr_actions.py:88`). Nothing in this spec grants the agent merge authority.
- Loop bounds are layered: 25 iterations (`claude.py:166`), 600s SIGALRM (`executor.py:216`), token precheck (`claude.py:234`), 50-file read cap (`tools.py:21`).
- Secret *values* are deliberately kept out of prompts (`executor.py:96-101`) and scrubbed in a `finally` (`executor.py:532-535`).
- `TenantDB` (`apps/api/src/db/client.py:31-37`) derives every partition key from a JWT claim the client cannot set. Cross-tenant reads via path parameters are structurally prevented.
- Commit messages were already hardened against shell injection via stdin (`git_ops.py:167-196`). That fix is the model for F2 below.

### 1.2 Threat model

Two adversaries, deliberately distinguished because they need different defenses:

- **A1 — Malicious repo content.** Anyone who can land text in a customer repo, or open a PR against it. Reaches the model because raw file contents are interpolated into prompts (`context.py:111,141`) and PR bodies reach advisors (`council/tools/github.py:32`). Requires no Cawnex account.
- **A2 — Authenticated tenant.** A signed-up user, supplying fields the API accepts without validation. Requires no LLM misbehavior at all.

Non-goals for this spec: rewriting the prompt architecture, adding a moderation layer, per-tenant EFS access points, container hardening (root user / readonly rootfs), egress restriction, CloudTrail. Those are real and tracked in §5, but they are infra-stack changes with a different review path and blast radius.

---

## 2. Verified findings

Each finding below carries the reproduction that confirmed it. Severity is ranked by exploitability, not by theoretical impact.

### F1 — Model-controlled path escapes the worktree on write (CRITICAL)

`apply_changes` joins a model-authored path straight into `open(w)` with no containment:

```python
# lambdas/worker/src/worker/git_ops.py:141
filepath = os.path.join(worktree_dir, change["path"])
```

The read tools *do* enforce containment via `_resolve_safe` (`tools.py:35-47`, realpath + prefix check). The write path has no equivalent. Verified:

```
read  ../../../etc/passwd  -> blocked
read  /etc/passwd          -> blocked
write ../outside/PWNED.txt -> ESCAPED
write /abs/path/ABS.txt    -> ESCAPED
```

`os.path.join(worktree, "/etc/x")` returns `/etc/x` — an absolute second argument discards the prefix entirely.

**Why the schema does not stop this:** `IMPLEMENTER_SUBMIT_RESULT_SCHEMA` (`tools.py:271`) types `path` as `"type": "string"` with description *"Path relative to repo root."* A description is not a constraint; the API validates type, not shape.

**Exploit chain (A1):** repo file contents are interpolated into the implementer prompt inside plain triple-backtick fences with no escaping (`context.py:141`) → model emits `{"path": "../../other-tenant-repo/.git/hooks/pre-commit"}` → written → `git add -A` (`git_ops.py:162`) → `git push --force` (`git_ops.py:172`).

**Aggravating factor:** git hooks are never disabled. `grep -rn "core.hooksPath" lambdas/worker/src/ infra/lib/` returns nothing. A written `.git/hooks/pre-commit` executes on the very next `git add`/`git commit` the worker runs — converting a file write into code execution inside the worker container.

**Mitigating factor (real, but insufficient):** the EFS access point chroots the mount to `/T/dev-tenant` (`infra/lib/cawnex-stack.ts:466`), so `../` cannot climb above the tenant root. NFS enforces what Python does not. But that path is hardcoded and shared by *all* tenants and by the council (`cawnex-stack.ts:597`), so it bounds blast radius without providing tenant isolation.

### F2 — Unvalidated `repo`/`branch` reach `shell=True` (CRITICAL)

`run_git` executes with `shell=True` (`git_ops.py:29`). `_normalize_repo` only strips a prefix and suffix:

```python
# lambdas/worker/src/worker/git_ops.py:42-45
repo = repo.removeprefix("https://github.com/").removesuffix(".git")
```

The API accepts `repo` as a bare unconstrained string — `repo: str = ""` (`apps/api/src/routes/projects.py:26`), no `Field`, no pattern. Verified:

```
input:  owner/repo$(id>/tmp/pwned).git
after normalize: owner/repo$(id>/tmp/pwned)
resulting cmd:   git clone https://x-access-token:TOK@github.com/owner/repo$(id>/tmp/pwned).git ...
```

Command substitution survives intact. This is **A2 → RCE**, requiring no LLM involvement. The worker container runs as root (no `USER` in `apps/worker/Dockerfile`) holding `GITHUB_TOKEN`, `ANTHROPIC_AUTH_TOKEN`, and a task role with `vaultKey.grantDecrypt` for every tenant (`cawnex-stack.ts:558`).

`branch` has the same shape, reaching `git_ops.py:99,102,172`, and is read with an empty-string default (`reactor.py:110` et al) with no validation anywhere.

### F3 — Council advisors read arbitrary absolute paths (CRITICAL)

Worse than the worker, because there is no containment at all:

```python
# lambdas/council/src/council/tools/filesystem.py:20
if not os.path.isfile(path):
```

Dispatched via a kwargs splat (`tools/palette.py:194`). The only scoping is `is_in_scope` (`palette.py:153-168`), which substring-matches for UX and Cost and then **returns `True` unconditionally** for everyone else. Verified by execution:

```
security      in_scope('/etc/passwd') -> True
architecture  in_scope('/etc/passwd') -> True
read_file('/etc/passwd')              -> {'content': '## User Database...'}
```

`is_in_scope` was written for relevance, not security. Advisors run on the same shared multi-tenant Fargate host as the worker, on the same EFS mount. `read_integration_file` (`tools/git.py:67`) has the same absolute-path-discards-prefix bug as F1.

### F4 — The safety gate fails open (HIGH)

```python
# lambdas/council/src/council/actions.py:46-52
elif decision.action == DecisionAction.ESCALATE:
    if auto_mode == "supervised":
        _notify_human(blackboard, pk, wave_id, decision)
    else:
        # In full auto, Monarch makes the final call — treat as approve
        _deliver_wave(blackboard, pk, wave_id)
```

Combined with `_exception_to_abstain` (`orchestrator.py:147`) and `return_exceptions=True` on the `asyncio.gather` (`orchestrator.py:166`): **six crashed advisors → six abstains → no majority → ESCALATE → wave ships.** Reachable by an API outage or a bad deploy, with no adversary. Mass-abstain is `synthesis.py:82` ("insufficient context") — the case where the council knows it knows nothing is exactly the case that currently auto-approves.

### F5 — Per-crow and per-MVI budget caps are dead code (HIGH)

`check_mvi_budget` and `check_crow_budget` are defined (`lambdas/murder/src/murder/cost.py:61,70`) and called nowhere outside tests. Verified:

```
$ grep -rn "check_crow_budget\|check_mvi_budget" --include="*.py" lambdas apps | grep -v /tests/
lambdas/murder/src/murder/cost.py:61:def check_mvi_budget(
lambdas/murder/src/murder/cost.py:70:def check_crow_budget(
```

The wave-level check that *does* run passes `proposed=0` (`reactor.py:91,205,471`), so `cost.py:41` computes `spent + 0` — it only ever answers "have we already overspent?", never "will this next call overspend?". A crow with $0.01 remaining proceeds and may spend up to 25 iterations × 32,768 output tokens (`claude.py:166`, `executor.py:311`) with no mid-loop check.

`budget_micros` is additionally client-supplied with no upper bound (`apps/api/src/routes/waves.py:41`).

### F6 — Integrator subprocesses inherit the full credential environment (HIGH)

`run_tests`, `run_lint`, `run_typecheck` (`integrator/checks/tests.py:17`, `lint.py:19,47`, `typecheck.py:17`) pass no `env=`, so they inherit `os.environ` wholesale. `pytest` executes *merged PR code* with `GITHUB_TOKEN`, `ANTHROPIC_AUTH_TOKEN`, live `SECRET_*` values, and the AWS task-role credential endpoint all reachable. This is the deterministic integrator path, not the LLM path — but it runs attacker-influenced code.

### F7 — Force-push with no lease; the main-branch guard does not cover the push (MEDIUM)

```python
# lambdas/worker/src/worker/git_ops.py:97
worktree_branch = branch if branch not in ("main", "master") else f"cawnex/{crow_id}"
# ...
# lambdas/worker/src/worker/git_ops.py:172
run_git(f"git push --force {push_url} {branch}", cwd=worktree_dir)
```

Line 97 renames the **local** branch; line 172 pushes the caller's **`branch`** variable. If `branch == "main"`, the guard has no effect on the push. Only the convention that `wave_launcher.py:55` populates `cawnex/{wave_id}-{mvi_id}` keeps this off main. No `--force-with-lease`, no branch-name allowlist. Repo-side branch protection is neither configured nor verified by this codebase.

### F8 — `grep_files` bypasses the containment `read_file` enforces (MEDIUM)

`grep_files` opens by bare join (`tools.py:165`) rather than `_resolve_safe`. Safe only because `os.walk` defaults to `followlinks=False` — but that guards symlinked *directories*, not symlinked *files*. Verified:

```
read_file('leak.txt' -> /etc/passwd)  -> blocked
grep_files('root')                    -> {'matches': [{'path': 'leak.txt', 'text': 'root:*:0:0:...'}]}
```

The same class of inconsistency as F1, on the read side.

### F9 — Live OAuth token prefix logged on every container start (LOW)

`apps/worker/main.py:22` logs `token[:15]`, `claude.py:127-133` logs `token[:12]`, to CloudWatch, on every start.

### F10 — Reviewer prompt is biased toward approval (LOW, judgment call)

```
prompts.py:161  Wrong blocking issues waste a full fixer cycle and burn budget.
```

Cost pressure applied to the component whose job is to block. A false block costs one cycle; a false approve ships the defect. Asymmetric costs deserve asymmetric framing.

### Corrections to earlier reporting

Two claims surfaced during the audit did **not** survive verification, and are recorded here so nobody re-raises them:

- **`unsafeUnwrap()` does not leak the token into the template.** `cawnex-stack.ts:509` uses `secretValue.unsafeUnwrap()`, but the synthesized output contains `{{resolve:secretsmanager:...}}`, and `grep -rlE "ghp_[A-Za-z0-9]{20}|github_pat_..." infra/cdk.out/` returns nothing. CloudFormation resolves it at deploy. The token *is* in the Lambda's plaintext env (readable via `lambda:GetFunctionConfiguration`) — a real but lesser issue, tracked in §5.
- **`/config` is not an information leak.** It returns an explicit allowlist of public Cognito identifiers (`apps/api/src/routes/config.py:22-29`), not an env dump. No action needed.

---

## 3. Design decisions

### D1 — One containment helper, shared, not three copies

F1, F3, and F8 are the same bug in three places. The fix is a single `resolve_within(root, path) -> str | None` primitive, with `tools._resolve_safe` becoming a thin delegate so the existing tested behavior is preserved exactly.

**Placement:** `lambdas/worker/src/worker/paths.py` (new). The council needs it too, but `lambdas/worker` and `lambdas/council` are separately packaged bounded contexts with no shared library and no cross-import — verified: neither `pyproject.toml` depends on the other. Duplicating ~15 lines into `lambdas/council/src/council/tools/paths.py` is correct here; inventing a shared package is a larger structural change than this spec should carry. The duplication is flagged in each module's docstring.

**Semantics (must match `_resolve_safe` exactly):**
- Absolute input → treated as a candidate, then realpath'd and prefix-checked (so `/etc/passwd` fails, but an absolute path *inside* the root succeeds).
- `realpath` before comparison, so `..` and symlinks both normalize.
- `full == root_real` allowed; otherwise require `full.startswith(root_real + os.sep)` — the `os.sep` guard prevents the `/mnt/repos/worktrees/cr_1-evil` sibling-prefix bug.
- Returns `None` on escape. Never raises. Never logs the resolved path at error level.

### D2 — Reject the whole changeset, not the offending file

If any path in `changes` escapes, `apply_changes` raises and the crow fails. Rationale: a partial write leaves the worktree in a state neither the model nor the reviewer reasoned about, and `git add -A` would commit the surviving half. Atomic rejection is both safer and easier to reason about. The crow-failure path already exists and is tested (`executor.py:379-415`).

### D3 — Defense in depth on writes: containment *and* hook neutralization

Containment alone still permits writing `.git/hooks/pre-commit` *inside* the worktree, which executes on the next commit. Both are needed:
- `resolve_within` for the path,
- `core.hooksPath=/dev/null` added to the git env in `run_git` and `_git_commit_with_stdin_message`.

`SKIP_DIRS` already excludes `.git` from walks (`tools.py:19`) but `read_file` can still target it and `apply_changes` can still write it.

### D4 — Validate `repo`/`branch` at both ends, and drop `shell=True`

Three independent layers, because each catches a different class:
1. **API boundary** — Pydantic `Field(pattern=...)` on `repo`, rejecting at HTTP 422 before storage.
2. **Worker boundary** — `_normalize_repo` validates after normalization and raises on violation. Data already in DynamoDB predates the API fix; the worker must not trust it.
3. **Execution boundary** — `run_git` takes `list[str]` and drops `shell=True`, so even a validation miss cannot become injection.

Layer 3 is the one that actually closes the class. Layers 1–2 give clean errors instead of confusing git failures.

**Regex:** `^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$` for repo. GitHub owner/repo names permit only alphanumerics, hyphen, underscore, period. Explicitly excludes `$`, backtick, `;`, `|`, `&`, space, newline.
**Branch:** `^[A-Za-z0-9_./-]+$` plus a rejection of `..` (git refname rule) and of leading `-` (argument injection).

`run_git` currently takes a string and is called ~20 times. Converting the signature is mechanical but touches every call site; it is its own task with its own review gate.

### D5 — Fail closed, but preserve the operator's intent

F4's `else` branch is not obviously wrong in intent — "full auto means don't block on a human" is a coherent product stance. What is wrong is that *inability to decide* is treated as *decision to approve*. The fix distinguishes:
- **ESCALATE from a genuine split vote** → keep current behavior in full-auto (Monarch decides).
- **ESCALATE from mass-abstain / advisor failure** → block, always, regardless of auto_mode.

This requires `synthesis` to distinguish the two, which it already nearly does (`synthesis.py:82` produces the "insufficient context" rationale). A new `DecisionAction.BLOCKED_INSUFFICIENT_CONTEXT` — or a boolean on the decision — carries it.

**This is the one decision in the spec that changes product behavior**, so it is sequenced last and flagged for explicit sign-off.

### D6 — Budget: wire the existing functions, do not redesign

F5's functions exist and are tested. The fix is calling them, plus passing a real `proposed` estimate instead of `0`. A full reservation/ledger system is out of scope — that is the `deterministic-wave-core` plan's territory (`docs/superpowers/plans/2026-07-02-deterministic-wave-core.md` makes the budget increment transactional). This spec does the minimum that stops unbounded per-crow spend, and bounds `budget_micros` at the API.

---

## 4. Acceptance criteria

Every criterion is a test that fails before the change and passes after.

| # | Criterion | Verifies |
|---|---|---|
| A1 | `apply_changes` with `path="../escape.txt"` raises; no file created outside worktree | F1 |
| A2 | `apply_changes` with an absolute `path` raises; no file created | F1 |
| A3 | `apply_changes` with a symlink-traversing path raises | F1 |
| A4 | A valid relative path still writes correctly; `delete` still deletes | F1 no-regress |
| A5 | Escape in *any* element rejects the whole changeset, writing nothing | D2 |
| A6 | Git env contains `core.hooksPath=/dev/null` in `run_git` and commit | D3 |
| A7 | `_normalize_repo("owner/repo$(id)")` raises | F2 |
| A8 | `POST /projects` with an injection payload in `repo` → HTTP 422 | F2 |
| A9 | `run_git` accepts `list[str]`; no call site passes a shell string | F2/D4 |
| A10 | Branch names with `..`, leading `-`, or metacharacters are rejected | F2 |
| A11 | Council `read_file('/etc/passwd')` returns a structured error, not content | F3 |
| A12 | Council `read_file` on an in-root relative path still succeeds | F3 no-regress |
| A13 | `read_integration_file` with an absolute path is rejected | F3 |
| A14 | Six abstaining advisors produce a blocking decision, not delivery | F4 |
| A15 | A genuine split vote in full-auto still delivers | F4 no-regress |
| A16 | A crow whose projected spend exceeds remaining budget does not call Claude | F5 |
| A17 | `budget_micros` above the cap → HTTP 422 | F5 |
| A18 | Integrator check subprocesses receive an explicit scrubbed `env=` | F6 |
| A19 | `commit_and_push` pushes `worktree_branch`, and uses `--force-with-lease` | F7 |
| A20 | `grep_files` cannot read through a symlinked file pointing outside | F8 |
| A21 | No token prefix appears in any log statement | F9 |

**Non-regression gate:** `lambdas/worker` (`pytest tests -q`, currently 14 passing in `test_git_ops.py` alone) and `apps/api` suites must stay green throughout. Council tests require DynamoDB Local (see §6).

---

## 5. Explicitly out of scope

Real, verified, and deliberately deferred — each needs an infra review path this spec does not have:

- Per-tenant EFS access points (`cawnex-stack.ts:466,597` hardcode `/T/dev-tenant` for all tenants and both services).
- Container hardening: worker runs as root, writable rootfs, no dropped capabilities, no `ephemeralStorageGiB`.
- Egress restriction: `allowAllOutbound: true` on all three SGs; public subnet + public IP in dev; no VPC endpoints.
- `dynamodb:LeadingKeys` — deliberately removed with a documented rationale (`cawnex-stack.ts:646`); the worker additionally holds `dynamodb:Query` on `${tableArn}/index/*`, including the GSI2 the schema labels "Cross-tenant queries (admin)".
- `GITHUB_TOKEN` in the API Lambda's plaintext env (a runtime `boto3` fetch is already possible — `grantRead` is on the next line).
- Single static GitHub token shared across all tenants; no per-tenant or GitHub-App installation tokens.
- Flat `worktrees/{crow_id}` namespace: `crow_id` is only MVI-unique (`reactor.py:1584`), so a collision makes `create_worktree` `shutil.rmtree` a live peer's work (`git_ops.py:83-91`). No orphan reaper exists.
- Prompt injection defenses generally (delimiting, spotlighting, escaping fences in `context.py:111,141`); `TRACE`-level Pipe logging of full tenant payloads (`cawnex-stack.ts:859`); no CloudTrail/WAF/MFA/alarm actions.
- Ungated self-modifying prompts: council reflection appends model-authored text into future system prompts (`memory_store.py:63`, `memory.py:70`).

---

## 6. Prerequisites and environment

- **Worker/API tests:** `cd lambdas/worker && pip install -e .[dev] && pytest tests -q`. Locally, `PYTHONPATH=src python3 -m pytest tests -q` works without install (verified: 14 passed).
- **Council tests are split.** The pure tool tests need nothing — verified: `PYTHONPATH=src python3 -m pytest tests/test_tools_filesystem.py tests/test_tools_palette.py -q` passes 14. But `test_actions.py` (where F4's fix lands) uses the `dynamodb_table` fixture (`tests/conftest.py:11`, default `http://localhost:8000`); without a local DynamoDB those 3 tests **error after a ~154s boto3 connection-retry timeout** rather than failing fast. Start it before touching Task 6:
  ```bash
  docker run -d -p 8000:8000 --name cawnex-ddb amazon/dynamodb-local
  ```
  This mirrors CI's `services: dynamodb` block (`.github/workflows/main-pipeline.yml:213`). Budget the wait: a full council run without it takes >2.5 minutes to report failures that are purely environmental.
- **Standards:** mypy `--strict`, black, complexity ≤ 10, bandit clean (`docs/STRICT-CODING-STANDARDS.md`). Conventional commits, **no AI attribution in commit messages or PR bodies**.
