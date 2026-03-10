# 🔑 BYOL — Bring Your Own LLM

> Cawnex never pays for tokens. Users bring their own AI.

---

## Core Principle

Cawnex charges for **orchestration**, not compute. The LLM cost is the user's responsibility.

This means:
- Zero LLM cost on our side
- No artificial execution limits
- Users control their own budget
- We can price aggressively (pure SaaS margins)

---

## Two BYOL Modes

### Mode 1 — API Key
User provides an API key (Anthropic, OpenAI, Google). Cawnex makes SDK calls directly.

```
User → Settings → Paste API key → Encrypted (KMS) → Used per execution
```

**Pros**: Precise token tracking, model selection per agent, structured output
**Cons**: User pays per token (can be expensive at scale)

### Mode 2 — Subscription Relay (Claude Max / Pro)
User has an unlimited subscription (Claude Max $200/mo). Cawnex orchestrates via Claude Code subprocess.

```
User → Installs Claude Code in sandbox → Cawnex sends commands → Parses output
```

**Pros**: Unlimited executions for flat fee, user already paying for subscription
**Cons**: Less control, output parsing (regex/structured), depends on CLI stability

**This is the "subprocess with regex" that Luiz ran in production for months.** It works.

### Mode Comparison

| | API Key | Subscription Relay |
|---|---------|-------------------|
| Cost to user | Per token ($0.50-2/exec) | Flat ($100-200/mo unlimited) |
| Control | Full (model, tokens, temp) | Limited (CLI interface) |
| Speed | Faster (direct SDK) | Slightly slower (subprocess) |
| Structured output | Native | Parsed |
| Token tracking | Exact | Estimated |
| Best for | Low-medium volume | High volume / power users |

### User's Total Cost

| Scenario | LLM Cost | Cawnex Cost | Total |
|----------|----------|-------------|-------|
| Light (20 exec/mo, API) | ~$20 | Free tier | ~$20 |
| Medium (100 exec/mo, API) | ~$100 | $29 Pro | ~$129 |
| Heavy (500+ exec/mo, Max sub) | $200 flat | $99 Team | ~$299 |
| Enterprise (unlimited, Max sub) | $200 flat | Custom | ~$500+ |

Compare: Lovable Pro = $50/mo with 500 message limits. Cawnex + Claude Max = $299/mo **unlimited**.

---

## Supported Providers

### Day 1

| Provider | Models | Use Case |
|----------|--------|----------|
| **Anthropic** | Opus 4.6, Sonnet 4.6, Haiku 4.6 | Primary. Best for code generation. |

### V1.1

| Provider | Models | Use Case |
|----------|--------|----------|
| **OpenAI** | GPT-4.1, o3, o4-mini | Alternative. Some users prefer. |

### V2

| Provider | Models | Use Case |
|----------|--------|----------|
| **Google** | Gemini 2.5 Pro | Cost-effective for simple tasks |
| **Custom/Local** | Ollama, vLLM | Self-hosted for enterprise/privacy |

---

## Model Assignment Per Agent

Users configure which model each crow uses. Sensible defaults:

```yaml
# Default agent model configuration
agents:
  refinement:
    model: opus           # Deep reasoning needed
    max_tokens: 8000
    temperature: 0.3

  dev:
    model: opus           # Code quality is critical
    max_tokens: 16000
    temperature: 0.2

  qa:
    model: sonnet         # Review is simpler, save cost
    max_tokens: 8000
    temperature: 0.1

  docs:
    model: haiku          # Documentation is simple
    max_tokens: 4000
    temperature: 0.3
```

Power users can override per-repo:
```yaml
# CAWNEX.md in repository
agent_config:
  dev:
    model: opus           # This repo needs highest quality
  qa:
    model: opus           # Critical service, thorough review
```

---

## Implementation

### API Key Storage

```python
from cryptography.fernet import Fernet

class LLMConfig(Base):
    __tablename__ = "llm_configs"

    id: int
    org_id: int
    provider: str          # anthropic | openai | google
    encrypted_key: bytes   # Fernet-encrypted API key
    mode: str              # "api_key" | "subscription_relay"
    default_model: str
    budget_limit_usd: float  # Monthly budget cap (optional)
    budget_used_usd: float   # Current month usage

    def decrypt_key(self) -> str:
        return fernet.decrypt(self.encrypted_key).decode()
```

### Budget Guard

Optional monthly budget cap. User sets max spend. Cawnex pauses executions when reached.

```python
async def check_budget(org: Organization, estimated_cost: float) -> bool:
    config = org.llm_config
    if config.budget_limit_usd is None:
        return True  # No limit set
    if config.budget_used_usd + estimated_cost > config.budget_limit_usd:
        await notify(org, "Monthly LLM budget reached. Executions paused.")
        return False
    return True
```

### Provider Abstraction

```python
class LLMProvider(Protocol):
    async def generate(self, messages, model, **kwargs) -> LLMResponse: ...
    async def stream(self, messages, model, **kwargs) -> AsyncIterator[str]: ...

class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)

    async def generate(self, messages, model="claude-sonnet-4-6", **kwargs):
        return await self.client.messages.create(
            model=model, messages=messages, **kwargs
        )

class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)

    async def generate(self, messages, model="gpt-4.1", **kwargs):
        return await self.client.chat.completions.create(
            model=model, messages=messages, **kwargs
        )

# Factory
def get_provider(org: Organization) -> LLMProvider:
    config = org.llm_config
    match config.provider:
        case "anthropic": return AnthropicProvider(config.decrypt_key())
        case "openai": return OpenAIProvider(config.decrypt_key())
        case "google": return GoogleProvider(config.decrypt_key())
```

### Subscription Relay (Mode 2)

```python
class ClaudeCodeRelay(LLMProvider):
    """Uses Claude Code CLI via subprocess — for subscription users."""

    async def generate(self, messages, model=None, **kwargs):
        prompt = self._format_prompt(messages)
        proc = await asyncio.create_subprocess_exec(
            "claude", "--print", "--output-format", "json",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate(prompt.encode())
        return self._parse_response(stdout.decode())
```

---

## Onboarding Flow

```
1. Sign up (GitHub OAuth)
2. "Connect your AI" screen:
   ┌─────────────────────────────────────┐
   │  🔑 How do you want to connect?     │
   │                                      │
   │  [Anthropic API Key]  ← recommended │
   │  [OpenAI API Key]                    │
   │  [Google AI API Key]                 │
   │                                      │
   │  ── or ──                            │
   │                                      │
   │  [Claude Max Subscription]           │
   │  Uses Claude Code CLI (unlimited)    │
   └─────────────────────────────────────┘
3. Paste key → Test connection → ✅
4. Connect GitHub repos
5. First issue → First PR → 🎉
```

---

## Marketing

### Positioning
> "The orchestration layer for AI development. Bring your own brain."

### Key Messages
- **No token limits**: Your API key, your budget, your rules
- **Works with what you have**: Already paying for Claude Max? Use it.
- **Transparent costs**: We charge for orchestration ($29-99/mo). LLM is yours.
- **Switch anytime**: Change providers without changing workflow

### vs. Competition

| Platform | LLM Model | Limits |
|----------|-----------|--------|
| Lovable | Built-in (OpenAI?) | 500 messages/mo on Pro |
| Bolt | Built-in | Credits run out fast |
| Cursor | Built-in + BYOK | 500 fast requests/mo |
| **Cawnex** | **BYOL only** | **No artificial limits** |

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| User enters invalid/expired key | Test on connect. Health check every execution. |
| User's key gets rate-limited | Detect 429s. Queue + exponential backoff. Notify user. |
| Budget overrun | Optional budget cap with notifications at 80%/100%. |
| Provider API changes | Abstraction layer isolates changes. |
| User wants provider we don't support | Plugin architecture for V2. Priority: Anthropic → OpenAI → Google. |
| Subscription relay breaks (CLI update) | Fallback to API key mode. Monitor CLI version compatibility. |
