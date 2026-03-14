# POC 6 — Worker Lambda + EFS + Worktrees

> Prove the worker can clone, analyze, modify code, and create PRs entirely on AWS.

---

## Goal

Move the local worker to AWS Lambda with persistent repository storage (EFS) and git worktrees for parallel execution isolation. Centralize all logs in CloudWatch. Eliminate VPS dependency.

---

## Architecture

```
DynamoDB Stream (TASK status=pending)
    │
    ▼
┌─────────────────────────────┐
│  Worker Lambda (Docker)      │
│  Python 3.12 + git + gh CLI │
│  VPC (private subnet)        │
│  EFS mount: /mnt/repos       │
│                               │
│  1. Check /mnt/repos/{repo}  │
│  2. Clone or fetch            │
│  3. Create worktree           │
│  4. Claude SDK analyzes code  │
│  5. Apply changes             │
│  6. git commit + push         │
│  7. gh pr create              │
│  8. Write REPORT to DDB      │
│  9. Cleanup worktree          │
└──────────┬────────────────────┘
           │
    ┌──────┴──────┐
    │    EFS       │
    │ /mnt/repos/  │
    │  {owner}/    │
    │   {repo}/    │  ← persistent clone (1x)
    │  worktrees/  │
    │   {exec_id}/ │  ← temporary per execution
    └─────────────┘
```

### Full System (POC 5 + POC 6)

```
User submits issue
    │
    ▼
┌──────────────┐
│  API Lambda   │  (existing, no VPC)
│  POST /murder │
└──────┬───────┘
       │ writes META + triggers
       ▼
┌──────────────┐     DynamoDB Stream     ┌──────────────────┐
│  DynamoDB     │ ──────────────────────→ │  Murder Lambda    │
│  Blackboard   │                         │  (no VPC, zip)    │
│               │ ←────────────────────── │  Judges + assigns │
└──────────────┘     writes DECISION+TASK └──────────────────┘
       │
       │ DynamoDB Stream (TASK pending)
       ▼
┌──────────────────┐     ┌─────┐
│  Worker Lambda    │────→│ EFS │
│  (VPC, Docker)    │     └─────┘
│  Clone/worktree   │
│  Claude SDK       │
│  git push + PR    │
│  Writes REPORT    │
└──────────────────┘
```

---

## Infrastructure (CDK)

### New Resources

| Resource                | Config                                    | Cost            |
| ----------------------- | ----------------------------------------- | --------------- |
| VPC                     | 2 AZs, 2 private subnets, 1 public subnet | $0              |
| NAT Instance            | t4g.nano (public subnet)                  | ~$3/mth         |
| EFS                     | General Purpose, bursting                 | ~$0.30/GB-month |
| EFS Access Point        | `/mnt/repos`, uid/gid 1000                | $0              |
| VPC Endpoint (DynamoDB) | Gateway type                              | $0              |
| Worker Lambda           | Docker, 1GB RAM, 15min timeout, VPC       | Pay per use     |
| ECR                     | Docker image registry                     | ~$0.10/GB-month |
| Security Groups         | EFS SG + Lambda SG + NAT SG               | $0              |

### Estimated Monthly Cost (idle)

- NAT Instance: ~$3
- EFS (1GB): ~$0.30
- ECR: ~$0.10
- **Total: ~$3.50/mth**

### Existing Resources (from POC 5)

- DynamoDB `cawnex-poc5-blackboard-dev` (or new table)
- Murder Lambda `cawnex-poc5-murder-dev`
- API Lambda `cawnex-poc5-api-dev`

---

## Docker Image

### Dockerfile

```dockerfile
FROM public.ecr.aws/lambda/python:3.12

# Install git + gh CLI
RUN dnf install -y git tar gzip && \
    curl -fsSL https://github.com/cli/cli/releases/download/v2.62.0/gh_2.62.0_linux_amd64.tar.gz | \
    tar xz -C /usr/local/bin --strip-components=2 gh_2.62.0_linux_amd64/bin/gh && \
    dnf clean all

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Handler
COPY handler.py .

CMD ["handler.lambda_handler"]
```

### requirements.txt

```
anthropic>=0.84.0
boto3>=1.35.0
```

### Build in CI/CD

```yaml
- name: Build and push Docker image
  run: |
    aws ecr get-login-password --region us-east-1 | \
      docker login --username AWS --password-stdin ${{ env.ECR_URI }}
    docker build -t cawnex-worker lambdas/poc6-worker/
    docker tag cawnex-worker:latest ${{ env.ECR_URI }}:latest
    docker push ${{ env.ECR_URI }}:latest
    aws lambda update-function-code \
      --function-name cawnex-poc6-worker-dev \
      --image-uri ${{ env.ECR_URI }}:latest
```

---

## Worker Handler Logic

```python
def lambda_handler(event, context):
    """Triggered by DynamoDB Stream when a TASK is written."""
    for record in event["Records"]:
        if record["eventName"] not in ("INSERT", "MODIFY"):
            continue

        new_image = deserialize(record["dynamodb"]["NewImage"])
        sk = new_image.get("SK", "")

        # Only react to TASK records with status=pending
        if "#TASK" not in sk or new_image.get("status") != "pending":
            continue

        pk = new_image["PK"]
        execution_id = pk.replace("EXEC#", "")

        # Conditional update: pending → running (prevent double pickup)
        if not mark_task_running(pk, sk):
            continue

        # Execute
        repo = new_image["repo"]  # "owner/repo"
        branch = new_image["branch"]
        instructions = new_image["instructions"]
        crow = new_image.get("crow", "worker")

        try:
            report = execute_task(
                execution_id=execution_id,
                repo=repo,
                branch=branch,
                instructions=instructions,
                crow=crow,
            )
            write_report(pk, sk.replace("#TASK", "#REPORT"), report)
        except Exception as e:
            write_report(pk, sk.replace("#TASK", "#REPORT"), {
                "outcome": "error",
                "summary": str(e),
            })


def execute_task(execution_id, repo, branch, instructions, crow):
    """Clone/fetch repo, create worktree, run Claude, commit+push, create PR."""

    repo_dir = f"/mnt/repos/{repo}"
    worktree_dir = f"/mnt/repos/worktrees/{execution_id}"

    # 1. Clone or fetch
    if not os.path.exists(repo_dir):
        run(f"git clone https://x-access-token:{GITHUB_TOKEN}@github.com/{repo}.git {repo_dir}")
    else:
        run(f"git -C {repo_dir} fetch origin")

    # 2. Create worktree
    run(f"git -C {repo_dir} worktree add {worktree_dir} -b {branch} origin/main")

    try:
        # 3. Analyze code with Claude
        code_context = gather_code_context(worktree_dir)
        prompt = build_prompt(crow, instructions, code_context)

        client = get_claude_client()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=f"You are a {crow} crow. Analyze the codebase and produce changes.",
            messages=[{"role": "user", "content": prompt}],
        )

        # 4. Parse and apply changes
        changes = parse_changes(response)
        apply_changes(worktree_dir, changes)

        # 5. Commit + push
        run(f"git -C {worktree_dir} add -A")
        run(f"git -C {worktree_dir} commit -m '{changes.commit_message}'")
        run(f"git -C {worktree_dir} push origin {branch}")

        # 6. Create PR (only on final step or if implementer)
        pr_url = None
        if crow in ("implementer", "worker"):
            pr_url = create_pr(repo, branch, changes)

        return {
            "outcome": "completed",
            "summary": changes.summary,
            "files_changed": changes.files,
            "pr_url": pr_url,
            "tokens_in": response.usage.input_tokens,
            "tokens_out": response.usage.output_tokens,
        }
    finally:
        # 7. Cleanup worktree
        run(f"git -C {repo_dir} worktree remove {worktree_dir} --force")
```

---

## DynamoDB Stream Filter

Worker Lambda reacts to:

- `SK` contains `#TASK`
- `status` = `pending`

CDK event source mapping with filter:

```typescript
{
  filters: [
    FilterCriteria.filter({
      eventName: FilterRule.isEqual("INSERT"),
      dynamodb: {
        NewImage: {
          SK: { S: FilterRule.exists() },
          status: { S: FilterRule.isEqual("pending") },
        },
      },
    }),
  ],
}
```

Note: Murder Lambda keeps its existing filter (reacts to `#REPORT` records).

---

## Logging (CloudWatch)

All Lambda logs go to CloudWatch automatically:

- `/aws/lambda/cawnex-poc6-worker-dev`
- `/aws/lambda/cawnex-poc5-murder-dev` (existing)
- `/aws/lambda/cawnex-poc5-api-dev` (existing)

### Structured log format (worker)

```python
import json, logging

logger = logging.getLogger()

def log_event(execution_id, component, event, **kwargs):
    logger.info(json.dumps({
        "execution_id": execution_id,
        "component": component,
        "event": event,
        **kwargs,
    }))

# Usage:
log_event("exec_001", "worker", "task_started", crow="planner")
log_event("exec_001", "worker", "claude_call", tokens_in=337, tokens_out=4096, cost=0.06, duration_ms=53000)
log_event("exec_001", "worker", "git_push", branch="cawnex/exec_001", files=3)
log_event("exec_001", "worker", "pr_created", url="https://github.com/...")
log_event("exec_001", "worker", "task_completed", duration_ms=65000)
```

### Query examples

```bash
# All logs for an execution
aws logs filter-log-events \
  --log-group-name /aws/lambda/cawnex-poc6-worker-dev \
  --filter-pattern '{ $.execution_id = "exec_001" }'

# All errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/cawnex-poc6-worker-dev \
  --filter-pattern '{ $.event = "error" }'

# CloudWatch Insights (cross log groups)
fields @timestamp, execution_id, component, event, @message
| filter execution_id = "exec_001"
| sort @timestamp
```

---

## CI/CD Workflow

`.github/workflows/poc6-deploy.yml`

```yaml
name: POC 6 Deploy
on:
  workflow_dispatch:
    inputs:
      action:
        type: choice
        options: [deploy, destroy]

jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: actions/checkout@v4

      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN }}
          aws-region: us-east-1

      - uses: actions/setup-node@v4
        with:
          node-version: 22

      - name: Install CDK
        run: cd infra && npm ci

      - name: CDK Deploy
        if: inputs.action == 'deploy'
        run: |
          cd infra
          npx cdk deploy --context stack=poc6 --require-approval never

      - name: Build and push Docker image
        if: inputs.action == 'deploy'
        run: |
          ECR_URI=$(aws ecr describe-repositories --repository-names cawnex-poc6-worker --query 'repositories[0].repositoryUri' --output text)
          aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $ECR_URI
          docker build -t cawnex-worker lambdas/poc6-worker/
          docker tag cawnex-worker:latest $ECR_URI:latest
          docker push $ECR_URI:latest
          aws lambda update-function-code \
            --function-name cawnex-poc6-worker-dev \
            --image-uri $ECR_URI:latest

      - name: Inject secrets
        if: inputs.action == 'deploy'
        run: |
          aws lambda update-function-configuration \
            --function-name cawnex-poc6-worker-dev \
            --environment "Variables={
              GITHUB_TOKEN=${{ secrets.GH_PAT }},
              ANTHROPIC_AUTH_TOKEN=${{ secrets.ANTHROPIC_AUTH_TOKEN }},
              BLACKBOARD_TABLE=cawnex-poc5-blackboard-dev
            }"

      - name: CDK Destroy
        if: inputs.action == 'destroy'
        run: |
          cd infra
          npx cdk destroy --context stack=poc6 --force
```

---

## Test Plan

### Setup

1. Clean blackboard (delete old executions)
2. Create simple test issue: "Add GET /health endpoint that returns `{"status":"ok","version":"1.0.0"}`"
3. Deploy POC 6 stack

### Execute

```bash
curl -s -X POST https://hmhwi06xx1.execute-api.us-east-1.amazonaws.com/murder \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "eduardoaugustoes/cawnex",
    "issue_number": <N>,
    "workflow": ["planner", "implementer", "reviewer"]
  }'
```

### Expected Flow

1. API creates execution → DynamoDB `META(pending)`
2. Murder Lambda → assigns planner → writes `STEP#01#TASK(pending)`
3. **Worker Lambda** picks up → clones repo to EFS → worktree → Claude plans → writes `STEP#01#REPORT`
4. Murder → reviews plan → assigns implementer → `STEP#02#TASK(pending)`
5. **Worker Lambda** picks up → reuses repo from EFS → new worktree → Claude implements → git push → `STEP#02#REPORT`
6. Murder → assigns reviewer → `STEP#03#TASK(pending)`
7. **Worker Lambda** picks up → worktree → Claude reviews → `STEP#03#REPORT`
8. Murder → approves → creates PR → `RESULT(completed)`

### Success Criteria

- [ ] Repo cloned once to EFS, reused on subsequent steps
- [ ] Each step uses isolated worktree
- [ ] Claude analyzes real code from worktree
- [ ] Git commit + push works from Lambda
- [ ] PR created with actual code changes
- [ ] Worktrees cleaned up after each step
- [ ] Only 1 branch created (not 20+)
- [ ] All logs visible in CloudWatch
- [ ] Structured JSON logs with execution_id filter
- [ ] End-to-end < 5 minutes for simple task
- [ ] Total cost < $0.50 (infra + LLM)

---

## Files to Create

```
infra/lib/poc6-worker-stack.ts     # CDK stack (VPC, NAT, EFS, Lambda, ECR)
lambdas/poc6-worker/Dockerfile     # Docker image
lambdas/poc6-worker/handler.py     # Worker handler
lambdas/poc6-worker/requirements.txt
.github/workflows/poc6-deploy.yml  # CI/CD
```

---

## Risk Register

| Risk                          | Impact                          | Mitigation                             |
| ----------------------------- | ------------------------------- | -------------------------------------- |
| Lambda cold start with VPC    | +2-5s latency                   | Provisioned concurrency (later)        |
| EFS latency vs /tmp           | Slower file I/O                 | Acceptable for POC                     |
| NAT Instance failure          | Worker offline                  | Monitor, upgrade to NAT GW later       |
| Git binary size in Docker     | Larger image, slower cold start | Use minimal git install                |
| OAuth token expiry (8h)       | Worker stops working            | Manual refresh for POC, automate later |
| 15-min Lambda timeout         | Large repos/complex tasks fail  | Monitor, Fargate migration path exists |
| Concurrent worktree conflicts | Git lock errors                 | Worktree isolation prevents this       |
| EFS throughput limits         | Slow clone for large repos      | Bursting mode handles spikes           |
