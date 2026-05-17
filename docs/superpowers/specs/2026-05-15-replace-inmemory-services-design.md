# Replace InMemory iOS services with real API implementations

**Date:** 2026-05-15
**Trigger:** Dogfood run 5 surfaced that tapping a task on the wave-execution screen showed mock "RBAC middleware" data with hardcoded `PR #15`. None of the data was real. Investigation found that 7 of 14 iOS services are still pure `InMemoryXService` mocks.

**Goal:** Wire every iOS service to a real backend endpoint, with honest placeholders for fields that don't yet exist in DDB. Eliminate the "tapping into iOS reveals fake data" failure mode.

## Current state — what's already real vs mock

| Service           | iOS impl exists | API impl exists         | Wired in `ServiceFactory`             |
| ----------------- | --------------- | ----------------------- | ------------------------------------- |
| Project           | ✅              | ✅ APIProjectService    | ✅ (when apiClient present)           |
| Document          | ✅              | ✅ APIDocumentService   | ✅                                    |
| ProjectHub        | ✅              | ✅ APIProjectHubService | ✅                                    |
| Backlog           | ✅              | ✅ APIBacklogService    | ✅                                    |
| Goal              | ✅              | ✅ APIGoalService       | ✅                                    |
| MVI               | ✅              | ✅ APIMVIService        | ✅                                    |
| HumanTask         | ✅              | ✅ APIHumanTaskService  | ✅                                    |
| Wave              | ✅              | ✅ APIWaveService       | ✅                                    |
| Autopilot         | ✅              | ✅ APIAutopilotService  | ✅                                    |
| **Task**          | ✅              | ❌                      | ❌ InMemoryTaskService always         |
| **PR**            | ✅              | ❌                      | ❌ InMemoryPRService always           |
| **Milestone**     | ✅              | ❌                      | ❌ InMemoryMilestoneService always    |
| **Murders**       | ✅              | ❌                      | ❌ InMemoryMurdersService always      |
| **Skills**        | ✅              | ❌                      | ❌ InMemorySkillsService always       |
| **Credits**       | ✅              | ❌                      | ❌ InMemoryCreditsService always      |
| **Notifications** | ✅              | ❌                      | ❌ InMemoryNotificationService always |

7 to build. **PR #15** that we saw in iOS was hardcoded in `InMemoryTaskService` and has nothing to do with the actual GitHub PR that happens to share the same number.

## Field-by-field gap analysis

For each service, three states per field:

- **(R)eal** — backend already has it
- **(D)erived** — backend has the raw data; new endpoint must compute/aggregate it
- **(P)laceholder** — iOS expects it but we don't track it yet; new endpoint returns empty/null and iOS renders a placeholder per user preference

### 1. Task service ⏱ Priority 1

iOS `TaskDetail` fields:

| Field                 | Status | Source                                                                                          |
| --------------------- | ------ | ----------------------------------------------------------------------------------------------- |
| `id`                  | D      | Composite `wave_id:mvi_id:task_index`                                                           |
| `name`                | R      | `cr_plan_01.outcome.tasks[i].name`                                                              |
| `description`         | R      | `tasks[i].description`                                                                          |
| `status`              | D      | Inferred from whether any implementer crow has touched the files in `tasks[i].files_to_modify`  |
| `breadcrumb`          | D      | `"Milestone X › Goal Y › MVI Z › Task N"` — build from parent items                             |
| `humanEstimate`       | R      | `tasks[i].estimated_hours`                                                                      |
| `aiCost`              | D      | Pro-rated share of implementer crow's cost (rough: `crow_cost / task_count`)                    |
| `roi`                 | D      | `humanEstimate / aiCost * humanRate`                                                            |
| `assignedCrow`        | R      | `cr_impl_02.crow_type`, `crow_id`, model, behavior_state, cost.duration_ms, files_changed count |
| `implementationSteps` | **P**  | Return `[]`; iOS renders "No implementation steps recorded yet" placeholder                     |
| `acceptanceCriteria`  | **P**  | Same — return `[]`, iOS shows placeholder                                                       |
| `pr`                  | D      | If `cr_impl_02.pr.number` exists, fetch live GitHub PR for title/branch/status/lines/files      |

**Endpoint:** `GET /projects/{project_id}/tasks/{task_id}` where `task_id = "{wave_id}:{mvi_id}:{task_index}"`.

### 2. PR service ⏱ Priority 1

iOS `PRReviewDetail` fields:

| Field                                                                     | Status | Source                                                                                      |
| ------------------------------------------------------------------------- | ------ | ------------------------------------------------------------------------------------------- |
| `title`, `branch`, `status`, `linesAdded`, `linesRemoved`, `filesChanged` | D      | GitHub API: `GET /repos/{repo}/pulls/{n}` — cache 1h in DDB                                 |
| `breadcrumbMVI`, `breadcrumbTask`                                         | D      | Parent walk                                                                                 |
| `creditsCost`, `aiMinutes`                                                | D      | Sum of all crows in the wave's cost                                                         |
| `verdict` (Approved/Changes/Rejected, confidence, summary, findings)      | R      | Reviewer crow's `outcome.summary`, `outcome.blocking_issues`, `outcome.non_blocking_issues` |
| `planSteps`                                                               | D      | Map of planner.tasks → implementer.changes                                                  |
| `suggestedQuestions`                                                      | **P**  | Return `[]`, iOS shows placeholder                                                          |
| `conversation`                                                            | **P**  | Return `[]`, iOS shows placeholder                                                          |

**Endpoint:** `GET /projects/{project_id}/waves/{wave_id}/mvis/{mvi_id}/prs/{pr_number}`.

**Caching:** GitHub responses cached at `PK=GITHUB#CACHE`, `SK=PR#{repo}#{pr_number}` with `expires_at` 1h TTL.

### 3. Milestone service ⏱ Priority 2

`/milestones` route already exists and returns the milestone list. iOS detail view needs:

| Field                                                         | Status | Source                                                                                                 |
| ------------------------------------------------------------- | ------ | ------------------------------------------------------------------------------------------------------ |
| Milestone (id, name, description, status)                     | R      | Existing `/milestones` response                                                                        |
| Section blocks (Business Achievement, Success Criteria, etc.) | D      | Currently text-flat in `description`; iOS expects structured sections. Parser? Or new field on schema? |
| Chat messages                                                 | D      | Reuse `autopilot.py` chat endpoint — already wires AI conversations                                    |
| Goals list with task summaries                                | D      | Existing goal items aggregated                                                                         |

**Endpoint:** Add `GET /milestones/{milestone_id}` to existing route file. Wire chat through existing `/autopilot/chat`.

**Deferred field:** structured sections — for v1, put the full milestone description in a single `overview` block; iOS hides the section list until backend supports it.

### 4. Murders service ⏱ Priority 3

Static catalog only. No DDB queries needed for v1.

**Endpoint:** `GET /murders` — returns hardcoded catalog of {Dev, Editorial, Social, Infra, Data} + their crow definitions. Live state (which crows are currently building) **deferred** — return placeholder status `"idle"` for all murders.

**Marketplace:** also static for v1.

### 5. Skills service ⏱ Deferred

**Skills are design-phase only.** No DDB schema in use, no implementation work done, no clear product surface yet. The iOS mock renders a non-functional list.

**Decision:** **defer**. Return `404 Not Implemented` from a stub endpoint OR hide the iOS Skills tab until the feature has a real backend. Reopens when we have a concrete skills design (likely after Agent SDK adoption, where skills are a Claude Code primitive we'd map onto).

### 6. Credits service ⏱ Priority 2

iOS `CreditsData` fields:

| Field                              | Status | Source                                                                                                             |
| ---------------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------ |
| `creditBalance` (remaining, total) | **P**  | No user-level balance modeled yet. Return `null` or fixed `Decimal("0")`, iOS renders "Setup required" placeholder |
| `projectBudgets`                   | R      | Per-wave `budget.spent` summed by project                                                                          |
| `costBreakdown`                    | D      | Same source, sliced by category (planner/implementer/reviewer)                                                     |
| `crowCosts`                        | D      | Sum `cost.credits` across all crow snapshots, group by `crow_type`                                                 |
| `roiSummary`                       | D      | Sum `humanEstimate` from all planner tasks; ROI = humanHours × hourlyRate / creditsSpent                           |

**Endpoint:** `GET /billing/usage?project_id={pid}` — aggregates from existing wave/crow data.

**Deferred:** purchase history, invoices, balance top-up. iOS shows placeholders for those tabs.

### 7. Notifications service ⏱ Priority 3

iOS `NotificationsData` has two sections: `needsAction` and `recent`.

**Data source:** the existing `cawnex-events-dev` events table has every wave/crow event. The notifications service is essentially a _projection_ of that event log into user-facing notifications.

| Field                     | Status | Source                                                                                             |
| ------------------------- | ------ | -------------------------------------------------------------------------------------------------- |
| Wave-failed notifications | D      | Filter events for `mvi_failed`, `wave_cancelled`                                                   |
| MVI-shipped notifications | D      | Filter for `mvi_ready`                                                                             |
| Task approvals            | **P**  | We don't have approval gates wired through events yet — return empty list, hide the section in iOS |

**Endpoint:** `GET /notifications?project_id={pid}` — queries the events table with project-scoped filter, transforms event types into iOS notification shapes.

**Deferred:** push notifications via APNs. v1 is in-app only.

## Endpoint additions summary

| #   | Method | Path                                                | Returns              | Priority |
| --- | ------ | --------------------------------------------------- | -------------------- | -------- |
| 1   | GET    | `/projects/{pid}/tasks/{task_id}`                   | TaskDetail           | P1       |
| 2   | GET    | `/projects/{pid}/waves/{wid}/mvis/{mid}/prs/{pr_n}` | PRReviewDetail       | P1       |
| 3   | GET    | `/milestones/{milestone_id}`                        | MilestoneDetail      | P2       |
| 4   | GET    | `/billing/usage`                                    | CreditsData          | P2       |
| 5   | GET    | `/murders`                                          | MurdersData (static) | P3       |
| 6   | GET    | `/notifications`                                    | NotificationsData    | P3       |
| 7   | —      | (Skills — deferred indefinitely)                    | —                    | —        |

## iOS changes summary

| Service       | New API impl             | Wire in `ServiceFactory`                | Placeholder UI changes                                            |
| ------------- | ------------------------ | --------------------------------------- | ----------------------------------------------------------------- |
| Task          | `APITaskService`         | wrap existing make                      | Hide implementationSteps + acceptanceCriteria sections when empty |
| PR            | `APIPRService`           | wrap existing make                      | Hide suggestedQuestions + conversation when empty                 |
| Milestone     | `APIMilestoneService`    | wrap existing make                      | Collapse structured sections to single "Overview" v1              |
| Credits       | `APICreditsService`      | wrap existing make                      | Balance section shows "Setup required"                            |
| Murders       | `APIMurdersService`      | wrap existing make                      | Live state shows "idle" badge                                     |
| Notifications | `APINotificationService` | wrap existing make                      | Hide "needs action" if empty                                      |
| Skills        | — (deferred)             | leave InMemorySkillsService OR hide tab | —                                                                 |

All placeholder UI changes follow the user-stated preference: **"keep the sections, render placeholders"** — never silently drop a section the user might expect to see.

## Execution order

Phase 1 (this session): **Tasks + PR** — directly fixes the screen the user just hit. ~3h estimate.
Phase 2 (next session): **Milestone + Credits** — moderate effort, real value. ~3h.
Phase 3 (later): **Murders + Notifications** — lower-priority polish. ~2h.
Phase 4 (when skills is a real product feature): **Skills** — deferred until product decision lands.

## Risk callouts

1. **GitHub API rate limits.** PR enrichment calls GitHub on every iOS request. Even with 1h cache, a busy wave could hit the 5000/hr authenticated limit. Mitigation: aggressive cache, batch-fetch on wave-level reads, fall back to DDB-only when cache miss + rate-limited.
2. **`task_id` composite key.** `wave_id:mvi_id:task_index` works but couples the task identity to the planner's output array order. If we ever support task reordering or re-planning, this composite breaks. Acceptable for v1; revisit when re-planning lands.
3. **Per-task cost pro-rating is approximate.** Implementer crow cost is per-crow, not per-task. Dividing by task count gives a rough number. Honest fix: surface the imprecision in the UI ("approx") or aggregate cost only at the MVI level. v1 ships the rough number with no UI hedge; deferred refinement.
4. **`implementationSteps` and `acceptanceCriteria`** are placeholders today. The right long-term answer is the implementer crow emits per-task step records and the reviewer crow emits per-criterion verdict records. That's a larger change to the crow output schema; for v1 we leave the fields empty.
5. **No new test infrastructure required** for the API additions — they pattern-match existing routes (projects.py, mvi.py) and reuse the same `tenant_db` + `boto3` plumbing.

## Out of scope for this initiative

- Adding implementation-step tracking to the implementer crow.
- Adding per-criterion verdict tracking to the reviewer crow.
- Replacing `InMemoryMilestoneService` planning chat flow with anything beyond the existing autopilot endpoint.
- iOS push notifications (APNs).
- Per-user credit balance and purchase flow.
- Skills product surface — entire feature deferred.

These are all real product gaps but each is a meaningful design effort in its own right and shouldn't block fixing the "iOS shows mock data" problem.
