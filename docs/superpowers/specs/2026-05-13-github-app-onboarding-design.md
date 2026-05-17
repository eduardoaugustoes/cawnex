# GitHub App Onboarding — Read the Repo, Skip the 24 Questions

> Spec for a Cawnex GitHub App that, when installed on a repo, lets Cawnex read the codebase directly and auto-author the 4 setup docs (Vision, Architecture, Glossary, Design) instead of asking the founder 24 sequential guided-chat questions on mobile.

---

## Overview

Today, a new Cawnex project requires the founder to author 4 documents through a guided-chat flow on iOS: Vision (6 sections), Architecture (7 sections), Glossary (5 sections), Design (6 sections). That's 24 sequential questions, each with non-trivial answers. Authoring takes ~30-60 minutes per project on mobile, with no save-on-background, no resume-mid-section, and a silent input-length cap that truncates long answers.

For founders with an existing repo (the common case — Cawnex's target audience already ships MVPs), most of the content for these 4 docs _already exists in the codebase_: README, ARCHITECTURE.md, package.json, CDK stacks, file structure, code conventions, ADRs. Asking the founder to manually re-author what's already in their repo is friction without value.

This spec adds a Cawnex GitHub App that, after one-time install on a repo, gives Cawnex repo-scoped read access. Monarch reads the repo and drafts the 4 setup docs autonomously. The founder reviews and edits the drafts instead of authoring from a blank chat.

---

## The Problem (Pain Felt Directly)

Authored the 4 setup docs for the Cawnex-in-Cawnex project on 2026-05-13. Real findings from that session:

- **24 sequential questions on mobile is exhausting.** The founder has to context-switch between strategic answers (Vision) and technical answers (Architecture) without leaving the chat surface.
- **Backgrounding the iOS app loses chat sequence state.** Re-opening the doc shows current section but no breadcrumb of prior questions.
- **Silent input-length cap truncates answers at ~7500 chars without warning.** Discovered when the Architecture clarification on failure modes silently chopped at "user-side cancell..."
- **The synthesizer's closing message says "vision document is now complete" regardless of which doc you just authored** — minor bug that signals lack of polish in the flow.
- **Most of the answers existed in the repo already.** README, ARCHITECTURE-V2.md, VISION.md, package.json, CDK stacks, the iOS DesignSystem/ folder all contained the canonical content. Re-authoring it manually was busywork.
- **The doc-generation chat isn't pasteable in bulk.** Even canonical content from existing docs has to be answered question-by-question; can't paste a 4-doc bundle in one go.

The cumulative finding: **for any founder with an existing repo, the 24-question onboarding is the wrong shape**. It treats the founder as the source of truth when the repo _is_ the source of truth.

For founders without an existing repo (greenfield projects), the guided chat is the right shape and stays. This spec is additive — it adds a path, doesn't replace one.

---

## Proposed Solution

### One-time setup: Cawnex GitHub App

A standard GitHub App registered under Cawnex's organization. Founders install it on individual repos (or all repos in an org) via the GitHub OAuth flow. The App requests these permissions:

- **Contents: read** — clone the repo, read files.
- **Metadata: read** — repo name, description, language stats, topics.
- **Pull requests: write** — needed for downstream Crow execution (Cawnex already requires this; folded into the same App).
- **Workflows: read** — read existing CI workflows to inform Design doc.

Installation creates a per-repo `installation_id` stored in the project's DDB record (alongside existing `repo` field) plus a per-tenant entry in Secrets Manager for the App's private key (one private key for the App globally; per-tenant access is gated by `installation_id`).

### Onboarding flow with GitHub App installed

When the founder creates a new Project and selects a connected repo:

1. **Repo Analysis (background, ~30-60s)** — Monarch fetches the repo via the App. Pulls:
   - README.md (root)
   - ARCHITECTURE.md, VISION.md, GLOSSARY.md if they exist
   - `docs/` directory recursively (markdown only)
   - `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, etc. (language signals)
   - `infra/`, `cdk/`, `terraform/`, `kubernetes/` if present (deployment signals)
   - Top-level file tree (depth ≤ 3) for module/feature inference
   - `.github/workflows/*.yml` (CI/CD signals)
   - Repo metadata: primary language, topics, description, default branch, star count

2. **Doc Drafting (background, ~1-2 min)** — Monarch runs 4 specialized Claude calls in parallel, one per doc type. Each call gets:
   - The relevant fetched content (README + topics for Vision; ARCHITECTURE.md + file tree + manifests for Architecture; glossary-like content + domain folder names for Glossary; design system files + CSS/SwiftUI tokens + screenshots if any for Design)
   - The existing per-doc prompt template (already in `lambdas/monarch/src/monarch/config.py`)
   - An augmented system prompt: "Draft sections that the founder will review and edit. When information is missing, mark the section as ⚠ NEEDS_INPUT with a specific question; do not invent."

3. **Founder Review (iOS)** — Project hub shows all 4 docs in a new "⚠ Drafts Ready" state instead of "Not started." Each doc card has:
   - Section-by-section preview of the AI-drafted content
   - Per-section status: ✓ Drafted from repo / ⚠ NEEDS_INPUT (with the specific question) / ✏ Manual override
   - Edit affordance: tap a section to edit inline (text editor, not chat)
   - Accept-all-as-drafted button (one tap, marks doc Complete if no ⚠ sections remain)
   - Fall-back to guided chat: a "Re-author with chat" option for founders who want the old experience

4. **Founder finalizes (5-10 min)** — Most sections are accepted as-is; a few sections (the ⚠ NEEDS_INPUT ones) get short manual answers. Founder hits "Mark Complete" on each doc. Project is ready to dispatch.

**Expected time savings:** 30-60 min of guided-chat authoring → 5-10 min of review-and-fill. ~6x improvement.

### Flow when no GitHub App / no repo

The guided-chat flow stays unchanged for:

- Greenfield projects (no repo yet)
- Founders who decline to install the App
- Repos the App can't access (private repos in another org, archived repos)

This is a strict superset of today's flow, not a replacement.

---

## Architecture

### New components

**Cawnex GitHub App** — a single App registered with GitHub. Lives in Cawnex's GitHub org. Private key stored in Secrets Manager (one key, used to sign JWTs that authenticate as the App per-installation).

**`/auth/github-app/install` route** — initiates the GitHub App installation flow. Returns the GitHub-hosted install URL. Founder clicks → installs on a repo → GitHub redirects to a Cawnex callback.

**`/auth/github-app/callback` route** — receives the GitHub callback after install. Stores `installation_id` against the founder's tenant in DDB. Returns success to iOS for repo selection.

**`/projects/{project_id}/connect-repo` route** — links an existing project to an installed repo. Stores `repo`, `repo_owner`, `installation_id` on the project root snapshot. Triggers the Repo Analysis flow asynchronously.

**Monarch's `analyze_repo` step (new)** — runs after `connect-repo` returns. Authenticates as the App, fetches the repo content via the GitHub REST API (using octokit or PyGithub from the Monarch Lambda), runs the 4 parallel doc-drafting Claude calls, writes drafts to DDB at `DOC#{doc_type}` with status `drafted` (new status, distinct from `pending`/`complete`).

**Section-level status field on docs** — extend the existing section schema with: `drafted | needs_input | manual | complete`. The doc-level status becomes `complete` only when no sections are `needs_input`.

**iOS Document review screen** — modifies `Features/Documents/DocumentScreen.swift` to support the new section-status types and the inline edit affordance. Adds a "Drafts Ready" badge to doc cards on the project hub.

### Modified components

- `Features/Projects/CreateProject` — adds repo selection step (post-Murders selection, pre-create). If GitHub App is installed on at least one repo, show a repo picker; otherwise show "Connect GitHub" CTA.
- `apps/api/src/routes/projects.py` — `POST /projects` accepts an optional `repo_installation_id` field. If present, the project is created with `repo`, `repo_owner`, `installation_id` set and a downstream `analyze_repo` job is queued.
- `lambdas/monarch/src/monarch/agent.py` — adds a new phase before "Phase 1: Generate documents" — `Phase 0: Analyze repo (if installation_id present)`. Phase 1 then runs in "draft from repo content" mode instead of "draft from one-liner."
- `lambdas/monarch/src/monarch/config.py` — adds 4 new prompt templates: `DOC_PROMPTS_FROM_REPO` (Vision/Architecture/Glossary/Design variants that take repo content as context). The original `DOC_PROMPTS` stays as fallback.

### Data model additions

**Project root snapshot — new fields:**

- `repo_owner: str` — GitHub org or user name.
- `repo_installation_id: int` — GitHub App installation ID. Null if the repo isn't connected via App.
- `repo_analyzed_at: str` — ISO timestamp of last repo analysis.

**Tenant entry — new SK:**

- `SK: GH_APP#installation#{installation_id}` — records which installations belong to which tenant. Used for tenant-scoping the App's per-installation access.

**Document section — extended:**

- `status: drafted | needs_input | manual | complete | pending`
- `drafted_from: str | null` — optional reference to the source file path (e.g., "README.md") so the founder sees provenance.

---

## Security Considerations

GitHub Apps with `Contents: read` have read access to _all_ private code in installed repos. This is a significant trust escalation from the current model (where Cawnex only needs write access to specific branches the user explicitly authorizes for Crow PRs).

**Mitigations:**

- **Scope per repo, not per org.** Even if a founder installs the App on their entire org, Cawnex stores installations _per repo_ and only ever fetches the specific repo a Project is connected to. The org-wide install is a convenience for the founder; Cawnex internally treats each repo as a separate scope.
- **No persistent caching of repo content beyond doc drafting.** Once the 4 doc drafts are written to DDB, the fetched repo content is discarded. Re-analyzing a repo requires re-fetching (with an explicit "Re-analyze" action; no automatic re-pulls).
- **Founder consent on each project.** Even with the App installed, connecting a repo to a specific Project requires an explicit tap in CreateProject. No background pulls.
- **Audit log entry on every repo fetch.** New event type in the Events table: `repo_analyzed` with tenant_id, project_id, repo, files_fetched_count, timestamp.
- **Founder can revoke per-project** via project Settings: "Disconnect repo" removes the `installation_id` from the project record. Disconnecting from the GitHub side (uninstalling the App) is detected via webhook and triggers cleanup.

**What we don't do:**

- **No PR content analysis** beyond what's needed for the 4 docs. We don't read PR descriptions, issues, discussions, or comments at onboarding time.
- **No multi-repo correlation.** Each project is connected to one repo. Multi-repo projects are roadmap.
- **No automatic upstream sync.** When the repo evolves (new README, new ADRs), we don't auto-update the Cawnex docs. The founder has to explicitly trigger a re-analysis.

---

## iOS Changes

### CreateProject flow

After the Murders selection step (current final step before Create), insert a new "Connect Repo" step:

```
[ Connect Repo (optional) ]
─────────────────────────────────────
  Speed up onboarding by connecting
  your repo. Cawnex will draft your
  setup docs from the codebase
  instead of asking 24 questions.

  [ Connect GitHub ]  (primary CTA)

  Or [ Skip — author manually ]
```

If GitHub App is already installed, show a repo picker instead:

```
[ Connect Repo ]
─────────────────────────────────────
  Select a repository:

  ○ eduardoaugustoes/cawnex
  ○ eduardoaugustoes/calhou
  ○ eduardoaugustoes/navvo.ai

  [ Continue ]

  Or [ Connect another repo ]
  Or [ Skip — author manually ]
```

### Document review screen

Replace the current 4-doc card grid on the project hub with this state machine:

| Project state                                    | Document card shows                      |
| ------------------------------------------------ | ---------------------------------------- |
| No repo connected, no docs started               | "Not started" + guided-chat tap-to-start |
| Repo connected, analysis running                 | "Analyzing repo..." + spinner            |
| Repo connected, drafts ready, ⚠ sections present | "Drafts ready (3 need input)" with badge |
| Repo connected, drafts ready, all clear          | "Drafts ready — review & accept"         |
| Founder finalized                                | "Complete"                               |

Tapping a doc card with drafts opens `DocumentReviewScreen` (new) instead of the chat screen:

- Section list (collapsible cards)
- Each section shows:
  - Section title + status icon
  - For `drafted` sections: the AI-drafted text + an "Edit" button + an "Accept" button + provenance line ("drafted from README.md")
  - For `needs_input` sections: the AI-flagged question + a text input + an "Answer" button
  - For `manual` sections: the founder's edited text + "Edit" button
- Doc-level "Mark Complete" CTA at the bottom, enabled when all sections are accepted/answered

A small "Re-author with chat" link at the top, in case the founder prefers the guided experience.

---

## Out of Scope

Explicit list so this spec doesn't drift:

- ❌ **Auto-sync the docs when the repo evolves.** Founder explicitly re-analyzes.
- ❌ **Multi-repo projects.** One project = one repo at launch.
- ❌ **Pulling issues, PRs, discussions, wiki.** Read-only access to repo _contents_ and _metadata_ only, used for the 4 docs.
- ❌ **GitHub Enterprise / self-hosted GitHub.** GitHub.com only at launch.
- ❌ **Other VCS providers.** No GitLab, Bitbucket, Codeberg. Roadmap if customer demand justifies.
- ❌ **Bring-your-own-GitHub-App.** Cawnex hosts and registers the App; founders install ours, they don't bring their own.
- ❌ **Replacing the guided-chat flow.** Guided chat stays for greenfield/disconnected projects.
- ❌ **Repo-driven Backlog/Goal generation.** This spec is doc-drafting only. Reading the repo to infer Milestones/Goals/MVIs is a separate, larger spec.
- ❌ **iOS-side repo content viewing.** The founder doesn't browse repo files inside Cawnex. The integration is upstream of the iOS surface.

---

## Implementation Order

Suggested slicing:

1. **GitHub App registration + private key management** — register the App with Cawnex's GitHub org, store the private key in Secrets Manager, add the install URL config. No code change yet.
2. **Auth routes (`/install`, `/callback`)** — implement the OAuth-style install flow. Test by installing on a personal repo and confirming `installation_id` lands in DDB.
3. **Monarch's `analyze_repo` function** — pure-function that takes `installation_id`, fetches repo content, returns a structured context object. Unit-tested against fixture installations using moto or a real-but-recorded GitHub API response.
4. **`DOC_PROMPTS_FROM_REPO` templates + Monarch Phase 0** — wire up the 4 specialized Claude calls. Test that drafts land in DDB with correct section statuses.
5. **iOS DocumentReviewScreen + section-level status UI** — new screen, replaces chat for repo-backed projects.
6. **CreateProject repo selection step** — UI for picking an installed repo or connecting a new one.
7. **End-to-end test on the Cawnex repo itself** — install the App on `cawnex`, create a new "Cawnex 2" project, watch the 4 docs auto-draft from the actual codebase, finalize in <10 minutes.

Each step is independently mergeable. Step 7 is the dogfood validation.

---

## Why This Goes On the Cawnex Project's Own Backlog

This is the same self-improvement pattern as the project-state-readout spec: Cawnex notices its own friction, files a spec, runs the spec through itself. The 24-question onboarding pain felt during this very session _is_ the operating-log entry that justifies this work.

When Cawnex executes this spec (after the readout spec ships and the factory is proven), the result is:

- Future Cawnex projects (Calhou, navvo.ai, any new product Eduardo starts) onboard in 5-10 minutes instead of 30-60.
- Founders who land on cawnex.com can install the App during their trial signup and have a working Cawnex project before their 7-day trial ends — without spending a meeting's worth of time answering chat questions.
- The doc quality is _higher_ in many cases, because the AI is grounded in actual repo content rather than the founder's recall from memory at midnight.

The activation metric (Vision + Architecture + Goal + first MVI shipped in 7 days, from the Glossary doc) becomes meaningfully easier to hit when the first 30 minutes of friction collapses to 5.
