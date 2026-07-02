# Adversary Review: Hierarchy Restructure Master Plan

Reviewed artifact: `docs/superpowers/plans/2026-07-01-hierarchy-restructure-master-plan.md`
Method: every factual claim in the plan was checked against the code on `main`. Empirical tests were run where words were insufficient (pytest against the lambda suites, pip vendoring of a local path dep). Line numbers below refer to the files as of this review.

## Verdict

**SHIP-WITH-FIXES — the staging order and governing rules are sound, but the plan contains five execution-breaking factual errors (Stage 0 CI job hangs, monarch can't `pip install`, `any_code` gating skips the very suites being added, the Stage-3 CloudFront analysis is self-contradicting, and Stage 3's whole mechanic ignores CloudFormation Stack Refactoring) plus a silent-deploy-death hole it warns about but never closes. Do not hand this to an executing agent until the blockers below are folded back into the plan.**

---

## Blockers (must fix before any code)

### B1. Task 0.1's CI job will hang, not pass — every lambda suite requires DynamoDB Local

The plan specs the new `services-tests` job as `pip install -e .[dev] && pytest` per package. Verified empirically:

- `lambdas/murder/tests/conftest.py:11-16` — fixtures connect to `http://localhost:8000` ("Requires DynamoDB Local running on port 8000: docker run -p 8000:8000 amazon/dynamodb-local").
- Same pattern in `lambdas/worker/tests/conftest.py`, `lambdas/council/tests/conftest.py`, `lambdas/monarch/tests/conftest.py`.
- I ran the murder suite locally without DynamoDB Local: 321 tests collect in 0.08s, then the run **hangs on the first integration test** (`tests/test_auto_mode_integration.py::TestAutoModeFullChain::test_reviewer_approve_triggers_council_in_auto_mode`) — killed after 14 minutes with zero tests completed. In GitHub Actions this burns runner-hours until the 6h job timeout, it does not "fail fast."

Additionally:
- `lambdas/monarch/` has **no `pyproject.toml`** (only `src/` and `tests/`) — `pip install -e .[dev]` errors immediately.
- `apps/stream/pyproject.toml` declares no dependencies and no `[dev]` extra — the specced install command installs nothing; the suite needs `requirements.txt` + test deps.

**Fix:** the job needs a `services:` block with `amazon/dynamodb-local` (and `DYNAMODB_ENDPOINT` env), a `pyproject.toml` for monarch, and a real install recipe for stream. "Verify each suite passes locally first" must explicitly include starting DynamoDB Local, or the baseline-verification step itself hangs.

### B2. The new test job is gated on `any_code`, which is `false` for council/monarch/stream-only changes

`main-pipeline.yml:125-134` computes `any_code` exclusively from the `infrastructure`/`api`/`auth_lambdas`/`murder_crow` filter outputs. No filter watches `lambdas/council/**`, `lambdas/monarch/**`, or `apps/stream/**` (`main-pipeline.yml:87-103`). So a PR touching only council makes `any_code=false` and the plan's `services-tests` job — gated on `any_code` per Task 0.1 — **does not run precisely when council/monarch/stream change**. The safety net has holes exactly over three of the five things it is supposed to protect.

**Fix:** add filter groups for council/monarch/stream (and later `packages/**`) and include them in the `any_code` disjunction, or gate the test job on its own paths-filter outputs instead of `any_code`.

### B3. Stage 3's Api extraction bricks every installed iOS build, and the plan's own escape hatch is void

Verified: iOS calls the **CloudFront domain**, hardcoded — `apps/ios/Cawnex/Cawnex/Core/Config/AppConfiguration.swift:47` returns `"https://d1elid9twwevj2.cloudfront.net"`. The plan's caveat says "If CloudFront fronts the API with a stable domain, only the origin needs updating — verify which URL iOS actually uses." But the plan's own target topology moves CloudFront **into** `CawnexApi-${stage}` (plan line 193), and the delete-then-create mechanic recreates the distribution → **new `d*.cloudfront.net` domain** → the "stable domain" premise destroys itself. Both candidate URLs (execute-api and CloudFront) change under the plan as written.

Also unpriced: CloudFront distribution deletion via CloudFormation requires disable-then-delete and routinely takes 15–40+ minutes, so the "seconds-to-minutes per group" downtime estimate (plan Task 3.2 step 2) is wrong for the Api group by an order of magnitude.

**Fix (pick one):** (a) treat the CloudFront distribution as quasi-stateful — clients pin its URL — and leave it in the Foundation stack, repointing only its origin to the new HTTP API; (b) attach the custom domain (`CawnexDomain` stack exists) to CloudFront *before* Stage 3 so the client-facing URL survives any recreation; (c) move it with stack refactoring (B4) so it is never recreated.

### B4. Stage 3's mechanics are the pre-2025 playbook — CloudFormation Stack Refactoring / `cdk refactor` solves exactly this problem without downtime or name collisions

The plan's core Stage-3 mechanic (delete from old stack in deploy N, create in new stack in deploy N+1, accept downtime; `cdk import` choreography for prod) reinvents what AWS now ships natively:

- [AWS CloudFormation Stack Refactoring](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/refactor-stacks.html) ([announcement, Feb 2025](https://aws.amazon.com/blogs/devops/introducing-aws-cloudformation-stack-refactoring/)) moves resources **between stacks** atomically, preserving the physical resource — no deletion, no recreation, no physical-name collision, no downtime.
- [`cdk refactor`](https://docs.aws.amazon.com/cdk/v2/guide/ref-cli-cmd-refactor.html) ([CDK launch blog](https://aws.amazon.com/blogs/devops/aws-cloud-development-kit-cdk-launches-refactor/)) detects moved constructs by comparing code to deployed state and drives the refactoring API for you.

This dissolves three of the plan's four "Critical" Stage-3 risks at once: the physical-name collision disappears (resource never recreated), the downtime window disappears, and — crucially — the murder/monarch **event source mappings move with their functions without recreation, so there is no TRIM_HORIZON replay at all** (see M5). Known constraints to design around: refactor-only operations must be a separate step from add/modify/delete deploys; all stacks must be in the same environment; a stack can't be left empty. The export-decoupling of Task 3.1 remains a valid prerequisite.

**Fix:** rewrite Task 3.2 around `cdk refactor` / `CreateStackRefactor` as the primary mechanism, with delete-then-create only as the documented fallback for any resource type the refactor API rejects. The plan as written sends the executor down a needlessly dangerous path.

### B5. The silent-deploy-death hole the plan warns about already exists and the plan never closes it

`main-pipeline.yml:292-297`: when only `murder_crow` changes, the deploy step is a stub (`echo "Murder/Crow deployment logic would go here"`) — **and then `tag-deployment` creates a new `deploy-*` tag anyway** (`main-pipeline.yml:312-356`), advancing the change-detection anchor. Net effect today: a murder- or worker-only change is *never deployed* by the main pipeline, yet is marked as deployed, so it won't be picked up by the next diff either. It only reaches AWS when something later trips the `infrastructure` filter.

Stage 1 makes this worse: Task 1.1 routes `packages/core/**` into the `murder_crow` filter, so **every change to the new shared domain package lands in the do-nothing stub and gets tagged as deployed**. The plan's Stage-1 risk register lists "paths-filter doesn't watch packages/** → core changes deploy nothing" and fixes the *filter* — but the deploy branch behind that filter is a no-op, which the plan's own fact table acknowledges ("deploy branches are stubs", plan line 36) and then never schedules fixing.

**Fix:** Stage 0 or Stage 1 must either implement the murder_crow fast path (build dist + `aws lambda update-function-code` + ECS image push, mirroring the api fast path) or delete the stub branches and let those changes route to the full-infra branch. Tagging a deployment that deployed nothing must stop.

---

## Major risks

### M1. Task 0.2's premise is misstated — there is no signup-breaking bug today
`lambdas/auth-post-confirmation/handler.py:96-116`: the `custom-email-sender` invoke is already wrapped in `try/except Exception` with `logger.warning(...)` and the comment "Don't fail the whole process if welcome email fails." Signup succeeds today; the failure is a warning line, not "a post-confirmation error." Consequence: the plan's verification step ("confirm no post-confirmation error in CloudWatch") **passes with zero changes made**, giving the executing agent false confirmation. Reframe Task 0.2 as "welcome emails silently never send; decide to deploy the sender or delete the dead invoke," and verify by asserting the *email arrives* (or the invoke block is gone), not by absence of errors.

### M2. Stage 0's venv "facts" are wrong; a literal executor will error out
- `git ls-files` matched **zero** `venv`/`.venv` paths — nothing is committed. The "~12k committed files" claim is false; `git rm -r --cached lambdas/murder/.venv` will fail with "did not match any files."
- `.gitignore:6-7,13,15` already contains `venv/`, `.venv/`, `**/venv/`, `**/.venv/` — the "add to .gitignore" step is already done.
- The on-disk dirs are `lambdas/murder/venv` + `lambdas/murder/.venv` + `lambdas/worker/.venv` + `apps/stream/venv` (~530MB, untracked). The correct action is plain local deletion, and it's optional.
This looks like an unverified explorer-report claim that survived into the plan. It's cheap to fix but it's exactly the kind of wrong step that derails a subagent executing checkboxes literally.

### M3. Stage 0's archive PR *will* trigger a full infra deploy — the risk table checked the wrong filter
Plan's Stage-0 risk register says the moves "match nothing — verified," but it only checked `lambdas/poc*` against the filters. Task 0.3 also moves `infra/lib/poc/`, `infra/lib/cawnex-auth-stack-enhanced.ts`, `infra/bin/infra.ts` and deletes `infra/lib/*.js` — all matched by the `infrastructure` filter (`main-pipeline.yml:88-91`, `infra/**`) → full `cdk deploy --all` on merge. Mostly harmless (synth should be a no-op diff) but it is the exact event the risk row claims cannot happen, and it means the archive commit must land only when a full deploy is acceptable.

### M4. Stage 1's unstated load-bearing constraint: `cawnex_core` must be stdlib+boto3-only with a lazy `__init__`
Verified: murder's entire external import surface is stdlib + `boto3` (no pydantic, no anthropic, no httpx) — consistent with its raw-source `fromAsset` deploy (`cawnex-stack.ts:282`). But worker (`lambdas/worker/requirements.txt`: `anthropic>=0.84.0`), council (`apps/council/requirements.txt`: `anthropic>=0.40.0`) and api (`apps/api/requirements.txt`: pydantic, anthropic) all carry third-party deps. The plan's proposed `cp -r ../../packages/core/src/cawnex_core dist/` for murder copies **source only, no dependencies**. If `cawnex_core/llm.py` imports `anthropic` (it must, to be useful to worker/council), and `cawnex_core/__init__.py` eagerly imports submodules, murder dies at import time with `ModuleNotFoundError` — the plan's own top risk, triggered by the plan's own module list. Worse, the plan says to seed `llm.py` "from the **murder** package's copy (it is canonical)" — **murder has no LLM client module at all** (verified directory listing: no `llm.py`, no `claude_client.py`; the LLM clients live in `monarch/claude_client.py`, `council/claude_client.py`, `worker/claude.py`, `apps/api/src/claude/client.py`). The canonical-source claim is false for this module. See design flag D1 for the fix.

### M5. "Verify `_should_skip` handles the replay burst" — verified: it does not
`lambdas/murder/src/murder/handler.py:109-117`: `_should_skip` returns True only for MODIFY records whose old/new `status` match. A recreated event source mapping with `TRIM_HORIZON` (`cawnex-stack.ts:310-317`) replays up to 24h of stream history: every INSERT and every status-*transition* MODIFY passes the guard and re-fires reactors (`react_to_crow_completion`, `react_to_mvi_queued`, `react_to_integration_complete`, …). Monarch is worse: `lambdas/monarch/src/monarch/handler.py:26-52` gates only on the **record's own** `status == "pending"` (true at insert time forever), so replayed `MONARCH#` INSERTs re-run full LLM project-setup chains — duplicate writes and duplicate Anthropic spend for every project created in the trailing 24h. Mitigations, in order of preference: (a) move the functions with stack refactoring so the mapping is never recreated (B4); (b) if recreating, set the *new* mapping's `startingPosition` to `LATEST` and quiesce writes during the gap — quiesce + LATEST loses nothing and replays nothing; (c) TRIM_HORIZON + quiesce is the plan's current answer and it replays a full day of history into reactors that were never audited for replay-idempotency.

### M6. Stage 4's "behavior pinned by existing api tests" is false for exactly the code being moved
`apps/api/src/routes/autopilot.py` contains **16 `# pragma: no cover` markers** — nearly every helper the plan wants to extract (`_create_project:220`, `_generate_and_save_documents:268`, `_save_milestones_and_mvis:381`, `_activate_wave:562`, `_handle_launch:657`, `_handle_message:718`, the route itself `:775`) is explicitly excluded from coverage, i.e. has no tests. The 75% gate passes *because* this code is exempted. Two consequences the plan misses: (1) the move is **not** behavior-pinned — there is no regression net over the riskiest helpers; (2) moving them into `services/api/src/orchestration/` without the pragmas drops them into the coverage denominator and the 75% gate fails until tests are written. "TDD per extracted module" is the right instinct — but the plan should say plainly: *characterization tests must be written before the move, because none exist.*

### M7. The infra "safety net" gate protects nothing
`infra/test/infra.test.ts` is a single test whose entire body is commented out (it references `lib/infra-stack`, which doesn't even exist as `.ts` anymore). The plan's global constraint "`tsc --noEmit` + jest for `infra`" (plan line 16) implies a working net; there is none. Stage 2's key invariant — "Expect **no** CloudFormation resource replacement" — and Stage 3's extractions have zero automated verification. Add CDK assertions/snapshot tests *in Stage 0*: synthesize `Cawnex-dev`, snapshot the template, and assert logical-ID stability across Stages 2–3. This is the cheapest falsifier available and the plan never asks for it.

### M8. Stage 3's cross-stack surface for `CawnexOrchestration` is far larger than the plan admits
The worker/council Fargate services consume, from what remains in Foundation: VPC + subnets, ECS cluster, EFS filesystem **and its access points** (`cawnex-stack.ts:434,565`), the EFS security-group ingress rules (`repoFs.connections.allowDefaultPortFrom(workerSg/councilSg)`, `cawnex-stack.ts:446,563` — when the consumer SGs move stacks, rule ownership must flip to the consumer side via imported SG IDs or you build a reverse dependency/cycle), task queue, both S3 buckets, the KMS vault key, three Secrets Manager secrets, and the events table. That's ~12 seams to re-plumb through SSM for one extraction; the murder Lambda adds the main-table stream. Two specifics the plan's 3.1 snippet drops: (a) `Table.fromTableAttributes` without `globalIndexes` produces grants that **exclude `/index/*`** — the explicit index policy at `cawnex-stack.ts:518-523` must survive, and any consumer relying on `grantReadWriteData` for GSI queries breaks silently; (b) `cawnex/${stage}/stream-pipe-secret` is an explicitly-named Secrets Manager secret — verify CloudFormation's delete semantics (scheduled-deletion vs force) before any delete-then-create sequence, or the re-create fails against a name in deletion-recovery. The "2–3 days + rehearsal" estimate covers the Streaming and Api extractions; Orchestration alone is that size.

### M9. `utilities.yml` production deploy is broken in a way that invalidates "rehearse then promote"
`utilities.yml` `deploy-production` runs `npx cdk bootstrap/deploy --context stage=production` — but the stack props type is `"dev" | "staging" | "prod"` and every guard is `stage === "prod"` (`cawnex-stack.ts:26,54-56` etc.). `stage=production` would create a parallel `Cawnex-production` universe with **dev semantics: `RemovalPolicy.DESTROY` on the prod buckets/tables/EFS**, FARGATE_SPOT, public IPs. Pre-existing bug, but the plan inventories this file (Stage 2 table) without noticing, and Stage 3's prod story ("verify prod stacks even exist first") should state the stronger fact: prod *cannot* have been deployed correctly through the only prod workflow that exists, and that workflow must be fixed before any prod rehearsal.

### M10. The worker image's murder dependency is dead weight, not coupling
`apps/worker/Dockerfile:13` copies `lambdas/murder/src/` and `PYTHONPATH` includes `/app/murder_src` — but `grep` finds **zero** `murder` imports anywhere in `lambdas/worker/src/` or `apps/worker/main.py` (which imports only `worker.handler`). The plan's fact table presents the murder COPY as live topology and Task 1.2 preserves it (`PYTHONPATH="/app/worker_src:/app/murder_src:/app/core_src"`). Drop the dead COPY in Stage 1 instead: it removes a spurious rebuild trigger and simplifies the exact `.dockerignore`/COPY story the plan is trying to clean up.

---

## Hidden assumptions

| # | Assumption | Verified against | Verdict |
|---|---|---|---|
| A1 | Lambda test suites pass today and only need to be "run in CI" | Empirical pytest run | **False** — they require DynamoDB Local (`lambdas/*/tests/conftest.py`); murder hangs indefinitely without it (B1) |
| A2 | murder is "canonical" for all six core modules incl. `llm.py` | `lambdas/murder/src/murder/` listing | **False for llm** — murder has no LLM client; four other services each have their own (M4) |
| A3 | Committed venvs (~12k files) need `git rm --cached` | `git ls-files` | **False** — zero tracked venv files; `.gitignore` already covers them (M2) |
| A4 | `_should_skip` dedups stream replays | `handler.py:109-117` | **False** — same-status-MODIFY guard only; INSERTs and transitions replay (M5) |
| A5 | Worker has 27 test files | `ls lambdas/worker/tests` | 22 files — minor, but symptomatic of unverified numbers |
| A6 | "8 CFN exports" | `cawnex-auth-stack.ts:213-268` | 9 declared, 8 imported (`Region` is exported, never imported) — two-phase removal must count all 9 |
| A7 | CloudFront gives iOS a stable URL through the split | `AppConfiguration.swift:47` + plan topology | **Self-contradicted** — iOS pins the CF domain and the plan recreates the distribution (B3) |
| A8 | Stage-2 rename causes "murder/monarch/checker/scaler/api Lambda code updates" via new asset hashes | CDK asset hashing model | Doubtful — `fromAsset` hashes *content*; a pure `git mv` with identical contents yields the same hash, so the raw-source lambdas likely deploy **nothing** (harmless either way, but the stated expectation is wrong and would confuse the post-deploy verification) |
| A9 | Docker images rebuild on Stage-2 move | Dockerfile COPY paths change | True — layer instructions change → new image, new task-def revision ✓ |
| A10 | `pip install --target` + `--only-binary=:all:` can vendor a local path dep | Empirical test with a scratch package | **True** (surprising but verified) — pip builds local directories despite `--only-binary`. Caveats: `-e` + `--target` is unsupported, and `name @ file:../relative` is not a valid URL — use a bare relative path in `requirements.txt` |
| A11 | POC archive moves match no deploy filter | `main-pipeline.yml:87-103` | True for `lambdas/poc*`, **false for the infra files** in the same PR (M3) |
| A12 | Prod may exist; verify first | `utilities.yml` deploy-production | Effectively cannot exist correctly — the only prod workflow passes an invalid stage (M9) |
| A13 | The three Blackboards are reconcilable copies | Diff of murder/worker/council modules | Directionally true but they are **subsets, not forks**: worker models 178 vs murder 631 lines, worker enums 40 vs murder 270. Reconciliation = "confirm subsets are compatible with the superset," which is cheaper than the plan's field-by-field framing suggests. `calculate_credits` is byte-identical with identical constants (3/15 microdollars) — today. One real drift found: the worker container runs a Haiku model (`cawnex-stack.ts:498`) while both `cost.py` copies hardcode "Sonnet pricing" — centralizing this in core is genuinely valuable |
| A14 | `TenantDB` is "the 4th Blackboard copy" | `apps/api/src/db/client.py` | **Mischaracterized** — TenantDB is a tenant-scoped generic table gateway (`PK=T#{tenant}`, all entity types); Blackboard is wave-execution snapshot persistence (`PK=T#{tenant}#P#{project}`). See D2 |
| A15 | wave-lifecycle.md is the canonical enum source for Stage 5 | `murder/enums.py` WaveStatus | Doc drift confirmed (`docs/system-reference.md:107` lacks REVIEW/STEERED) — but the **code** has 14 wave states incl. INTEGRATING/NEEDS_REWORK/UNDER_COUNCIL_REVIEW/UNDER_HUMAN_REVIEW that the "canonical" doc's 11 don't cover. Stage 5 should reconcile docs against code (post-Stage-1: against `cawnex_core.enums`), not doc-against-doc |
| A16 | SSE queue buffers events during the Streaming-stack gap | `cawnex-stack.ts:812-835` | Wrong mechanism — the **Pipe** is deleted during the gap, so nothing lands in the queue; coverage actually comes from the events-table DDB stream retention + TRIM_HORIZON replay, which then bursts up-to-24h of stale events at reconnected SSE clients. Same LATEST-on-recreate remedy as M5 |

---

## Design red flags (Ousterhout)

### D1. `packages/core` = {blackboard, models, enums, keys, cost, **llm**} — siblings at different abstraction levels + Information Leakage
`llm.py` is an outbound adapter with a heavyweight third-party dependency (anthropic) and four divergent per-service implementations; the other five modules are a zero-dependency persistence/domain kernel. Bundling them leaks the packaging decision into murder's deploy model (M4): the moment `llm.py` exists in the package, every consumer that vendors core by `cp -r` inherits an import landmine. **Cleaner boundary:** `cawnex-core` = domain kernel, hard-constrained to stdlib+boto3 (enforced by a bare-venv import test in CI, see F2); LLM clients either stay per-service or become a second package (`cawnex-llm`) consumed only by services that pip-install their deps. This also fixes the false "seed from murder" instruction — there is nothing in murder to seed llm from.

### D2. `TenantDB` as "thin façade over `cawnex_core.blackboard`" — Special-General Mixture / Pass-Through Method
TenantDB (`apps/api/src/db/client.py:17`) is the API's general tenant-isolation gateway serving profiles, billing, sessions, projects at `PK=T#{tenant}`; Blackboard is special-purpose wave/crow snapshot persistence at `PK=T#{tenant}#P#{project}`. Rebuilding one on the other welds a general module to a special one and produces pass-through methods for every non-wave entity. **Cleaner boundary:** the API imports core's `keys`, `models`, `enums` (kill the redeclarations — that's the real win) and gains a `Blackboard` instance *alongside* TenantDB for wave-scoped reads; TenantDB stays what it is.

### D3. `services/ops` — Vague Name, and the code tree contradicts the stack tree
"ops" is a junk drawer (Ousterhout #11/#12: if the honest name is generic, the grouping is wrong). Checker and worker-scaler read wave/crow state and scale the murder-adjacent services; Stage 3 itself files them under `CawnexOrchestration-${stage}`. Having Stage 2 put them in `services/ops` while Stage 3 puts them in the orchestration stack spreads one design decision ("these belong to the orchestration bounded context") across two disagreeing hierarchies — textbook Information Leakage. **Fix:** `services/orchestration/{checker,worker-scaler}` (or fold them under the murder service), matching the stack boundary.

### D4. Stage-4 module list decomposes by execution timeline — Temporal Decomposition risk
`autopilot_session → plan_extraction → project_setup → wave_activation` is literally the autopilot chat's run order. Two of the four earn their keep as information-hiding modules (`autopilot_session` hides session schema; `plan_extraction` hides parsing rules). The other two need scrutiny:
- `project_setup` name-collides with monarch, whose stack-level comment is *"async project setup chain"* (`cawnex-stack.ts:320`). Two components in one codebase "doing project setup" is a Vague Name plus future confusion for every agent pointed at the repo. The API-side concern is really *project record + document persistence* — name it that.
- `wave_activation` logic also lives in `routes/waves.py` (`_scale_ecs:90`, activation flow, `_merge_pr_for_wave:588`). If the extracted module serves only autopilot, the Repetition flag (#6) persists in waves.py, which the plan says will "shrink" but assigns no modules. **Fix:** make `wave_activation` the shared module consumed by both routes (that consumption test is also the proof it's an information-hiding module and not a pipeline stage), and name the waves-side leftovers (event emission, PR merge) in the plan.
- The plan's `services/api/src/models/` step ("replace domain-shape declarations with imports from `cawnex_core` where they mirror snapshots") risks Overexposure: binding wire-format response models to internal domain dataclasses couples the public API to internal schema evolution. Keep transport models separate; map explicitly.

### D5. Main table stays in the Auth stack — pragmatic, but the justification is stale and the proposed rename admits the smell
The plan's reasoning ("requires orphan-and-import choreography on the most critical resource") predates stack refactoring (B4), which moves a DynamoDB table between stacks without touching the physical resource. The decision to defer can still be right — don't practice the fanciest maneuver on the crown jewels — but the plan should record the true trade-off ("we *could* move it safely with CreateStackRefactor; we choose not to yet") rather than a false impossibility. And `CawnexIdentityAndDataStack` is a name that confesses Special-General Mixture; if the rename ships, the docs should mark the table's residence as a known wart with the refactor path as the exit.

### D6. Shallow-module check on the extraction itself — passes
For balance: `packages/core` minus `llm.py` is *not* a shallow module — it hides the single-table key encoding, snapshot serialization, enum transition rules, and pricing behind a small import surface, replacing 1,872 lines of quadruplicated code (verified line counts). That part of the design is sound.

---

## Best-practice gaps

| Practice | Source | Divergence |
|---|---|---|
| Move resources between stacks with CloudFormation Stack Refactoring / `cdk refactor`, not delete-recreate or orphan-import | [AWS docs: Moving resources between stacks](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/refactor-stacks.html), [AWS DevOps blog (Feb 2025)](https://aws.amazon.com/blogs/devops/introducing-aws-cloudformation-stack-refactoring/), [cdk refactor docs](https://docs.aws.amazon.com/cdk/v2/guide/ref-cli-cmd-refactor.html), [CDK refactor launch](https://aws.amazon.com/blogs/devops/aws-cloud-development-kit-cdk-launches-refactor/) | Plan's Stage 3 uses downtime-accepting delete/create on dev and `cdk import` choreography for prod; ignores the purpose-built primitive (B4) |
| Snapshot/fine-grained assertion tests on synthesized templates before/through infra refactors | [AWS CDK testing guide](https://docs.aws.amazon.com/cdk/v2/guide/testing.html) | Zero real infra tests exist (`infra/test/infra.test.ts` is commented out); plan adds none (M7) |
| Ephemeral service containers for integration deps in CI (`services:` in GitHub Actions), or moto for DynamoDB | [GitHub Actions service containers](https://docs.github.com/en/actions/using-containerized-services/about-service-containers) | Task 0.1 specs bare `pytest`; suites hard-require DynamoDB Local (B1) |
| Deploy-path filters must cover every deployable, generated or audited from one source of truth | dorny/paths-filter README; general trunk-based CD hygiene | council/monarch/stream have no filter today; plan fixes only `packages/**` and only for the murder group (B2) |
| Never advance a deployment marker without deploying | continuous-delivery basics (Humble/Farley) | `tag-deployment` tags stub "deploys" as successful, silently swallowing murder/worker changes (B5) |
| Two-phase export removal (keep producer's export until no consumer imports it) | [AWS knowledge: Cannot delete export errors](https://repost.aws/knowledge-center/cloudformation-stack-export-name-error) | Plan **follows** this correctly in Task 3.1 ✓ |
| Shared internal Python packages: single workspace tool (uv/hatch workspaces) or built wheels, not per-package hand venvs + cp-vendoring | uv workspaces docs; Python packaging guide | Plan's cp-vendoring for murder is acceptable *only* under the zero-dep constraint of D1; the constraint is unstated. Four divergent local venvs (~530MB) remain unaddressed |

---

## Missing from the plan

1. **No fix for the deploy stubs** (B5) — the largest omission, since the plan's own biggest "silent" fear is deploys quietly stopping.
2. **No observability work**: no CloudWatch alarms exist for murder/monarch errors or DLQ depth; the plan references "CloudWatch alarm on murder errors" as a Stage-1 mitigation but never creates it. Stage 0 is the natural home.
3. **No characterization-test step before Stage 4** (M6) — "TDD per extracted module" is stated, but the plan must acknowledge the helpers currently have zero tests and pragmas that hide them from the gate.
4. **Pre-commit `entry` strings**: `.pre-commit-config.yaml` hardcodes `cd apps/api && source venv/bin/activate` in every hook `entry`, not just the `files:` regexes the Stage-2 table lists.
5. **Committed `__pycache__`/`.egg-info` inside Lambda assets**: `lambdas/murder/src/` ships `__pycache__` and `murder.egg-info` into the deployed asset (`fromAsset` on the raw dir). Cleanup belongs in Stage 0 and also stabilizes asset hashes.
6. **`.dockerignore`/Dockerfile dead-weight removal** (M10): dropping the unused `murder_src` COPY from the worker image.
7. **Rollback for Stage 1's murder packaging change**: the CDK path flip (`src` → `dist`) plus two workflow edits land across repos of concern; a revert restores CDK but the workflows' `make build-lambda` calls for murder must be revert-safe too (plan's Stage-3 rollback note doesn't cover Stage 1).
8. **Stage-2 trigger-path nuance**: `apps/ios` stays, so the workflow `push.paths` must keep `apps/**` (or add `apps/ios/**` handling) while adding `services/**` and `packages/**` — the plan's table says "`apps/**`,`lambdas/**`→`services/**`,`packages/**`" which as written drops iOS-triggered runs (currently harmless-ish, but it changes behavior unremarked).
9. **Council/monarch deploy path** — even after Stage 2/3, nothing in any workflow deploys a council-image-only or monarch-only change (they ride the `infrastructure` filter). If Stage 0 adds their tests, Stage 1–2 should add their filters *and* a deploy route.
10. **Secrets Manager delete/recreate semantics** for `cawnex/${stage}/stream-pipe-secret` under the delete-then-create fallback (M8b).

---

## Falsifying tests to add

- **F1 (falsifies "suites just need running"):** run each lambda suite in a clean container with no DynamoDB Local and a 5-minute timeout. Expected today: murder/worker/council/monarch hang or error. Already reproduced locally for murder.
- **F2 (falsifies core's zero-dep invariant, forever):** CI job — `python -m venv /tmp/v && /tmp/v/bin/pip install boto3 && cp -r packages/core/src/cawnex_core /tmp/v/lib/python3.12/site-packages/ && /tmp/v/bin/python -c "import cawnex_core, cawnex_core.blackboard, cawnex_core.models, cawnex_core.enums, cawnex_core.keys, cawnex_core.cost"`. The day someone adds pydantic or anthropic to core, this fails before murder does.
- **F3 (falsifies Stage 2's "no resource replacement"):** `cdk synth --all` before and after the rename commit; diff the templates ignoring asset-hash metadata keys. Any logical-ID or non-asset property change fails the check. Also directly tests A8.
- **F4 (falsifies murder dist completeness):** after `make build-lambda` in murder, `docker run --rm -v $PWD/dist:/var/task python:3.12 python -c "import sys; sys.path.insert(0,'/var/task'); import murder.handler"` with only boto3 installed.
- **F5 (falsifies "replay is handled"):** on dev, with ~a day of history in the table stream, delete and recreate murder's event source mapping with TRIM_HORIZON; count duplicate side-effects (new DISPATCH rows, duplicate COUNCIL# inserts, monarch re-runs, Anthropic spend delta). Expected today per M5: duplicates occur. This is the test the plan's own instruction ("verify `_should_skip` handles the replay burst") implies but never specs.
- **F6 (falsifies deploy liveness, the anti-B5 canary):** after any filter/pipeline change, push a one-line comment change under `lambdas/murder/**` (later `services/murder/**`) and assert the deployed Lambda's `CodeSha256` changed (`aws lambda get-function --query 'Configuration.CodeSha256'`). Detects both filter death and stub death — filter-log inspection (the plan's check) misses the stub case.
- **F7 (falsifies the iOS-URL survivability story before it matters):** on dev, tear down and recreate the CloudFront distribution; confirm the installed app breaks and the `update-ios-config` flow is the only recovery. Cheap now, expensive discovered in prod.
- **F8 (falsifies export-removal understanding):** on dev, attempt `cdk deploy CawnexAuthStack-dev` with one imported export deleted while `Cawnex-dev` still imports it; expect the "Cannot delete export" failure. A 20-minute rehearsal that inoculates the executor against the plan's #1 critical risk.
- **F9 (pin the reconciliation):** before deleting any duplicated module in Task 1.2, add a temporary test asserting `worker.models.CrowSnapshot.to_item()` output == `cawnex_core` equivalent for a fixture crow (same for enum values and `calculate_credits(1000, 1000)`). Deletes with the last consumer.

---

## What's actually solid (verified)

- The five-stage risk ordering, the "stateful resources never move" governing rule, and two-phase export removal (Task 3.1) are correct and well-sequenced; Task 3.1-first is exactly right.
- Every `cawnex-stack.ts` line reference checked is accurate: raw-source `fromAsset` for murder/monarch (`:282,326`), api dist requirement (`:174`), repo-root Docker contexts (`:485,590,678`), checker/scaler assets (`:849,878`), import coupling (`:38-40,151-165`).
- The paths-filter groups, `apps/api`-only CI, hardcoded `cawnex-api-dev` fast path (`main-pipeline.yml:281`), and stub branches (`:290,297`) are all as the plan states.
- `cdk.json` app is `bin/cawnex.ts` only — the POC stacks, `CawnexAuthStackEnhanced`, `bin/infra.ts`, and `mcp-monarch` are indeed dead; the email sender exists only in the dormant enhanced stack (`cawnex-auth-stack-enhanced.ts:69-99`).
- The 4-way duplication is real and worth killing: `Blackboard` ×3 (`murder/blackboard.py:15`, `worker/blackboard.py:27`, `council/_blackboard.py:10`), duplicated `CrowSnapshot`/`CrowStatus`/`CrowType`, byte-identical `calculate_credits`; council's half-migration leftovers (`_blackboard.py`, `_claude_client.py`, `advisors_legacy.py`, legacy `lambda_handler`) all exist as claimed.
- Docs enum drift is real (`docs/system-reference.md:107` vs `docs/design/wave-lifecycle.md:26-29`).
- `pip install --target --platform manylinux2014_x86_64 --only-binary=:all:` **does** vendor a local directory dependency (tested empirically) — the plan's api-vendoring approach works, modulo the `-e`/relative-`file:` syntax notes in A10.
- Worker-scaler scales worker and council to 0 when idle (`lambdas/orchestration/worker-scaler/handler.py`) — the Stage-3 quiesce precondition is available as claimed.
