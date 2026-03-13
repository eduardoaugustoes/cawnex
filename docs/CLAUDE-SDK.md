# Claude API / SDK Reference

> Reference for integrating Claude into Cawnex — backend (Python), mobile (Swift), and Lambda.

---

## Authentication

### Three Auth Modes

| Mode | Token Format | Cost | Header |
|------|-------------|------|--------|
| API Key | `sk-ant-api03-...` | Pay per token | `X-Api-Key: <key>` |
| OAuth (subscription) | `sk-ant-oat01-...` | $0 (included in plan) | `Authorization: Bearer <token>` + `anthropic-beta: oauth-2025-04-20` |
| OAuth Refresh | `sk-ant-ort01-...` | N/A (exchange only) | Used to get new access token |

### OAuth PKCE Flow (for mobile app)

```
1. Generate code_verifier (43-128 chars, [A-Za-z0-9-._~])
2. Generate code_challenge = base64url(sha256(code_verifier))
3. Open browser:
   GET https://claude.ai/oauth/authorize
     ?client_id=9d1c250a-e61b-44d9-88ed-5944d1962f5e
     &response_type=code
     &redirect_uri=https://console.anthropic.com/oauth/code/callback
     &scope=user:inference user:profile
     &code_challenge={code_challenge}
     &code_challenge_method=S256
     &state={code_verifier}

4. User approves → redirected to callback with ?code=...&state=...
5. Exchange code for tokens:
   POST https://console.anthropic.com/v1/oauth/token
   Content-Type: application/json
   {
     "grant_type": "authorization_code",
     "client_id": "9d1c250a-e61b-44d9-88ed-5944d1962f5e",
     "code": "<auth_code>",
     "redirect_uri": "https://console.anthropic.com/oauth/code/callback",
     "code_verifier": "<code_verifier>"
   }
```

### Token Exchange Response

```json
{
  "token_type": "Bearer",
  "access_token": "sk-ant-oat01-lYxV_KPy_HHqs...",
  "expires_in": 28800,
  "refresh_token": "sk-ant-ort01-YrGUQ8bkFAf-...",
  "scope": "user:inference user:profile",
  "organization": {
    "uuid": "1dfabe8f-f7af-439b-8655-c1e03676bccf",
    "name": "user@example.com's Organization"
  },
  "account": {
    "uuid": "8a8c93ff-b806-498e-8f89-599ea0a647cc",
    "email_address": "user@example.com"
  }
}
```

### Token Refresh

⚠️ **Refresh tokens are single-use** — each refresh rotates the token. Store the new one immediately.

```
POST https://console.anthropic.com/v1/oauth/token
Content-Type: application/json
{
  "grant_type": "refresh_token",
  "client_id": "9d1c250a-e61b-44d9-88ed-5944d1962f5e",
  "refresh_token": "<refresh_token>"
}
```

Response: same structure as token exchange (new access_token + new refresh_token).

### Access Token Expiry

- **Lifetime**: 8 hours (28800 seconds)
- **Refresh buffer**: refresh when < 5 min remaining
- **Refresh blocked from**: AWS Lambda IPs, GitHub Actions (Cloudflare 403)
- **Refresh works from**: User devices, VPS with residential IP

---

## Messages API

### Endpoint

```
POST https://api.anthropic.com/v1/messages
```

### Required Headers

| Header | Value |
|--------|-------|
| `Content-Type` | `application/json` |
| `anthropic-version` | `2023-06-01` |
| `X-Api-Key` | `sk-ant-api03-...` (API key mode) |
| `Authorization` | `Bearer sk-ant-oat01-...` (OAuth mode) |
| `anthropic-beta` | `oauth-2025-04-20` (OAuth mode only) |

⚠️ **Never send both `X-Api-Key` and `Authorization`** — the API rejects the request if `X-Api-Key` contains an OAuth token format.

### Request Body

```json
{
  "model": "claude-sonnet-4-20250514",
  "max_tokens": 4096,
  "system": "You are a helpful assistant.",
  "messages": [
    {
      "role": "user",
      "content": "Hello, Claude!"
    }
  ],
  "temperature": 1.0,
  "top_p": 0.999,
  "stop_sequences": []
}
```

### Response Body

```json
{
  "id": "msg_01XFDUDYJgAACzvnptvVoYEL",
  "type": "message",
  "role": "assistant",
  "model": "claude-sonnet-4-20250514",
  "content": [
    {
      "type": "text",
      "text": "Hello! How can I help you today?"
    }
  ],
  "stop_reason": "end_turn",
  "stop_sequence": null,
  "usage": {
    "input_tokens": 337,
    "output_tokens": 4096,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 0
  }
}
```

### Content Block Types

```json
// Text block
{ "type": "text", "text": "..." }

// Tool use block (when using tools)
{ "type": "tool_use", "id": "toolu_01...", "name": "tool_name", "input": { ... } }

// Tool result (in user messages)
{ "type": "tool_result", "tool_use_id": "toolu_01...", "content": "..." }
```

### Models & Pricing

| Model | Input ($/1M) | Output ($/1M) | Max Output |
|-------|-------------|---------------|------------|
| `claude-sonnet-4-20250514` | $3.00 | $15.00 | 8,192 |
| `claude-opus-4-0-20250514` | $15.00 | $75.00 | 8,192 |
| `claude-haiku-3-5-20241022` | $0.80 | $4.00 | 8,192 |

### Cost Calculation

```python
cost = (usage.input_tokens * input_price + usage.output_tokens * output_price) / 1_000_000

# Example: Sonnet, 337 in / 4096 out
cost = (337 * 3 + 4096 * 15) / 1_000_000  # = $0.0625
```

---

## Streaming

### Request

Add `"stream": true` to request body.

### Response (Server-Sent Events)

```
event: message_start
data: {"type":"message_start","message":{"id":"msg_01...","type":"message","role":"assistant","content":[],"model":"claude-sonnet-4-20250514","stop_reason":null,"usage":{"input_tokens":337,"output_tokens":0}}}

event: content_block_start
data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello"}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"! How"}}

event: content_block_stop
data: {"type":"content_block_stop","index":0}

event: message_delta
data: {"type":"message_delta","delta":{"stop_reason":"end_turn","stop_sequence":null},"usage":{"output_tokens":42}}

event: message_stop
data: {"type":"message_stop"}
```

### Stream Event Types

| Event | Description |
|-------|-------------|
| `message_start` | Start of message, includes model/usage |
| `content_block_start` | New content block beginning |
| `content_block_delta` | Incremental text/tool content |
| `content_block_stop` | Content block complete |
| `message_delta` | Final stop_reason + output token count |
| `message_stop` | Stream complete |
| `ping` | Keep-alive |
| `error` | Error during stream |

---

## Error Responses

### 401 Unauthorized

```json
{
  "type": "error",
  "error": {
    "type": "authentication_error",
    "message": "invalid x-api-key"
  }
}
```

**Common causes:**
- OAuth token in `X-Api-Key` header (must use `Authorization: Bearer`)
- Missing `anthropic-beta: oauth-2025-04-20` header with OAuth token
- Both `X-Api-Key` and `Authorization` headers sent simultaneously
- Expired access token (8h lifetime)

### 429 Rate Limited

```json
{
  "type": "error",
  "error": {
    "type": "rate_limit_error",
    "message": "Rate limit reached"
  }
}
```

Headers: `retry-after: <seconds>`

### 529 Overloaded

```json
{
  "type": "error",
  "error": {
    "type": "overloaded_error",
    "message": "Overloaded"
  }
}
```

---

## SDK Usage

### Python (Lambda / Backend)

```python
import anthropic

# API Key mode
client = anthropic.Anthropic(api_key="sk-ant-api03-...")

# OAuth mode ($0 cost)
client = anthropic.Anthropic(
    api_key=None,  # CRITICAL: prevents SDK from reading ANTHROPIC_API_KEY env var
    auth_token="sk-ant-oat01-...",
    default_headers={"anthropic-beta": "oauth-2025-04-20"},
)

response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    system="You are a helpful assistant.",
    messages=[{"role": "user", "content": "Hello!"}],
)

# Access response
text = "\n".join(b.text for b in response.content if b.type == "text")
print(f"Tokens: in={response.usage.input_tokens} out={response.usage.output_tokens}")
```

### Swift (iOS App)

```swift
import Foundation

struct ClaudeAPIClient {
    let baseURL = URL(string: "https://api.anthropic.com/v1/messages")!

    enum AuthMode {
        case apiKey(String)
        case oauth(accessToken: String)
    }

    func sendMessage(
        auth: AuthMode,
        model: String = "claude-sonnet-4-20250514",
        system: String? = nil,
        messages: [[String: Any]],
        maxTokens: Int = 4096,
        stream: Bool = false
    ) async throws -> MessageResponse {
        var request = URLRequest(url: baseURL)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("2023-06-01", forHTTPHeaderField: "anthropic-version")

        switch auth {
        case .apiKey(let key):
            request.setValue(key, forHTTPHeaderField: "X-Api-Key")
        case .oauth(let token):
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
            request.setValue("oauth-2025-04-20", forHTTPHeaderField: "anthropic-beta")
        }

        var body: [String: Any] = [
            "model": model,
            "max_tokens": maxTokens,
            "messages": messages,
            "stream": stream,
        ]
        if let system { body["system"] = system }

        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw ClaudeError.invalidResponse
        }

        guard httpResponse.statusCode == 200 else {
            let error = try? JSONDecoder().decode(APIError.self, from: data)
            throw ClaudeError.apiError(
                status: httpResponse.statusCode,
                message: error?.error.message ?? "Unknown error"
            )
        }

        return try JSONDecoder().decode(MessageResponse.self, from: data)
    }
}

// MARK: - Models

struct MessageResponse: Codable {
    let id: String
    let type: String
    let role: String
    let model: String
    let content: [ContentBlock]
    let stopReason: String?
    let usage: Usage

    enum CodingKeys: String, CodingKey {
        case id, type, role, model, content, usage
        case stopReason = "stop_reason"
    }
}

struct ContentBlock: Codable {
    let type: String
    let text: String?
}

struct Usage: Codable {
    let inputTokens: Int
    let outputTokens: Int

    enum CodingKeys: String, CodingKey {
        case inputTokens = "input_tokens"
        case outputTokens = "output_tokens"
    }
}

struct APIError: Codable {
    let type: String
    let error: ErrorDetail
}

struct ErrorDetail: Codable {
    let type: String
    let message: String
}

enum ClaudeError: Error {
    case invalidResponse
    case apiError(status: Int, message: String)
    case tokenExpired
}
```

### Swift Streaming (iOS)

```swift
func streamMessage(
    auth: AuthMode,
    messages: [[String: Any]],
    onDelta: @escaping (String) -> Void,
    onComplete: @escaping (Usage) -> Void
) async throws {
    // Same request setup as above, with stream: true
    var request = makeRequest(auth: auth, messages: messages, stream: true)

    let (bytes, response) = try await URLSession.shared.bytes(for: request)
    guard let httpResponse = response as? HTTPURLResponse,
          httpResponse.statusCode == 200 else {
        throw ClaudeError.invalidResponse
    }

    var totalUsage: Usage?

    for try await line in bytes.lines {
        guard line.hasPrefix("data: ") else { continue }
        let json = String(line.dropFirst(6))
        guard let data = json.data(using: .utf8),
              let event = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let type = event["type"] as? String else { continue }

        switch type {
        case "content_block_delta":
            if let delta = event["delta"] as? [String: Any],
               let text = delta["text"] as? String {
                onDelta(text)
            }
        case "message_delta":
            if let usage = event["usage"] as? [String: Any],
               let outputTokens = usage["output_tokens"] as? Int {
                totalUsage = Usage(inputTokens: 0, outputTokens: outputTokens)
            }
        case "message_start":
            if let message = event["message"] as? [String: Any],
               let usage = message["usage"] as? [String: Any],
               let inputTokens = usage["input_tokens"] as? Int {
                totalUsage = Usage(inputTokens: inputTokens, outputTokens: 0)
            }
        default:
            break
        }
    }

    if let usage = totalUsage {
        onComplete(usage)
    }
}
```

---

## Real Execution Samples (from POC 5)

### Murder → Planner Assignment

Murder reads the blackboard, judges via Claude, and assigns a planner crow:

**Claude Input** (system + user prompt with blackboard state):
- Input tokens: **337**
- Output tokens: **4096** (max)
- Cost: **$0.0625** (Sonnet pricing)
- Latency: **~53s**

**Murder Decision Output:**
```json
{
  "action": "assign",
  "crow": "planner",
  "instructions": "Create a detailed plan for building the cawnex-design MCP server..."
}
```

### Blackboard Schema (DynamoDB)

```
PK: EXEC#{execution_id}
SK: META                    → Execution metadata (status, repo, issue)
SK: STEP#01#DECISION        → Murder's decision (assign crow, instructions)
SK: STEP#01#TASK            → Task for worker (status: pending→running→completed)
SK: STEP#01#REPORT          → Worker's report (output, files changed)
SK: STEP#02#DECISION        → Next decision after reviewing report
SK: STEP#02#TASK            → Next task...
SK: RESULT                  → Final execution result
```

### Task Lifecycle

```
pending → running → completed
   ↑                    │
   └── reset (if worker crashes without reporting)
```

### Sample Blackboard Items

**META (execution metadata):**
```json
{
  "PK": "EXEC#exec_47ed0c4d",
  "SK": "META",
  "status": "waiting_for_crow",
  "repo": "eduardoaugustoes/cawnex",
  "issue_number": 2,
  "issue_title": "Build cawnex-design MCP server for .pen file operations",
  "branch": "cawnex/exec_47ed0c4d"
}
```

**STEP DECISION (Murder assigns crow):**
```json
{
  "PK": "EXEC#exec_47ed0c4d",
  "SK": "STEP#01#DECISION",
  "action": "assign",
  "crow": "planner",
  "instructions": "Create a detailed plan for building the cawnex-design MCP server..."
}
```

**STEP TASK (for worker pickup):**
```json
{
  "PK": "EXEC#exec_47ed0c4d",
  "SK": "STEP#01#TASK",
  "status": "pending",
  "crow": "planner",
  "branch": "cawnex/exec_47ed0c4d",
  "repo": "eduardoaugustoes/cawnex",
  "issue_number": 2,
  "instructions": "Create a detailed plan..."
}
```

**STEP REPORT (worker output):**
```json
{
  "PK": "EXEC#exec_47ed0c4d",
  "SK": "STEP#01#REPORT",
  "raw_output": "I'll create a detailed plan for building the cawnex-design MCP server...",
  "dependencies": {
    "@modelcontextprotocol/sdk": "^latest",
    "express": "^4.18.0",
    "satori": "^0.10.0",
    "puppeteer": "^21.0.0",
    "node-canvas": "^2.11.0",
    "ajv": "^8.12.0",
    "uuid": "^9.0.0"
  }
}
```

---

## Official SDKs

| Language | Package | Install |
|----------|---------|---------|
| Python | `anthropic` | `pip install anthropic` |
| TypeScript | `@anthropic-ai/sdk` | `npm install @anthropic-ai/sdk` |
| Java | `com.anthropic:anthropic-java` | Maven/Gradle |
| Go | `github.com/anthropics/anthropic-sdk-go` | `go get` |
| Ruby | `anthropic` | `gem install anthropic` |
| C# | `Anthropic` | NuGet |
| PHP | `anthropic/anthropic-sdk-php` | Composer |

---

## Gotchas & Lessons Learned

1. **`api_key=None` is mandatory with OAuth** — Python SDK auto-reads `ANTHROPIC_API_KEY` env var; if set, it sends dual headers (`X-Api-Key` + `Authorization: Bearer`) and the API rejects it

2. **`anthropic-beta: oauth-2025-04-20` is required** — Without this header, API returns "OAuth authentication is currently not supported"

3. **Refresh tokens are single-use** — Each refresh rotates the token; using the old one again returns an error. Store immediately.

4. **Refresh blocked from cloud IPs** — AWS Lambda, GitHub Actions get 403 from `console.anthropic.com` (Cloudflare). Only works from user devices or VPS.

5. **Token endpoint is `console.anthropic.com`** — NOT `platform.claude.com` or `claude.ai`. Only `POST https://console.anthropic.com/v1/oauth/token` works.

6. **Auth URL uses `claude.ai`** — The authorize URL is `https://claude.ai/oauth/authorize`, different from the token endpoint domain.

7. **max_tokens caps output** — Set appropriately; `4096` is usually enough for most tasks. Maximum is `8192` for current models.

8. **Cost is zero with OAuth** — OAuth tokens from Claude Pro/Max subscriptions don't incur API charges. All inference is covered by the subscription.
