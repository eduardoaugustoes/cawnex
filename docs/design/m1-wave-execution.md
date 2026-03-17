# M1: Wave Execution — Implementation Plan

> The milestone that turns Cawnex from a planning tool into an execution platform.

## End-to-End Flow After M1

```
Plan MVIs (exists) → Create Wave (SM2) → Activate (SM2) →
  "Engine warming up..." event (SM2) →
  ECS scales up (SM1) → "Engine ready" event (Worker) →
  Murder queues MVIs (exists) → Planner crow dispatched (exists) →
  Worker claims crow on EFS worktree (SM1) →
  Planner → Implementer → Reviewer → Fixer (exists) →
  Events stream via SSE to iOS (SM1 + SM4) →
  Founder sees live events → Ships MVI → Wave delivered →
  ECS scales down (SM1)
```

## Decisions Made

| Decision         | Choice                                      | Rationale                                                       |
| ---------------- | ------------------------------------------- | --------------------------------------------------------------- |
| Worker runtime   | ECS Fargate (not Lambda)                    | Crows need git, worktrees, persistent repo cache                |
| Repo storage     | EFS with Access Points                      | Hard isolation by design — no application-level guards          |
| Tenant isolation | EFS Access Point per tenant                 | NFS-level enforcement, no path traversal possible               |
| Instances        | 1 for MVP                                   | Sequential crows, Claude API latency dominates                  |
| Scale-up         | Wave activation sets desiredCount=1         | Zero cost when idle                                             |
| Scale-down       | EventBridge checks every 15min              | Auto-shutdown after work completes                              |
| Events           | Separate DynamoDB table with TTL            | No bloat in main table, no false Murder triggers                |
| Real-time UI     | SSE via Lambda Function URL (streaming)     | <1s latency, no API GW timeout issue                            |
| ECS warm-up      | Synthetic events written at activation time | Founder sees full lifecycle from "warming up" to "crow working" |

## Sub-Milestones

### SM1: Infrastructure (EFS + Events Table + ECS Auto-Scale + SSE Lambda)

**Goal:** EFS with Access Point for tenant isolation, events table with TTL, ECS auto-scale, SSE streaming endpoint.

#### CDK Changes (`infra/lib/cawnex-stack.ts`)

**EFS:**

- New EFS filesystem `cawnex-repos-{stage}`
  - Encrypted at rest (AWS-managed KMS)
  - Performance mode: generalPurpose
  - Throughput mode: bursting
  - Lifecycle: transition to IA after 30 days
  - RemovalPolicy: RETAIN in prod, DESTROY in dev
- Access Point for the dev tenant:
  - path: `/T/dev-tenant`
  - posixUser: `{ uid: '1000', gid: '1000' }`
  - createAcl: `{ ownerUid: '1000', ownerGid: '1000', permissions: '750' }`
- Security Group: allow NFS (port 2049) from ECS security group only
- Mount targets in each VPC subnet
- ECS task definition mounts the Access Point (not raw filesystem) at `/mnt/repos`

**Events Table:**

- New DynamoDB table `cawnex-events-{stage}`
  - PK: `T#{tenant}#P#{project}#W#{wave_id}` (string)
  - SK: `{iso_timestamp}#{event_type}` (string)
  - TTL attribute: `expires_at`
  - GSI1PK: `T#{tenant}#P#{project}`, GSI1SK: `{iso_timestamp}`
  - PAY_PER_REQUEST billing
  - No DynamoDB Streams
- Grant read/write to: API Lambda, Murder Lambda, Worker ECS, SSE Lambda
- Environment variable: `EVENTS_TABLE_NAME` on all four

**ECS Auto-Scale:**

- EventBridge rule `cawnex-worker-scaledown-{stage}`: every 15 minutes
  - Target: new Lambda `cawnex-worker-scaler-{stage}`
  - Logic: query GSI1 for DISPATCH#pending; if empty AND no running crows → set desiredCount=0
- API Lambda gets `ecs:UpdateService` permission
- API Lambda gets environment variables: `ECS_CLUSTER_NAME`, `ECS_SERVICE_NAME`

**SSE Lambda:**

- New Lambda `cawnex-sse-{stage}`
  - Runtime: Python 3.12
  - Memory: 256 MB
  - Timeout: 15 minutes
  - Function URL with `invokeMode: RESPONSE_STREAM`
  - CORS: allow all origins
  - Auth: JWT validation in code (Cognito JWKS)
- Grants: read events table, read main table (for auth/tenant context)
- Environment: `EVENTS_TABLE_NAME`, `USER_POOL_ID`, `COGNITO_DOMAIN`

#### Murder Changes

**`lambdas/murder/src/murder/models.py`:**

- Update `EventRecord`: add `to_events_item()` with new PK/SK pattern + `expires_at` TTL

**`lambdas/murder/src/murder/config.py`:**

- Add `EVENTS_TABLE_NAME`, `EVENT_TTL_DAYS`

**`lambdas/murder/src/murder/blackboard.py`:**

- Add `events_table` parameter, `write_event()` method

**`lambdas/murder/src/murder/handler.py`:**

- Instantiate events table, pass to Blackboard

**`lambdas/murder/src/murder/reactor.py`:**

- Replace `blackboard.write_item(evt.to_item())` → `blackboard.write_event(evt.to_events_item())`

#### Worker Changes

- Same pattern: events table instantiation, write events there
- On first poll after startup, write `worker_ready` event

#### SSE Lambda

**`lambdas/sse/handler.py`:**

- Validate JWT from Authorization header
- Query events table for initial batch
- Loop: poll events table every 1s for new events (SK > last seen)
- Write SSE format: `data: {json}\n\n`
- Exit on wave terminal state or 14min timeout

#### Tests

- Updated murder + worker tests for event routing
- New SSE handler test (mock DynamoDB, verify SSE format output)

---

### SM2: Wave Lifecycle API

**Goal:** Create waves from backlog MVIs, activate for execution, pause, cancel, list, events endpoint.

#### Endpoints

**POST `/projects/{pid}/waves`** — Create wave from backlog MVIs

- Reads backlog MVIs, creates wave + MVI snapshots
- Annotates backlog MVIs with `wave_id`

**GET `/projects/{pid}/waves`** — List waves

- Returns wave summaries sorted by created_at desc

**POST `/projects/{pid}/waves/{wid}/activate`** — Start execution

- Transitions wave to `executing`, queues MVIs
- Writes synthetic events: `wave_activated`, `worker_warming`
- Calls ECS UpdateService (desiredCount=1)

**POST `/projects/{pid}/waves/{wid}/pause`**

- Transitions to paused, writes event

**POST `/projects/{pid}/waves/{wid}/cancel`**

- Cancels wave + all non-terminal MVIs, writes event

**GET `/projects/{pid}/waves/{wid}/events`**

- Paginated read from events table (fallback for non-SSE clients)

---

### SM3: Backlog → Wave Bridge

**Goal:** Backlog/goal screens show execution state. Hub shows active waves.

- `goals.py`: MVIs with `wave_id` include execution status
- `hub.py`: active wave count, pending human tasks, pending ship count

---

### SM4: iOS Wave Screens + SSE

**Goal:** Founder creates waves, activates, sees live events via SSE, ships MVIs.

#### SSE Client (iOS)

`WaveSSEClient` — connects to Lambda Function URL, receives events:

```swift
final class WaveSSEClient {
    func connect(waveId: String, token: String) -> AsyncStream<WaveEvent>
    func disconnect()
}
```

- Uses `URLSession` with `URLSessionDataDelegate`
- Parses `data: {json}\n\n` SSE format
- Reconnects on disconnect with exponential backoff
- Provides `AsyncStream<WaveEvent>` consumed by ViewModel

#### Screens

- `WaveListScreen` — active/completed waves, create button
- `WaveExecutionScreen` — live event feed (SSE), MVI cards, budget bar, ship buttons
- `CreateWaveSheet` — select MVIs from goal, create + activate

#### ECS Warm-Up Visibility

Events rendered in the feed:

1. `wave_activated` → "Wave activated — starting execution engine" (blue dot)
2. `worker_warming` → "Execution engine warming up (~30s)" (yellow dot, pulsing)
3. `worker_ready` → "Engine ready — dispatching crows" (green dot)
4. `crow_assigned` → "Planner crow assigned" (purple dot)
5. ... normal execution events

---

## Dependency Order

```
SM1 (Infrastructure) ──┐
                        ├── SM3 (Bridge)
SM2 (Wave API) ─────────┤
                        └── SM4 (iOS + SSE)
```

## What This Unlocks

After M1, the full execution flow works end-to-end:

1. Plan MVIs from goal-level AI chat (exists)
2. Create wave selecting MVIs (SM2)
3. Activate → see "Engine warming up..." (SM2 + SSE)
4. Planner identifies human tasks → Murder creates them (exists)
5. Non-blocked crows execute immediately (exists)
6. Founder sees events streaming live via SSE (SM1 + SM4)
7. Founder responds to human tasks (exists)
8. Blocked crows unblock and resume (exists)
9. Reviewer approves → MVI ready to ship (exists)
10. Founder ships MVI (SM2 + SM4)
