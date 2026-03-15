# Screen Query Analysis — S11 Create Project

> DynamoDB single-table mapping for project creation.

---

## S11 — Create Project

**Purpose:** Quick project creation form; minimal fields, AI refines during Vision phase.

### Data Needed

| Field    | Type     | Required | Default   |
| -------- | -------- | -------- | --------- |
| name     | string   | yes      | —         |
| oneLiner | string   | no       | —         |
| murders  | string[] | yes      | `["dev"]` |

No data is read from DynamoDB to render this screen. The form is self-contained. Murder type options (Dev, Editorial, Social, Infra, Data) are client-side constants.

### DynamoDB Write Operations

On "Create Project" tap, the API executes a **TransactWriteItems** with the following records:

#### 1. Project record (under PROJECTS partition)

| PK                       | SK               | Purpose                                   |
| ------------------------ | ---------------- | ----------------------------------------- |
| `T#{tenant_id}#PROJECTS` | `P#{project_id}` | Register project in tenant's project list |

Attributes:

- `projectId`: generated UUID
- `name`: from form
- `oneLiner`: from form (or empty)
- `murders`: `["dev"]` or selected set
- `status`: `"active"`
- `phase`: `"vision"` (new projects start in Vision phase)
- `createdAt`: ISO timestamp
- `updatedAt`: ISO timestamp
- `entityType`: `"Project"`

#### 2. Root snapshot (project's own partition)

| PK                             | SK   | Purpose                             |
| ------------------------------ | ---- | ----------------------------------- |
| `T#{tenant_id}#P#{project_id}` | `S#` | Root of the recursive snapshot tree |

Attributes:

- `projectId`: same UUID
- `name`: from form
- `oneLiner`: from form
- `murders`: selected set
- `phase`: `"vision"`
- `status`: `"active"`
- `tasks`: `{"done": 0, "active": 0, "refined": 0, "draft": 0}`
- `creditsSpent`: `0`
- `humanEquivSaved`: `0`
- `documents`: `{"vision": "empty", "architecture": "empty", "glossary": "empty", "designSystem": "empty"}`
- `createdAt`: ISO timestamp
- `updatedAt`: ISO timestamp
- `entityType`: `"ProjectSnapshot"`

#### 3. Initial memory record

| PK                             | SK       | Purpose                                      |
| ------------------------------ | -------- | -------------------------------------------- |
| `T#{tenant_id}#P#{project_id}` | `MEMORY` | Monarch's persistent memory for this project |

Attributes:

- `projectId`: same UUID
- `directive`: `""` (empty until human steers)
- `decisions`: `[]`
- `context`: `{}`
- `createdAt`: ISO timestamp
- `entityType`: `"ProjectMemory"`

### What Records Get Created

| Record             | Count | Purpose                                                                     |
| ------------------ | ----- | --------------------------------------------------------------------------- |
| Project list entry | 1     | Adds project to `T#{tenant_id}#PROJECTS` so S10 Dashboard can list it       |
| Root snapshot      | 1     | Initializes `S#` — the root of the snapshot tree under the project's own PK |
| Project memory     | 1     | Empty memory record for Monarch to accumulate decisions and context         |

**No initial wave is created.** Waves are created by the Monarch during the Vision phase after the human provides direction. A newly created project has zero waves — the first wave emerges from the Vision document flow (S20).

### Transactional Considerations

All three records must be written atomically via `TransactWriteItems`:

1. **Atomicity** — If any write fails (e.g., duplicate project name check via condition expression), none are committed. The user sees a clean error.
2. **Condition on project list entry** — `attribute_not_exists(SK)` on the `PROJECTS` entry prevents duplicate project IDs (defense in depth; UUIDs make collisions near-impossible).
3. **No cross-partition consistency needed** — The `PROJECTS` entry and the `P#{project_id}` partition are different PKs, but DynamoDB `TransactWriteItems` handles up to 100 items across partitions.
4. **Idempotency** — The API should accept a client-generated idempotency key to prevent duplicate project creation on network retries.

### How This Bootstraps the Snapshot Tree

```
T#{tenant_id}#P#{project_id}
├── S#                          ← root snapshot (created here)
├── S#documents/vision          ← created when Vision chat starts (S20)
├── S#documents/architecture    ← created when Architecture chat starts (S21)
├── S#milestones/m1             ← created during Strategy phase
│   ├── S#milestones/m1/goals/g1
│   │   ├── S#milestones/m1/goals/g1/mvis/mvi1
│   │   │   └── S#milestones/m1/goals/g1/mvis/mvi1/tasks/t1
│   │   ...
├── MEMORY                      ← Monarch memory (created here)
├── EVT#w0#1710000000           ← events appear when waves start
...
```

The `S#` root is the only snapshot node that exists at project creation. The tree grows recursively as the project progresses through phases:

- **Vision phase** adds `S#documents/*` children
- **Strategy phase** adds `S#milestones/*` children
- **Planning phase** adds goals, MVIs, and tasks deeper in the tree
- **Execution phase** adds `EVT#` event records as waves run

Each `S#{path}` node can be queried independently with `begins_with(S#{prefix})` to load any subtree, enabling efficient partial reads (e.g., load just one milestone's goals without fetching the entire project).
