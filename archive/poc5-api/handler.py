"""
POC 5 — API Lambda

POST /murder — Create execution, return immediately with exec_id
GET  /murder/{id} — Return current blackboard state
"""

import json
import logging
import os
import time
import uuid
import urllib.request

import boto3
from boto3.dynamodb.conditions import Key as DKey

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TABLE_NAME = os.environ.get("BLACKBOARD_TABLE", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

dynamodb = boto3.resource("dynamodb")


def github_api(method: str, path: str, body: dict | None = None) -> dict:
    url = f"https://api.github.com{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"token {GITHUB_TOKEN}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("User-Agent", "cawnex-api")
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def handle_create(body: dict) -> dict:
    """POST /murder — create execution and return immediately."""
    repo = body.get("repo")
    issue_number = body.get("issue_number")

    if not repo or not issue_number:
        return _response(400, {"error": "Missing 'repo' or 'issue_number'"})

    issue_number = int(issue_number)

    # Fetch issue
    try:
        issue = github_api("GET", f"/repos/{repo}/issues/{issue_number}")
    except Exception as e:
        return _response(400, {"error": f"Failed to fetch issue: {e}"})

    issue_title = issue.get("title", "")
    issue_body = issue.get("body", "") or ""

    # Create branch
    execution_id = f"exec_{uuid.uuid4().hex[:8]}"
    branch = f"cawnex/{execution_id}"

    try:
        ref_data = github_api("GET", f"/repos/{repo}/git/ref/heads/main")
        sha = ref_data["object"]["sha"]
        github_api("POST", f"/repos/{repo}/git/refs", {
            "ref": f"refs/heads/{branch}", "sha": sha,
        })
    except Exception as e:
        return _response(500, {"error": f"Failed to create branch: {e}"})

    # Write META to blackboard (this triggers Murder via Stream)
    table = dynamodb.Table(TABLE_NAME)
    table.put_item(Item={
        "PK": f"EXEC#{execution_id}",
        "SK": "META",
        "ts": int(time.time()),
        "status": "pending",
        "repo": repo,
        "branch": branch,
        "issue_number": issue_number,
        "issue_title": issue_title,
        "issue_body": issue_body,
    })

    logger.info("Execution created: %s for %s#%d", execution_id, repo, issue_number)

    # Return immediately
    return _response(200, {
        "execution_id": execution_id,
        "status": "pending",
        "branch": branch,
        "message": "Execution created. Murder will react via Stream.",
    })


def handle_status(execution_id: str) -> dict:
    """GET /murder/{id} — return current blackboard state."""
    table = dynamodb.Table(TABLE_NAME)
    pk = f"EXEC#{execution_id}"

    resp = table.query(KeyConditionExpression=DKey("PK").eq(pk))
    items = resp.get("Items", [])

    if not items:
        return _response(404, {"error": f"Execution {execution_id} not found"})

    meta = next((i for i in items if i["SK"] == "META"), {})
    result = next((i for i in items if i["SK"] == "RESULT"), None)
    steps = []

    for item in sorted(items, key=lambda x: x.get("ts", 0)):
        sk = item["SK"]
        if sk in ("META", "RESULT"):
            continue
        steps.append({
            "sk": sk,
            **{k: v for k, v in item.items() if k not in ("PK", "SK")},
        })

    output = {
        "execution_id": execution_id,
        "status": meta.get("status", "unknown"),
        "repo": meta.get("repo", ""),
        "issue_number": meta.get("issue_number"),
        "issue_title": meta.get("issue_title", ""),
        "branch": meta.get("branch", ""),
        "steps": steps,
    }

    if result:
        output["pr_url"] = result.get("pr_url", "")
        output["pr_number"] = result.get("pr_number")

    if meta.get("error"):
        output["error"] = meta["error"]

    return _response(200, output)


# ─────────────────────────────────────────────
# Lambda Handler (API Gateway v2)
# ─────────────────────────────────────────────


def handler(event, context):
    logger.info("API invoked: %s %s", event.get("requestContext", {}).get("http", {}).get("method"), event.get("rawPath"))

    method = event.get("requestContext", {}).get("http", {}).get("method", "")
    path = event.get("rawPath", "")

    if method == "POST" and path == "/murder":
        try:
            body = event.get("body", "{}")
            if event.get("isBase64Encoded"):
                import base64
                body = base64.b64decode(body).decode()
            return handle_create(json.loads(body))
        except Exception as e:
            logger.exception("Create failed")
            return _response(500, {"error": str(e)})

    elif method == "GET" and path.startswith("/murder/"):
        exec_id = path.split("/murder/", 1)[1].strip("/")
        if not exec_id:
            return _response(400, {"error": "Missing execution_id"})
        return handle_status(exec_id)

    else:
        return _response(404, {"error": "Not found"})


def _response(code: int, body: dict) -> dict:
    return {
        "statusCode": code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }
