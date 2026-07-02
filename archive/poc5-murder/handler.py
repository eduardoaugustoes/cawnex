"""
POC 5 -- Murder as Stream-Triggered State Machine

Murder is triggered by DynamoDB Streams when a REPORT is written.
It reads the blackboard, judges via Claude, writes the next TASK or final RESULT.
Each invocation is <5s. Never blocks. Never calls crows directly.

Authentication: Uses Claude OAuth token (ANTHROPIC_AUTH_TOKEN env var, injected by VPS refresher).
"""

import json
import logging
import os
import time

import anthropic
import boto3
from boto3.dynamodb.conditions import Key as DKey

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
TABLE_NAME = os.environ.get("BLACKBOARD_TABLE", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

ANTHROPIC_AUTH_TOKEN = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")

dynamodb = boto3.resource("dynamodb")


def _get_claude_client() -> anthropic.Anthropic:
    """Get Anthropic client with OAuth token."""
    if not ANTHROPIC_AUTH_TOKEN:
        raise RuntimeError("No auth: set ANTHROPIC_AUTH_TOKEN")

    return anthropic.Anthropic(
        api_key=None,
        auth_token=ANTHROPIC_AUTH_TOKEN,
        default_headers={"anthropic-beta": "oauth-2025-04-20"},
    )


# ─────────────────────────────────────────────
# Claude SDK (lightweight judgment calls only)
# ─────────────────────────────────────────────


def claude_judge(system_prompt: str, user_message: str) -> str:
    """Quick Claude call for Murder's judgment. Should be <3s."""
    client = _get_claude_client()
    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=2048,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    text = "\n".join(
        b.text for b in response.content if b.type == "text"
    )
    logger.info(
        "Claude judge: in=%d out=%d",
        response.usage.input_tokens,
        response.usage.output_tokens,
    )
    return text


# ─────────────────────────────────────────────
# Blackboard helpers
# ─────────────────────────────────────────────


def bb_write(pk: str, sk: str, data: dict):
    table = dynamodb.Table(TABLE_NAME)
    table.put_item(Item={"PK": pk, "SK": sk, "ts": int(time.time()), **data})
    logger.info("BB write: %s / %s", pk, sk)


def bb_read(pk: str, sk: str) -> dict | None:
    table = dynamodb.Table(TABLE_NAME)
    resp = table.get_item(Key={"PK": pk, "SK": sk})
    return resp.get("Item")


def bb_query(pk: str, sk_prefix: str = "") -> list:
    table = dynamodb.Table(TABLE_NAME)
    if sk_prefix:
        resp = table.query(
            KeyConditionExpression=DKey("PK").eq(pk) & DKey("SK").begins_with(sk_prefix)
        )
    else:
        resp = table.query(KeyConditionExpression=DKey("PK").eq(pk))
    return resp.get("Items", [])


def bb_update_meta(pk: str, updates: dict):
    table = dynamodb.Table(TABLE_NAME)
    expr_parts = []
    values = {}
    names = {}
    for k, v in updates.items():
        safe = k.replace("-", "_")
        expr_parts.append(f"#{safe} = :{safe}")
        values[f":{safe}"] = v
        names[f"#{safe}"] = k
    table.update_item(
        Key={"PK": pk, "SK": "META"},
        UpdateExpression="SET " + ", ".join(expr_parts),
        ExpressionAttributeValues=values,
        ExpressionAttributeNames=names,
    )


# ─────────────────────────────────────────────
# GitHub helpers
# ─────────────────────────────────────────────


def github_api(method: str, path: str, body: dict | None = None) -> dict:
    url = f"https://api.github.com{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"token {GITHUB_TOKEN}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("User-Agent", "cawnex-murder")
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def create_pr(repo: str, title: str, body: str, head: str, base: str = "main") -> dict:
    return github_api("POST", f"/repos/{repo}/pulls", {
        "title": title, "body": body, "head": head, "base": base,
    })


# ─────────────────────────────────────────────
# Murder System Prompt
# ─────────────────────────────────────────────

MURDER_SYSTEM = """You are Murder, the orchestrator. You JUDGE and DISPATCH. You never write code.

Read the blackboard state and decide the next action. Respond with ONLY JSON.

Actions:

1. First time (no PLAN yet):
{"action":"assign","crow":"planner","instructions":"What to plan based on the issue"}

2. Plan report received:
{"action":"assign","crow":"implementer","instructions":"Detailed implementation instructions based on the plan"}

3. Implementation report received:
{"action":"assign","crow":"reviewer","instructions":"Review these changes against the issue requirements"}

4. Review passed:
{"action":"approve","pr_title":"PR title","pr_body":"PR body referencing the issue"}

5. Review failed:
{"action":"assign","crow":"fixer","instructions":"Fix these specific issues: ..."}

6. Something is wrong after 2+ retries:
{"action":"escalate","reason":"Why this needs human attention"}

Rules:
- One action per decision
- Be specific in instructions
- ONLY output JSON, nothing else"""


# ─────────────────────────────────────────────
# Murder State Machine
# ─────────────────────────────────────────────


def murder_react(execution_pk: str):
    """Murder reacts to a blackboard change. One decision, <5s."""

    start = time.time()
    logger.info("=== MURDER REACT === %s", execution_pk)

    # Read full blackboard
    items = bb_query(execution_pk)
    meta = next((i for i in items if i["SK"] == "META"), None)
    if not meta:
        logger.error("No META found for %s", execution_pk)
        return

    status = meta.get("status", "")
    if status in ("completed", "failed", "escalated"):
        logger.info("Execution already %s, skipping", status)
        return

    repo = meta.get("repo", "")
    issue_title = meta.get("issue_title", "")
    issue_body = meta.get("issue_body", "")
    issue_number = meta.get("issue_number", 0)
    branch = meta.get("branch", "")

    # Build blackboard summary for Claude
    bb_summary = []
    for item in sorted(items, key=lambda x: x.get("ts", 0)):
        sk = item["SK"]
        if sk == "META":
            continue
        entry = {k: v for k, v in item.items() if k not in ("PK", "ts")}
        bb_summary.append(entry)

    # Count steps for step numbering
    tasks = [i for i in items if "#TASK" in i.get("SK", "")]
    next_step = len(tasks) + 1

    user_msg = f"""## Issue #{issue_number}: {issue_title}
{issue_body}

## Repository: {repo} (branch: {branch})

## Blackboard
{json.dumps(bb_summary, indent=2, default=str)}

What should we do next?"""

    # Judge
    decision_raw = claude_judge(MURDER_SYSTEM, user_msg)
    logger.info("Murder decision: %s", decision_raw[:300])

    # Parse
    try:
        clean = decision_raw.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
            if clean.endswith("```"):
                clean = clean[:-3]
            clean = clean.strip()
        decision = json.loads(clean)
    except json.JSONDecodeError:
        logger.error("Invalid JSON from Murder: %s", decision_raw[:200])
        bb_write(execution_pk, f"STEP#{next_step:02d}#DECISION", {
            "action": "error", "raw": decision_raw[:500],
        })
        return

    action = decision.get("action", "")
    logger.info("Action: %s (step %d)", action, next_step)

    # Write decision
    bb_write(execution_pk, f"STEP#{next_step:02d}#DECISION", decision)

    if action == "assign":
        # Write a TASK for the worker to pick up
        bb_write(execution_pk, f"STEP#{next_step:02d}#TASK", {
            "status": "pending",
            "crow": decision.get("crow", "worker"),
            "instructions": decision.get("instructions", ""),
            "repo": repo,
            "branch": branch,
            "issue_title": issue_title,
            "issue_number": issue_number,
        })
        bb_update_meta(execution_pk, {"status": "waiting_for_crow"})

    elif action == "approve":
        # Create PR
        try:
            pr = create_pr(
                repo,
                decision.get("pr_title", f"[Cawnex] {issue_title}"),
                decision.get("pr_body", f"Closes #{issue_number}"),
                branch,
            )
            bb_write(execution_pk, "RESULT", {
                "status": "completed",
                "pr_url": pr.get("html_url", ""),
                "pr_number": pr.get("number"),
            })
            bb_update_meta(execution_pk, {
                "status": "completed",
                "pr_url": pr.get("html_url", ""),
                "pr_number": str(pr.get("number", "")),
            })
            logger.info("PR created: %s", pr.get("html_url", ""))
        except Exception as e:
            logger.error("PR creation failed: %s", e)
            bb_update_meta(execution_pk, {"status": "failed", "error": str(e)})

    elif action == "escalate":
        bb_update_meta(execution_pk, {
            "status": "escalated",
            "escalate_reason": decision.get("reason", ""),
        })
        logger.info("Escalated: %s", decision.get("reason", ""))

    else:
        logger.warning("Unknown action: %s", action)

    elapsed = time.time() - start
    logger.info("Murder react done in %.1fs", elapsed)


# ─────────────────────────────────────────────
# Lambda Handler (DynamoDB Stream)
# ─────────────────────────────────────────────


def handler(event, context):
    """Triggered by DynamoDB Streams on blackboard writes."""

    logger.info("Stream event: %d records", len(event.get("Records", [])))

    for record in event.get("Records", []):
        if record.get("eventName") not in ("INSERT", "MODIFY"):
            continue

        # Get the new image
        new_image = record.get("dynamodb", {}).get("NewImage", {})
        pk = new_image.get("PK", {}).get("S", "")
        sk = new_image.get("SK", {}).get("S", "")

        logger.info("Stream: %s / %s", pk, sk)

        # Only react to:
        # - META (new execution created)
        # - REPORT (crow finished a task)
        if not pk.startswith("EXEC#"):
            continue

        if sk == "META":
            status = new_image.get("status", {}).get("S", "")
            if status == "pending":
                logger.info("New execution, Murder reacting")
                murder_react(pk)
        elif "#REPORT" in sk:
            logger.info("Crow report received, Murder reacting")
            murder_react(pk)
        else:
            logger.debug("Ignoring %s", sk)
