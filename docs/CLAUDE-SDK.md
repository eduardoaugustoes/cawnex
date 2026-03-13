# Claude SDK — Authentication & Usage Guide

> Internal reference for Cawnex's integration with the Anthropic API.
> Last updated: 2026-03-13

---

## Table of Contents

1. [Authentication Methods](#authentication-methods)
2. [OAuth Flow (PKCE)](#oauth-flow-pkce)
3. [SDK Configuration](#sdk-configuration)
4. [API Request/Response](#api-requestresponse)
5. [Tool Use (Agent Loop)](#tool-use-agent-loop)
6. [Cawnex Architecture](#cawnex-architecture)
7. [Gotchas & Lessons Learned](#gotchas--lessons-learned)

---

## Authentication Methods

The Anthropic API (`api.anthropic.com`) supports two authentication mechanisms:

### 1. API Key (`x-api-key` header)

```
x-api-key: sk-ant-api03-...
```

- Created at [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys)
- Billed per token (Sonnet: $3/M input, $15/M output)
- Works everywhere (Lambda, VPS, local, CI)
- Prefix: `sk-ant-api03-*`

### 2. OAuth Token (`Authorization: Bearer` header)

```
Authorization: Bearer sk-ant-oat01-...
anthropic-beta: oauth-2025-04-20
```

- Obtained via OAuth PKCE flow against `claude.ai`
- Uses your Claude subscription (Pro/Max) — **$0 cost**
- Requires the beta header `anthropic-beta: oauth-2025-04-20`
- Access token expires in **8 hours**
- Refresh token rotates on each use (one-time use)
- Prefix: `sk-ant-oat01-*` (access), `sk-ant-ort01-*` (refresh)

> ⚠️ **Without the beta header**, the API returns:
> `"OAuth authentication is currently not supported."`

---

## OAuth Flow (PKCE)

Cawnex uses the same OAuth flow as Claude Code CLI. It's a standard Authorization Code flow with PKCE (Proof Key for Code Exchange).

### Endpoints

| Purpose | URL |
|---------|-----|
| Authorize | `https://claude.ai/oauth/authorize` |
| Token | `https://console.anthropic.com/v1/oauth/token` |
| Redirect | `https://console.anthropic.com/oauth/code/callback` |

> ⚠️ `platform.claude.com/v1/oauth/token` returns "Invalid request format".
> The correct token endpoint is `console.anthropic.com/v1/oauth/token`.

### Client

| Field | Value |
|-------|-------|
| Client ID | `9d1c250a-e61b-44d9-88ed-5944d1962f5e` |
| Type | Public client (no client_secret) |
| PKCE | Required (S256) |

This is Claude Code's public client ID. No registration needed.

### Scopes

| Scope | Purpose |
|-------|---------|
| `user:inference` | Make API calls using subscription |
| `user:profile` | Read user profile info |
| `org:create_api_key` | Create API keys (not needed for inference) |

For Cawnex, only `user:inference` and `user:profile` are needed.

### Step-by-Step Flow

#### 1. Generate PKCE values

```python
import secrets, hashlib, base64

code_verifier = secrets.token_urlsafe(32)
code_challenge = base64.urlsafe_b64encode(
    hashlib.sha256(code_verifier.encode()).digest()
).rstrip(b'=').decode()
```

#### 2. Build authorize URL

```
https://claude.ai/oauth/authorize?
  code=true
  &client_id=9d1c250a-e61b-44d9-88ed-5944d1962f5e
  &response_type=code
  &redirect_uri=https://console.anthropic.com/oauth/code/callback
  &scope=user:inference user:profile
  &code_challenge={code_challenge}
  &code_challenge_method=S256
  &state={code_verifier}
```

> **Trick**: Use `code_verifier` as `state`. The state is echoed back,
> so you get the verifier back in the callback without storing it.

#### 3. User authorizes

User opens URL in browser → logs in → authorizes → gets redirected.
The callback page shows a code in format: `{auth_code}#{state}`

#### 4. Exchange code for tokens

```bash
curl -s -X POST https://console.anthropic.com/v1/oauth/token \
  -H "Content-Type: application/json" \
  -d '{
    "grant_type": "authorization_code",
    "client_id": "9d1c250a-e61b-44d9-88ed-5944d1962f5e",
    "code": "<auth_code>",
    "state": "<state>",
    "redirect_uri": "https://console.anthropic.com/oauth/code/callback",
    "code_verifier": "<code_verifier>"
  }'
```

Response:
```json
{
  "token_type": "Bearer",
  "access_token": "sk-ant-oat01-...",
  "expires_in": 28800,
  "refresh_token": "sk-ant-ort01-...",
  "scope": "user:inference user:profile",
  "organization": {
    "uuid": "...",
    "name": "user@example.com's Organization"
  },
  "account": {
    "uuid": "...",
    "email_address": "user@example.com"
  }
}
```

#### 5. Refresh token

```bash
curl -s -X POST https://console.anthropic.com/v1/oauth/token \
  -H "Content-Type: application/json" \
  -d '{
    "grant_type": "refresh_token",
    "client_id": "9d1c250a-e61b-44d9-88ed-5944d1962f5e",
    "refresh_token": "sk-ant-ort01-..."
  }'
```

> ⚠️ **Refresh tokens are one-time use.** Each refresh returns a new
> `refresh_token`. The old one is immediately invalidated.

> ⚠️ **Cloudflare blocks** the token endpoint from some IPs (AWS Lambda,
> GitHub Actions runners). The VPS and local machines work fine.

---

## SDK Configuration

### Python SDK

Install:
```bash
pip install anthropic
```

The SDK supports two auth params:

| Param | Header | Env Var |
|-------|--------|---------|
| `api_key` | `X-Api-Key: ...` | `ANTHROPIC_API_KEY` |
| `auth_token` | `Authorization: Bearer ...` | `ANTHROPIC_AUTH_TOKEN` |

### Using API Key

```python
import anthropic

client = anthropic.Anthropic(api_key="sk-ant-api03-...")
# or just set ANTHROPIC_API_KEY env var
client = anthropic.Anthropic()
```

### Using OAuth Token

```python
import anthropic

client = anthropic.Anthropic(
    api_key=None,                # ← CRITICAL: must be None
    auth_token="sk-ant-oat01-...",
    default_headers={"anthropic-beta": "oauth-2025-04-20"},
)
```

> ⚠️ **Dual header bug**: If `ANTHROPIC_API_KEY` env var is set, the SDK
> sends BOTH `X-Api-Key` and `Authorization: Bearer` headers. The API
> rejects the `X-Api-Key` with an OAuth token value (`invalid x-api-key`).
>
> **Fix**: Either set `api_key=None` explicitly, or use `ANTHROPIC_AUTH_TOKEN`
> env var instead of `ANTHROPIC_API_KEY`.

### Auto-detection pattern

```python
import os
import anthropic

token = os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY", "")

if token.startswith("sk-ant-oat"):
    client = anthropic.Anthropic(
        api_key=None,
        auth_token=token,
        default_headers={"anthropic-beta": "oauth-2025-04-20"},
    )
else:
    client = anthropic.Anthropic(api_key=token)
```

### Available SDKs

| Language | Package | Docs |
|----------|---------|------|
| Python | `pip install anthropic` | [platform.claude.com/docs/en/api/sdks/python](https://platform.claude.com/docs/en/api/sdks/python) |
| TypeScript | `npm install @anthropic-ai/sdk` | [/docs/en/api/sdks/typescript](https://platform.claude.com/docs/en/api/sdks/typescript) |
| Java | `com.anthropic:anthropic-java` | [/docs/en/api/sdks/java](https://platform.claude.com/docs/en/api/sdks/java) |
| Go | `github.com/anthropics/anthropic-sdk-go` | [/docs/en/api/sdks/go](https://platform.claude.com/docs/en/api/sdks/go) |
| Ruby | `bundler add anthropic` | [/docs/en/api/sdks/ruby](https://platform.claude.com/docs/en/api/sdks/ruby) |
| C# | `dotnet add package Anthropic` | [/docs/en/api/sdks/csharp](https://platform.claude.com/docs/en/api/sdks/csharp) |
| PHP | `composer require anthropic-ai/sdk` | [/docs/en/api/sdks/php](https://platform.claude.com/docs/en/api/sdks/php) |

Source: [github.com/anthropics/anthropic-sdk-python](https://github.com/anthropics/anthropic-sdk-python)

---

## API Request/Response

### Basic message

```python
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    system="You are a helpful assistant.",
    messages=[
        {"role": "user", "content": "Hello, Claude"}
    ],
)

print(response.content[0].text)
print(f"Tokens: {response.usage.input_tokens} in, {response.usage.output_tokens} out")
```

### Streaming

```python
with client.messages.stream(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    messages=[{"role": "user", "content": "Hello"}],
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)
```

### Models

| Model | Input | Output | Context |
|-------|-------|--------|---------|
| `claude-opus-4-6` | $15/M | $75/M | 200K |
| `claude-sonnet-4-20250514` | $3/M | $15/M | 200K |
| `claude-haiku-3-5-20241022` | $0.80/M | $4/M | 200K |

With OAuth subscription: all models at **$0**.

---

## Tool Use (Agent Loop)

To make Claude actually DO things (read files, write code, run commands),
you need to provide tools and implement an agent loop.

### Define tools

```python
tools = [
    {
        "name": "read_file",
        "description": "Read the contents of a file",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file",
        "description": "Write content to a file",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path"},
                "content": {"type": "string", "description": "File content"}
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "run_command",
        "description": "Run a shell command",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command"}
            },
            "required": ["command"]
        }
    }
]
```

### Agent loop

```python
messages = [{"role": "user", "content": task_prompt}]

while True:
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        tools=tools,
        messages=messages,
    )

    # Collect assistant response
    messages.append({"role": "assistant", "content": response.content})

    # Check if Claude wants to use tools
    tool_uses = [b for b in response.content if b.type == "tool_use"]

    if not tool_uses:
        # No tool calls — Claude is done
        break

    # Execute each tool and collect results
    tool_results = []
    for tool_use in tool_uses:
        result = execute_tool(tool_use.name, tool_use.input)
        tool_results.append({
            "type": "tool_result",
            "tool_use_id": tool_use.id,
            "content": result,
        })

    messages.append({"role": "user", "content": tool_results})

def execute_tool(name: str, params: dict) -> str:
    if name == "read_file":
        return open(params["path"]).read()
    elif name == "write_file":
        with open(params["path"], "w") as f:
            f.write(params["content"])
        return f"Written {len(params['content'])} bytes to {params['path']}"
    elif name == "run_command":
        result = subprocess.run(params["command"], shell=True, capture_output=True, text=True)
        return result.stdout + result.stderr
```

### Without tools (current Cawnex POC)

```python
# Single-shot: Claude generates text but can't execute anything
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    messages=[{"role": "user", "content": prompt}],
    # No tools= parameter → Claude can only respond with text
)
```

This is why the POC worker "imagines" code instead of writing it.

---

## Cawnex Architecture

### How Murder and Workers use the SDK

```
┌─────────────────────────────────────────────────┐
│                  GitHub Issue                    │
└──────────────────────┬──────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────┐
│  POST /murder  →  API Lambda                    │
│  Creates blackboard entry (DynamoDB)            │
└──────────────────────┬──────────────────────────┘
                       ▼ (DynamoDB Stream)
┌─────────────────────────────────────────────────┐
│  Murder Lambda (judge)                          │
│  SDK: auth_token + beta header ($0)             │
│  Single-shot call: reads blackboard → decides   │
│  Writes DECISION + TASK to blackboard           │
└──────────────────────┬──────────────────────────┘
                       ▼ (polling)
┌─────────────────────────────────────────────────┐
│  Local Worker (crow)                            │
│  SDK: auth_token + beta header ($0)             │
│  TODAY: single-shot (text only, no tools)       │
│  NEXT:  agent loop with read/write/shell tools  │
│  Writes REPORT to blackboard                    │
└──────────────────────┬──────────────────────────┘
                       ▼ (DynamoDB Stream)
┌─────────────────────────────────────────────────┐
│  Murder Lambda (judge again)                    │
│  Reads report → assign next crow OR approve     │
│  On approve → creates PR via GitHub API         │
└─────────────────────────────────────────────────┘
```

### Environment Variables

| Var | Where | Purpose |
|-----|-------|---------|
| `ANTHROPIC_AUTH_TOKEN` | Lambda + Worker | OAuth access token ($0) |
| `ANTHROPIC_API_KEY` | Fallback | API key (costs money) |
| `ANTHROPIC_REFRESH_TOKEN` | CI/scripts | For refreshing access tokens |
| `GITHUB_TOKEN` | Lambda + Worker | GitHub API access |

### Token Lifecycle

```
User clicks authorize URL
        │
        ▼
  Auth code (60s TTL)
        │
        ▼ POST /oauth/token
  Access token (8h TTL) + Refresh token (one-time)
        │
        ├──► Lambda (ANTHROPIC_AUTH_TOKEN env var)
        ├──► Worker (ANTHROPIC_AUTH_TOKEN env var)
        │
        │  ... 8 hours later ...
        │
        ▼ POST /oauth/token (refresh)
  New access token + New refresh token
        │
        ▼ Update Lambda env var
```

---

## Gotchas & Lessons Learned

### 1. Beta header is mandatory for OAuth
Without `anthropic-beta: oauth-2025-04-20`, the API returns:
`"OAuth authentication is currently not supported."`

### 2. Dual header bug
If both `api_key` and `auth_token` are set, the SDK sends both headers.
The API rejects the `X-Api-Key` header with an OAuth token value.
Always set `api_key=None` when using `auth_token`.

### 3. `ANTHROPIC_API_KEY` env var auto-read
The SDK reads `ANTHROPIC_API_KEY` from env automatically. If this var
contains an OAuth token, it goes into `api_key` (wrong header).
Use `ANTHROPIC_AUTH_TOKEN` instead — the SDK reads it into `auth_token`.

### 4. Refresh tokens are one-time use
Each refresh invalidates the previous token. Don't refresh from multiple
places (VPS + CI + Lambda) — they'll invalidate each other.

### 5. Cloudflare blocks token endpoint from cloud IPs
`console.anthropic.com/v1/oauth/token` is blocked by Cloudflare from
AWS Lambda and GitHub Actions runners. Refresh from a non-cloud IP (VPS, local).

### 6. Token endpoint is NOT on `claude.ai`
- ❌ `claude.ai/oauth/token` → 404
- ❌ `platform.claude.com/v1/oauth/token` → "Invalid request format"
- ✅ `console.anthropic.com/v1/oauth/token` → works

### 7. `state` parameter required in token exchange
The token exchange body must include `state` (echoed from authorize callback).
Missing it causes "Invalid request format".

### 8. Lambda warm starts cache old code
After updating Lambda code, existing warm instances may still run the old code.
Force a cold start by updating an env var (e.g., `COLD=<timestamp>`).

---

## References

- [Python SDK docs](https://platform.claude.com/docs/en/api/sdks/python)
- [Python SDK source](https://github.com/anthropics/anthropic-sdk-python)
- [API overview](https://platform.claude.com/docs/en/api/overview)
- [Client SDKs list](https://platform.claude.com/docs/en/api/client-sdks)
- [SDK client source (_client.py)](https://github.com/anthropics/anthropic-sdk-python/blob/main/src/anthropic/_client.py)
- [Tool use docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview)
