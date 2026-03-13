"""
POC 3 — Murder as MCP Client + LLM Judge

Murder receives a GitHub issue, orchestrates crows via MCP,
and judges their output using Claude as the decision engine.

Trigger: POST /murder with { "repo": "owner/repo", "issue_number": 1 }
"""

import json
import logging
import os
import time
import uuid
import urllib.request
import urllib.error
import base64

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Config
CROW_MCP_ENDPOINT = os.environ.get("CROW_MCP_ENDPOINT", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
TABLE_NAME = os.environ.get("BLACKBOARD_TABLE", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
MAX_STEPS = int(os.environ.get("MAX_STEPS", "10"))

dynamodb = boto3.resource("dynamodb")

# ─────────────────────────────────────────────
# MCP Client (minimal — calls crow via HTTP)
# ─────────────────────────────────────────────


def mcp_call(method: str, params: dict, call_id: int = 1) -> dict:
    """Send a JSON-RPC request to the crow MCP endpoint."""
    payload = {
        "jsonrpc": "2.0",
        "id": call_id,
        "method": method,
        "params": params,
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(CROW_MCP_ENDPOINT, data=data, method="POST")
    req.add_header("Content-Type", "application/json")

    logger.info("MCP → %s(%s)", method, json.dumps(params)[:200])

    with urllib.request.urlopen(req, timeout=290) as resp:
        result = json.loads(resp.read().decode())

    if "error" in result:
        logger.error("MCP error: %s", result["error"])
        raise Exception(f"MCP error: {result['error']}")

    return result.get("result", {})


def mcp_discover_tools() -> list:
    """Discover available tools from the crow."""
    result = mcp_call("tools/list", {})
    tools = result.get("tools", [])
    logger.info("Discovered %d tools: %s", len(tools), [t["name"] for t in tools])
    return tools


def mcp_call_tool(tool_name: str, arguments: dict, call_id: int = 1) -> str:
    """Call a specific tool on the crow. Returns the text content."""
    result = mcp_call("tools/call", {"name": tool_name, "arguments": arguments}, call_id)
    contents = result.get("content", [])
    text_parts = [c.get("text", "") for c in contents if c.get("type") == "text"]
    return "\n".join(text_parts)


# ─────────────────────────────────────────────
# GitHub API (for reading issues)
# ─────────────────────────────────────────────


def github_api(method: str, path: str, body: dict | None = None) -> dict:
    url = f"https://api.github.com{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"token {GITHUB_TOKEN}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("User-Agent", "cawnex-murder-poc3")
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def fetch_issue(repo: str, issue_number: int) -> dict:
    """Fetch a GitHub issue."""
    return github_api("GET", f"/repos/{repo}/issues/{issue_number}")


def create_branch(repo: str, branch_name: str, base: str = "main") -> str:
    """Create a branch from base. Returns the new branch ref."""
    # Get base SHA
    ref_data = github_api("GET", f"/repos/{repo}/git/ref/heads/{base}")
    sha = ref_data["object"]["sha"]
    # Create branch
    github_api("POST", f"/repos/{repo}/git/refs", {
        "ref": f"refs/heads/{branch_name}",
        "sha": sha,
    })
    logger.info("Created branch %s from %s (%s)", branch_name, base, sha[:8])
    return sha


# ─────────────────────────────────────────────
# Anthropic API (direct HTTP — no SDK dependency)
# ─────────────────────────────────────────────


def claude_decide(system_prompt: str, user_message: str) -> str:
    """Call Claude and return the text response."""
    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 4096,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_message}],
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=data, method="POST"
    )
    req.add_header("x-api-key", ANTHROPIC_API_KEY)
    req.add_header("anthropic-version", "2023-06-01")
    req.add_header("Content-Type", "application/json")

    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read().decode())

    text_parts = [b["text"] for b in result.get("content", []) if b.get("type") == "text"]
    response_text = "\n".join(text_parts)

    # Log usage
    usage = result.get("usage", {})
    logger.info(
        "Claude: model=%s input=%d output=%d",
        ANTHROPIC_MODEL,
        usage.get("input_tokens", 0),
        usage.get("output_tokens", 0),
    )

    return response_text


# ─────────────────────────────────────────────
# Blackboard (DynamoDB)
# ─────────────────────────────────────────────


def blackboard_write(pk: str, sk: str, data: dict):
    """Write a record to the blackboard."""
    table = dynamodb.Table(TABLE_NAME)
    item = {"PK": pk, "SK": sk, "timestamp": int(time.time()), **data}
    table.put_item(Item=item)
    logger.info("Blackboard write: %s / %s", pk, sk)


def blackboard_read(pk: str, sk: str) -> dict | None:
    """Read a single record from the blackboard."""
    table = dynamodb.Table(TABLE_NAME)
    resp = table.get_item(Key={"PK": pk, "SK": sk})
    return resp.get("Item")


def blackboard_query(pk: str, sk_prefix: str = "") -> list:
    """Query all records for an execution."""
    table = dynamodb.Table(TABLE_NAME)
    from boto3.dynamodb.conditions import Key as DKey

    if sk_prefix:
        resp = table.query(
            KeyConditionExpression=DKey("PK").eq(pk) & DKey("SK").begins_with(sk_prefix)
        )
    else:
        resp = table.query(KeyConditionExpression=DKey("PK").eq(pk))
    return resp.get("Items", [])


# ─────────────────────────────────────────────
# Murder System Prompt
# ─────────────────────────────────────────────

MURDER_SYSTEM_PROMPT = """You are Murder, the orchestrator of Cawnex — an AI-powered software development pipeline.

You are a JUDGE and DISPATCHER. You NEVER write code yourself. You decide what needs to happen and assign crows (AI agents) to do the work.

## Your Role
1. Read the current state (issue, plan, reports from crows)
2. Decide the next action
3. Respond with a JSON decision

## Available Actions

### When no plan exists yet:
Respond with a plan for the crow to execute:
```json
{
  "action": "plan",
  "plan": {
    "summary": "Brief description of what needs to be done",
    "steps": [
      {"description": "Step description", "files": ["file1.py", "file2.py"]}
    ]
  }
}
```

### When plan exists, ready to implement:
```json
{
  "action": "implement",
  "instructions": "Detailed instructions for the implementer crow. Be specific about what code to write, where, and how."
}
```

### When reviewing implementation results:
```json
{
  "action": "approve",
  "reason": "Why this is good enough to merge"
}
```

OR:

```json
{
  "action": "reject",
  "reason": "What's wrong",
  "feedback": "Specific instructions for what to fix"
}
```

OR:

```json
{
  "action": "create_pr",
  "title": "PR title",
  "body": "PR description referencing the issue"
}
```

## Rules
- Always start with "plan" for new issues
- After planning, move to "implement"
- After implementation, review the changes and either approve or reject
- If approved, create a PR
- Be specific in instructions — crows are literal executors
- Keep it simple. One clear action per decision.
- Respond with ONLY the JSON. No markdown, no explanation outside the JSON.
"""

# ─────────────────────────────────────────────
# Murder Orchestration Loop
# ─────────────────────────────────────────────


def run_murder(repo: str, issue_number: int) -> dict:
    """Main Murder orchestration loop."""

    execution_id = f"exec_{uuid.uuid4().hex[:8]}"
    bb_pk = f"EXEC#{execution_id}"

    logger.info("=== MURDER START === execution=%s repo=%s issue=#%d", execution_id, repo, issue_number)

    # 1. Fetch the issue
    issue = fetch_issue(repo, issue_number)
    issue_title = issue.get("title", "")
    issue_body = issue.get("body", "") or ""
    logger.info("Issue #%d: %s", issue_number, issue_title)

    # 2. Discover crow tools
    crow_tools = mcp_discover_tools()
    tools_summary = "\n".join(
        [f"- {t['name']}: {t['description']}" for t in crow_tools]
    )

    # 3. Create execution record
    blackboard_write(bb_pk, "META", {
        "status": "started",
        "repo": repo,
        "issue_number": issue_number,
        "issue_title": issue_title,
    })

    # 4. Create working branch
    branch_name = f"cawnex/{execution_id}"
    try:
        create_branch(repo, branch_name)
    except Exception as e:
        logger.error("Failed to create branch: %s", e)
        blackboard_write(bb_pk, "META", {"status": "failed", "error": str(e)})
        return {"status": "failed", "error": f"Branch creation failed: {e}"}

    # 5. Orchestration loop
    step = 0
    context_messages = []
    total_cost = {"input_tokens": 0, "output_tokens": 0}
    final_result = {"status": "unknown"}

    while step < MAX_STEPS:
        step += 1
        logger.info("=== STEP %d ===", step)

        # Build context for Murder
        blackboard_state = blackboard_query(bb_pk)
        state_summary = json.dumps(
            [{"SK": item["SK"], **{k: v for k, v in item.items() if k not in ("PK", "SK")}}
             for item in blackboard_state],
            indent=2, default=str,
        )

        user_message = f"""## Issue
**#{issue_number}: {issue_title}**
{issue_body}

## Repository
{repo} (branch: {branch_name})

## Available Crow Tools
{tools_summary}

## Current Blackboard State
{state_summary}

## What should we do next?"""

        # Murder decides
        decision_raw = claude_decide(MURDER_SYSTEM_PROMPT, user_message)
        logger.info("Murder decision (raw): %s", decision_raw[:500])

        # Parse decision
        try:
            # Strip markdown code fences if present
            clean = decision_raw.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
                if clean.endswith("```"):
                    clean = clean[:-3]
                clean = clean.strip()
            decision = json.loads(clean)
        except json.JSONDecodeError:
            logger.error("Failed to parse Murder decision as JSON: %s", decision_raw[:200])
            blackboard_write(bb_pk, f"STEP#{step:02d}#DECISION", {
                "error": "Invalid JSON from Murder",
                "raw": decision_raw[:500],
            })
            final_result = {"status": "failed", "error": "Murder produced invalid JSON"}
            break

        action = decision.get("action", "")
        logger.info("Murder action: %s", action)

        # Write decision to blackboard
        blackboard_write(bb_pk, f"STEP#{step:02d}#DECISION", {
            "action": action,
            "decision": decision,
        })

        # Execute the decision
        if action == "plan":
            plan = decision.get("plan", {})
            blackboard_write(bb_pk, "PLAN", {"plan": plan, "status": "approved"})
            logger.info("Plan recorded: %s", plan.get("summary", ""))

        elif action == "implement":
            instructions = decision.get("instructions", "")
            # Read relevant files first
            files_context = []
            plan_item = blackboard_read(bb_pk, "PLAN")
            if plan_item and plan_item.get("plan", {}).get("steps"):
                for plan_step in plan_item["plan"]["steps"]:
                    for f in plan_step.get("files", []):
                        try:
                            content = mcp_call_tool("read_file", {
                                "repo": repo, "path": f, "ref": "main"
                            }, call_id=step * 10)
                            files_context.append(f"### {f}\n```\n{content[:3000]}\n```")
                        except Exception:
                            files_context.append(f"### {f}\n(file does not exist yet)")

            # Ask Claude to generate the code
            code_prompt = f"""You are an expert software developer. Write the code changes needed.

## Task
{instructions}

## Existing Files
{chr(10).join(files_context) if files_context else "(no existing files)"}

## Output Format
Respond with a JSON array of file changes:
```json
[
  {{"path": "path/to/file.py", "content": "full file content here"}}
]
```
Respond with ONLY the JSON array. No markdown, no explanation."""

            code_response = claude_decide(
                "You are a code generation assistant. Output ONLY valid JSON.",
                code_prompt,
            )

            try:
                clean = code_response.strip()
                if clean.startswith("```"):
                    clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
                    if clean.endswith("```"):
                        clean = clean[:-3]
                    clean = clean.strip()
                file_changes = json.loads(clean)
            except json.JSONDecodeError:
                logger.error("Failed to parse code response: %s", code_response[:200])
                blackboard_write(bb_pk, f"STEP#{step:02d}#REPORT", {
                    "outcome": "error",
                    "error": "Code generation returned invalid JSON",
                })
                continue

            # Write files via crow MCP
            files_written = []
            for change in file_changes:
                fpath = change.get("path", "")
                fcontent = change.get("content", "")
                try:
                    result = mcp_call_tool("write_file", {
                        "repo": repo,
                        "path": fpath,
                        "content": fcontent,
                        "branch": branch_name,
                        "message": f"feat: {fpath} — {issue_title}",
                    }, call_id=step * 10 + 1)
                    files_written.append(fpath)
                    logger.info("Wrote file: %s → %s", fpath, result[:100])
                except Exception as e:
                    logger.error("Failed to write %s: %s", fpath, e)

            blackboard_write(bb_pk, f"STEP#{step:02d}#REPORT", {
                "outcome": "completed",
                "files_written": files_written,
                "branch": branch_name,
            })

        elif action == "approve":
            # Murder approves — create PR
            logger.info("Murder approved: %s", decision.get("reason", ""))
            blackboard_write(bb_pk, f"STEP#{step:02d}#REPORT", {
                "outcome": "approved",
                "reason": decision.get("reason", ""),
            })
            # Auto-proceed to create_pr
            try:
                pr_result = mcp_call_tool("create_pull_request", {
                    "repo": repo,
                    "title": f"[Cawnex] {issue_title}",
                    "body": f"Closes #{issue_number}\n\n{decision.get('reason', '')}",
                    "head": branch_name,
                    "base": "main",
                }, call_id=step * 10 + 2)
                pr_data = json.loads(pr_result)
                logger.info("PR created: %s", pr_data.get("pr_url", ""))
                blackboard_write(bb_pk, "RESULT", {
                    "status": "completed",
                    "pr_url": pr_data.get("pr_url", ""),
                    "pr_number": pr_data.get("pr_number"),
                })
                final_result = {
                    "status": "completed",
                    "pr_url": pr_data.get("pr_url", ""),
                    "pr_number": pr_data.get("pr_number"),
                    "execution_id": execution_id,
                    "steps": step,
                }
            except Exception as e:
                logger.error("PR creation failed: %s", e)
                final_result = {"status": "failed", "error": f"PR creation failed: {e}"}
            break

        elif action == "create_pr":
            try:
                pr_result = mcp_call_tool("create_pull_request", {
                    "repo": repo,
                    "title": decision.get("title", f"[Cawnex] {issue_title}"),
                    "body": decision.get("body", f"Closes #{issue_number}"),
                    "head": branch_name,
                    "base": "main",
                }, call_id=step * 10 + 2)
                pr_data = json.loads(pr_result)
                logger.info("PR created: %s", pr_data.get("pr_url", ""))
                blackboard_write(bb_pk, "RESULT", {
                    "status": "completed",
                    "pr_url": pr_data.get("pr_url", ""),
                    "pr_number": pr_data.get("pr_number"),
                })
                final_result = {
                    "status": "completed",
                    "pr_url": pr_data.get("pr_url", ""),
                    "pr_number": pr_data.get("pr_number"),
                    "execution_id": execution_id,
                    "steps": step,
                }
            except Exception as e:
                logger.error("PR creation failed: %s", e)
                final_result = {"status": "failed", "error": f"PR creation failed: {e}"}
            break

        elif action == "reject":
            logger.info("Murder rejected: %s", decision.get("reason", ""))
            blackboard_write(bb_pk, f"STEP#{step:02d}#REPORT", {
                "outcome": "rejected",
                "reason": decision.get("reason", ""),
                "feedback": decision.get("feedback", ""),
            })
            # Loop continues — Murder will see the rejection and decide next

        else:
            logger.warning("Unknown action: %s", action)
            blackboard_write(bb_pk, f"STEP#{step:02d}#REPORT", {
                "outcome": "error",
                "error": f"Unknown action: {action}",
            })
            final_result = {"status": "failed", "error": f"Unknown action: {action}"}
            break

    # Update final status
    if final_result.get("status") != "completed":
        if step >= MAX_STEPS:
            final_result = {"status": "failed", "error": f"Max steps ({MAX_STEPS}) exceeded"}
        blackboard_write(bb_pk, "META", {
            "status": final_result.get("status", "failed"),
            "error": final_result.get("error", ""),
            "steps": step,
        })

    logger.info("=== MURDER END === execution=%s result=%s", execution_id, final_result)
    return {"execution_id": execution_id, **final_result}


# ─────────────────────────────────────────────
# Lambda Handler
# ─────────────────────────────────────────────


def handler(event, context):
    """
    POST /murder
    Body: { "repo": "owner/repo", "issue_number": 1 }
    """
    logger.info("Murder Lambda invoked — requestId=%s", context.aws_request_id)

    try:
        body = event.get("body", "{}")
        if event.get("isBase64Encoded"):
            body = base64.b64decode(body).decode("utf-8")
        request = json.loads(body)
    except Exception as e:
        return _response(400, {"error": f"Invalid JSON: {e}"})

    repo = request.get("repo")
    issue_number = request.get("issue_number")

    if not repo or not issue_number:
        return _response(400, {"error": "Missing 'repo' or 'issue_number'"})

    try:
        result = run_murder(repo, int(issue_number))
        return _response(200, result)
    except Exception as e:
        logger.exception("Murder failed")
        return _response(500, {"error": str(e)})


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }
