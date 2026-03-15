# Screen Query Analysis — S70 Notifications

> DynamoDB single-table mapping for the notification center.

---

## S70 — Notifications

**Purpose:** Cross-project actionable inbox where the founder approves, retries, ships, or reviews items surfaced by the system.

### Data Needed

| Field            | Type     | Example                                                                         |
| ---------------- | -------- | ------------------------------------------------------------------------------- |
| id               | string   | UUID                                                                            |
| type             | enum     | task_approval, mvi_ready, task_failed, mvi_shipped, credits_low, vision_ready   |
| title            | string   | "RBAC middleware needs approval"                                                |
| timestamp        | datetime | ISO 8601                                                                        |
| category         | enum     | action, info                                                                    |
| status           | enum     | created, seen, acted_on                                                         |
| deepLink         | object   | `{screen: "S33", projectId, entityId}`                                          |
| actions          | array    | `[{label: "Approve", type: "approve", color: "green"}]`                         |
| projectId        | string   | UUID (which project generated this)                                             |
| projectName      | string   | "Cawnex Platform" (denormalized for display)                                    |
| sourceEntityType | string   | task, mvi, document, billing                                                    |
| sourceEntityPath | string   | `S#milestones/m1/goals/g1/mvis/mvi1/tasks/t1` (snapshot path that triggered it) |

### DynamoDB Access Patterns

#### Separate notification partition (not inside project snapshots)

Notifications live under a **tenant-level notification partition**, not under individual project PKs. This is because S70 aggregates across all projects and needs a single query to load the inbox.

#### Records

| PK                            | SK                                | Purpose                 |
| ----------------------------- | --------------------------------- | ----------------------- |
| `T#{tenant_id}#NOTIFICATIONS` | `N#{timestamp}#{notification_id}` | One notification record |

SK uses timestamp-first ordering so `Query` returns newest first via `ScanIndexForward: false`.

#### Read: Load notification inbox

```
GET /notifications?filter=all|action|info&cursor=...

Query:
  PK = T#{tenant_id}#NOTIFICATIONS
  SK begins_with N#
  ScanIndexForward: false
  Limit: 20
  FilterExpression: (if filter=action) category = "action"
                    (if filter=info)   category = "info"
```

Returns paginated, newest-first. Client groups into "NEEDS ACTION" (category=action, status!=acted_on) and "RECENT" (category=info or status=acted_on).

#### Read: Unread badge count (for S10 bell icon)

```
Query:
  PK = T#{tenant_id}#NOTIFICATIONS
  SK begins_with N#
  FilterExpression: status = "created"
  Select: COUNT
```

Alternatively, maintain a counter on the dynasty record to avoid scanning:

| PK                      | SK     | Attribute                    |
| ----------------------- | ------ | ---------------------------- |
| `T#{tenant_id}#DYNASTY` | `META` | `unreadNotificationCount: N` |

Atomically incremented on notification create, decremented on seen/acted_on.

#### Write: Mark as seen

```
POST /notifications/:id/actions/seen

UpdateItem:
  PK = T#{tenant_id}#NOTIFICATIONS
  SK = N#{timestamp}#{notification_id}
  SET status = "seen", seenAt = :now
  CONDITION: status = "created"

+ UpdateItem (atomic decrement):
  PK = T#{tenant_id}#DYNASTY, SK = META
  SET unreadNotificationCount = unreadNotificationCount - 1
```

#### Write: Act on notification (approve, retry, ship)

```
POST /notifications/:id/actions/:action

TransactWriteItems:
  1. Update notification:
     PK = T#{tenant_id}#NOTIFICATIONS
     SK = N#{timestamp}#{notification_id}
     SET status = "acted_on", actedAt = :now, actionTaken = :action

  2. Update dynasty counter (if transitioning from "created"):
     PK = T#{tenant_id}#DYNASTY, SK = META
     SET unreadNotificationCount = unreadNotificationCount - 1

  3. Execute the action on the source entity:
     (varies by action type — see below)
```

**Action side-effects by type:**

| Notification Type | Action  | Side-Effect Write                                                                                                                                            |
| ----------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| task_approval     | approve | Update task snapshot status from `pending_approval` → `approved`. PK=`T#{tenant_id}#P#{project_id}`, SK=`S#milestones/.../tasks/{id}`, SET status="approved" |
| task_approval     | review  | No write — deep link navigation to S33                                                                                                                       |
| mvi_ready         | ship    | Update MVI snapshot status → `shipped`. Triggers merge queue.                                                                                                |
| mvi_ready         | review  | No write — deep link navigation to S32                                                                                                                       |
| task_failed       | retry   | Update task snapshot status → `queued`, reset error fields. Murder picks it up.                                                                              |
| task_failed       | view    | No write — deep link navigation to S33                                                                                                                       |

All action writes are transactional with the notification status update to prevent double-actions.

---

### How Notifications Are Generated

Notifications are **not derived on-read** from snapshot diffs. They are **explicitly created as records** when specific state transitions occur in the system.

#### Generation triggers

| Trigger Event                                    | Notification Type | Category | Producer                                   |
| ------------------------------------------------ | ----------------- | -------- | ------------------------------------------ |
| Crow completes task, needs human approval        | `task_approval`   | action   | Murder (after crow reports completion)     |
| All tasks in MVI complete, merge checklist green | `mvi_ready`       | action   | Murder (wave completion check)             |
| Crow fails task after max retries                | `task_failed`     | action   | Murder (escalation rule fires)             |
| MVI shipped (merged to main)                     | `mvi_shipped`     | info     | Ship endpoint (post-merge)                 |
| Credit balance drops below threshold             | `credits_low`     | info     | Billing Lambda (on credit deduction)       |
| Vision document AI synthesis complete            | `vision_ready`    | info     | Document chat Lambda (all sections filled) |

#### Generation flow

```
State change in snapshot (e.g., task status → "pending_approval")
    │
    ▼
Lambda / Murder writes the snapshot update
    │
    ▼
Same Lambda (or EventBridge rule) creates notification:
    PutItem:
      PK = T#{tenant_id}#NOTIFICATIONS
      SK = N#{ISO_timestamp}#{uuid}
      Attributes: type, title, category, status="created",
                  projectId, projectName, deepLink, actions,
                  sourceEntityPath
    │
    ▼
Atomically increment:
    T#{tenant_id}#DYNASTY → META → unreadNotificationCount += 1
    │
    ▼
Push to real-time channel (see below)
```

---

### Notification Lifecycle

```
created ──────► seen ──────► acted_on
   │              │              │
   │  User opens  │  User taps  │
   │  S70 screen  │  action btn │
   │              │              │
   │  (bulk mark  │  (approve,  │
   │   on scroll) │   ship,     │
   │              │   retry)    │
   │              │              │
   └──── OR ──────┴──► expired  │
         (TTL after 30 days)    │
```

- **created**: Record written, unread counter incremented, push sent.
- **seen**: User scrolled past it or opened detail. Counter decremented.
- **acted_on**: User performed the inline action. Source entity updated transactionally.
- **expired**: DynamoDB TTL removes stale notifications after 30 days. Add `ttl` attribute (epoch seconds) on creation.

For `action` category notifications that are never acted on, they remain visible until either:

- The underlying entity changes state through another path (e.g., someone approves from S33 directly). A cleanup Lambda marks the notification as `acted_on` with `actionTaken: "resolved_externally"`.
- TTL expires.

---

### Storage Decision: Separate Records (Not Derived)

**Decision: Dedicated notification records under `T#{tenant_id}#NOTIFICATIONS`.**

| Option                        | Pros                                                                                                         | Cons                                                                                                                                |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------- |
| Derived from snapshot diffs   | No extra storage, always consistent                                                                          | Requires scanning all project snapshots, cross-project fan-out is expensive, can't track seen/acted_on state, no ordering guarantee |
| Separate notification records | Single-PK query for entire inbox, supports lifecycle states, TTL cleanup, cross-project by design, paginated | Requires creation logic, minor denormalization (projectName), could drift if source entity changes                                  |

Separate records win because:

1. S70 queries **across all projects** — scanning every `T#{tenant_id}#P#*` partition would be N+1.
2. Notifications have their own lifecycle (created/seen/acted_on) that doesn't belong on the source entity.
3. TTL-based cleanup keeps the partition from growing unbounded.
4. The bell badge count needs a fast path — a counter on `DYNASTY#META` is O(1).

---

### Real-Time: Push + SSE

#### Push notifications (app backgrounded)

```
Notification creation Lambda
    │
    ▼
SNS → APNs (Apple Push Notification Service)
    │
    Payload: {
      title: "Task needs approval",
      body: "RBAC middleware — Cawnex Platform",
      data: { notificationId, deepLink }
    }
```

- Push registration token stored on `T#{tenant_id}#DYNASTY` → `DEVICE#{device_id}` records.
- APNs handles delivery, badge count sync.

#### SSE (app foregrounded on S70 or S10)

```
Client connects:
  GET /notifications/stream
  Headers: Authorization: Bearer {jwt}
  Accept: text/event-stream

Server (API Gateway + Lambda@Edge or AppSync):
  - On notification creation, publish to per-tenant SNS topic or EventBridge
  - SSE adapter fans out to connected clients for that tenant

Event format:
  data: {"type":"new_notification","payload":{"id":"...","type":"task_approval","title":"...","category":"action"}}
```

When the client receives a new_notification event:

1. Prepend to local notification list.
2. Increment local badge count.
3. Play haptic/sound if category=action.

---

### Cross-Project Aggregation

The `T#{tenant_id}#NOTIFICATIONS` partition is **project-agnostic by design**. Every notification carries `projectId` and `projectName` as denormalized attributes, but they all live under the same PK.

This means:

- One `Query` loads the entire inbox across all projects.
- Client-side filtering by project is possible if needed (FilterExpression on `projectId`).
- No GSI is needed for the primary inbox use case.

If per-project notification views become necessary later (e.g., "show notifications for this project only"), add:

| GSI                      | PK                             | SK                                |
| ------------------------ | ------------------------------ | --------------------------------- |
| GSI-ProjectNotifications | `T#{tenant_id}#P#{project_id}` | `N#{timestamp}#{notification_id}` |

This GSI is **not needed for MVP** since S70 always shows all-project notifications.

---

### Complete Record Schema

```json
{
  "PK": "T#acme#NOTIFICATIONS",
  "SK": "N#2026-03-14T10:32:00Z#n_abc123",
  "notificationId": "n_abc123",
  "type": "task_approval",
  "title": "RBAC middleware needs approval",
  "category": "action",
  "status": "created",
  "projectId": "p_xyz",
  "projectName": "Cawnex Platform",
  "deepLink": {
    "screen": "S33",
    "projectId": "p_xyz",
    "entityId": "t_456"
  },
  "actions": [
    { "label": "Approve", "type": "approve", "color": "green" },
    { "label": "Review", "type": "review", "color": "muted" }
  ],
  "sourceEntityPath": "S#milestones/m1/goals/g1/mvis/mvi1/tasks/t1",
  "createdAt": "2026-03-14T10:32:00Z",
  "seenAt": null,
  "actedAt": null,
  "actionTaken": null,
  "ttl": 1747219920,
  "entityType": "Notification"
}
```
