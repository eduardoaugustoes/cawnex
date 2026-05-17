# SSE Live Updates for Wave and MVI Screens

**Date:** 2026-05-15
**Status:** Phase 1 deployed, Phase 2 in progress

## Revision 2026-05-15 (after Phase 1)

The original design had EventBridge Pipes POST directly to the stream
service's `/_pipe` endpoint. EventBridge Pipes only support AWS-service
targets (Lambda/SQS/SNS/Step Functions/API Destination/etc.) — arbitrary
HTTP isn't a native target.

**Revised fanout for Phase 2:**

DDB Streams → EventBridge Pipe → **SQS queue** → stream service polls
the queue in a background asyncio task → fans out to in-memory subscribers.

The `/_pipe` HTTP endpoint stays for test injection and survives as the
canonical fanout entry point inside the service (the SQS poller calls
the same publishing code). Production traffic flows via SQS, not HTTP.

## Problem

iOS Wave Execution polls `GET /projects/{pid}/waves/{wid}` and `/events` every 3
seconds. iOS MVI Detail does not refresh at all after the initial load. Users
watching a wave see stale state until they back out of the screen, and the
3-second polling cadence is both wasteful (full wave refetched even when
nothing changed) and laggy.

We want push-based live updates on Wave Execution and MVI Detail. The wire
format should be debuggable with `curl`, recoverable across reconnects, and
not require adding a new operational concept (Redis, WebSockets) to the
platform.

## Constraints

- **API runs on Lambda.** Lambda cannot hold long-lived HTTP connections
  (API Gateway HTTP API caps at 30s, Lambda caps at 15min). The SSE endpoint
  must live elsewhere.
- **Worker runs on Fargate ECS** with EFS, behind a private VPC. Adding a
  second Fargate task is incremental — no new infrastructure category.
- **Worker writes events to the `cawnex-events-{stage}` DDB table** via
  `Blackboard.put_event`. The events table already exists, already has the
  right schema (`PK`, `SK`, `GSI1PK`, `GSI1SK`), and is the source of truth.
- **No Redis in the stack today.** A prior decision (see
  `cawnex-stack.ts:127` — "SQS — Task queue (replaces Redis Streams)")
  rejected Redis for the work queue. Re-introducing it for live updates is
  possible but adds an operational surface that isn't otherwise needed.
- **SSE clients must survive a 30-60s stream-service restart** without losing
  events.

## Out of Scope

- Notifications screen real-time updates (still uses polling on app foreground).
- Push notifications to a backgrounded app (separate APNs concern).
- Bidirectional client→server messaging during a stream (SSE is server→client).
- Multi-region replication of the stream service.
- Live updates for any screen other than Wave Execution and MVI Detail in
  this phase. Task Detail, Project Hub, etc. continue to be one-shot loads.

## Architecture

```
┌──────────┐    DDB put_item     ┌─────────────────┐
│  Worker  │ ──────────────────▶ │  Events Table   │
│ (Fargate)│                     │  (DynamoDB)     │
└──────────┘                     └────────┬────────┘
                                          │
                                          │ DynamoDB Streams
                                          ▼
                                 ┌─────────────────┐
                                 │ EventBridge Pipe│
                                 │ (filter +       │
                                 │  enrich)        │
                                 └────────┬────────┘
                                          │
                                          │ Pipe target = HTTP POST
                                          ▼
                                 ┌─────────────────┐         SSE
                                 │  Stream Service │ ──────────────▶  iOS
                                 │  (Fargate)      │                   client
                                 │                 │ ──────────────▶  iOS
                                 │  - holds N conn │                   client
                                 │  - in-mem map:  │
                                 │    wave_id →    │
                                 │    Set<conn>    │
                                 └────────┬────────┘
                                          │ backfill query on reconnect
                                          ▼
                                 ┌─────────────────┐
                                 │  Events Table   │
                                 │  (GSI1)         │
                                 └─────────────────┘
```

### Pieces

**Stream Service (new Fargate task)** — small ASGI app (FastAPI + uvicorn).
Single container, no EFS, no state. Holds long-lived SSE connections in
memory and maintains a per-wave subscription map. Exposed via the same
private VPC as the worker, fronted by a new public ALB target group.

**DynamoDB Streams on events table** — enabled with view type
`NEW_IMAGE`. Streams emit one record per `put_item`. Retention is 24h
(AWS default, not configurable).

**EventBridge Pipe** — source = DDB Streams ARN, target = HTTP POST to the
stream service's internal `/_pipe` endpoint. Filter pattern drops events we
don't broadcast (e.g., `event_type` matching internal-only types). Target
batches up to 10 events per POST.

**iOS SSE client** — `URLSession.bytes(for:)` for the underlying byte
stream, a small `EventStreamDecoder` for the SSE wire format, and a
`@MainActor`-isolated handler that routes parsed events into the existing
`WaveExecutionViewModel` / `MVIDetailViewModel`.

### Wire format

Standard SSE:

```
id: 1747332779492#crow_assigned
event: wave_event
data: {"event_id": "...", "wave_id": "w1778...", "mvi_id": "m1778...", "event_type": "crow_assigned", "payload": {...}, "timestamp": "2026-05-15T19:14:12Z"}

id: 1747332779492#planner_completed
event: wave_event
data: {...}

: keepalive

```

- `id:` — the DDB event's `SK` value (already monotonic per wave: ISO
  timestamp + event type suffix). Used by iOS for `Last-Event-ID` on
  reconnect.
- `event:` — `wave_event` for all wave/mvi/crow events; `error` for
  recoverable server-side issues; `bye` when the server is asking the
  client to disconnect (e.g., before shutdown).
- `data:` — JSON payload matching what `/events` returns today, so the
  iOS event model is unchanged.
- `:` (comment lines) every 25 seconds — keepalive so the ALB idle
  timeout (60s) doesn't kill us.

### Endpoints

| Endpoint                                 | Host           | Purpose                                                                                                                                                                                   |
| ---------------------------------------- | -------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /projects/{pid}/waves/{wid}/stream` | Stream service | Public SSE endpoint for clients. Auth via `Authorization: Bearer` header (Cognito JWT, same as Lambda API).                                                                               |
| `POST /_pipe`                            | Stream service | Private endpoint for the EventBridge Pipe. Receives batched event records, fans them out to in-memory subscribers. Restricted to the Pipe's IAM role via ALB listener rule + auth header. |
| `GET /_health`                           | Stream service | ALB target health check.                                                                                                                                                                  |

### Subscription model

The stream service holds two maps:

```python
subscribers: dict[str, set[Connection]]  # wave_id -> connections
mvi_to_wave: dict[str, str]              # mvi_id -> wave_id (cache)
```

When a client connects to `/projects/{pid}/waves/{wid}/stream`:

1. Validate JWT, extract tenant_id.
2. Look up the wave: `(tenant_id, wid)` must match — reject with 403 otherwise.
3. If `Last-Event-ID` header present, query the events table:
   `PK = T#{tenant}#P#{pid}#W#{wid}`, `SK > {last_event_id}`, limit 200.
   Send each backfill event as a normal SSE frame. (Bounded by events table
   TTL but client-controlled.)
4. Add the connection to `subscribers[wid]`.
5. Loop forever: every 25s send a keepalive comment.
6. On client disconnect, remove from `subscribers[wid]`.

When the Pipe POSTs an event batch:

1. For each event in the batch, extract `wave_id` from the DDB row's PK
   (`T#{tenant}#P#{pid}#W#{wid}` — wave_id is everything after `#W#`).
2. Look up `subscribers.get(wave_id, set())`.
3. For each connection, write the SSE frame to its send queue. Backpressure:
   if a connection's queue is over 100 events deep, drop the connection
   (client will reconnect and backfill).
4. ACK 200 to the Pipe.

### iOS data flow

```
URLSession.bytes
    → EventStreamDecoder (parses SSE frames)
    → WaveEventDispatcher (@MainActor)
    → WaveExecutionViewModel.appendEvent(_:)
    → @Observable triggers SwiftUI re-render
```

`WaveExecutionViewModel` already has an `events: [WaveEvent]` array and
`mvis: [WaveMVI]`. The dispatcher appends/dedupes by event id, and on
event types that mutate wave/MVI status (e.g., `mvi_ready`, `wave_failed`),
also triggers a one-shot refetch of `getWave` to refresh aggregate state.
This avoids reimplementing the aggregation logic that the API already does.

`MVIDetailViewModel` subscribes to the same wave stream but filters
client-side: only events whose `mvi_id` matches its current MVI are kept.

## Failure modes & recovery

| Failure                                  | What happens                                                   | Recovery                                                                                                                                                                                                                                                                                                                                                                                                        |
| ---------------------------------------- | -------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Stream service crashes                   | All connected clients see a TCP close.                         | Clients auto-reconnect (URLSession does this for SSE; if not, our wrapper does). On reconnect, they send `Last-Event-ID` and get backfill. Max gap: 24h (events table is long-lived, but DDB Streams retains 24h — if we restart **and** lose a Pipe message **and** are down >24h, we'd lose some events. Mitigation: clients backfill from the events table directly via `Last-Event-ID`, not from the Pipe.) |
| Pipe is throttled / behind               | New events buffer in DDB Streams.                              | Pipe automatically retries. Within 24h, no data loss. Clients see latency spike.                                                                                                                                                                                                                                                                                                                                |
| DDB Streams disabled by accident         | No new events delivered to clients.                            | Clients see stale UI until reconnect; reconnect's backfill query reads the events table directly, so UI catches up — but no further push updates until Streams is re-enabled. Alarmable.                                                                                                                                                                                                                        |
| iOS device sleeps, then wakes            | URLSession suspends connection; on wake, OS resumes or closes. | Wrapper detects close, reconnects with `Last-Event-ID`.                                                                                                                                                                                                                                                                                                                                                         |
| Client sends invalid JWT                 | 401 immediately, connection refused.                           | iOS surfaces auth error, kicks user to login.                                                                                                                                                                                                                                                                                                                                                                   |
| Client subscribes to wave they don't own | 403, connection refused.                                       | Same surface as today's REST endpoints.                                                                                                                                                                                                                                                                                                                                                                         |
| ALB idle timeout (60s default)           | Without keepalive, connection silently dies.                   | Keepalive every 25s prevents this.                                                                                                                                                                                                                                                                                                                                                                              |

## What this introduces vs. removes

**Introduces:**

- One new Fargate task (~$10-15/mo, 0.25 vCPU / 0.5 GB).
- One ALB target group + listener rule.
- DynamoDB Streams enabled on `cawnex-events-{stage}` (free; per-read cost
  ~$0.01/mo at our scale).
- One EventBridge Pipe (free at our scale).
- ~300 lines of Python in the stream service.
- ~150 lines of Swift for the iOS SSE client.

**Removes:**

- `Timer.scheduledTimer` polling in `WaveExecutionViewModel` (replaced).
- The "MVI page doesn't refresh" gap (now subscribes to wave stream).

**No change to:**

- Worker code. It keeps writing to DDB the same way.
- API Lambda. It keeps serving REST.
- Auth flow. Stream service validates the same Cognito JWTs.
- Existing iOS REST calls. Initial load is still REST; SSE is incremental
  updates on top.

## Out-of-the-box AWS quotas

- **DDB Streams** retention: 24h, fixed.
- **EventBridge Pipe** throughput: 100 records/sec per shard (DDB Streams
  shards). Our events table has 1 shard at current write rate; if we
  exceed 100 events/sec sustained, DDB auto-splits.
- **ALB idle timeout**: 60s default, we keepalive at 25s.
- **Fargate task concurrent connections**: 65k per task in theory; in
  practice tested to 10k+ on 0.25 vCPU. We're far below that.

## Phases

### Phase 1: Backend — stream service skeleton

1. New `apps/stream/` directory: Dockerfile, `main.py` (FastAPI), tests.
2. SSE endpoint `/projects/{pid}/waves/{wid}/stream` with JWT validation,
   keepalive, subscriber map. No backfill, no Pipe yet — manual `POST /_pipe`
   for tests.
3. ALB target group + listener rule (CDK).
4. New Fargate service in `cawnex-stack.ts` (same VPC, same cluster,
   different task def).
5. Deploy and curl-test from a developer laptop with a real JWT.

### Phase 2: Backend — Pipe wiring

1. Enable DynamoDB Streams on `EventsTable` (CDK property).
2. Create EventBridge Pipe: source = events table stream, target = stream
   service `/_pipe`, filter pattern drops internal-only event types.
3. Add a Pipe-only auth check on `/_pipe` (shared secret in env, or IAM
   SigV4 verification).
4. Smoke test: trigger a real wave, confirm events arrive at
   `/projects/{pid}/waves/{wid}/stream`.

### Phase 3: iOS — SSE client

1. New `Core/Network/EventStreamClient.swift` — `URLSession.bytes` wrapper,
   SSE parser, reconnect logic with `Last-Event-ID`.
2. Wire into `WaveExecutionViewModel` — replace `startPolling`/`stopPolling`
   with `subscribe`/`unsubscribe`.
3. Wire into `MVIDetailViewModel` — subscribe to parent wave's stream,
   filter to current MVI.
4. Keep initial REST load on both screens; SSE is delta updates only.
5. Test in simulator against deployed dev stage.

### Phase 4: Backfill + polish

1. Implement `Last-Event-ID` backfill query in stream service.
2. Add `Sentry`-style metrics: connections gauge, events/sec counter,
   backfill queries counter.
3. Add ALB access logging for the stream service.
4. Update `docs/ARCHITECTURE.md`.

## Open questions

None blocking. The design is tight enough to start Phase 1.

## Rejected alternatives

**Polling at higher cadence (1s) instead of SSE.** Wasteful at any scale.
Would still leave MVI Detail unfixed (it currently doesn't poll at all).

**WebSockets via API Gateway WebSocket API.** Adds a new AWS service
category, requires a connection-ID DDB table, makes the wire format harder
to debug with `curl`. SSE solves our use case (server→client only) without
the bidirectional baggage.

**Redis pub/sub + Fargate SSE.** The classical 2020s answer. Sub-second
latency, mature operational story. Rejected because it reintroduces Redis,
which the platform already chose against (SQS instead). 3-5s latency is
acceptable for "agent finished a step" UX. If a future feature (live cursors,
real-time chat) needs sub-second, reconsider.

**SNS topic with worker dual-write.** Worker publishes to both DDB and
SNS for each event. Lower latency than DDB Streams (~1-2s), but introduces
dual-write correctness risk: DDB writes succeed but SNS publishes fail
silently, and the event never streams. Solvable with an outbox pattern,
which costs design time we don't need to spend. DDB Streams is a single
source of truth.

**Have the worker hold connections directly.** Couples streaming lifecycle
to worker execution. A worker restart (deploy, scale-in) kills client
streams. Separating concerns wins.

**Stream service polls DDB Streams directly (no Pipe).** Saves
EventBridge but couples shard-ownership coordination into the stream
service. Pipes handles this for free at our scale.
