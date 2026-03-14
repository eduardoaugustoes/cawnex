# Cawnex — POC Plan

> Prove the engine before building the product.

---

## The Bet

Cawnex's core value proposition: **AI agents autonomously turn GitHub issues into merged PRs.**

Everything else — iOS app, design system, billing, multi-tenant — is packaging. If the Murder→Crow pipeline doesn't produce quality code via MCP, nothing else matters.

These POCs validate every architectural risk before committing to the full build.

---

## Architecture Under Test

```
GitHub Issue
    │
    ▼
┌──────────────────────┐
│  Murder (MCP Client)  │ ← LLM-as-judge, discovers & calls crows
│  Lambda + DynamoDB    │
└──────────┬───────────┘
           │ MCP (Streamable HTTP)
           ▼
┌──────────────────────┐
│  Crow (MCP Server)    │ ← Exposes skills as MCP tools
│  Lambda + API GW      │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Blackboard (DynamoDB) │ ← Shared state, DynamoDB Streams triggers Murder
└──────────────────────┘
```

**Key concepts:**

- **Skills** = tool packs (collections of MCP tools)
- **Agents (Crows)** = MCP servers loaded with skills + system prompt + model
- **Murders** = MCP clients that orchestrate agents via tool discovery + LLM judgment
- **Blackboard** = DynamoDB shared state, Streams drive the event loop
- **MCP** = the universal protocol between Murder and Crows

---

## POC Dependency Graph

```
POC 1 (MCP Crow on Lambda)  ───┐
                                ├──→ POC 3 (Murder + Crow Integration) ──→ POC 4 (Full Loop)
POC 2 (Blackboard + Streams) ──┘
```

POC 1 and 2 are independent. POC 3 combines them. POC 4 is the demo.

---

## POC 1 — MCP Crow on Lambda

### Goal

Prove a crow can run as an MCP server on AWS Lambda, expose tools dynamically, and be called by an MCP client.

### What We're Validating

- MCP Streamable HTTP transport works behind API Gateway → Lambda
- Stateless Lambda can serve MCP tool discovery + invocation
- Cold start impact on MCP handshake + tool calls
- Session state recovery from DynamoDB/S3 between invocations

### Architecture

```
┌───────────────┐     MCP (Streamable HTTP)     ┌─────────────────┐
│  Test Client   │ ────────────────────────────→ │  API Gateway v2  │
│  (local Python)│ ←──────────────────────────── │       │          │
└───────────────┘                                │       ▼          │
                                                 │  Lambda (Crow)   │
                                                 │  - MCP Server    │
                                                 │  - 3 tools       │
                                                 │  - Anthropic SDK │
                                                 └────────┬────────┘
                                                          │
                                                    ┌─────┴─────┐
                                                    │ S3 (state) │
                                                    └───────────┘
```

### Crow Tools (Skills)

The POC crow exposes 3 tools via MCP:

```
tools/list response:
{
  "tools": [
    {
      "name": "read_file",
      "description": "Read contents of a file from the repository",
      "inputSchema": {
        "type": "object",
        "properties": {
          "repo": { "type": "string", "description": "owner/repo" },
          "path": { "type": "string", "description": "File path" },
          "ref": { "type": "string", "description": "Branch or commit SHA" }
        },
        "required": ["repo", "path"]
      }
    },
    {
      "name": "write_file",
      "description": "Create or update a file in the repository",
      "inputSchema": {
        "type": "object",
        "properties": {
          "repo": { "type": "string", "description": "owner/repo" },
          "path": { "type": "string", "description": "File path" },
          "content": { "type": "string", "description": "File content" },
          "branch": { "type": "string", "description": "Target branch" },
          "message": { "type": "string", "description": "Commit message" }
        },
        "required": ["repo", "path", "content", "branch", "message"]
      }
    },
    {
      "name": "create_pull_request",
      "description": "Open a pull request",
      "inputSchema": {
        "type": "object",
        "properties": {
          "repo": { "type": "string", "description": "owner/repo" },
          "title": { "type": "string" },
          "body": { "type": "string" },
          "head": { "type": "string", "description": "Source branch" },
          "base": { "type": "string", "description": "Target branch" }
        },
        "required": ["repo", "title", "head", "base"]
      }
    }
  ]
}
```

### Session State

Lambda is stateless. Between invocations, crow state lives in S3:

```json
{
  "session_id": "sess_abc123",
  "execution_id": "exec_xyz",
  "messages": [
    /* conversation history with Anthropic API */
  ],
  "tool_results": [
    /* accumulated tool call results */
  ],
  "branch": "cawnex/exec_xyz",
  "files_touched": ["src/auth.py", "tests/test_auth.py"]
}
```

On each MCP tool call:

1. Lambda starts → loads session from S3
2. Processes the tool call (calls GitHub API, Anthropic API, etc.)
3. Saves updated session to S3
4. Returns MCP response

### Implementation

**Language:** Python 3.12
**Dependencies:** `mcp` (MCP Python SDK), `anthropic`, `httpx` (GitHub API)
**CDK:** Lambda + API GW v2 + S3 bucket
**Test client:** Python script using MCP client SDK

### Steps

1. Set up CDK stack: `poc1-mcp-crow`

   - Lambda function (Python 3.12, 1GB memory, 5-min timeout)
   - API Gateway v2 HTTP API (single route: `POST /mcp`)
   - S3 bucket for session state
   - IAM roles

2. Implement MCP server in Lambda handler:

   - `initialize` → return server capabilities
   - `tools/list` → return 3 tools above
   - `tools/call` → dispatch to tool implementations
   - Session load/save on S3

3. Implement tools:

   - `read_file` → GitHub API `GET /repos/{owner}/{repo}/contents/{path}`
   - `write_file` → GitHub API `PUT /repos/{owner}/{repo}/contents/{path}`
   - `create_pull_request` → GitHub API `POST /repos/{owner}/{repo}/pulls`

4. Write test client:
   - Connect to MCP endpoint
   - Call `tools/list` → verify 3 tools
   - Call `read_file` → verify returns file content
   - Call `write_file` → verify creates commit
   - Call `create_pull_request` → verify opens PR

### Success Criteria

- [ ] MCP handshake completes in <3s (including cold start)
- [ ] `tools/list` returns all 3 tools with correct schemas
- [ ] `read_file` returns real file content from GitHub
- [ ] `write_file` creates a real commit on a branch
- [ ] `create_pull_request` opens a real PR
- [ ] Session state persists across multiple tool calls
- [ ] Cold start < 3s, warm invocation < 500ms

### Estimated Effort

Half a day. Mostly boilerplate CDK + MCP SDK wiring.

---

## POC 2 — Blackboard + Stream Filtering

### Goal

Prove DynamoDB Streams can drive the Murder event loop without noise, and that concurrent writes don't cause race conditions.

### What We're Validating

- DynamoDB Streams event filtering works (only specific SK patterns trigger Murder)
- Concurrent crow writes to same execution don't corrupt state
- Conditional writes prevent Murder race conditions
- Stream latency is acceptable (<1s from write to Lambda trigger)

### Architecture

```
┌───────────────┐                    ┌───────────────┐
│  Test Script   │ ── writes ──────→ │   DynamoDB     │
│  (simulates    │                   │   (blackboard) │
│  crows)        │                   └───────┬───────┘
└───────────────┘                            │ Streams
                                             │ (filtered)
                                             ▼
                                    ┌───────────────┐
                                    │  Murder Lambda  │
                                    │  (logs events)  │
                                    └───────────────┘
```

### Stream Filter

DynamoDB Streams event filter (in CDK):

```typescript
{
  eventName: ["MODIFY", "INSERT"],
  dynamodb: {
    NewImage: {
      SK: {
        S: [
          { "prefix": "META" },           // Execution created/updated
          { "prefix": "PLAN" },           // Plan submitted
          { "suffix": "#REPORT" },        // Crow report submitted
          { "suffix": "#DECISION" }       // Murder decision (for chaining)
        ]
      }
    }
  }
}
```

**Filtered OUT (no trigger):**

- `EVENT#<ts>` — fine-grained tool call events (high volume, noise)
- `STEP#<seq>#TASK` — task assignments (Murder wrote these, no need to re-trigger)

### Blackboard Records

```
Write pattern during a typical execution:

1. API creates execution:
   PK=T#tid#EXEC#e1  SK=META  status=pending          → TRIGGERS MURDER ✅

2. Murder assigns planner:
   PK=T#tid#EXEC#e1  SK=STEP#01#TASK  crow=planner    → no trigger ❌ (Murder wrote it)

3. Planner writes events (10-50 per execution):
   PK=T#tid#EXEC#e1  SK=EVENT#1710000001  type=tool    → no trigger ❌ (noise)
   PK=T#tid#EXEC#e1  SK=EVENT#1710000002  type=output  → no trigger ❌ (noise)
   ...

4. Planner submits report:
   PK=T#tid#EXEC#e1  SK=STEP#01#REPORT  outcome=done   → TRIGGERS MURDER ✅

5. Murder reviews, approves:
   PK=T#tid#EXEC#e1  SK=STEP#01#DECISION  verdict=go   → TRIGGERS MURDER ✅ (for chaining)

6. Murder assigns implementer:
   PK=T#tid#EXEC#e1  SK=STEP#02#TASK  crow=implementer → no trigger ❌

... and so on
```

**Result:** Murder fires ~2N+1 times for N steps (1 META + N reports + N decisions), NOT 50+ times from event noise.

### Concurrent Write Test

Simulate two crows finishing simultaneously:

```python
# Crow A writes report
table.put_item(Item={
    "PK": "T#t1#EXEC#e1", "SK": "STEP#02#REPORT",
    "crow": "implementer", "outcome": "completed"
})

# Crow B writes report (same execution, different step)
table.put_item(Item={
    "PK": "T#t1#EXEC#e1", "SK": "STEP#03#REPORT",
    "crow": "reviewer", "outcome": "completed"
})

# Both trigger Murder. Murder uses conditional update:
table.update_item(
    Key={"PK": "T#t1#EXEC#e1", "SK": "META"},
    UpdateExpression="SET #status = :new, #step = :step",
    ConditionExpression="#status = :expected",
    ExpressionAttributeValues={
        ":new": "step_03_deciding",
        ":expected": "step_02_deciding",  # Only one Murder wins
    }
)
# Loser gets ConditionalCheckFailedException → re-reads state → acts correctly
```

### Implementation

**CDK:** DynamoDB table (with Streams) + Lambda (Murder stub) + stream event source mapping with filters
**Test script:** Python script that writes various record patterns and verifies which ones trigger Murder

### Steps

1. CDK stack: `poc2-blackboard`

   - DynamoDB table with Streams enabled (NEW_AND_OLD_IMAGES)
   - Lambda function (Murder stub — logs received events)
   - Event source mapping with filter criteria

2. Implement Murder stub:

   - Logs: which PK/SK triggered it, event type
   - Writes to a "received events" table or CloudWatch for verification

3. Test script:

   - Write META record → verify Murder triggered
   - Write EVENT records (10x) → verify Murder NOT triggered
   - Write TASK record → verify Murder NOT triggered
   - Write REPORT record → verify Murder triggered
   - Write DECISION record → verify Murder triggered
   - Write two REPORTs simultaneously → verify both trigger Murder, conditional write resolves correctly

4. Measure latency:
   - Time from `put_item` to Murder Lambda invocation

### Success Criteria

- [ ] Murder fires ONLY on META, PLAN, REPORT, DECISION writes
- [ ] Murder does NOT fire on EVENT or TASK writes
- [ ] Stream latency < 1s (write to Lambda trigger)
- [ ] Concurrent reports both trigger Murder, conditional write prevents corruption
- [ ] Conditional write loser re-reads and acts correctly
- [ ] 50 EVENT writes produce 0 Murder invocations

### Estimated Effort

Half a day. Mostly CDK + a test script.

---

## POC 3 — Murder as MCP Client + LLM Judge

### Goal

Prove Murder can connect to crow MCP servers, discover their tools, orchestrate a multi-step task using LLM judgment, and drive the blackboard event loop.

### What We're Validating

- Murder can act as MCP client connecting to crow MCP servers
- LLM (Claude) can effectively judge crow output and decide next steps
- The full loop works: blackboard event → Murder → MCP call → crow executes → report → Murder judges
- Murder's decision quality: does it approve good work and reject bad work?

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        DynamoDB                               │
│                       (blackboard)                            │
└───────┬──────────────────────────────────┬───────────────────┘
        │ Streams                          ▲ writes
        ▼                                  │
┌───────────────┐    MCP (HTTP)    ┌───────────────┐
│  Murder Lambda │ ──────────────→ │  Crow Lambda   │
│  (MCP Client)  │ ←────────────── │  (MCP Server)  │
│                │                 │                 │
│  1. Read       │                 │  1. Receive     │
│     blackboard │                 │     tool call   │
│  2. Decide     │                 │  2. Execute     │
│     (Claude)   │                 │     (Claude +   │
│  3. Call crow   │                 │      GitHub)    │
│     via MCP    │                 │  3. Return      │
│  4. Write      │                 │     result      │
│     decision   │                 │                 │
└───────────────┘                 └───────────────┘
```

### Murder Decision Logic

Murder uses Claude as a judge. On each invocation:

```python
async def murder_decide(blackboard_state: dict) -> Decision:
    """Murder reads the blackboard and decides what to do next."""

    client = anthropic.AsyncAnthropic(api_key=user_api_key)

    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        system=MURDER_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"""
Current execution state:
{json.dumps(blackboard_state, indent=2)}

Based on the current state, decide the next action.
Respond with a JSON decision.
"""
        }]
    )

    return parse_decision(response)
```

**Murder system prompt (core):**

```
You are Murder, the orchestrator of a software development pipeline.
You are a JUDGE and DISPATCHER. You never write code or create plans yourself.

Your job:
1. Read the current state of an execution (the "blackboard")
2. Decide what needs to happen next
3. Assign the right crow (agent) for the job
4. Judge the quality of their output

Available crows (discovered via MCP):
{crow_tools}

Decision format:
{
  "action": "assign_crow" | "approve" | "reject" | "escalate",
  "crow": "planner" | "implementer" | "reviewer" | "fixer",
  "tool": "<MCP tool name to call>",
  "input": { /* tool input */ },
  "reason": "Why this decision",
  "feedback": "Instructions for the crow (if rejecting/assigning)"
}

Rules:
- Always start with the planner crow for new executions
- Review the plan before approving implementation
- After implementation, always send to reviewer
- If reviewer rejects, send to fixer with specific feedback
- Approve only when all acceptance criteria are met
- Escalate to human if stuck after 2 retries on same step
```

### MCP Client in Murder

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def call_crow(crow_url: str, tool_name: str, arguments: dict):
    """Murder calls a crow's MCP tool."""

    async with streamablehttp_client(crow_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Discover tools (optional — can cache)
            tools = await session.list_tools()

            # Call the specific tool
            result = await session.call_tool(tool_name, arguments)

            return result
```

### Test Scenario

**Issue:** "Add a health check endpoint to the API that returns `{"status": "ok", "version": "1.0.0"}`"

**Expected flow:**

1. Execution created → Murder fires
2. Murder: "New execution, needs a plan" → calls Planner crow via MCP
3. Planner returns plan: "Create `health.py` with GET /health endpoint"
4. Murder: "Plan is simple and correct, approve" → assigns Implementer
5. Implementer: creates file, commits, pushes branch
6. Murder: "Code done, send to reviewer" → assigns Reviewer
7. Reviewer: "Looks good, passes criteria"
8. Murder: "All approved" → opens PR → writes final approval

### Implementation

**Reuses:** POC 1 (crow Lambda) + POC 2 (blackboard + streams)
**New:** Murder Lambda with MCP client + LLM judge logic

### Steps

1. Extend CDK stack to include Murder Lambda

   - Permissions: DynamoDB read/write, invoke API GW (crow endpoint)
   - Event source: DynamoDB Streams (with filters from POC 2)
   - Environment: crow MCP endpoint URL, Anthropic API key (from Secrets Manager)

2. Implement Murder Lambda:

   - Event handler: parse DynamoDB Stream event → determine what changed
   - State reader: load full execution state from blackboard
   - Decision engine: call Claude with blackboard state → get decision
   - MCP caller: connect to crow, call tool based on decision
   - State writer: write decision + result to blackboard (with conditional write)

3. Extend crow from POC 1:

   - Add `plan_implementation` tool (Planner skill)
   - Add `review_code` tool (Reviewer skill)
   - Keep `read_file`, `write_file`, `create_pull_request`

4. Run test:
   - Create execution record in DynamoDB (simulating GitHub webhook)
   - Watch Murder + Crows execute autonomously
   - Verify PR is opened with correct code

### Success Criteria

- [ ] Murder discovers crow tools via MCP `tools/list`
- [ ] Murder correctly sequences: plan → approve → implement → review → approve
- [ ] Murder rejects a deliberately bad plan and asks for redo
- [ ] Murder rejects deliberately bad code and sends to fixer
- [ ] Full pipeline completes in < 5 minutes for a simple task
- [ ] PR is opened with working code
- [ ] Total cost < $1 for the simple test case
- [ ] Murder escalates to human after 2 failed retries (writes `escalate` to blackboard)

### Estimated Effort

1-2 days. Murder logic is the core product — worth spending time here.

---

## POC 4 — Full Loop (Integration Demo)

### Goal

End-to-end: real GitHub issue → autonomous pipeline → merged PR. This is the "would you invest?" demo.

### What We're Validating

- Everything works together under real conditions
- Real GitHub issue (not synthetic)
- Real repository (Cawnex itself — dogfooding)
- Real PR that could actually be merged
- Cost and time are reasonable

### Test Case

Use a real Cawnex issue. Candidates:

1. **"Add `/health` endpoint to API"** — simple, good for first run
2. **"Create DynamoDB data access layer for Projects"** — medium complexity
3. **"Implement Cognito JWT validation middleware"** — real feature, tests Murder's judgment

### Architecture

Full stack from POC 1 + 2 + 3, plus:

- GitHub webhook Lambda (receives issue events)
- Actual Cawnex repo as target
- Real Anthropic API key (Eduardo's BYOL key)

```
GitHub Issue Created
    │
    ▼ (webhook)
┌───────────────┐
│ Webhook Lambda │ → creates Execution in DynamoDB
└───────┬───────┘
        │
        ▼ (Stream)
┌───────────────┐         ┌───────────────┐
│ Murder Lambda  │ ──MCP──→│ Planner Crow   │
│                │ ←───────│ (Lambda)       │
│                │         └───────────────┘
│                │
│                │         ┌───────────────┐
│                │ ──MCP──→│ Implementer    │
│                │ ←───────│ Crow (Lambda)  │
│                │         └───────────────┘
│                │
│                │         ┌───────────────┐
│                │ ──MCP──→│ Reviewer Crow  │
│                │ ←───────│ (Lambda)       │
└───────┬───────┘         └───────────────┘
        │
        ▼
   PR Opened → Merged ✅
```

### Steps

1. Deploy full CDK stack combining all POCs
2. Configure GitHub webhook on Cawnex repo → webhook Lambda endpoint
3. Create a labeled issue (e.g., `cawnex-automate` label triggers the pipeline)
4. Watch it run
5. Review the PR
6. Merge if good

### Success Criteria

- [ ] Issue creation triggers full autonomous pipeline
- [ ] Plan is coherent and specific to the issue
- [ ] Code compiles / passes linting
- [ ] PR description references the issue
- [ ] Code review crow catches at least one real issue (or confirms quality)
- [ ] Total time < 10 minutes
- [ ] Total cost < $5
- [ ] PR is mergeable without manual fixes

### Estimated Effort

1 day (mostly integration + debugging edge cases).

---

## Timeline

```
Week 1:
├── Day 1-2: POC 1 (MCP Crow) + POC 2 (Blackboard) — parallel
├── Day 3-4: POC 3 (Murder + Crow integration)
└── Day 5:   POC 4 (Full loop demo)

Week 2:
├── Iterate on Murder judgment quality
├── Add more crow skills
└── Record demo video for landing page
```

**Total estimated cost:** < $20 in AWS + Anthropic API calls for all POCs.

---

## CDK Structure

```
cawnex/
└── infra/
    └── lib/
        ├── poc1-crow-stack.ts      # MCP Crow Lambda + API GW + S3
        ├── poc2-blackboard-stack.ts # DynamoDB + Streams + Murder stub
        ├── poc3-murder-stack.ts     # Murder Lambda + integration
        ├── poc4-full-stack.ts       # Combined + webhook
        └── cawnex-stack.ts          # Full production stack (later)
```

Each POC is a separate CDK stack. Deploy independently, test independently, combine for POC 4.

---

## What This Proves

After POC 4:

| Question                                         | Answer                   |
| ------------------------------------------------ | ------------------------ |
| Can crows run as MCP servers on Lambda?          | POC 1 ✅                 |
| Can DynamoDB drive the event loop without noise? | POC 2 ✅                 |
| Can Murder judge and orchestrate via MCP?        | POC 3 ✅                 |
| Does it produce real, mergeable PRs?             | POC 4 ✅                 |
| Is the cost reasonable?                          | Measured across all POCs |
| Is the latency acceptable?                       | Measured across all POCs |

**What it doesn't prove (yet):**

- Multi-tenant isolation (but architecture supports it)
- iOS app integration (but API is the same)
- User-created skills/crows (but MCP makes it pluggable)
- Scale (but serverless scales by nature)

Those come after the engine is proven.

---

## Risk Register

| Risk                                 | Severity | Mitigation                                               | POC |
| ------------------------------------ | -------- | -------------------------------------------------------- | --- |
| MCP transport doesn't work on Lambda | HIGH     | Test early in POC 1; fallback to direct HTTP if needed   | 1   |
| DynamoDB Streams latency too high    | MEDIUM   | Measure in POC 2; alternative: direct Lambda invoke      | 2   |
| Murder LLM judgment is unreliable    | HIGH     | Iterate on system prompt in POC 3; add structured output | 3   |
| Cold starts kill responsiveness      | MEDIUM   | Provisioned concurrency for Murder; measure in POC 1     | 1,3 |
| Crow Lambda hits 15-min timeout      | LOW      | Simple test tasks won't hit it; Fargate path exists      | 3,4 |
| Cost per execution too high          | MEDIUM   | Budget constraints in CrowTask; measure in all POCs      | 1-4 |
| GitHub API rate limiting             | LOW      | Use installation tokens; cache reads                     | 1,4 |

---

## After POCs → Production

Once all 4 POCs pass, the path to production:

1. **Combine POC stacks** into single `cawnex-stack.ts`
2. **Add Cognito auth** (already designed in ARCHITECTURE.md)
3. **Add multi-tenant partition keys** (already designed)
4. **Add API endpoints** for iOS app (projects, executions, blackboard read)
5. **Connect iOS app** to live API
6. **Add WebSocket** for real-time blackboard updates → iOS
7. **Add more crow skills** (shell, filesystem, testing, documentation)
8. **User-configurable crows** via iOS app (S42 Create Crow screen)
9. **Skills marketplace** (S50 screen)
10. **Billing** (S61 screen)

The POCs become the production core. No throwaway code.
