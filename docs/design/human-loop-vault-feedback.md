# Human-in-the-Loop, Vault, Feedback Loops & Blocking States

> Real projects need humans. Crows can't buy e-SIMs, configure Meta Business Manager,
> or paste API tokens. This document designs the missing layer between AI execution
> and human reality.

---

## Problems Solved

| #   | Problem                                                          |
| --- | ---------------------------------------------------------------- |
| 2   | Human must stay in control (approve, steer, reject)              |
| 7   | Failure resilience (retry, fix, escalate)                        |
| NEW | Tasks that depend on human actions outside the platform          |
| NEW | Crows need credentials but should never see raw values           |
| NEW | External dependencies discovered mid-execution must not deadlock |
| NEW | Blocked tasks must communicate clearly what they need and why    |

---

## Concrete Test Case: Caioo WhatsApp Project

The Caioo project (M1: WhatsApp Channel Foundation) surfaces every gap:

| Dependency                      | Type       | Who     | Duration  | Blocks         |
| ------------------------------- | ---------- | ------- | --------- | -------------- |
| Buy e-SIM number                | Physical   | Eduardo | 5 days    | g1, g2, g3, g5 |
| Meta Business App approval      | External   | Meta    | 7 days    | g1 templates   |
| Meta template approval          | External   | Meta    | 3 days    | g2 outbound    |
| WhatsApp Business API token     | Credential | Eduardo | After app | g2, g3, g5     |
| Webhook verification token      | Credential | Eduardo | After app | g3             |
| Upload message template content | Content    | Eduardo | 1 hour    | g2             |
| Dashboard design mockup         | Asset      | Eduardo | 2 hours   | g4             |

Every single goal has at least one human dependency. Without this design, the engine would spin up crows that immediately fail or produce unusable output.

---

## Part 1: Human-in-the-Loop Tasks

### The Core Concept: Human Tasks

A **human task** is a task within an MVI that requires a person to do something outside the platform. It follows the same snapshot pattern as crow tasks but has a different executor: a human, not an AI agent.

Human tasks are first-class citizens in the task pipeline. They are not exceptions or workarounds.

### Task Type Enum Extension

```
task_type: "crow" | "human"
```

Every task in the system gets an explicit type. Crow tasks are dispatched to workers. Human tasks are dispatched to humans via notifications.

### Human Task Subtypes

| Subtype           | Description                                    | Example                             |
| ----------------- | ---------------------------------------------- | ----------------------------------- |
| `provide_secret`  | User must supply a credential or API key       | WhatsApp Business API token         |
| `upload_asset`    | User must upload a file, image, or document    | Logo image (PNG/SVG), reference PDF |
| `fill_content`    | User must write or paste text content          | Message template body text          |
| `configure_ext`   | User must configure an external platform       | Meta Business Manager setup         |
| `physical_action` | User must do something in the physical world   | Buy e-SIM, mail a document          |
| `wait_external`   | Waiting for an external party (no user action) | Meta template approval (3 day wait) |
| `confirm`         | User must confirm something happened           | "Did you receive the e-SIM?"        |

### Human Task Lifecycle

```
PENDING ──► NOTIFIED ──► IN_PROGRESS ──► COMPLETED
  │             │             │              │
  │             │             │              └── auto-unblocks dependent tasks
  │             │             └── user started working on it
  │             └── notification sent, waiting for user
  └── created but not yet notified (batch with other notifications)
                │
                └──► EXPIRED (optional TTL)
                      │
                      └── re-notify or escalate
```

### DynamoDB Record: Human Task

Lives in the same snapshot tree as crow tasks. Same PK, same SK pattern.

```json
{
  "PK": "T#t_0_71899937#P#caioo-653d43",
  "SK": "S#w001#m_dev#ht_esim",

  "id": "ht_esim",
  "level": "crow",
  "task_type": "human",
  "human_task_subtype": "physical_action",
  "status": "notified",

  "ask": "Purchase an e-SIM number for WhatsApp Business registration",
  "instructions": "Buy a dedicated phone number (e-SIM or physical SIM) that will be used exclusively for the WhatsApp Business Account. This number must be able to receive SMS for verification. Do not use a number already registered with WhatsApp.",

  "input_schema": {
    "phone_number": {
      "type": "string",
      "label": "Phone number (with country code)",
      "placeholder": "+55 11 99999-9999",
      "pattern": "^\\+[1-9]\\d{1,14}$",
      "pattern_hint": "E.164 format: +55 11 99999-9999",
      "required": true
    },
    "carrier": {
      "type": "string",
      "label": "Carrier name",
      "required": false
    }
  },

  "assigned_to": "human",
  "estimated_human_hours": 1,
  "deadline_hint": "2026-03-21T00:00:00Z",

  "blocks": ["S#w001#m_dev#cr_meta_setup", "S#w001#m_dev#cr_outbound_api"],

  "response": null,
  "steer": null,
  "completed_at": null,
  "notification_id": "n_abc123",

  "created_at": "2026-03-16T10:00:00Z",
  "entityType": "Snapshot"
}
```

### How Murder Creates Human Tasks

During the planning phase, the Planner crow identifies tasks that require human action. The planner outputs a standard plan, but some tasks are tagged `"task_type": "human"`.

Murder reads the plan. For each human task:

1. Writes a human task snapshot (same tree as crow tasks)
2. Creates a notification record (see Part 4)
3. Marks dependent crow tasks as `blocked` (see Part 4)
4. Continues dispatching non-blocked crow tasks

This means work proceeds in parallel wherever possible. If g4 (Dashboard) has no human dependencies but g1 (WhatsApp Account) is blocked, Murder works on g4 while waiting for the human to unblock g1.

### Input Schema Specification

The `input_schema` defines what the human must provide. It supports rich validation so Crows receive usable, validated data — not garbage that causes downstream failures.

#### Field Types

| Type      | Description                        | iOS Renders As            | Validation                           |
| --------- | ---------------------------------- | ------------------------- | ------------------------------------ |
| `string`  | Plain text input                   | Text field                | `pattern`, `minLength`, `maxLength`  |
| `text`    | Multi-line text                    | Text area                 | `minLength`, `maxLength`             |
| `secret`  | Sensitive credential               | Password field (masked)   | `pattern`, routes to vault on submit |
| `file`    | File upload (image, PDF, document) | File picker + upload      | `accept`, `maxSizeMB`                |
| `url`     | URL input                          | URL field with validation | Auto-validates URL format            |
| `email`   | Email input                        | Email field               | Auto-validates email format          |
| `color`   | Color value                        | Color picker              | Hex format `#RRGGBB`                 |
| `enum`    | Pick from allowed values           | Dropdown / segmented      | `options` array                      |
| `boolean` | Yes/No confirmation                | Toggle / checkbox         | N/A                                  |
| `number`  | Numeric input                      | Number field              | `min`, `max`                         |

#### Validation Properties

Every field can include:

```json
{
  "type": "string",
  "label": "Human-readable label",
  "placeholder": "Example value",
  "required": true,
  "pattern": "^EAAGm0[A-Za-z0-9]+$",
  "pattern_hint": "Meta access tokens start with EAAGm0...",
  "minLength": 10,
  "maxLength": 500,
  "description": "Why this is needed and where to find it"
}
```

For `file` type:

```json
{
  "type": "file",
  "label": "Company logo",
  "required": true,
  "accept": ["image/png", "image/svg+xml"],
  "maxSizeMB": 5,
  "minResolution": { "width": 512, "height": 512 },
  "description": "Square logo, minimum 512x512px, PNG or SVG"
}
```

For `enum` type:

```json
{
  "type": "enum",
  "label": "Color scheme preference",
  "required": true,
  "options": [
    { "value": "light", "label": "Light mode" },
    { "value": "dark", "label": "Dark mode" },
    { "value": "auto", "label": "Follow system" }
  ]
}
```

#### Validation Flow

```
Human submits response via iOS
  → API Lambda validates EVERY field against its schema rules:
    1. Required fields present
    2. Type matches (string, number, file ref, etc.)
    3. Pattern matches (regex)
    4. Length/size constraints met
    5. File type and size validated (if file)
  → If validation fails:
    - 400 response with field-level errors
    - iOS highlights invalid fields with error messages
    - Human corrects and resubmits
  → If validation passes:
    - Secrets routed to vault (encrypted, never stored raw)
    - Files already in S3 (uploaded via presigned URL)
    - Response stored in human task record
    - Stream fires → Murder unblocks
```

### 10 Real-World Examples with Schema

| #   | Scenario                     | Schema                                                                                                                                                        | Score |
| --- | ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----- |
| 1   | **Logo image**               | `{ logo: { type: "file", accept: ["image/png","image/svg+xml"], maxSizeMB: 5, minResolution: {w:512,h:512} } }`                                               | 9/10  |
| 2   | **Meta Access Token**        | `{ token: { type: "secret", pattern: "^EAAGm0.+", pattern_hint: "Starts with EAAGm0..." } }`                                                                  | 10/10 |
| 3   | **PDF reference doc**        | `{ document: { type: "file", accept: ["application/pdf"], maxSizeMB: 20 }, post_processing: "extract_text" }`                                                 | 9/10  |
| 4   | **e-SIM phone number**       | `{ phone: { type: "string", pattern: "^\\+[1-9]\\d{1,14}$", pattern_hint: "E.164: +5511999999999" } }`                                                        | 10/10 |
| 5   | **Meta Business config**     | `{ confirmed: { type: "boolean", label: "I have configured Meta Business Manager" }, verification: { crow_check: "call Meta API to validate WABA status" } }` | 9/10  |
| 6   | **Webhook verify token**     | `{ token: { type: "secret", minLength: 8, description: "Any random string you set in Meta" } }`                                                               | 10/10 |
| 7   | **Message template content** | `{ body: { type: "text", maxLength: 1024 }, header: { type: "string", maxLength: 60 }, has_variables: { type: "boolean" } }`                                  | 9/10  |
| 8   | **Wait for Meta approval**   | No input needed — `wait_external` with checker pattern                                                                                                        | 9/10  |
| 9   | **Brand color palette**      | `{ primary: { type: "color" }, secondary: { type: "color" }, accent: { type: "color" } }`                                                                     | 9/10  |
| 10  | **Domain/DNS config**        | `{ domain: { type: "url" }, verification: { crow_check: "DNS lookup to verify A/CNAME record" } }`                                                            | 9/10  |

### File Upload Flow (S3 Presigned URLs)

Files are NOT sent through the API body. Instead:

```
1. iOS requests upload URL:
   POST /projects/{pid}/human-tasks/{htid}/upload-url
   Body: { "field": "logo", "filename": "logo.png", "content_type": "image/png" }

2. API Lambda validates:
   - Field exists in input_schema with type "file"
   - content_type matches field's accept list
   - Generates S3 presigned PUT URL (5 min TTL)

3. API Lambda returns:
   {
     "upload_url": "https://s3.amazonaws.com/cawnex-assets-dev/...",
     "asset_key": "T/t_0_71899937/P/caioo-653d43/assets/ht_logo/logo.png",
     "expires_in": 300
   }

4. iOS uploads file directly to S3 using presigned URL

5. iOS submits human task response with asset reference:
   POST /projects/{pid}/human-tasks/{htid}/respond
   Body: {
     "response": {
       "logo": { "asset_key": "T/.../logo.png", "content_type": "image/png" }
     }
   }

6. API Lambda validates:
   - Asset exists in S3
   - Size within maxSizeMB
   - Image resolution meets minResolution (if applicable)
   - Marks human task complete
```

#### S3 Bucket Structure

```
cawnex-assets-{stage}/
  T/{tenant_id}/
    P/{project_id}/
      assets/
        {human_task_id}/
          logo.png
          reference-doc.pdf
          extracted/
            reference-doc.txt       ← post-processing output
```

### Post-Processing Pipeline

Some uploaded files need processing before Crows can use them. The `post_processing` field on a file schema field tells the system what to do after upload.

| Processing Type | Trigger                | Output                                   | Used For                 |
| --------------- | ---------------------- | ---------------------------------------- | ------------------------ |
| `extract_text`  | PDF or document upload | Plain text stored in `extracted/` prefix | Reference docs, formulas |
| `extract_meta`  | Image upload           | Dimensions, format, color profile        | Design assets            |
| `none`          | Default                | File stored as-is                        | Logos, icons             |

```
Post-processing flow:

1. Human uploads PDF (reference doc with secret formula)
2. API stores in S3: .../assets/ht_formula/formula.pdf
3. API writes processing record:
   {
     "PK": "T#{tenant}#P#{project}",
     "SK": "PROCESS#{human_task_id}",
     "source": "s3://cawnex-assets-dev/.../formula.pdf",
     "processing": "extract_text",
     "status": "pending"
   }
4. S3 event triggers Processing Lambda:
   - PDF → text extraction (PyPDF2 or Textract for complex layouts)
   - Output → s3://.../extracted/formula.txt
   - Updates PROCESS record: status = "completed"
   - Stores extracted text as project context:
     PK: T#{tenant}#P#{project}
     SK: CTX#ht_formula
     { content: "The secret formula requires...", source: "formula.pdf" }
5. Crows reference this context: {{context:ht_formula}}
   - Worker resolves it like secrets, but from CTX# records
   - Content injected into crow's prompt (not env vars — this is not secret)
```

### Verification Step

Some human tasks need verification — the human says they did something, but a Crow should confirm it actually worked. The `verification` field enables this.

```json
{
  "id": "ht_dns_config",
  "task_type": "human",
  "human_task_subtype": "configure_ext",
  "ask": "Point your domain caioo.com.br to our server",
  "instructions": "Add a CNAME record pointing to api.cawnex.io in your DNS provider",

  "input_schema": {
    "domain": {
      "type": "url",
      "label": "Your domain",
      "required": true
    }
  },

  "verification": {
    "type": "crow_check",
    "instructions": "Perform DNS lookup for the provided domain. Verify CNAME points to api.cawnex.io. Return approved:true if correct, approved:false with explanation if not.",
    "max_retries": 3,
    "retry_delay_hours": 1
  }
}
```

#### Verification Flow

```
1. Human responds: { "domain": "caioo.com.br" }
2. API validates input schema → passes
3. Human task status: notified → responded (NOT completed yet)
4. DynamoDB Stream fires → Murder sees verification is required
5. Murder dispatches a lightweight verification crow:
   - Crow runs DNS lookup
   - If CNAME correct → verification passed
   - If CNAME wrong → verification failed with explanation
6. On pass:
   - Human task status: responded → completed
   - Dependent tasks unblocked
7. On fail:
   - Human task status: responded → verification_failed
   - Notification: "DNS is not configured correctly. Expected CNAME to api.cawnex.io
     but found: [current value]. Please update and I'll check again."
   - Murder schedules re-check (retry_delay_hours)
   - After max_retries: escalate with detailed error
```

#### Verification for External Configs

Same pattern works for Meta Business Manager:

```json
{
  "verification": {
    "type": "crow_check",
    "instructions": "Call Meta Graph API /v18.0/{waba_id} with the stored whatsapp_api_token. If status is CONNECTED, verification passes. If 401 or status != CONNECTED, verification fails.",
    "required_secrets": ["whatsapp_api_token"],
    "max_retries": 2,
    "retry_delay_hours": 0
  }
}
```

This closes the trust gap: the system does not just take the human's word — it confirms.

### Human Task Lifecycle (Updated)

```
PENDING ──► NOTIFIED ──► IN_PROGRESS ──► RESPONDED ──► COMPLETED
  │             │             │              │              │
  │             │             │              │              └── auto-unblocks dependent tasks
  │             │             │              │
  │             │             │              ├── (no verification) → COMPLETED directly
  │             │             │              │
  │             │             │              └── (has verification) → VERIFYING
  │             │             │                       │
  │             │             │                       ├── pass → COMPLETED
  │             │             │                       │
  │             │             │                       └── fail → VERIFICATION_FAILED
  │             │             │                                   │
  │             │             │                                   └── re-notify, human corrects
  │             │             │                                       → RESPONDED (retry)
  │             │             └── user started working on it
  │             └── notification sent, waiting for user
  └── created but not yet notified (batch with other notifications)
                │
                └──► EXPIRED (optional TTL)
                      │
                      └── re-notify or escalate
```

### API Endpoints for Human Input

```
POST /projects/{pid}/human-tasks/{htid}/respond
  Body: {
    "response": {                                   // OPTIONAL if steer provided
      "phone_number": "+55 11 99999-9999",
      "carrier": "Claro"
    },
    "steer": "Use this number with Twilio, not Meta" // OPTIONAL — human guidance
  }

  Validation rules:
    - At least one of `response` or `steer` must be provided
    - If `response` is provided: validate EVERY field against input_schema
    - If only `steer` is provided: skip input_schema validation (input is optional)
    - If both provided: validate response AND store steer

  Three scenarios:
    1. Input only: Crow resumes with original instructions + human's data
    2. Input + Steer: Crow resumes with original instructions + data + human guidance
    3. Steer only: Crow resumes with modified instructions, no input data required

  Effect:
    - Validates fields against input_schema (if response provided)
    - Returns 400 with field-level errors if validation fails
    - Routes secret fields to vault (encrypted, never stored raw)
    - Stores steer text on human task record (if provided)
    - If verification defined: status → responded → verifying
    - If no verification: status → completed
    - Triggers post-processing for file fields (if configured)
    - DynamoDB Stream fires → Murder wakes up
    - Murder injects steer into resuming Crow's instructions as "## Human Guidance"
    - Murder unblocks dependent tasks (after verification passes, if applicable)

POST /projects/{pid}/human-tasks/{htid}/upload-url
  Body: { "field": "logo", "filename": "logo.png", "content_type": "image/png" }
  Returns: { "upload_url": "https://s3...", "asset_key": "T/.../logo.png", "expires_in": 300 }
  Effect:
    - Validates field exists in input_schema with type "file"
    - Validates content_type matches field's accept list
    - Generates S3 presigned PUT URL (5 min TTL)

GET /projects/{pid}/human-tasks
  Returns: all human tasks for the project, grouped by status
  Used by: iOS app to show "what does the AI need from you?"

GET /projects/{pid}/human-tasks/{htid}
  Returns: single human task with full context, instructions, input schema
```

### iOS Integration

A new section appears in the Project Hub (S12): **"Needs Your Input"** — a card showing the count of pending human tasks. Tapping it opens a list of human tasks with clear instructions and input fields.

Each human task card shows:

- What is needed (plain language)
- Why it is needed (which goals it unblocks)
- Input fields matching the `input_schema`
- Deadline hint (if applicable)
- Status indicator

---

## Part 2: Vault Integration

### Design Philosophy

The vault exists so that crows can use credentials without seeing them. A crow never receives `WHATSAPP_API_TOKEN=EAAGm0PX4ZCps...`. Instead, it receives `{{secret:whatsapp_api_token}}` in its instructions, and the Worker Lambda resolves the reference at execution time, injecting the value into environment variables or tool configurations.

### V1 Approach: DynamoDB + KMS

For V1, secrets are stored as encrypted DynamoDB items. No need for AWS Secrets Manager yet. The simplicity of DynamoDB-based secrets with KMS encryption is sufficient for early-stage single-tenant usage.

### DynamoDB Record: Secret

```json
{
  "PK": "T#t_0_71899937#VAULT",
  "SK": "P#caioo-653d43#whatsapp_api_token",

  "name": "whatsapp_api_token",
  "project_id": "caioo-653d43",
  "scope": "project",

  "encrypted_value": "<KMS-encrypted base64 string>",
  "kms_key_id": "alias/cawnex-vault",

  "metadata": {
    "description": "WhatsApp Business API access token from Meta",
    "provided_via": "human_task:ht_meta_token",
    "expires_at": null,
    "last_rotated": "2026-03-23T14:00:00Z"
  },

  "created_at": "2026-03-23T14:00:00Z",
  "updated_at": "2026-03-23T14:00:00Z",
  "entityType": "Secret"
}
```

### Secret Scoping

| Scope   | PK                 | SK Pattern                  | Visible To                    |
| ------- | ------------------ | --------------------------- | ----------------------------- |
| Project | `T#{tenant}#VAULT` | `P#{project}#{secret_name}` | Crows working on this project |
| Tenant  | `T#{tenant}#VAULT` | `TENANT#{secret_name}`      | All crows for this tenant     |

Project-scoped secrets take precedence over tenant-scoped secrets with the same name.

### Secret Resolution Flow

```
1. Murder writes crow task with instructions containing {{secret:whatsapp_api_token}}
2. Worker Lambda picks up the task
3. Before executing the crow:
   a. Scan instructions for {{secret:...}} patterns
   b. For each reference, query VAULT partition:
      - First: PK=T#{tenant}#VAULT, SK=P#{project}#{name}
      - Fallback: PK=T#{tenant}#VAULT, SK=TENANT#{name}
   c. Decrypt value using KMS
   d. Inject into crow's environment (not into prompt text)
4. Crow uses the secret via environment variable or tool parameter
5. Secret value is NEVER written to snapshots, logs, or events
```

### How Secrets Flow from Human Tasks

When a human task has `subtype: "provide_secret"`, the response is automatically stored in the vault:

```
Human completes task "Provide WhatsApp API token"
  → API Lambda receives response with token value
  → API Lambda writes to VAULT partition (encrypted)
  → API Lambda updates human task status to completed
  → API Lambda DOES NOT store the raw value in the human task response field
  → Human task response field stores: { "secret_ref": "whatsapp_api_token", "stored": true }
  → DynamoDB Stream fires → Murder unblocks dependent tasks
```

### API Endpoints

```
POST /projects/{pid}/vault/secrets
  Body: { "name": "whatsapp_api_token", "value": "EAAGm0...", "description": "..." }
  Effect: encrypts + stores in VAULT partition
  Note: value is NEVER returned in any GET response

GET /projects/{pid}/vault/secrets
  Returns: list of secret names + metadata (NEVER values)
  Example: [{ "name": "whatsapp_api_token", "description": "...", "last_rotated": "..." }]

DELETE /projects/{pid}/vault/secrets/{name}
  Effect: removes secret, Murder re-checks if any active tasks depended on it

PUT /projects/{pid}/vault/secrets/{name}/rotate
  Body: { "value": "new_value" }
  Effect: encrypts new value, updates last_rotated timestamp
```

### Security Constraints

1. Secret values are NEVER logged (structured logger strips fields matching `*secret*`, `*token*`, `*key*`, `*password*`)
2. Secret values are NEVER stored in snapshots, events, or any DynamoDB record outside VAULT
3. Secret values are NEVER sent in the crow's prompt text; they are injected as environment variables
4. KMS key is per-stage (`alias/cawnex-vault-dev`, `alias/cawnex-vault-prod`)
5. Lambda IAM role includes `kms:Decrypt` only for the vault key
6. DynamoDB item-level access: vault reads require explicit `GetItem` on the VAULT partition

---

## Part 3: Feedback Loop Design

### The Problem

Execution does not always proceed linearly. Real-world failures create feedback loops:

1. A credential does not work (token expired, wrong scope, rate limited)
2. A new dependency is discovered mid-execution (crow realizes it needs an API key it was not given)
3. An external API changed its contract (Meta updated their webhook format)
4. A human task was completed incorrectly (wrong phone number format)

Each of these must be handled without deadlocking the system.

### Feedback Loop States

These extend the existing crow snapshot `status` field:

```
Existing:  pending → running → completed | failed
New:       pending → running → blocked_on_human | blocked_on_secret | blocked_on_external
```

| Status                | Meaning                                               | Next Step                             |
| --------------------- | ----------------------------------------------------- | ------------------------------------- |
| `blocked_on_human`    | Crow discovered it needs human input mid-execution    | Creates human task, pauses, notifies  |
| `blocked_on_secret`   | Crow needs a credential that does not exist in vault  | Creates provide_secret task, notifies |
| `blocked_on_external` | Waiting for external system (API approval, DNS, etc.) | Creates wait_external task, notifies  |

### Feedback Loop: Credential Failure

```
Crow attempts to call WhatsApp API
  → API returns 401 (token invalid)
  → Crow writes structured failure:
    {
      "status": "blocked_on_secret",
      "blocker": {
        "type": "credential_failure",
        "secret_name": "whatsapp_api_token",
        "error": "401 Unauthorized — token may be expired or have insufficient scope",
        "attempted_at": "2026-03-24T10:30:00Z"
      }
    }
  → DynamoDB Stream fires → Murder wakes up
  → Murder reads blocker, decides:
    a. Secret exists but is stale → create human task: "Your WhatsApp token is not working. Please provide a new one."
    b. Secret does not exist → create human task: "I need a WhatsApp API token to continue."
  → Murder marks dependent tasks as blocked
  → Notification sent to human
  → Human provides new token via vault endpoint
  → DynamoDB Stream fires → Murder wakes up
  → Murder unblocks and re-dispatches the crow with retry_count += 1
```

### Feedback Loop: New Dependency Discovered

```
Implementer crow working on webhook receiver
  → Reads Meta documentation (via tool)
  → Discovers: webhook requires a verification token (not in requirements)
  → Crow writes:
    {
      "status": "blocked_on_secret",
      "blocker": {
        "type": "missing_dependency",
        "discovery": "Meta webhook verification requires a VERIFY_TOKEN that the server echoes back during setup. This was not in the original requirements.",
        "secret_name": "whatsapp_verify_token",
        "suggestion": "Any random string works — the operator sets it in Meta Business Manager and we echo it back."
      }
    }
  → Murder creates human task with clear explanation
  → Work continues on other non-blocked tasks
  → Human provides the verify token
  → Crow resumes
```

### Feedback Loop: External Dependency

```
Task: Submit message template for Meta approval
  → Crow calls Meta API to submit template
  → API returns: "Template submitted, review pending (typically 24-72 hours)"
  → Crow writes:
    {
      "status": "blocked_on_external",
      "blocker": {
        "type": "external_approval",
        "provider": "meta",
        "resource": "message_template:welcome_msg",
        "expected_duration": "24-72 hours",
        "check_endpoint": "GET /v18.0/{waba_id}/message_templates?name=welcome_msg",
        "resolution": "Template status changes to APPROVED"
      }
    }
  → Murder creates a wait_external human task
  → Notification: "Meta is reviewing your message template. This typically takes 24-72 hours. I'll check back automatically."
  → Murder sets a TTL-based reminder (EventBridge rule or DynamoDB TTL item)
  → After TTL: Murder dispatches a lightweight "checker" crow to poll the status
  → If approved: unblock and continue
  → If rejected: create human task with Meta's rejection reason
```

### The Checker Pattern

For `blocked_on_external` tasks, Murder does not poll continuously. Instead:

1. Write a `CHECK` record with a TTL:

```json
{
  "PK": "T#t_0_71899937#P#caioo-653d43",
  "SK": "CHECK#2026-03-27T10:00:00Z#template_approval",

  "check_type": "external_status",
  "blocked_task_sk": "S#w001#m_dev#cr_template_submit",
  "check_instructions": "Call Meta API to check template status",
  "ttl": 1743073200,

  "entityType": "Check"
}
```

2. A scheduled Lambda (runs every hour) queries for CHECK records where `ttl <= now`
3. For each, dispatches a lightweight crow to check the status
4. If resolved: removes CHECK record, unblocks task
5. If not resolved: writes new CHECK record with updated TTL (exponential backoff, max 24h)

### DynamoDB Record: Blocker

Blockers are embedded in the task snapshot, not separate records. This keeps the audit trail intact.

```json
{
  "PK": "T#t_0_71899937#P#caioo-653d43",
  "SK": "S#w001#m_dev#cr_outbound_api",

  "status": "blocked_on_human",
  "blocker": {
    "type": "credential_failure",
    "secret_name": "whatsapp_api_token",
    "error": "401 Unauthorized",
    "human_task_ref": "S#w001#m_dev#ht_new_token",
    "blocked_at": "2026-03-24T10:30:00Z"
  },
  "blocker_history": [
    {
      "type": "credential_failure",
      "secret_name": "whatsapp_api_token",
      "error": "401 Unauthorized",
      "resolved_at": null,
      "blocked_at": "2026-03-24T10:30:00Z"
    }
  ]
}
```

---

## Part 4: Task Dependency & Blocking States

### The Problem

Tasks within an MVI (and across MVIs within a wave) have dependencies. Some are known at planning time. Others are discovered during execution. The system must:

1. Track what is blocked and why
2. Automatically resume when blockers are resolved
3. Clearly communicate to the human what is needed
4. Never deadlock (circular dependency detection)

### Task Status Extension

The existing task statuses are extended:

```
Existing:  pending → running → completed | failed
Extended:  pending → running → completed | failed | blocked

blocked substates (stored in blocker.type):
  - blocked_on_human      → waiting for human task completion
  - blocked_on_secret     → waiting for credential
  - blocked_on_external   → waiting for external system
  - blocked_on_task       → waiting for another task to complete first
```

### Dependency Declaration

The Planner crow declares dependencies in its output:

```json
{
  "tasks": [
    {
      "id": "t1_meta_setup",
      "name": "Configure Meta Business Account",
      "task_type": "human",
      "human_task_subtype": "configure_ext",
      "human_estimate_hours": 2,
      "dependencies": []
    },
    {
      "id": "t2_template_submit",
      "name": "Submit message template to Meta",
      "task_type": "crow",
      "human_estimate_hours": 1,
      "dependencies": ["t1_meta_setup"],
      "required_secrets": ["whatsapp_api_token"]
    },
    {
      "id": "t3_template_wait",
      "name": "Wait for Meta template approval",
      "task_type": "human",
      "human_task_subtype": "wait_external",
      "dependencies": ["t2_template_submit"]
    },
    {
      "id": "t4_outbound_api",
      "name": "Implement outbound template message endpoint",
      "task_type": "crow",
      "human_estimate_hours": 6,
      "dependencies": ["t3_template_wait"],
      "required_secrets": ["whatsapp_api_token"]
    }
  ]
}
```

### Murder's Dispatch Algorithm (Extended)

```python
def determine_next_actions(wave, mvi):
    """Murder decides what to do next. Extended with blocking logic."""

    tasks = get_all_tasks(mvi)
    actionable = []

    for task in tasks:
        if task.status in ("completed", "running", "blocked"):
            continue

        # Check dependencies
        unmet_deps = [
            dep for dep in task.dependencies
            if get_task(dep).status != "completed"
        ]

        if unmet_deps:
            if task.status != "blocked":
                mark_blocked(task, "blocked_on_task", unmet_deps)
            continue

        # Check required secrets
        missing_secrets = [
            name for name in task.required_secrets
            if not vault_has_secret(name)
        ]

        if missing_secrets:
            for secret_name in missing_secrets:
                create_human_task(
                    subtype="provide_secret",
                    ask=f"Please provide: {secret_name}",
                    blocks=[task.sk]
                )
            mark_blocked(task, "blocked_on_secret", missing_secrets)
            continue

        # Task is ready
        if task.task_type == "human":
            create_notification(task)
            update_status(task, "notified")
        else:
            actionable.append(task)

    return actionable
```

### Unblocking Flow

```
Human completes a human task or provides a secret
  → API Lambda updates the record (response + steer stored)
  → Secret stored in vault / file stored in S3 (persists regardless of dispatch)
  → DynamoDB Stream fires
  → Murder Lambda wakes up
  → STALENESS GUARD (before any dispatch):
    1. Read wave snapshot → is wave still executing or paused?
       - If delivered/cancelled/steered → log "stale_unblock", do NOT dispatch
       - Human input is NOT lost (vault/S3 persist), available for future waves
    2. Read MVI snapshot → is MVI still executing/queued/blocked?
       - If failed/cancelled/shipped → log "stale_unblock", do NOT dispatch
    3. Check wave budget → is there budget remaining?
       - If exceeded → log "budget_exhausted", notify human, do NOT dispatch
    4. All guards pass → proceed with unblocking
  → Murder scans for blocked tasks that referenced this blocker
  → For each:
    a. Check if ALL blockers are now resolved
    b. If yes: create NEW crow with:
       - Original MVI instructions
       - Previous crow's outcome (what it tried, why it blocked)
       - Human's steer text as "## Human Guidance" (if provided)
       - {{secret:...}} references now resolvable from vault
    c. Dispatch new crow (retry_count incremented)
```

### Why Input Is Never Lost

Even if the wave/MVI has moved on, the human's input persists:

- **Secrets** → stored in vault (`T#{tenant}#VAULT` partition), available to any future wave
- **Files** → stored in S3 (`cawnex-assets-{stage}/`), referenced by asset_key
- **Context** → extracted text stored in `CTX#` records, available via `{{context:...}}`
- **Steer** → stored on human task record, queryable for future planning

The next wave's planner can discover these resources exist and skip creating duplicate human tasks.

### Circular Dependency Detection

Murder validates the dependency graph before starting execution:

```python
def validate_dependency_graph(tasks):
    """Detect circular dependencies before execution starts."""
    visited = set()
    in_stack = set()

    def has_cycle(task_id):
        if task_id in in_stack:
            return True
        if task_id in visited:
            return False
        visited.add(task_id)
        in_stack.add(task_id)
        task = get_task(task_id)
        for dep in task.dependencies:
            if has_cycle(dep):
                return True
        in_stack.remove(task_id)
        return False

    for task in tasks:
        if has_cycle(task.id):
            raise CircularDependencyError(
                f"Circular dependency detected involving task {task.id}"
            )
```

### Blocking State Notification

Every time a task enters a blocked state, a notification is created:

```json
{
  "PK": "T#t_0_71899937#NOTIFICATIONS",
  "SK": "N#2026-03-24T10:30:00Z#n_block_001",

  "type": "task_blocked",
  "severity": "action_required",
  "project_id": "caioo-653d43",
  "project_name": "Caioo",

  "title": "I need your help to continue",
  "body": "The outbound message API cannot proceed because the WhatsApp API token is not working (401 Unauthorized). Please provide a valid token.",

  "action": {
    "type": "respond_human_task",
    "human_task_id": "ht_new_token",
    "deep_link": "/projects/caioo-653d43/human-tasks/ht_new_token"
  },

  "context": {
    "wave_id": "w001",
    "goal": "g2: Outbound Template Message API",
    "blocked_tasks_count": 3,
    "estimated_delay": "Until token provided"
  },

  "status": "unread",
  "ttl": 1745665200,

  "created_at": "2026-03-24T10:30:00Z",
  "entityType": "Notification"
}
```

### Notification Types (Extended)

| Type                    | Severity          | Trigger                                  | Action                    |
| ----------------------- | ----------------- | ---------------------------------------- | ------------------------- |
| `task_blocked`          | action_required   | Task enters blocked state                | Respond to human task     |
| `secret_needed`         | action_required   | Crow needs a credential not in vault     | Provide via vault UI      |
| `secret_expired`        | action_required   | Credential failed (401/403)              | Rotate via vault UI       |
| `external_waiting`      | info              | Task waiting on external party           | No action (informational) |
| `external_resolved`     | info              | External dependency resolved             | No action (work resumes)  |
| `dependency_discovered` | action_required   | Crow discovered new requirement mid-task | Review and provide input  |
| `wave_proposed`         | approval_required | Wave plan ready for review               | Approve / revise / reject |
| `mvi_ready`             | approval_required | MVI ready to ship                        | Review and ship           |
| `budget_warning`        | warning           | 80% of wave budget consumed              | Increase or reduce scope  |

---

## Part 5: End-to-End Flow (Caioo Example)

Here is how the complete system handles Caioo's M1 Wave:

### Phase 1: Wave Planning

```
1. Human approves Wave 1 for M1 (WhatsApp Channel Foundation)
2. Murder dispatches Planner crow for Goal g1
3. Planner identifies tasks:
   - t1: [HUMAN] Buy e-SIM number (physical_action, 5 days)
   - t2: [HUMAN] Configure Meta Business Account (configure_ext, 2 days, depends: t1)
   - t3: [HUMAN] Wait for Meta App approval (wait_external, 7 days, depends: t2)
   - t4: [CROW]  Implement Meta API client library (4h, no dependencies)
   - t5: [HUMAN] Provide WhatsApp API token (provide_secret, depends: t3)

4. Murder dispatches Planner for all goals in parallel
5. After all plans: Murder has the full dependency graph
```

### Phase 2: Parallel Execution

```
Murder's dependency analysis reveals:
  - t4 (Meta API client) has NO dependencies → dispatch immediately
  - g4 tasks (Dashboard) have NO human dependencies → dispatch immediately
  - t1 (buy e-SIM) is human task → notify immediately
  - Everything else is blocked

Actions:
  1. Dispatch implementer crow for t4 (Meta API client library)
  2. Dispatch implementer crow for g4 tasks (Dashboard UI)
  3. Send notification: "I need you to buy an e-SIM number"
  4. Mark t2, t3, t5 as blocked_on_task
  5. Mark g2/g3/g5 crow tasks as blocked_on_secret (whatsapp_api_token)
```

### Phase 3: Human Unblocking (Rolling)

```
Day 1: Eduardo buys e-SIM, responds to human task with phone number
  → Murder unblocks t2 (Meta Business setup)
  → Murder sends notification: "Please configure Meta Business Account"

Day 3: Eduardo configures Meta, responds
  → Murder unblocks t3 (wait for approval)
  → Murder sends notification: "Meta is reviewing your app. I'll check automatically."
  → Murder schedules CHECK record (poll in 24h)

Day 10: Checker crow polls Meta API → approved
  → Murder unblocks t5 (provide token)
  → Murder sends notification: "Meta approved your app. Please provide the API token."

Day 10: Eduardo provides token
  → Token stored in vault
  → Murder unblocks ALL g2/g3/g5 tasks that need whatsapp_api_token
  → Murder dispatches crow tasks for g2, g3, g5 in parallel

Meanwhile: g4 (Dashboard) and t4 (API client) completed on Day 2
```

### Phase 4: Feedback Loop (Token Failure)

```
Day 11: Implementer crow for g2 (outbound API) runs
  → Calls WhatsApp API with resolved {{secret:whatsapp_api_token}}
  → Gets 403: "Token does not have messages:send scope"
  → Crow reports blocked_on_secret with clear error

Murder reacts:
  → Creates human task: "Your WhatsApp token needs the messages:send permission scope.
    Please generate a new token with this scope in Meta Business Manager."
  → Notification sent with deep link
  → Other tasks using the same token: continue if they don't need send scope,
    or get blocked too

Eduardo provides corrected token
  → Vault secret rotated (PUT /vault/secrets/whatsapp_api_token/rotate)
  → Murder re-dispatches the blocked crow
  → Execution continues
```

---

## Part 6: How This Fits Into the Existing 6 Contracts

### Contract Extensions

| Contract   | Current                           | Extension                                                |
| ---------- | --------------------------------- | -------------------------------------------------------- |
| Contract 1 | API creates wave + MVI snapshots  | Also creates human task snapshots from planner output    |
| Contract 2 | Murder assigns crow tasks         | Murder also creates human tasks + checks vault           |
| Contract 3 | Worker completes crow tasks       | Worker can set blocked*on*\* status instead of completed |
| Contract 4 | Murder marks MVI ready_to_ship    | Only when all tasks (crow AND human) are completed       |
| Contract 5 | API ships MVI                     | No change                                                |
| Contract 6 | Stream updates materialized views | Also processes human task completions and unblocking     |

### New Contract: Contract 7 — Human Task Response

```
Writer:      API Lambda
Trigger:     HTTP POST from user (human task response)
Mechanism:   TransactWriteItems

Records updated:

  1. Human task snapshot
     PK: T#{tenant}#P#{project}
     SK: S#{wave}#m#{murder}#ht_{task_id}
     {
       status: "completed",
       response: { ... } | { "secret_ref": "name", "stored": true },
       completed_at: <timestamp>
     }

  2. Secret (if subtype = provide_secret)
     PK: T#{tenant}#VAULT
     SK: P#{project}#{secret_name}
     { encrypted_value, metadata }

  3. EVT record
     {
       type: "human_task_completed",
       message: "Eduardo provided the WhatsApp API token",
       color: "blue"
     }

Postconditions:
  - Human task status = completed
  - Secret stored in vault (if applicable)
  - DynamoDB Stream fires → Murder unblocks dependent tasks
  - Notification badge decremented
```

### New Contract: Contract 8 — External Status Check

```
Writer:      Scheduled Lambda (hourly)
Trigger:     EventBridge schedule rule
Mechanism:   Query CHECK records, dispatch lightweight crows

Flow:
  1. Query: PK begins_with T#, SK begins_with CHECK#, ttl <= now
  2. For each CHECK record:
     a. Dispatch a lightweight "checker" crow
     b. Checker calls external API to check status
     c. If resolved: delete CHECK, update blocked task, write EVT
     d. If not resolved: write new CHECK with extended TTL
  3. Max check attempts: 30 (prevents indefinite polling)
  4. After max attempts: escalate to human
```

---

## Part 7: New DynamoDB Records Summary

### New SK Patterns (under existing PK: `T#{tenant}#P#{project}`)

```
HUMAN TASKS (same tree as crow snapshots):
  S#{wave}#m#{murder}#ht_{task_id}                → human task snapshot

EXTERNAL CHECKS:
  CHECK#{iso_timestamp}#{check_id}                → scheduled status check

POST-PROCESSING:
  PROCESS#{human_task_id}                         → file processing status

EXTRACTED CONTEXT:
  CTX#{human_task_id}                             → extracted text/metadata from uploaded files
                                                    (referenced by Crows via {{context:ht_id}})

EVENTS (new types):
  EVT#{wave}#{timestamp}                          → human_task_created, human_task_completed,
                                                    task_blocked, task_unblocked,
                                                    secret_requested, external_check,
                                                    verification_passed, verification_failed
```

### New Partition: `T#{tenant}#VAULT`

```
  P#{project}#{secret_name}                       → project-scoped secret
  TENANT#{secret_name}                            → tenant-scoped secret
```

### S3 Bucket: `cawnex-assets-{stage}`

```
  T/{tenant_id}/P/{project_id}/assets/{ht_id}/   → uploaded files
  T/{tenant_id}/P/{project_id}/assets/{ht_id}/extracted/  → post-processing output
```

### Extended Enums

```python
class TaskType(str, Enum):
    CROW = "crow"
    HUMAN = "human"

class HumanTaskSubtype(str, Enum):
    PROVIDE_SECRET = "provide_secret"
    UPLOAD_ASSET = "upload_asset"
    FILL_CONTENT = "fill_content"
    CONFIGURE_EXT = "configure_ext"
    PHYSICAL_ACTION = "physical_action"
    WAIT_EXTERNAL = "wait_external"
    CONFIRM = "confirm"

class HumanTaskStatus(str, Enum):
    PENDING = "pending"
    NOTIFIED = "notified"
    IN_PROGRESS = "in_progress"
    RESPONDED = "responded"          # Human submitted, pending verification
    VERIFYING = "verifying"          # Verification crow dispatched
    VERIFICATION_FAILED = "verification_failed"
    COMPLETED = "completed"
    EXPIRED = "expired"

class InputFieldType(str, Enum):
    STRING = "string"
    TEXT = "text"
    SECRET = "secret"
    FILE = "file"
    URL = "url"
    EMAIL = "email"
    COLOR = "color"
    ENUM = "enum"
    BOOLEAN = "boolean"
    NUMBER = "number"

class PostProcessingType(str, Enum):
    NONE = "none"
    EXTRACT_TEXT = "extract_text"     # PDF/doc → plain text for crow context
    EXTRACT_META = "extract_meta"    # Image → dimensions, format, color profile

class BlockerType(str, Enum):
    BLOCKED_ON_HUMAN = "blocked_on_human"
    BLOCKED_ON_SECRET = "blocked_on_secret"
    BLOCKED_ON_EXTERNAL = "blocked_on_external"
    BLOCKED_ON_TASK = "blocked_on_task"

class NotificationType(str, Enum):
    # Existing
    WAVE_PROPOSED = "wave_proposed"
    MVI_READY = "mvi_ready"
    BUDGET_WARNING = "budget_warning"
    # New
    TASK_BLOCKED = "task_blocked"
    SECRET_NEEDED = "secret_needed"
    SECRET_EXPIRED = "secret_expired"
    EXTERNAL_WAITING = "external_waiting"
    EXTERNAL_RESOLVED = "external_resolved"
    DEPENDENCY_DISCOVERED = "dependency_discovered"
    VERIFICATION_FAILED = "verification_failed"
```

---

## Part 8: Implementation Priority

### What to Build First (V1 Scope)

| Priority | Component                          | Why First                                                             |
| -------- | ---------------------------------- | --------------------------------------------------------------------- |
| P0       | Human task records + API endpoints | Without this, no real project can start (every goal has human deps)   |
| P0       | Input schema with validation       | Inputs must be validated before Crows use them — garbage in = failure |
| P0       | Vault (DynamoDB + KMS)             | Crows need credentials to call external APIs                          |
| P0       | Murder blocking logic              | Murder must skip blocked tasks and dispatch non-blocked ones          |
| P0       | Notification for human tasks       | Human must know what the AI needs                                     |
| P1       | File upload (S3 presigned URLs)    | Logo images, reference PDFs are common from Day 1                     |
| P1       | Secret resolution in Worker        | Worker must resolve {{secret:...}} before crow execution              |
| P1       | Feedback loop (credential failure) | Most common real-world failure mode                                   |
| P1       | Unblocking flow (stream-triggered) | Automatic resume when human provides input                            |
| P1       | Verification step (crow checks)    | Don't trust "I configured DNS" — verify it                            |
| P2       | PDF/doc post-processing            | Extract text for Crow context — can paste text manually in V1         |
| P2       | External check pattern             | Needed for Meta approval wait, but can be manual in V1                |
| P2       | iOS human task UI                  | Can use existing notification UI + API calls for V1                   |
| P2       | Circular dependency detection      | Good practice but unlikely in V1 with simple task graphs              |

### What NOT to Build in V1

- Secret rotation reminders (manual is fine)
- Automatic secret expiry detection (react to failures, don't predict)
- Complex dependency graph visualization (list view is enough)
- Multi-user task assignment (single founder for now)
- Webhook-based external status checks (polling is simpler)
- Advanced file processing (OCR, image recognition — simple text extraction only)

---

## Part 9: CDK Infrastructure Changes

### KMS Key

```typescript
const vaultKey = new kms.Key(this, "VaultKey", {
  alias: `cawnex-vault-${stage}`,
  description: "Encrypts project secrets in the vault",
  enableKeyRotation: true,
});
```

### Lambda Permissions (Worker)

```typescript
workerLambda.addToRolePolicy(
  new iam.PolicyStatement({
    actions: ["kms:Decrypt"],
    resources: [vaultKey.keyArn],
  })
);
```

### Lambda Permissions (API)

```typescript
apiLambda.addToRolePolicy(
  new iam.PolicyStatement({
    actions: ["kms:Encrypt"],
    resources: [vaultKey.keyArn],
  })
);
```

### S3 Bucket (Assets)

```typescript
const assetsBucket = new s3.Bucket(this, "AssetsBucket", {
  bucketName: `cawnex-assets-${stage}`,
  encryption: s3.BucketEncryption.S3_MANAGED,
  blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
  cors: [
    {
      allowedMethods: [s3.HttpMethods.PUT],
      allowedOrigins: ["*"], // iOS uploads directly
      allowedHeaders: ["Content-Type"],
      maxAge: 300,
    },
  ],
  lifecycleRules: [
    {
      prefix: "T/",
      transitions: [
        {
          storageClass: s3.StorageClass.INFREQUENT_ACCESS,
          transitionAfter: Duration.days(90),
        },
      ],
    },
  ],
});
```

### Scheduled Lambda (Checker)

```typescript
const checkerLambda = new lambda.Function(this, "Checker", {
  runtime: lambda.Runtime.PYTHON_3_12,
  handler: "handler.handler",
  code: lambda.Code.fromAsset("lambdas/orchestration/checker"),
  timeout: Duration.minutes(1),
  environment: { TABLE_NAME: table.tableName },
});

new events.Rule(this, "CheckerSchedule", {
  schedule: events.Schedule.rate(Duration.hours(1)),
  targets: [new targets.LambdaFunction(checkerLambda)],
});
```

### Processing Lambda (File Post-Processing)

```typescript
const processingLambda = new lambda.Function(this, "FileProcessor", {
  runtime: lambda.Runtime.PYTHON_3_12,
  handler: "handler.handler",
  code: lambda.Code.fromAsset("lambdas/orchestration/file-processor"),
  timeout: Duration.minutes(5),
  memorySize: 512,
  environment: {
    TABLE_NAME: table.tableName,
    ASSETS_BUCKET: assetsBucket.bucketName,
  },
});

assetsBucket.grantReadWrite(processingLambda);
table.grantReadWriteData(processingLambda);
```

---

## Design Principles

1. **Human tasks are first-class** — same snapshot tree, same status tracking, same audit trail as crow tasks
2. **Inputs are validated, not trusted** — every field has schema validation; files checked for type and size; configs verified by Crows
3. **Crows never see raw secrets** — resolution happens in the Worker, injection via environment, never in prompts
4. **Blocked is not failed** — blocked tasks wait and resume automatically, failed tasks need retry logic
5. **Parallel by default** — Murder dispatches everything that is not blocked, maximizing throughput
6. **Notifications explain why** — every blocked notification tells the human exactly what is needed and which goals it unblocks
7. **Feedback loops are expected** — credential failures, new discoveries, and external waits are designed flows, not exceptions
8. **Verify, don't trust** — human says "I configured DNS"? A Crow checks. Token provided? Test it before using it in production tasks
9. **Files flow through S3, not APIs** — presigned URLs for upload, asset keys for reference, post-processing for extraction
10. **No polling loops** — CHECK records with TTL + scheduled Lambda, not busy-wait
11. **Vault is simple** — DynamoDB + KMS for V1, migrate to Secrets Manager only if needed
12. **Everything is auditable** — blocker_history on every task, EVT records for every state change
