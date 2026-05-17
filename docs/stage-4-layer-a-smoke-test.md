# Stage 4 Layer A — Smoke Test Procedure

Runbook for verifying Layer A end-to-end against a dev deployment. Layer A is
"shippable" only after every step here passes. If any step fails, do NOT mark
the layer done — open an issue and iterate.

## Prerequisites

- `cdk deploy -c stage=dev --require-approval never` completed successfully
- AWS CLI configured with credentials for the dev account
- A dev project + tenant exists in DynamoDB
- `GITHUB_TOKEN` set as a Fargate secret so Council advisors can read PR metadata

## Step 1 — Prepare a controlled synthetic wave

In a dev project, create 2 trivial MVIs whose PRs cannot conflict:

- MVI A: edit `README.md` (add a line)
- MVI B: edit `CHANGELOG.md` (add a line)

Manually advance the wave through `executing → review` by writing `status=ready_to_ship`
on both MVI rows. This bypasses the planner/implementer for the smoke test.

## Step 2 — Watch the Murder reactor logs

```bash
aws logs tail /aws/lambda/cawnex-murder-dev --follow
```

Expected log line: `integrator_dispatched` with `wave_id` and `pr_count=2`.

## Step 3 — Watch the Worker Fargate logs

```bash
aws logs tail /ecs/cawnex-worker-dev --follow
```

Expected:

- `crow_claimed` for the integrator-task
- Worktrees created (`add_pr_worktree` succeeds for both PRs)
- Integration merge: `merge_status=ok`
- Checks: any of `ok`/`skipped` per check (test envs often skip missing tools)
- `INTEGRATION#{wave_id}` row written with `overall=ready_for_council`

## Step 4 — Watch the Council Fargate logs

```bash
aws logs tail /ecs/cawnex-council-dev --follow
```

Expected:

- Service scaled up from desiredCount=0 to 1 after the COUNCIL# row was written
- 6 advisor invocations happening in parallel (interleaved log lines)
- Each advisor making 3–8 tool calls within 180 s
- All 6 returning a vote (either `submit_vote` or `abstain` due to cap)

## Step 5 — Inspect the CouncilSession in DDB

```bash
SESSION_SK=$(aws dynamodb query \
  --table-name cawnex-dev \
  --key-condition-expression "PK = :pk AND begins_with(SK, :sk)" \
  --expression-attribute-values '{":pk":{"S":"P#<projectId>"},":sk":{"S":"COUNCIL#"}}' \
  --query 'Items[-1].SK.S' --output text)

aws dynamodb get-item --table-name cawnex-dev \
  --key "{\"PK\":{\"S\":\"P#<projectId>\"},\"SK\":{\"S\":\"$SESSION_SK\"}}" \
  --query 'Item'
```

Expected:

- `status=completed`
- `decision` present (action/reasoning/confidence)
- `rounds[0].votes` has 6 entries
- Each vote carries `investigation_trace` and (where applicable) `cited_evidence`

## Step 6 — Verify no council_pipeline_error events

```bash
aws dynamodb query --table-name cawnex-events-dev \
  --key-condition-expression "PK = :pk AND begins_with(SK, :sk)" \
  --filter-expression "event_type = :et" \
  --expression-attribute-values '{
    ":pk":{"S":"P#<projectId>"},
    ":sk":{"S":"E#"},
    ":et":{"S":"council_pipeline_error"}
  }'
```

Expected: empty `Items` array. Any error rows mean the loud-failure path fired
and you must investigate before declaring Layer A shippable.

## Step 7 — Verify total session cost lands in budget

Pull the CouncilSession row from step 5. Compute:

```
total_cost = sum across all advisor cost records:
  tokens_in  * $1 / 1_000_000
+ tokens_out * $5 / 1_000_000
```

Target: ~$0.21 per session, accept ±25 % → range $0.16 – $0.26. Costs above
$0.30 indicate the call-cap (15) is being hit too often; below $0.10 indicates
advisors are submitting votes without investigation.

## Step 8 — Verify wave reached under_human_review

```bash
aws dynamodb get-item --table-name cawnex-dev \
  --key '{"PK":{"S":"P#<projectId>"},"SK":{"S":"S#<waveId>"}}' \
  --query 'Item.status.S'
```

Expected: `"under_human_review"`.

## Step 9 — Mark Layer A done

If steps 1–8 all passed:

```bash
git commit --allow-empty -m "chore(stage-4): Layer A smoke test passed on dev"
git tag stage-4-layer-a-ga
```

If any step failed, do NOT tag. Open issues for what failed and iterate.

## Rollback (if needed)

```bash
git revert <last-stage-4-commit>
cd infra && npx cdk deploy -c stage=dev --require-approval never
```

The Council Fargate service can be scaled to 0 immediately without rolling back
the code:

```bash
aws ecs update-service \
  --cluster cawnex-dev \
  --service cawnex-council-dev \
  --desired-count 0
```
