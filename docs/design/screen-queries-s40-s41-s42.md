# Screen Query Analysis — S40, S41, S42 (Murders & Crows)

> DynamoDB single-table mapping for murder configuration screens.

---

## S40 — Murders List

**Purpose:** Display all tenant murders with behavior states, crow roster, stats; browse marketplace templates.

### Data Needed

| Field              | Type     | Example                                     |
| ------------------ | -------- | ------------------------------------------- |
| name               | string   | "Dev Murder"                                |
| type               | enum     | Dev, Editorial, Social, Infra, Data, Custom |
| status             | enum     | active, idle, error                         |
| crowBehaviorStates | array    | [{name: "Planner", state: "Planning"}, ...] |
| crows              | array    | [{name, role, avatarIcon}]                  |
| activeTaskCount    | number   | 7                                           |
| totalCost          | currency | $42                                         |

Plus marketplace section: community templates with name, crowCount, installCount, rating, description.

### DynamoDB Queries

**List tenant murders:**

| Purpose                | PK                      | SK                     | Operation |
| ---------------------- | ----------------------- | ---------------------- | --------- |
| All murders for tenant | `T#{tenant_id}#DYNASTY` | `begins_with(MURDER#)` | `Query`   |

Returns all murder config records. Each murder record embeds its crow list inline (denormalized).

**Behavior states (live):**

| Purpose                                   | PK                                           | SK                  | Operation       |
| ----------------------------------------- | -------------------------------------------- | ------------------- | --------------- |
| Active executions referencing this murder | GSI: `T#{tenant_id}#MURDER#{murder_id}#EXEC` | `begins_with(META)` | `Query` on GSI2 |

Crow behavior states are derived from active execution records, not stored on the murder config itself. The client (or a Lambda) joins murder config with active execution state.

**Marketplace:** See Section 6 below.

### Write Operations

None from S40. Read-only screen.

---

## S41 — Create / Edit Murder

**Purpose:** Configure murder identity, crow roster, coordination flow, quality gates, escalation rules, budget limits.

### Data Needed (Form)

| Field           | Type              | Required    |
| --------------- | ----------------- | ----------- |
| name            | string            | yes         |
| type            | enum              | yes         |
| description     | string            | no          |
| crows           | CrowRef[]         | yes (min 1) |
| murderPrompt    | string            | no          |
| crowFlow        | FlowStep[]        | no          |
| qualityGates    | QualityGateConfig | no          |
| escalationRules | EscalationConfig  | no          |
| budgetLimits    | BudgetConfig      | no          |

### DynamoDB Queries

**Load for edit:**

| Purpose           | PK                      | SK                   | Operation |
| ----------------- | ----------------------- | -------------------- | --------- |
| Get murder config | `T#{tenant_id}#DYNASTY` | `MURDER#{murder_id}` | `GetItem` |

### Write Operations

**Create:**

| Purpose       | PK                      | SK                   | Operation                                   |
| ------------- | ----------------------- | -------------------- | ------------------------------------------- |
| Create murder | `T#{tenant_id}#DYNASTY` | `MURDER#{murder_id}` | `PutItem` (condition: attribute_not_exists) |

**Update:**

| Purpose       | PK                      | SK                   | Operation             |
| ------------- | ----------------------- | -------------------- | --------------------- |
| Update murder | `T#{tenant_id}#DYNASTY` | `MURDER#{murder_id}` | `PutItem` (overwrite) |

Crows are stored as a nested list attribute on the murder record (see design decision below). The full murder document is written atomically.

---

## S42 — Create Crow

**Purpose:** Define a crow's identity, model, skills, personality, and constraints within a murder.

### Data Needed (Form)

| Field       | Type     | Required |
| ----------- | -------- | -------- |
| name        | string   | yes      |
| role        | string   | yes      |
| goal        | string   | yes      |
| model       | enum     | yes      |
| description | string   | no       |
| skills      | string[] | no       |
| backstory   | string   | no       |
| constraints | string   | no       |
| temperature | number   | no       |
| maxTokens   | number   | no       |

### DynamoDB Queries

**Load murder (to show existing crows):**

| Purpose           | PK                      | SK                   | Operation |
| ----------------- | ----------------------- | -------------------- | --------- |
| Get parent murder | `T#{tenant_id}#DYNASTY` | `MURDER#{murder_id}` | `GetItem` |

### Write Operations

**Option A — Crow embedded in murder (recommended):**

| Purpose               | PK                      | SK                   | Operation                                       |
| --------------------- | ----------------------- | -------------------- | ----------------------------------------------- |
| Append crow to murder | `T#{tenant_id}#DYNASTY` | `MURDER#{murder_id}` | `UpdateItem` (list_append on `crows` attribute) |

**Option B — Crow as separate item:**

| Purpose     | PK                      | SK                                  | Operation |
| ----------- | ----------------------- | ----------------------------------- | --------- |
| Create crow | `T#{tenant_id}#DYNASTY` | `MURDER#{murder_id}#CROW#{crow_id}` | `PutItem` |

Option A is preferred: a murder rarely has more than 10 crows, the entire config is always loaded together, and atomic writes avoid partial states. The API endpoint `POST /murders/:murderId/crows` appends to the murder item's `crows` list.

---

## 4. Key Question: Where Do Murders Live?

Murders are **tenant-level configuration**, not project-level data. A single "Dev Murder" can be assigned to multiple projects.

### Decision: `T#{tenant_id}#DYNASTY` partition

```
PK: T#{tenant_id}#DYNASTY
SK: MURDER#{murder_id}      -- murder config
SK: META                     -- tenant metadata (already exists)
SK: SKILL#{skill_id}         -- skill configs (same pattern)
SK: SETTINGS                 -- tenant settings
```

**Why DYNASTY, not a separate `T#{tenant_id}#MURDERS` partition:**

1. **Access pattern alignment** — S40 loads all murders for a tenant. One `Query` on DYNASTY with `begins_with(MURDER#)` returns them all.
2. **Partition density** — A tenant will have 2-10 murders max. DYNASTY already holds org-wide config (META, settings). Adding murders keeps related config co-located without creating a hot partition.
3. **No cross-partition joins** — Loading S12 (Project Hub) needs murder names for the Agents card. The project snapshot references `murder_id`; the client resolves the name from a cached DYNASTY query (or a denormalized name on the project record).
4. **Consistent with existing V1 schema** — The V1 architecture already stores murders at `T#{tid}` / `MURDER#{mid}`. Moving to DYNASTY partition aligns with the V2 dynasty concept while keeping the same SK pattern.

### Alternative Considered: `T#{tenant_id}` (flat tenant PK)

The V1 schema uses `PK: T#{tid}`, `SK: MURDER#{mid}`. This works but mixes murders with projects, profiles, and other top-level records in one partition. The DYNASTY prefix provides cleaner logical grouping.

---

## 5. How Murder Config Connects to Snapshot Execution

Murder configs are **templates**. Execution snapshots **reference** them but do not embed them.

```
MURDER CONFIG (tenant-level, mutable)
  PK: T#{tenant_id}#DYNASTY
  SK: MURDER#{murder_id}
  Data: name, type, crows[], crowFlow[], qualityGates, ...

PROJECT ASSIGNMENT (project-level, snapshot)
  PK: T#{tenant_id}#P#{project_id}
  SK: WORKFLOW#{workflow_id}
  Data: murder_id (FK reference), project-specific overrides

EXECUTION (runtime, immutable snapshot)
  PK: T#{tenant_id}#EXEC#{exec_id}
  SK: META
  Data: mvi_id, murder_id, murder_snapshot: { ...frozen config at execution start }
```

### The Snapshot Rule

When a Murder starts executing an MVI:

1. **Freeze** — The execution META record captures `murder_snapshot`: a deep copy of the murder config at that moment. This ensures the execution is reproducible even if the murder config is later edited.
2. **Reference** — The execution also stores `murder_id` for lineage (which config template was this based on?).
3. **Isolate** — Crows in the execution read from the frozen snapshot, never from the live config. Mid-execution config changes do not affect running work.

This separation means:

- S40/S41/S42 read and write the **live config** in DYNASTY.
- S32 (MVI Blackboard) reads the **frozen snapshot** from the execution record.
- Editing a murder on S41 affects **future** executions, not in-flight ones.

### Crow Behavior States on S40

The "Planner: Planning / Implementer: Building" display on S40 comes from **active executions**, not the murder config. Query pattern:

```
GSI2PK: T#{tenant_id}#STATUS#running
Filter: murder_id = #{murder_id}
```

Then extract crow states from the execution's step records. This is a read-time join, acceptable because S40 is not a high-frequency polling screen.

---

## 6. Marketplace: Separate Partition or External Service?

### Recommendation: Separate Service (Phase 2), Read-Through Cache (Phase 1)

**Phase 1 — Stub with curated templates:**

Store marketplace templates in a global (non-tenant) partition:

```
PK: MARKETPLACE
SK: TEMPLATE#{template_id}
Data: name, description, type, crowCount, installCount, rating, author, config: { ...murder template }
```

This lives in the same DynamoDB table but uses a non-tenant PK. Any tenant can query it. Install = copy template config into `T#{tenant_id}#DYNASTY` / `MURDER#{murder_id}` as a new murder.

**Phase 2 — External service:**

When the marketplace grows (community submissions, versioning, reviews, search), extract to:

- Dedicated DynamoDB table or Aurora Postgres for richer queries
- S3 for template bundles
- CloudFront for caching
- Separate API (`/marketplace/*`) with its own Lambda

**Why not tenant-scoped:**

Marketplace templates are shared across all tenants. Storing them under a tenant PK would require cross-tenant reads, which breaks the single-table access pattern. The `MARKETPLACE` global PK keeps them accessible without tenant context.

### S40 Query for Marketplace

| Purpose            | PK            | SK                       | Operation                                       |
| ------------------ | ------------- | ------------------------ | ----------------------------------------------- |
| Featured templates | `MARKETPLACE` | `begins_with(TEMPLATE#)` | `Query` (limit 6, sort by installCount via GSI) |

---

## Summary: Complete Access Pattern Map

| Screen | Operation            | PK                             | SK / GSI                 | DynamoDB Op              |
| ------ | -------------------- | ------------------------------ | ------------------------ | ------------------------ |
| S40    | List murders         | `T#{tid}#DYNASTY`              | `begins_with(MURDER#)`   | Query                    |
| S40    | Crow behavior states | GSI2: `T#{tid}#STATUS#running` | filter by murder_id      | Query + filter           |
| S40    | Marketplace featured | `MARKETPLACE`                  | `begins_with(TEMPLATE#)` | Query                    |
| S41    | Load murder          | `T#{tid}#DYNASTY`              | `MURDER#{mid}`           | GetItem                  |
| S41    | Create murder        | `T#{tid}#DYNASTY`              | `MURDER#{mid}`           | PutItem                  |
| S41    | Update murder        | `T#{tid}#DYNASTY`              | `MURDER#{mid}`           | PutItem                  |
| S42    | Load parent murder   | `T#{tid}#DYNASTY`              | `MURDER#{mid}`           | GetItem                  |
| S42    | Add crow to murder   | `T#{tid}#DYNASTY`              | `MURDER#{mid}`           | UpdateItem (list_append) |
