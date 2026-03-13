"""
POC 1 — MCP Crow on Lambda
Minimal MCP server implementing Streamable HTTP transport.
Exposes 3 tools: read_file, write_file, create_pull_request.

This is a stub. Tools return placeholder responses.
Real GitHub API integration comes during POC testing.
"""

import json
import logging
import os
import uuid

logger = logging.getLogger()
logger.setLevel(logging.INFO)

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

# ─────────────────────────────────────────────
# MCP Server Info
# ─────────────────────────────────────────────

SERVER_INFO = {
    "name": "cawnex-crow-poc1",
    "version": "0.1.0",
}

SERVER_CAPABILITIES = {
    "tools": {"listChanged": False},
}

# ─────────────────────────────────────────────
# MCP JSON-RPC Handlers
# ─────────────────────────────────────────────


def handle_initialize(params: dict) -> dict:
    """Handle MCP initialize request."""
    logger.info("MCP initialize — client: %s", params.get("clientInfo", {}))
    return {
        "protocolVersion": "2025-03-26",
        "capabilities": SERVER_CAPABILITIES,
        "serverInfo": SERVER_INFO,
    }


def handle_tools_list(params: dict) -> dict:
    """Handle MCP tools/list request."""
    logger.info("MCP tools/list")
    return {"tools": TOOLS}


def handle_tools_call(params: dict) -> dict:
    """Handle MCP tools/call request — stub implementation."""
    tool_name = params.get("name", "")
    arguments = params.get("arguments", {})

    logger.info("MCP tools/call — tool=%s args=%s", tool_name, json.dumps(arguments))

    # Stub responses — real implementation during POC testing
    if tool_name == "read_file":
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"[STUB] Contents of {arguments.get('path', '?')} from {arguments.get('repo', '?')}",
                }
            ]
        }

    elif tool_name == "write_file":
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "status": "stub",
                            "message": f"[STUB] Would write to {arguments.get('path', '?')} on branch {arguments.get('branch', '?')}",
                            "repo": arguments.get("repo", "?"),
                            "commit_sha": "stub_" + uuid.uuid4().hex[:8],
                        }
                    ),
                }
            ]
        }

    elif tool_name == "create_pull_request":
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "status": "stub",
                            "message": f"[STUB] Would create PR: {arguments.get('title', '?')}",
                            "pr_number": 999,
                            "pr_url": f"https://github.com/{arguments.get('repo', '?')}/pull/999",
                        }
                    ),
                }
            ]
        }

    else:
        return {
            "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}],
            "isError": True,
        }


# JSON-RPC method router
MCP_HANDLERS = {
    "initialize": handle_initialize,
    "tools/list": handle_tools_list,
    "tools/call": handle_tools_call,
}


# ─────────────────────────────────────────────
# Lambda Handler — Streamable HTTP Transport
# ─────────────────────────────────────────────


def handler(event, context):
    """
    AWS Lambda handler for MCP Streamable HTTP transport.
    Receives JSON-RPC requests via API Gateway v2.
    """

    logger.info("Lambda invoked — requestId=%s", context.aws_request_id)

    # Parse request
    try:
        body = event.get("body", "{}")
        if event.get("isBase64Encoded"):
            import base64

            body = base64.b64decode(body).decode("utf-8")
        request = json.loads(body)
    except (json.JSONDecodeError, Exception) as e:
        logger.error("Failed to parse request body: %s", e)
        return _response(400, {"error": "Invalid JSON"})

    # Handle single JSON-RPC request
    jsonrpc_id = request.get("id")
    method = request.get("method", "")
    params = request.get("params", {})

    logger.info("JSON-RPC method=%s id=%s", method, jsonrpc_id)

    handler_fn = MCP_HANDLERS.get(method)

    if handler_fn is None:
        logger.warning("Unknown method: %s", method)
        return _response(
            200,
            {
                "jsonrpc": "2.0",
                "id": jsonrpc_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            },
        )

    try:
        result = handler_fn(params)
        return _response(
            200,
            {
                "jsonrpc": "2.0",
                "id": jsonrpc_id,
                "result": result,
            },
        )
    except Exception as e:
        logger.exception("Handler error for method=%s", method)
        return _response(
            200,
            {
                "jsonrpc": "2.0",
                "id": jsonrpc_id,
                "error": {"code": -32603, "message": str(e)},
            },
        )


def _response(status_code: int, body: dict) -> dict:
    """Build API Gateway v2 response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
        },
        "body": json.dumps(body),
    }
