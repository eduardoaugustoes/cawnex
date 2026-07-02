"""
POC 1 — MCP Crow on Lambda
MCP server with real GitHub API integration.
Exposes 3 tools: read_file, write_file, create_pull_request.
"""

import json
import logging
import os
import base64
import urllib.request
import urllib.error

logger = logging.getLogger()
logger.setLevel(logging.INFO)

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

# ─────────────────────────────────────────────
# GitHub API helpers
# ─────────────────────────────────────────────


def github_api(method: str, path: str, body: dict | None = None) -> dict:
    """Call GitHub API. Returns parsed JSON."""
    url = f"https://api.github.com{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"token {GITHUB_TOKEN}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("User-Agent", "cawnex-crow-poc1")
    if data:
        req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        logger.error("GitHub API error: %s %s → %s %s", method, path, e.code, error_body)
        raise


# ─────────────────────────────────────────────
# Tool Implementations
# ─────────────────────────────────────────────


def tool_read_file(args: dict) -> dict:
    """Read a file from a GitHub repository."""
    repo = args["repo"]
    path = args["path"]
    ref = args.get("ref", "main")

    logger.info("read_file: %s/%s@%s", repo, path, ref)

    data = github_api("GET", f"/repos/{repo}/contents/{path}?ref={ref}")

    if data.get("encoding") == "base64" and data.get("content"):
        content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
    else:
        content = data.get("content", "")

    return {
        "content": [{"type": "text", "text": content}],
    }


def tool_write_file(args: dict) -> dict:
    """Create or update a file in a GitHub repository."""
    repo = args["repo"]
    path = args["path"]
    content = args["content"]
    branch = args["branch"]
    message = args["message"]

    logger.info("write_file: %s/%s on %s", repo, path, branch)

    # Check if file exists (to get SHA for updates)
    sha = None
    try:
        existing = github_api("GET", f"/repos/{repo}/contents/{path}?ref={branch}")
        sha = existing.get("sha")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise

    body = {
        "message": message,
        "content": base64.b64encode(content.encode()).decode(),
        "branch": branch,
    }
    if sha:
        body["sha"] = sha

    result = github_api("PUT", f"/repos/{repo}/contents/{path}", body)

    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps({
                    "status": "ok",
                    "commit_sha": result.get("commit", {}).get("sha", ""),
                    "path": path,
                    "branch": branch,
                }),
            }
        ],
    }


def tool_create_pull_request(args: dict) -> dict:
    """Open a pull request."""
    repo = args["repo"]
    title = args["title"]
    body_text = args.get("body", "")
    head = args["head"]
    base_branch = args.get("base", "main")

    logger.info("create_pull_request: %s %s → %s", repo, head, base_branch)

    result = github_api("POST", f"/repos/{repo}/pulls", {
        "title": title,
        "body": body_text,
        "head": head,
        "base": base_branch,
    })

    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps({
                    "status": "ok",
                    "pr_number": result.get("number"),
                    "pr_url": result.get("html_url", ""),
                    "head": head,
                    "base": base_branch,
                }),
            }
        ],
    }


# ─────────────────────────────────────────────
# MCP Tool Definitions
# ─────────────────────────────────────────────

TOOLS = [
    {
        "name": "read_file",
        "description": "Read contents of a file from the repository",
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "owner/repo"},
                "path": {"type": "string", "description": "File path"},
                "ref": {"type": "string", "description": "Branch or commit SHA", "default": "main"},
            },
            "required": ["repo", "path"],
        },
    },
    {
        "name": "write_file",
        "description": "Create or update a file in the repository",
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "owner/repo"},
                "path": {"type": "string", "description": "File path"},
                "content": {"type": "string", "description": "File content"},
                "branch": {"type": "string", "description": "Target branch"},
                "message": {"type": "string", "description": "Commit message"},
            },
            "required": ["repo", "path", "content", "branch", "message"],
        },
    },
    {
        "name": "create_pull_request",
        "description": "Open a pull request",
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "owner/repo"},
                "title": {"type": "string"},
                "body": {"type": "string"},
                "head": {"type": "string", "description": "Source branch"},
                "base": {"type": "string", "description": "Target branch", "default": "main"},
            },
            "required": ["repo", "title", "head"],
        },
    },
]

TOOL_DISPATCH = {
    "read_file": tool_read_file,
    "write_file": tool_write_file,
    "create_pull_request": tool_create_pull_request,
}

SERVER_INFO = {"name": "cawnex-crow-poc1", "version": "0.2.0"}
SERVER_CAPABILITIES = {"tools": {"listChanged": False}}

# ─────────────────────────────────────────────
# MCP JSON-RPC Handlers
# ─────────────────────────────────────────────


def handle_initialize(params: dict) -> dict:
    logger.info("MCP initialize — client: %s", params.get("clientInfo", {}))
    return {
        "protocolVersion": "2025-03-26",
        "capabilities": SERVER_CAPABILITIES,
        "serverInfo": SERVER_INFO,
    }


def handle_tools_list(params: dict) -> dict:
    logger.info("MCP tools/list")
    return {"tools": TOOLS}


def handle_tools_call(params: dict) -> dict:
    tool_name = params.get("name", "")
    arguments = params.get("arguments", {})
    logger.info("MCP tools/call — tool=%s", tool_name)

    dispatch = TOOL_DISPATCH.get(tool_name)
    if dispatch is None:
        return {
            "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}],
            "isError": True,
        }

    if not GITHUB_TOKEN and tool_name != "read_file":
        return {
            "content": [{"type": "text", "text": "GITHUB_TOKEN not configured"}],
            "isError": True,
        }

    try:
        return dispatch(arguments)
    except Exception as e:
        logger.exception("Tool error: %s", tool_name)
        return {
            "content": [{"type": "text", "text": f"Error: {str(e)}"}],
            "isError": True,
        }


MCP_HANDLERS = {
    "initialize": handle_initialize,
    "tools/list": handle_tools_list,
    "tools/call": handle_tools_call,
}

# ─────────────────────────────────────────────
# Lambda Handler
# ─────────────────────────────────────────────


def handler(event, context):
    logger.info("Lambda invoked — requestId=%s", context.aws_request_id)

    try:
        body = event.get("body", "{}")
        if event.get("isBase64Encoded"):
            body = base64.b64decode(body).decode("utf-8")
        request = json.loads(body)
    except (json.JSONDecodeError, Exception) as e:
        logger.error("Failed to parse request body: %s", e)
        return _response(400, {"error": "Invalid JSON"})

    jsonrpc_id = request.get("id")
    method = request.get("method", "")
    params = request.get("params", {})

    logger.info("JSON-RPC method=%s id=%s", method, jsonrpc_id)

    handler_fn = MCP_HANDLERS.get(method)
    if handler_fn is None:
        return _response(200, {
            "jsonrpc": "2.0", "id": jsonrpc_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        })

    try:
        result = handler_fn(params)
        return _response(200, {"jsonrpc": "2.0", "id": jsonrpc_id, "result": result})
    except Exception as e:
        logger.exception("Handler error for method=%s", method)
        return _response(200, {
            "jsonrpc": "2.0", "id": jsonrpc_id,
            "error": {"code": -32603, "message": str(e)},
        })


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
