# Hierarchy Restructure — Master Migration Plan (v2, post-adversary)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Revision:** v2 incorporates the adversary review at `docs/superpowers/reviews/2026-07-01-hierarchy-restructure-master-plan-adversary-review.md` (verdict: SHIP-WITH-FIXES). All 5 blockers (B1–B5) and 10 major risks (M1–M10) are folded in; key changes: Stage 3 rewritten around `cdk refactor` (verified available in the pinned CLI 2.1106.0), CloudFront treated as quasi-stateful, `llm` excluded from `packages/core`, deploy-stub fix promoted into Stage 0, `services/ops` renamed `services/orchestration`.
>
> **Scope note:** This is a master plan spanning five independent subsystems. Each stage is an independently shippable unit and stages 1–3 warrant their own detailed task-level plan before execution. Execute stages strictly in order.

**Goal:** Convert the repo from a deployment-accident hierarchy (`apps/` vs `lambdas/`) into a design-driven hierarchy (`services/` + `packages/core`), split the god-stack, and extract the API service layer — without breaking CI/CD or losing AWS state.

**Architecture:** Five stages ordered by risk containment: (0) safety net + deploy-liveness fixes + dead-weight removal, (1) extract the shared `packages/core` domain kernel (stdlib+boto3 ONLY — no LLM client), (2) regroup source into `services/`, (3) split `CawnexStack` using CloudFormation Stack Refactoring via `cdk refactor` (resources move without recreation), (4) extract the API service layer out of routes (characterization tests first), (5) docs-vs-code reconciliation.

**Tech Stack:** Python 3.12 (FastAPI/Mangum, boto3, pydantic), Swift/SwiftUI, AWS CDK 2 (CLI 2.1106.0 — `cdk refactor` available), GitHub Actions, Docker/Fargate.

## Global Constraints

- Commit messages: conventional commits, subject ≤72 chars, lower-case subject. `commitlint.config.js` **rejects any message containing `Co-Authored-By:`, `Claude`, `claude-code`, or `🤖 Generated`** — never use the word "Claude" in a commit subject/body (write "LLM client").
- CI quality gates that must keep passing: `mypy src --strict`, `black --line-length=88`, `flake8 --max-complexity=10`, `pytest --cov-fail-under=75` (CI) for the api package; `tsc --noEmit` for infra. NOTE: `infra/test/infra.test.ts` is a single fully-commented-out test — there is **no** working infra test net until Task 0.4 creates one.
- **`cawnex-core` invariant (load-bearing):** `packages/core` may import ONLY stdlib + boto3. Enforced by the bare-venv import test (F2). The LLM client is NOT part of core.
- All AWS resources have explicit physical names (`cawnex-*-${stage}`); dev uses `RemovalPolicy.DESTROY`, prod `RETAIN`.
- Deploys go through `main-pipeline.yml` change detection anchored on `deploy-*` git tags with `dorny/paths-filter` groups. `any_code` (`main-pipeline.yml:125-134`) is computed from ONLY `infrastructure`/`api`/`auth_lambdas`/`murder_crow` — council/monarch/stream have no filter today.
- `cdk deploy` requires `apps/api/dist` to exist (`make build-lambda` first) — `cawnex-stack.ts:174`.
- Docker build context for worker/council/stream images is the repo root (`cawnex-stack.ts:485/590/678`); COPY paths and the `.dockerignore` whitelist are repo-root-relative.
- Lambda test suites require **DynamoDB Local** (`lambdas/*/tests/conftest.py`, endpoint `DYNAMODB_ENDPOINT` defaulting to `http://localhost:8000`). Without it the murder suite HANGS indefinitely (empirically reproduced), it does not fail fast.
- iOS dev pins the raw CloudFront domain (`AppConfiguration.swift:47`: `d1elid9twwevj2.cloudfront.net`); staging/prod use `api-staging.cawnex.ai`/`api.cawnex.ai`. The CloudFront distribution is therefore **quasi-stateful: clients pin its URL — it never moves stacks and is never recreated.**
- Rehearse every infra-touching stage on `dev`. Before stage 3: `aws cloudformation list-stacks --query "StackSummaries[?contains(StackName,'Cawnex')].{Name:StackName,Status:StackStatus}"`. Note prod cannot currently exist in a correct form — see Task 3.0.

---

## Current-state facts this plan depends on (v2-corrected)

| Fact | Evidence |
|---|---|
| `apps/worker` & `apps/council` are 38/64-line shims; real code COPY'd from `lambdas/` at Docker build. The worker image's `lambdas/murder/src` COPY is **dead weight** — zero `murder` imports exist in worker code | Dockerfiles; grep verified |
| `Blackboard` defined 3×; worker/council copies are **subsets** of murder's superset (worker models 178 vs murder 631 lines); `calculate_credits` byte-identical today. `TenantDB` is NOT a 4th copy — it is the API's general tenant gateway (`PK=T#{tenant}`), a different module than Blackboard (`PK=T#{tenant}#P#{project}`) | `lambdas/{murder,worker,council}`, `apps/api/src/db/client.py:17` |
| Murder is stdlib+boto3-only and has **no LLM client module**; LLM clients live in monarch, council, worker, and api — four divergent implementations | grep verified |
| Murder/Monarch Lambdas deploy raw source (`fromAsset("../lambdas/murder/src")`) — no dependency bundling; the asset currently ships `__pycache__` + `murder.egg-info` | `cawnex-stack.ts:282,326` |
| Auth→Main coupling: **9 exports declared, 8 imported** (`Region` exported, never imported) | `cawnex-auth-stack.ts:213-268`, `cawnex-stack.ts:38-40` |
| `custom-email-sender` invoke in post-confirmation is **already wrapped in try/except** (`handler.py:96-116`) — signup works today; welcome emails silently never send | verified |
| CI runs ONLY api tests; lambda suites need DynamoDB Local; `lambdas/monarch` has **no pyproject.toml**; `apps/stream/pyproject.toml` declares no deps/extras | `main-pipeline.yml:154-177`; conftest files |
| `main-pipeline.yml` murder_crow/auth_lambdas deploy branches are **stubs that still advance the `deploy-*` tag** — murder/worker-only changes are never deployed yet marked deployed | `main-pipeline.yml:290-297,312-356` |
| `utilities.yml` deploy-production passes `stage=production`, which doesn't match the `"dev"\|"staging"\|"prod"` prop type — a `Cawnex-production` stack would get **dev semantics (DESTROY policies, SPOT, public IPs)** | `cawnex-stack.ts:26,54-56` |
| No venv is committed to git (`git ls-files` = 0 matches); `.gitignore` already covers `**/venv/`, `**/.venv/`. ~530MB of **untracked** local venvs exist on disk | verified |
| `_should_skip` (`murder/handler.py:109-117`) guards ONLY same-status MODIFYs — stream replays re-fire all INSERT and transition reactors; monarch (`handler.py:26-52`) re-runs full LLM chains on replayed INSERTs | verified |
| `routes/autopilot.py` carries **16 `# pragma: no cover`** — the helpers Stage 4 extracts have zero tests; the 75% gate passes because they're exempted | verified |
| Wave states: code has **14** (`murder/enums.py`) vs 11 in `wave-lifecycle.md` vs fewer in `system-reference.md` — docs trail code, not just each other | verified |
| POC stacks, `CawnexAuthStackEnhanced`, `bin/infra.ts`, `mcp-monarch`, `lambdas/orchestration/file-processor` are dead | `cdk.json` app = `bin/cawnex.ts` |
| **Live stacks (checked 2026-07-01):** `Cawnex-dev`, `CawnexAuthStack-dev`, **`CawnexAuthStack-prod`, `CawnexCloudflareStack-prod`** — a partial prod exists (auth+domain, no main stack), presumably deployed manually with `--context stage=prod`. User pools `cawnex-dev` + `cawnex-prod` live. SES: production access ON, `cawnex.ai` verified, DKIM SUCCESS. `cawnex-custom-email-sender-{dev,prod}` do NOT exist | AWS account 961454950210, us-east-1 |

---

## Stage 0 — Safety net + deploy liveness + dead-weight removal

**Objective:** Make later stages observable and reversible; stop the pipeline lying about deployments. Zero AWS topology change (but see Task 0.3's deploy note).

### Task 0.1: Run the orphaned test suites in CI — with their real dependencies

**Files:**
- Modify: `.github/workflows/main-pipeline.yml`
- Create: `lambdas/monarch/pyproject.toml` (mirror murder's: setuptools, `[dev]` extra with pytest)
- Modify: `apps/stream/pyproject.toml` (declare deps from `requirements.txt` + a `[dev]` extra) or have the CI job `pip install -r requirements.txt pytest`

- [ ] Add paths-filter groups for `council` (`lambdas/council/**`), `monarch` (`lambdas/monarch/**`), `stream` (`apps/stream/**`) and include them in the `any_code` disjunction (`main-pipeline.yml:125-134`). **Do NOT gate the new test job on `any_code` alone** — gate it on its own filter outputs so council/monarch/stream-only PRs run their tests (adversary B2).
- [ ] Add a `services-tests` job (matrix: `lambdas/murder`, `lambdas/worker`, `lambdas/council`, `lambdas/monarch`, `apps/stream`) with:
  ```yaml
  services:
    dynamodb:
      image: amazon/dynamodb-local
      ports: ["8000:8000"]
  env:
    DYNAMODB_ENDPOINT: http://localhost:8000
  ```
  and a per-job `timeout-minutes: 15` (the suites HANG without DynamoDB Local — adversary B1; never rely on failure, rely on timeout).
- [ ] Verify each suite locally **with DynamoDB Local running** (`docker run -p 8000:8000 amazon/dynamodb-local`). Baseline-fix or explicitly skip pre-broken tests in a separate commit so the gate starts green.
- [ ] Commit: `ci: run murder, worker, council, monarch and stream test suites`

### Task 0.2: The murder_crow deploy stub — stop tagging deployments that deploy nothing (adversary B5)

Today a murder/worker-only change hits a stub branch (`main-pipeline.yml:290-297`, `echo "...logic would go here"`) and `tag-deployment` advances the `deploy-*` anchor anyway — the change is never deployed and never re-detected. Stage 1 routes `packages/core/**` into this same black hole.

**Files:**
- Modify: `.github/workflows/main-pipeline.yml`

- [ ] **DECIDED (user, 2026-07-01): option (b)** — delete the stub branches and route `murder_crow`/`auth_lambdas` changes into the full-infra deploy branch. Rationale: one controlled deploy mechanism (CDK via the pipeline's OIDC role), no CloudFormation drift, no second IAM surface. The existing api fast path (`main-pipeline.yml:273-282`) is the same anti-pattern but stays for now as a conscious exception (api iteration speed); flagged for later removal.
- [ ] Add the deploy-liveness canary (adversary F6): after merge, push a one-line comment change under `lambdas/murder/**`, then assert the Lambda's code actually changed: `aws lambda get-function --function-name cawnex-murder-dev --query 'Configuration.CodeSha256'` differs from before. This catches both filter-death and stub-death; log inspection does not.
- [ ] Commit: `ci: deploy murder and auth lambda changes instead of stub-tagging them`

### Task 0.3: Infra test net + observability (adversary M7 + missing-item 2)

**Files:**
- Modify: `infra/test/infra.test.ts` (replace the commented-out corpse)
- Modify: `infra/lib/cawnex-stack.ts` (alarms)

- [ ] Add CDK snapshot tests: synth `Cawnex-dev` + `CawnexAuthStack-dev`, snapshot templates, plus fine-grained assertions on logical IDs of the stateful resources (`MainTable`, `ArtifactsBucket`, `AssetsBucket`, `VaultKey`, `EventsTable`, `RepoFileSystem`, `UserPool`). This is the automated falsifier for Stage 2's "no replacement" and Stage 3's refactor invariants (F3).
- [ ] Add CloudWatch alarms: murder Lambda errors > 0, monarch errors > 0, `cawnex-tasks-dlq-${stage}` depth > 0. Stage 1's mitigation ("alarm on murder errors") must exist before Stage 1.
- [ ] Commit: `test(infra): add template snapshot assertions and orchestration alarms`

### Task 0.4: Welcome-email decision (reframed per adversary M1 — there is NO signup bug)

The invoke at `lambdas/auth-post-confirmation/handler.py:96-116` is already try/except-wrapped; signup works. The real defect: welcome/verification emails silently never send because only the dormant `CawnexAuthStackEnhanced` deploys the sender.

- [ ] **DECIDED (user + SES verification, 2026-07-01): deploy the sender.** SES is production-ready (production access ON, `cawnex.ai` verified, DKIM SUCCESS) — port the Lambda from `cawnex-auth-stack-enhanced.ts:70-110` into the active auth stack.
- [ ] Verify by the OUTCOME, not by absence of errors: either a test signup **receives the email**, or the invoke block is gone from the handler. (Absence-of-CloudWatch-errors passes today with zero changes — a false gate.)
- [ ] Commit: `fix(auth): deploy welcome email sender` or `chore(auth): remove dead email-sender invocation`

### Task 0.5: Archive dead code, clean the tree (v2-corrected facts)

**Files:**
- Move to `archive/`: `lambdas/poc1-crow`, `lambdas/poc3-murder`, `lambdas/poc5-api`, `lambdas/poc5-murder`, `lambdas/poc6-worker`, `mcp-monarch/`, `infra/lib/poc/`, `infra/lib/cawnex-auth-stack-enhanced.ts` (after Task 0.4 resolves), `infra/bin/infra.ts`, `lambdas/orchestration/file-processor`
- Delete: stale `infra/lib/*.js`, `infra/lib/*.d.ts`, `infra/bin/infra.js`, `infra/bin/infra.d.ts`, root `dist/`, `htmlcov/`; **`__pycache__/` and `murder.egg-info/` inside `lambdas/murder/src`** (they ship inside the deployed Lambda asset today and destabilize asset hashes)
- Local-only (optional, not a git operation): `rm -rf` the ~530MB of untracked venvs (`lambdas/murder/{venv,.venv}`, `lambdas/worker/.venv`, `apps/stream/venv`). **No `git rm --cached` — nothing is tracked; `.gitignore` already covers venvs** (adversary M2).

- [ ] Execute moves/deletes; verify `cd infra && npx tsc --noEmit && npx cdk synth --context stage=dev --quiet`.
- [ ] Verify `npm ci` at root still resolves workspaces.
- [ ] **Schedule note (adversary M3):** the `infra/lib` moves match the `infrastructure` filter → this PR triggers a full `cdk deploy --all` on merge. Expected diff: murder/monarch asset hash change ONLY (from the pycache/egg-info cleanup). Land when a full deploy is acceptable; review the deploy log against that expectation.
- [ ] Commit: `chore: archive poc lambdas, mcp-monarch and dead infra; clean lambda assets`

---

## Stage 1 — Extract `packages/core` (the domain kernel — NOT the LLM client)

**Objective:** One source of truth for `Blackboard`, domain models/enums, key builders, `calculate_credits`. **Scope cut per adversary D1: `llm.py` is OUT.** The LLM clients (4 divergent implementations with the `anthropic` dependency) stay per-service; a separate `packages/llm` may follow later. This keeps core stdlib+boto3-only, which is what makes murder's cp-vendored packaging safe.

**Reconciliation framing (adversary A13):** worker/council modules are *subsets* of murder's superset, not forks — the work is "confirm subset-compatibility with murder's canonical copy," cheaper than field-by-field merge. One real drift already found: the worker container runs a Haiku model (`cawnex-stack.ts:498`) while both `cost.py` copies hardcode Sonnet pricing — centralize model-aware pricing in core and fix it.

### Task 1.1: Create the package

**Files:**
- Create: `packages/core/pyproject.toml` (name `cawnex-core`, src layout `src/cawnex_core`)
- Create: `packages/core/src/cawnex_core/{blackboard.py,models.py,enums.py,keys.py,cost.py,__init__.py}` — seeded from **murder's** copies (murder IS canonical for these five; it has no LLM module, which is why llm is excluded)
- Create: `packages/core/tests/` — port murder's + worker's blackboard/model/cost tests

- [ ] `__init__.py` stays lazy/empty — no eager submodule imports (an eager import chain is the landmine that would kill murder at cold start).
- [ ] Add the zero-dep enforcement test to CI (adversary F2): bare venv + boto3 only, `python -c "import cawnex_core, cawnex_core.blackboard, cawnex_core.models, cawnex_core.enums, cawnex_core.keys, cawnex_core.cost"`. The day someone adds pydantic/anthropic to core, this fails before murder does.
- [ ] Add `packages/core/**` to paths-filters — to the murder_crow group AND the new council/monarch/stream test filters. (Safe now because Task 0.2 removed the deploy stub — without that fix this routes core changes into a black hole.)
- [ ] Commit: `feat(core): add cawnex-core shared domain kernel (stdlib+boto3 only)`

### Task 1.2: Adopt per consumer — worker → murder → council → api, one PR each

**Worker** (22 test files — best coverage):
- [ ] Before deleting any duplicated module, add pin tests (adversary F9): assert `worker.models.CrowSnapshot.to_item()` == `cawnex_core` equivalent for a fixture crow; same for enum values and `calculate_credits(1000, 1000)`. Delete the pins with the last consumer migration.
- [ ] Migrate imports; delete superseded local modules; `pytest` green (DynamoDB Local up).
- [ ] Dockerfile: add `COPY packages/core/src/ ./core_src/`; **drop the dead `COPY lambdas/murder/src/ ./murder_src/`** and remove `/app/murder_src` from PYTHONPATH (adversary M10 — zero murder imports exist; removes a spurious rebuild trigger). Update `.dockerignore` whitelist (`!packages/core/src/**`).
- [ ] Local verify: `docker build -f apps/worker/Dockerfile .`; `docker run --entrypoint python <img> -c "from cawnex_core.blackboard import Blackboard; import worker.handler"`.
- [ ] Deploy to dev, run one wave end-to-end.

**Murder** — the packaging change:
- [ ] Create `lambdas/murder/Makefile` `build-lambda`: `rm -rf dist && mkdir dist && cp -r src/murder dist/ && cp -r ../../packages/core/src/cawnex_core dist/` (source-only copy is safe ONLY under the core zero-dep invariant).
- [ ] Point CDK at `fromAsset("../lambdas/murder/dist")`; add the build step to `main-pipeline.yml` (infra branch AND the Task-0.2 fast path) and `infrastructure-only.yml`, beside the api `make build-lambda`.
- [ ] Dist-completeness falsifier (adversary F4): `docker run --rm -v $PWD/dist:/var/task python:3.12 sh -c "pip install -q boto3 && python -c \"import sys; sys.path.insert(0,'/var/task'); import murder.handler\""`.
- [ ] **Rollback note (adversary missing-7):** reverting this PR must revert BOTH the CDK path flip and the workflow build-step additions — a stray `make build-lambda` for murder in a workflow after revert fails the deploy. Revert = `git revert` of the whole PR, never cherry-picked.
- [ ] Same treatment for monarch when it adopts core.

**Council:**
- [ ] Docker path like worker; in the same PR delete the half-migration leftovers: `_blackboard.py`, `_claude_client.py`, `advisors_legacy.py`, the dead `lambda_handler`.

**API** (adversary D2 — REVISED):
- [ ] `TenantDB` **stays as-is** — it is the API's general tenant gateway, not a Blackboard copy; welding it onto Blackboard would be Special-General Mixture with pass-through methods for every non-wave entity.
- [ ] The API instead: imports core's `keys`/`models`/`enums` to kill its inline redeclarations of domain shapes, and gains a `cawnex_core.Blackboard` instance ALONGSIDE TenantDB for wave-scoped reads.
- [ ] Vendoring: add core to `apps/api/requirements.txt` as a **bare relative path** (`../../packages/core`) — NOT `-e`, NOT `name @ file:../relative` (both fail with `pip install --target`; bare-path vendoring verified working by the adversary, A10). Post-build assertion: `test -d apps/api/dist/cawnex_core`.

**Stage 1 risk register (v2)**

| Risk | Severity | Mitigation |
|---|---|---|
| Murder ships without `cawnex_core` → `ModuleNotFoundError` on every stream event | High | Makefile dist + F4 docker import test + Task-0.3 alarm + dev wave smoke |
| A third-party import sneaks into core | High (same failure) | F2 bare-venv CI test — permanent |
| Docker COPY fails on `.dockerignore` miss | Medium (loud) | Local docker build step |
| Subset-reconciliation misses a semantic drift | Medium | F9 pin tests; Haiku/Sonnet pricing drift explicitly in scope |
| `pip --target` doesn't vendor core into api dist | Medium | Bare-relative-path syntax + `test -d` assertion |

---

## Stage 2 — Regroup into `services/`

**Objective:** `services/{api,monarch,murder,worker,council,stream,orchestration,auth}` + `packages/core` + `apps/ios`. **Renamed per adversary D3: `services/orchestration/{checker,worker-scaler}`** (not `services/ops` — "ops" is a junk-drawer name, and the Stage-3 stack that owns these is `CawnexOrchestration`; code tree and stack tree must agree on the boundary). `services/auth/{post-confirmation,email-sender}`.

### Task 2.1: The move + every path that names the old tree, in ONE PR

`git mv`: `lambdas/{murder,worker,council,monarch}→services/…`, `apps/api→services/api`, `apps/stream→services/stream`, `lambdas/orchestration/{checker,worker-scaler}→services/orchestration/…`, `lambdas/auth-post-confirmation→services/auth/post-confirmation`, `lambdas/custom-email-sender→services/auth/email-sender` (or delete, per Task 0.4), `apps/worker/*→services/worker/fargate/`, `apps/council/*→services/council/fargate/`.

**Path-update checklist (all in the same commit):**

| File | What changes |
|---|---|
| `infra/lib/cawnex-stack.ts:174,282,326,485,590,678,849,878` | all `fromAsset`/Dockerfile `file:` paths |
| `infra/lib/cawnex-auth-stack.ts:181` | post-confirmation asset path |
| 3 Dockerfiles | COPY paths (context stays repo root) |
| `.dockerignore` | whitelist entries |
| `.github/workflows/main-pipeline.yml` | trigger paths — **keep `apps/**` (iOS stays there; dropping it changes iOS-push behavior — adversary missing-8)** and add `services/**`, `packages/**`; all paths-filter groups (incl. the Task-0.1 council/monarch/stream groups); `working-directory`/`cd` for api |
| `.github/workflows/infrastructure-only.yml:75-80`, `utilities.yml` | api build dirs, `mkdir -p` stub |
| root `package.json` | workspaces, `build:api`, `test:python` scripts |
| `.pre-commit-config.yaml` | BOTH the `files:` regexes AND the hook `entry:` strings — they hardcode `cd apps/api && source venv/bin/activate` (adversary missing-4) |
| `scripts/quality-control.sh`, `scripts/deploy-enhanced-emails.sh`, `scripts/setup-post-confirmation-trigger.sh` | path refs |

- [ ] Execute; local verify: api `make build-lambda`, all 3 docker builds, `npx cdk synth --context stage=dev --quiet`, full test sweep.
- [ ] Template-diff falsifier (adversary F3): `cdk synth --all` before and after the rename commit; diff ignoring asset-hash keys → must show zero logical-ID/property changes. (The Task-0.3 snapshot tests enforce the same thing in CI.)
- [ ] **Corrected expectation (adversary A8):** `fromAsset` hashes CONTENT — a pure `git mv` produces identical hashes, so the raw-source/dist lambdas likely deploy **nothing** on this PR. Docker images DO rebuild (COPY instructions changed). Post-deploy verification should expect: 3 new ECS task-def revisions, zero-or-few Lambda updates, zero CloudFormation replacements.
- [ ] Post-merge: run the F6 deploy-liveness canary against `services/murder/**`.
- [ ] Commit: `refactor: regroup backend into services/ and packages/, retire apps-vs-lambdas split`

**Stage 2 risks:** unchanged from v1 (silent filter-death is the big one — F6 canary now closes it; missed-path breakage is loud), plus the two v2 additions above (pre-commit `entry:` strings, keeping `apps/**` triggers).

---

## Stage 3 — Split the god-stack ⚠️ REWRITTEN AROUND `cdk refactor` (adversary B4)

**Objective:** `Cawnex-${stage}` (1,002 lines) → bounded-context stacks. Two governing rules now:
1. **Stateful resources never move** — the shrinking `Cawnex-${stage}` becomes the Foundation stack.
2. **Stateless resources move via CloudFormation Stack Refactoring** (`cdk refactor`, verified available in CLI 2.1106.0) — resources transfer between stacks **without deletion or recreation**: no physical-name collisions, no downtime, no new URLs, **no event-source-mapping recreation and therefore no stream replay**. Delete-then-create is the documented fallback ONLY for resource types the refactor API rejects.

Target topology:

```
CawnexDomain-${stage}        (exists)  DNS, ACM, SES
CawnexAuthStack-${stage}     (exists)  Cognito + main table (stays; see D5 note below)
Cawnex-${stage}              (shrinks) Foundation: VPC, ECS cluster, EFS, S3×2, KMS,
                                        events table, SQS, secrets, **CloudFront**
CawnexApi-${stage}           (new)     API Lambda + HTTP API GW + JWT authorizer
CawnexOrchestration-${stage} (new)     murder, monarch, checker, worker-scaler,
                                        worker/council Fargate services + schedules
CawnexStreaming-${stage}     (new)     stream Fargate + ALB + Pipe + stream SQS/DLQ
```

**CloudFront stays in Foundation (adversary B3).** iOS dev pins `d1elid9twwevj2.cloudfront.net`; recreating the distribution mints a new domain and bricks installed builds, and CF distribution delete/recreate takes 15–40+ min. Treat it as quasi-stateful: it never moves; only its **origin** is repointed at the new HTTP API. Hardening (recommended before this stage): attach the custom domain (`CawnexDomain` stack exists; staging/prod configs already expect `api*.cawnex.ai`) so the client-facing URL is permanently decoupled from any distribution.

**Main table stays in Auth stack — honest framing (adversary D5):** stack refactoring COULD move it safely now; we choose not to practice the newest maneuver on the most critical resource first. Recorded as a known wart with `cdk refactor` as the exit path.

### Task 3.0: Preconditions

- [ ] Fix `utilities.yml` deploy-production: `stage=production` doesn't match the `"dev"|"staging"|"prod"` prop type — a `Cawnex-production` universe would get **dev semantics: DESTROY policies on prod data, SPOT, public IPs** (adversary M9). Change to `prod` and add a type guard in `bin/cawnex.ts` that throws on unknown stages. Pre-existing bug; must precede any prod rehearsal. NOTE: `CawnexAuthStack-prod` + `CawnexCloudflareStack-prod` already exist (deployed manually with `stage=prod`, correctly typed) — the bug is in the workflow, not the deployed stacks; any pipeline-driven prod deploy would still create the parallel `-production` universe.
- [ ] Inventory live stacks + verify `cdk refactor` against a toy resource on dev (move one SSM parameter or log group between stacks) to confirm the workflow end-to-end before betting on it.
- [ ] Export-deadlock rehearsal (adversary F8, 20 min): on dev, attempt to delete one still-imported export; observe the "Cannot delete export" failure once, safely.

### Task 3.1: Neutralize the export coupling FIRST

- [ ] Replace the **8 imported** exports with literal physical names + SSM capability registry (`Table.fromTableAttributes` with `tableName: cawnex-${stage}` + stream ARN via SSM; Cognito IDs via SSM). There are **9 declared** exports (`Region` is exported but never imported — adversary A6); two-phase removal must account for all 9: keep every `CfnOutput` until no stack imports it, remove in a later deploy.
- [ ] **GSI-grant gotcha (adversary M8a):** `Table.fromTableAttributes` without `globalIndexes` yields grants that EXCLUDE `/index/*` — pass `globalIndexes: ["GSI1","GSI2"]` or preserve the explicit index policy (`cawnex-stack.ts:518-523`), else GSI queries break silently.
- [ ] `cdk diff` must show only IAM/parameter wiring, zero replacements. Deploy dev.
- [ ] Commit: `refactor(infra): decouple stacks via ssm capability registry, retire cfn exports`

### Task 3.2: Extract stacks — Streaming → Api → Orchestration, via refactor

Per extraction: (1) define the new (initially near-empty — a stack can't be **left** empty, but needs a seed resource) stack in CDK and deploy it; (2) move the constructs in code to the new stack, changing NOTHING else; (3) `cdk refactor` to map moved resources (refactor-only step — never mixed with add/modify/delete changes); (4) deploy; (5) smoke.

- [ ] **Streaming first.** Note the SSE-gap mechanism correction (adversary A16): if any resource does fall back to delete/recreate, coverage comes from the events-table DDB stream (not SQS buffering — the Pipe would be down), and TRIM_HORIZON on a recreated Pipe replays up to 24h of stale events at SSE clients. Fallback rule for ANY recreated stream/pipe consumer: **recreate with `LATEST` + quiesced writes**, never TRIM_HORIZON (adversary M5 — `_should_skip` does NOT dedup replays: INSERTs and status transitions re-fire reactors; monarch re-runs full LLM chains and re-spends).
- [ ] **Api second.** With CloudFront staying in Foundation, the client URL survives; the work is repointing the CF origin to the new HTTP API endpoint + updating `infrastructure-only.yml:170-201` (reads `CloudFrontUrl` from `Cawnex-${stage}` — output stays; API GW outputs move to `CawnexApi-${stage}`).
- [ ] **Orchestration last — this is the big one (adversary M8).** Cross-stack surface: VPC/subnets, ECS cluster, EFS + access points, **EFS security-group ingress rules** (`cawnex-stack.ts:446,563` — when worker/council SGs move stacks, rule ownership must flip to the consumer side via imported SG ids, or you create a reverse dependency), task queue, both S3 buckets, KMS key, 3 secrets, events table, main-table stream. ~12 seams through SSM. If any resource falls back to delete/recreate: `cawnex/${stage}/stream-pipe-secret` is an explicitly-named secret — deleted secrets enter scheduled-deletion recovery and block same-name recreation; use force-delete or rename. Budget Orchestration as its own 2–3 day effort with its own detailed plan.
- [ ] Quiesce before Orchestration moves: no EXECUTING wave; worker-scaler already idles services to 0.
- [ ] After each extraction: template snapshot assertions (Task 0.3) updated + green, dev smoke (signup → project → wave → SSE event), separate commit. Update stack names hardcoded in `main-pipeline.yml` deploy job and `infrastructure-only.yml:99-106,220-234` in the same PR.
- [ ] During Stage 3, remove the ECR "immutable tag" error-swallowing (`main-pipeline.yml:259`) so image-push failures surface.

**Stage 3 risk register (v2)**

| Risk | Severity | Change from v1 |
|---|---|---|
| "Cannot delete export" deadlock | Critical | Unchanged; Task 3.1-first + F8 rehearsal + 9-export accounting |
| Physical-name collision on move | ~~Critical~~ → Low | `cdk refactor` never recreates; collision only possible in the documented fallback |
| iOS URL breakage | ~~High~~ → Low | CloudFront never moves/recreates; custom-domain hardening recommended |
| Stream replay re-fires reactors / monarch re-spends | Medium | Only in fallback path; LATEST+quiesce rule mandatory (verified: `_should_skip` does not protect) |
| Orchestration extraction underestimated | High | Now explicit: ~12 SSM seams + SG-ownership flip + GSI grants; own sub-plan required |
| `cdk refactor` immaturity / unsupported resource type | Medium (new) | Task 3.0 toy rehearsal; per-resource fallback documented; refactor-only steps never mixed with other changes |
| Prod rehearsal impossible until utilities.yml fixed | High (pre-existing) | Task 3.0 fixes `stage=production` |

---

## Stage 4 — API service-layer extraction

**Objective:** `routes/autopilot.py` (795 lines) and `routes/waves.py` (746) become transport adapters over modules that hide one design decision each.

**Reality check first (adversary M6):** the helpers being extracted carry **16 `# pragma: no cover`** markers — `_create_project:220`, `_generate_and_save_documents:268`, `_save_milestones_and_mvis:381`, `_activate_wave:562`, `_handle_launch:657`, `_handle_message:718` have **zero tests**; the 75% gate passes because they're exempted. Moving them without the pragmas drops them into the coverage denominator and fails the gate.

- [ ] **Step 0 per module: write characterization tests BEFORE the move** (pin current behavior with recorded fixtures), then move, then drop the pragma.
- [ ] Module boundaries (revised per adversary D4 — decompose by information hiding, not chat-pipeline order):
  - `autopilot_session.py` — hides the session persistence schema ✓
  - `plan_extraction.py` — hides plan-parsing rules ✓
  - ~~`project_setup.py`~~ → `project_documents.py` (project record + document persistence — "project setup" name-collides with monarch's stack-level "async project setup chain", `cawnex-stack.ts:320`)
  - `wave_activation.py` — MUST be the shared module consumed by BOTH `autopilot.py` and `waves.py` (activation logic currently duplicated at `waves.py:90,588`); that dual consumption is the proof it's an information-hiding module and not a pipeline stage. Name the waves.py leftovers explicitly: event emission, PR merge.
- [ ] **Transport models stay separate from domain models** (adversary D4c): route request/response Pydantic models map explicitly to/from `cawnex_core` dataclasses — do NOT bind wire formats to internal schema (Overexposure).
- [ ] One PR per module; `mypy --strict` + complexity gates on new modules.

**Risk: Low-Medium** (raised from v1's Low — the missing test net was the hidden cost).

---

## Stage 5 — Docs + naming triage

- [ ] `README.md` → point at `docs/design/orchestration.md`; mark ARCHITECTURE-V2 historical.
- [ ] `docs/archive/` for the ~30 stale root files.
- [ ] **Reconcile docs against CODE, not doc-against-doc (adversary A15):** `murder/enums.py` (post-Stage-1: `cawnex_core.enums`) has 14 wave states including INTEGRATING/NEEDS_REWORK/UNDER_COUNCIL_REVIEW/UNDER_HUMAN_REVIEW that even the "canonical" `wave-lifecycle.md` (11 states) lacks. Regenerate the lifecycle doc from the enum source; then fix `system-reference.md` from it.
- [ ] Unify decider naming (`agent.py`/`reactor.py`/`orchestrator.py`) — taste-level, optional.
- [ ] Fold `worker/integration.py` into the `integrator/` package.
- [ ] `docs_only` filter keeps this PR deploy-free — verify in the detect-changes log.

---

## Falsifying tests (adversary F1–F9, cross-referenced above)

| # | Falsifies | Where it lives |
|---|---|---|
| F1 | "suites just need running" | Task 0.1 baseline verification |
| F2 | core zero-dep invariant | Task 1.1 CI job — permanent |
| F3 | "no resource replacement" in Stages 2–3 | Task 0.3 snapshot tests + Task 2.1 synth diff |
| F4 | murder dist completeness | Task 1.2 docker import test |
| F5 | "replay is handled" | Made moot by refactor path; run only if fallback recreation is ever used |
| F6 | deploy liveness (filter death AND stub death) | Task 0.2 canary; rerun after Stage 2 |
| F7 | iOS URL survivability | Made moot by CloudFront-stays rule; do NOT run (it bricks dev builds by design) |
| F8 | export-removal understanding | Task 3.0 rehearsal |
| F9 | copy reconciliation | Task 1.2 pin tests |

---

## Trade-offs: doing it vs. not (v2)

| Stage | Cost to do | Cost of NOT doing | Verdict |
|---|---|---|---|
| 0 | ~1–1.5 days (grew: deploy-stub fix + infra tests + DynamoDB Local CI) | Pipeline keeps lying about deployments; later stages fly blind | Do unconditionally — B5 alone justifies it |
| 1 | 2–4 days | Schema/pricing drift across copies (Haiku-vs-Sonnet pricing drift already live) | Highest value/risk ratio |
| 2 | 1 day, one careful PR | Confusion tax on every reader/agent | Do right after 1 |
| 3 | 3–5 days (Orchestration alone ≈ 2–3; was underestimated in v1) | God-stack keeps growing; but it works today | Defer until it hurts; do 3.0 (utilities.yml fix) + 3.1 (export decoupling) regardless — both are cheap and defuse standing traps |
| 4 | 2–3 days (grew: characterization tests first) | autopilot.py keeps accreting untested orchestration | Do opportunistically, per-module |
| 5 | ½ day | Stale front door poisons context for the platform's own agents | Do with Stage 2 |

**The meta-benefit** stands: Cawnex's premise is agents building software from this repo's own context — every copy-fork, dead COPY, lying pipeline tag, and stale doc is context poison for its own Crows. This is product work on the substrate they consume.
