# Screen Specifications — Cawnex iOS App

> Reverse-engineered from the implemented `.pen` design file.
> Each spec describes what the screen shows, its data requirements, user actions, and navigation targets.

---

## Global Layout

- **Device frame:** 393 × 852 pt (iPhone 15 Pro)
- **Theme:** Dark mode (background `#0A0A0A`, cards `#1A1C1E`)
- **Font stack:** Inter (UI), JetBrains Mono (data/code)
- **Primary color:** `#7C3AED` (crow purple)
- **Screen structure:** StatusBar → Content → [TabBar | ActionBar | InputBar]

---

## S01 — Splash

**Purpose:** App launch, brand moment.

**Layout:**

- Full-screen centered, `$--background`
- Logo container (centered vertically + horizontally)
- Crow logo animation

**Data:** None.

**Actions:**

- Auto-transition → S02 Sign In (after animation)

**Navigation:** S01 → S02

---

## S02 — Sign In

**Purpose:** Authentication entry point.

**Layout:**

- StatusBar
- Content area (centered vertically, 32px horizontal padding)
  - Logo + app name
  - "Sign In" heading
  - Apple Sign In button (full width)
  - Divider "or"
  - Email input field
  - Password input field
  - "Sign In" primary button
  - "Don't have an account? Sign Up" link

**Data:** None (auth form).

**Actions:**
| Action | Target |
|--------|--------|
| Tap Apple Sign In | Apple OAuth → S10 Dashboard |
| Tap Sign In (email) | Cognito auth → S10 Dashboard |
| Tap Sign Up | Registration flow (TBD) |

**API:** `POST /auth/sign-in`, Apple Sign In via Cognito

**Navigation:** S02 → S10

---

## S10 — Dashboard

**Purpose:** Global home. Shows all projects with progress and budget at a glance.

**Layout:**

- StatusBar
- Scroll Content (16px top, 20px sides)
  - **Header:** greeting + user name | bell button (→ S70) + add button (→ S11)
  - **Projects Section:**
    - Section header: "Your Projects" + sort/filter controls
    - **Project Card** (repeated per project):
      - Top row: project name + active Crow count badge
      - One-liner description
      - **Pipeline Bar:** stacked horizontal bar (done/active/refined/draft in tones of same color)
      - Summary text: "Tasks · 5 done · 3 active · 4 refined · 6 draft"
      - **Budget Row:** spent amount | stacked bar | saved amount
- TabBar (Projects active)

**Data per Project Card:**
| Field | Type | Example |
|-------|------|---------|
| name | string | "Cawnex Platform" |
| description | string | "Multi-agent AI orchestration platform" |
| tasksDone | number | 5 |
| tasksActive | number | 3 |
| tasksRefined | number | 4 |
| tasksDraft | number | 6 |
| creditsSpent | currency | $182 |
| humanEquivSaved | currency | ~$14k |
| activeCrowCount | number | 3 |

**Actions:**
| Action | Target |
|--------|--------|
| Tap "+" button | S11 Create Project |
| Tap bell button | S70 Notifications |
| Tap project card | S12 Project Hub |
| Tab: Murders | S40 Murders |
| Tab: Skills | S50 Skills |
| Tab: Settings | S60 Settings |

**Navigation:** S10 → S11, S70, S12, S40, S50, S60

---

## S40 — Murders

**Purpose:** Manage all Murders across projects. Browse marketplace for templates.

**Layout:**

- StatusBar
- Scroll Content
  - **Header:** "Murders" title + "+ New" button (→ S41)
  - **Your Murders section:**
    - **Murder Card** (repeated):
      - Top row: bird icon + murder name + type badge (Dev/Editorial/Social) + active dot (green/gray)
      - **Behavior Status:** dark inset panel showing current Crow behavior states (e.g., "Planner: Planning · Implementer: Building")
      - **Crow row:** avatar chips for each Crow in the murder
      - **Stats row:** task count + cost + active execution indicator
    - Divider
  - **Marketplace section:**
    - Header: store icon + "Marketplace" + "See all" link
    - Description: "Community murder templates ready to install"
    - **Marketplace Card** (repeated):
      - Name + crow count + install count
      - Description
      - Meta row: star rating + download badge

- TabBar (Murders active)

**Data per Murder Card:**
| Field | Type | Example |
|-------|------|---------|
| name | string | "Dev Murder" |
| type | enum | Dev, Editorial, Social, Infra, Data, Custom |
| status | enum | active, idle, error |
| crowBehaviorStates | array | [{name: "Planner", state: "Planning"}, ...] |
| crows | array | [{name, role, avatarIcon}] |
| activeTaskCount | number | 3 |
| totalCost | currency | $142 |

**Actions:**
| Action | Target |
|--------|--------|
| Tap "+ New" | S41 Create Murder |
| Tap murder card | S41 (edit mode) |
| Tap marketplace card | Install flow (TBD) |

**Navigation:** S40 → S41

---

## S50 — Skills

**Purpose:** Skill library — reusable capabilities attached to Crows. Browse + marketplace.

**Layout:**

- StatusBar
- Scroll Content
  - **Header:** "Skills" title + "+ New Skill" button (→ S51)
  - Description: "Skills define what crows can do. Attach skills to murders to shape their capabilities."
  - **Filter Chips:** All (active) | Dev | Editorial | Social | Custom
  - **Your Skills section:**
    - **Skill Card** (repeated):
      - Top row: icon (lucide) + skill name + category badge
      - Description text
      - Meta row: input count + "Used by N crows" + behavior annotation badges (RO/Dest/Idem)
  - Divider
  - **Marketplace section:**
    - Header: store icon + "Marketplace" + "See all" link
    - Description: "Community skills ready to add to your murders"
    - Marketplace Skill Cards (same format with install button)

- TabBar (Skills active)

**Data per Skill Card:**
| Field | Type | Example |
|-------|------|---------|
| name | string | "generate-rest-crud" |
| displayName | string | "REST CRUD Generator" |
| icon | string (lucide) | "code" |
| category | enum | Dev, Editorial, Social, Custom |
| description | string | "Generate REST CRUD endpoints..." |
| inputParamCount | number | 3 |
| usedByCrowCount | number | 2 |
| behaviorAnnotations | object | {readOnly: false, destructive: false, idempotent: true} |

**Actions:**
| Action | Target |
|--------|--------|
| Tap "+ New Skill" | S51 Add Skill |
| Tap skill card | S51 (edit mode) |
| Tap filter chip | Filter skills by category |
| Tap marketplace card | Install flow (TBD) |

**Navigation:** S50 → S51

---

## S60 — Settings

**Purpose:** Account settings, billing access, integrations.

**Layout:**

- StatusBar
- Scroll Content
  - **Header:** "Settings" title
  - **Settings rows** (grouped):
    - Account section: profile, email, password
    - Credits & Billing row (→ S61)
    - Webhooks row
    - API Keys row
    - Notifications preferences row
    - About / Support row
- TabBar (Settings active)

**Actions:**
| Action | Target |
|--------|--------|
| Tap Credits & Billing | S61 |
| Other rows | In-screen or modal (TBD) |

**Navigation:** S60 → S61

---

## S11 — Create Project

**Purpose:** Quick project creation. Minimal fields — AI refines during Vision setup.

**Layout:**

- StatusBar
- NavBarModal (Cancel / New Project / Create)
- Scroll Content (24px top, 20px sides)
  - **Hero:** "What are we building?" + subtitle explaining AI will shape everything else
  - **Name Field:** label "PROJECT NAME" + input (48px height)
  - **One-Liner Field:** label "ONE-LINER" + input + hint "Optional — AI will refine this during Vision setup"
  - **Murder Section:**
    - Label "MURDERS"
    - Hint: "Which AI teams should work on this project?"
    - **Chip row:** Dev Murder (selected, purple) | Editorial | Social | Infra | Data
    - Note: "Dev Murder is selected by default. Tap to toggle."
- CTA Bar: "Create Project" primary button + "Start with Vision AI" secondary

**Data (form):**
| Field | Type | Required |
|-------|------|----------|
| name | string | yes |
| oneLiner | string | no |
| murders | string[] | yes (default: ["dev"]) |

**Actions:**
| Action | Target |
|--------|--------|
| Tap Cancel | Dismiss → S10 |
| Tap Create | POST project → S12 Project Hub |
| Tap murder chip | Toggle selection |

**API:** `POST /projects`

**Navigation:** S11 → S12

---

## S70 — Notifications

**Purpose:** Actionable notification center. Founder's inbox for approvals, alerts, and status updates.

**Layout:**

- StatusBar
- NavBarBack (← Notifications)
- **Filter Tabs:** All (active) | Action | Info
- Scroll Content
  - **NEEDS ACTION section:**
    - **Notification Card — Task Approval:**
      - Left icon (amber clock) + title + timestamp
      - Inline action buttons: Approve (green) | Review (muted)
    - **Notification Card — MVI Ready:**
      - Left icon (green check) + title + timestamp
      - Inline action buttons: Ship (green) | Review (muted)
    - **Notification Card — Task Failed:**
      - Left icon (red x) + title + timestamp + red border accent
      - Inline action buttons: Retry (amber) | View (muted)
  - **RECENT section:**
    - **Notification Card — MVI Shipped:** icon + title + chevron (→ deep link)
    - **Notification Card — Credits Low:** amber border + icon + title + chevron
    - **Notification Card — Vision Ready:** icon + title + chevron

**Data per Notification:**
| Field | Type | Example |
|-------|------|---------|
| id | string | UUID |
| type | enum | task_approval, mvi_ready, task_failed, mvi_shipped, credits_low, vision_ready |
| title | string | "RBAC middleware needs approval" |
| timestamp | datetime | "2 min ago" |
| category | enum | action, info |
| deepLink | string | Target screen + entity ID |
| actions | array | [{label, type, color}] |

**Actions:**
| Action | Target |
|--------|--------|
| Tap Approve | Approve task inline |
| Tap Review | Navigate to entity (deep link) |
| Tap Ship | Navigate to S32 MVI Blackboard |
| Tap Retry | Re-queue failed task |
| Tap notification chevron | Deep link to relevant screen |
| Tap filter tab | Filter by category |

**Navigation:** S70 → S33 (task), S32 (MVI), S34 (PR), S31 (goal), S61 (credits)

---

## S42 — Create Crow

**Purpose:** Define a new Crow — identity, model, skills, personality, constraints.

**Layout:**

- StatusBar
- NavBarModal (Cancel / New Crow / Save)
- Scroll Content (20px sides, 28px section gaps)
  - **IDENTITY section:**
    - Name field (slug-style input)
    - Role field (e.g., "Implementer")
    - Goal field (e.g., "Write clean, tested code")
  - **MODEL section:**
    - Model picker card (icon + model name + provider + chevron)
    - Hint: "Choose based on task complexity and cost"
  - **DESCRIPTION section:**
    - Textarea (68px height)
    - Hint: "The Murder reads this to decide when to deploy this crow"
  - **SKILLS section:**
    - Hint: "What capabilities does this crow have?"
    - Chip row: skill chips (selected = purple, unselected = muted)
  - **BACKSTORY section:**
    - Textarea (100px height)
    - Hint: "Shapes how this crow approaches problems and makes decisions"
  - **CONSTRAINTS section:**
    - Textarea (80px height, red border accent)
    - Hint (red): "Hard boundaries — these override all other instructions"
  - **Advanced section:**
    - Collapsible header with chevron
    - Card with: temperature slider, max tokens input, retry behavior toggles

**Data (form):**
| Field | Type | Required |
|-------|------|----------|
| name | string | yes |
| role | string | yes |
| goal | string | yes |
| model | enum | yes |
| description | string | yes |
| skills | string[] | no |
| backstory | string | no |
| constraints | string | no |
| temperature | number | no (default: 0.7) |
| maxTokens | number | no (default: 4096) |

**Actions:**
| Action | Target |
|--------|--------|
| Tap Cancel | Dismiss → S41 |
| Tap Save | Save crow to murder → S41 |
| Tap model picker | Model selection sheet |
| Tap skill chip | Toggle selection |

**API:** `POST /murders/:murderId/crows`

**Navigation:** S42 → S41

---

## S41 — Create Murder

**Purpose:** Configure a Murder — identity, crows, coordination flow, quality gates, escalation, budget.

**Layout:**

- StatusBar
- NavBarModal (Cancel / New Murder / Save)
- Scroll Content (20px sides, 28px section gaps)
  - **IDENTITY section:**
    - Name field
    - Type picker (Dev | Editorial | Social | Infra | Data | Custom)
  - **Description field:**
    - Textarea (64px)
  - **CROWS section:**
    - Header: "CROWS" + "+ Add Crow" button (→ S42)
    - Hint: "Select which crows belong to this murder"
    - **Crow Card** (repeated, purple border):
      - Avatar + name + role
      - Model badge + skill count
      - Remove button (x)
  - **MURDER PROMPT section:**
    - Textarea (100px)
    - Hint: "Injected as context into every crow's system prompt"
  - **CROW FLOW section:**
    - Hint: "Define the handoff chain. Murder uses this as guidance but can deviate when context demands."
    - Flow Step cards connected by arrow separators:
      - Step card: # badge + crow name + role + produces/requires labels
    - Visual chain: Step 1 → Step 2 → Step 3 → Step 4

  _(scrolled variation S41 continues below)_
  - **QUALITY GATES section:**
    - Card with toggle rows:
      - CI must pass (on)
      - Test coverage > threshold (on, 80% input)
      - Lint checks (on)
  - **ESCALATION RULES section:**
    - Card (red border accent) with:
      - Max retries per crow (input: 3)
      - Failure action picker (Retry → Fallback Crow → Alert Human)
      - Alert after N minutes stuck (input: 30)
  - **BUDGET LIMITS section:**
    - Card with:
      - Max credits per task (input: 50)
      - Max credits per execution (input: 200)
      - Alert at % threshold (input: 80%)

**Data (form):**
| Field | Type | Required |
|-------|------|----------|
| name | string | yes |
| type | enum | yes |
| description | string | no |
| crows | CrowRef[] | yes (min 1) |
| murderPrompt | string | no |
| crowFlow | FlowStep[] | no |
| qualityGates | QualityGateConfig | no |
| escalationRules | EscalationConfig | no |
| budgetLimits | BudgetConfig | no |

**Actions:**
| Action | Target |
|--------|--------|
| Tap Cancel | Dismiss → S40 |
| Tap Save | Save murder → S40 |
| Tap "+ Add Crow" | S42 Create Crow |
| Tap crow card (x) | Remove crow |
| Drag flow steps | Reorder flow |

**API:** `POST /murders`, `PUT /murders/:id`

**Navigation:** S41 → S42, S40

---

## S51 — Add Skill

**Purpose:** Define a new Skill — identity, input schema, behavior, security, execution, test.

**Layout:**

- StatusBar
- NavBarModal (Cancel / New Skill / Save)
- Scroll Content (20px sides, 28px section gaps)
  - **IDENTITY section:**
    - Name field (slug: `read-file`)
    - Display Name field ("Read File")
    - Icon picker (lucide icon) + Category picker (Dev/Editorial/Social/Shell)
    - Description textarea + purple hint: "Critical — this is what the LLM reads to decide when to invoke this skill"
    - Tags: chip input (dev, backend + "+ Add tag")
  - **INPUT PARAMETERS section:**
    - Parameter cards (repeated):
      - Grip handle (drag) + param name + type badge (string/number/boolean) + required badge + delete
    - "+ Add Parameter" link
    - Strict Mode toggle row
  - **BEHAVIOR section:**
    - Card with toggle rows + descriptions:
      - Read Only (on) — "No mutations or side effects"
      - Destructive (off) — "Irreversible changes"
      - Idempotent (on) — "Safe to retry"

  _(scrolled variation S51 continues below)_
  - **SECURITY & PERMISSIONS section:**
    - Card with:
      - Permission Level picker (Read/Write/Admin) + colored badge
      - Requires Human Approval toggle (off)
      - Sandboxed toggle (on)
      - Rate Limits: requests/min (60) + requests/hour (500)
  - **EXECUTION section:**
    - Card with:
      - Type chips: Native (selected) | API | MCP | Shell
      - Timeout input (30000 ms)
      - Max Retries input (3)
  - **TEST section:**
    - Card with:
      - Sample Input (JSON editor, monospace, dark inset)
      - "Run Test" purple button
      - Output area: green success "Schema valid · Response in 42ms"

**Data (form):**
| Field | Type | Required |
|-------|------|----------|
| name | string (slug) | yes |
| displayName | string | yes |
| icon | string (lucide) | no |
| category | enum | yes |
| description | string | yes |
| tags | string[] | no |
| inputParams | ParamDef[] | no |
| strictMode | boolean | no (default: false) |
| readOnly | boolean | no (default: false) |
| destructive | boolean | no (default: false) |
| idempotent | boolean | no (default: true) |
| permissionLevel | enum (read/write/admin) | yes |
| requiresHumanApproval | boolean | no (default: false) |
| sandboxed | boolean | no (default: true) |
| rateLimitPerMin | number | no |
| rateLimitPerHour | number | no |
| executionType | enum (native/api/mcp/shell) | yes |
| timeout | number (ms) | no (default: 30000) |
| maxRetries | number | no (default: 3) |
| sampleInput | JSON | no |

**Actions:**
| Action | Target |
|--------|--------|
| Tap Cancel | Dismiss → S50 |
| Tap Save | Save skill → S50 |
| Tap "+ Add Parameter" | Append param row |
| Tap param delete | Remove param |
| Drag param handle | Reorder params |
| Tap "Run Test" | Execute skill with sample input |
| Tap execution type chip | Select type |

**API:** `POST /skills`, `PUT /skills/:id`

**Navigation:** S51 → S50

---

## S12 — Project Hub

**Purpose:** Central routing screen for a project. Stats overview, document cards, backlog pipeline, assigned murders, cost footer.

**Layout:**

- StatusBar
- Scroll Content (8px top, 20px sides)
  - **Nav Row:** ← back + project name | dashboard icon
  - **Project Header:** project name (22px bold) + one-liner description
  - **Stats Row** (4 equal cards):
    - Progress: 40% (purple)
    - Tasks: 12/30 (green)
    - Pending: 3 (amber)
    - ROI: 78x (orange)
  - **DOCUMENTS section:**
    - Label: "DOCUMENTS"
    - **Doc Cards Row** (2×2 grid or horizontal scroll):
      - Vision (purple border accent) — icon + name + section count + completion status
      - Architecture (blue border) — same pattern
      - Glossary (green border) — same pattern
      - Design System (orange border) — same pattern
  - **Backlog Card** (green border accent):
    - Top row: calendar icon + "Backlog" + "2 milestones" + chevron (→ S24)
    - Pipeline Bar (green tones: done/active/refined/draft)
    - Legend: 4 color dots with labels
    - Summary: "3 active · 5 of 18 MVIs shipped"
  - **Agents Card:**
    - Top row: bird icon + "Agents" + "Manage" link
    - Murder rows (compact): Dev Murder (active dot) | Editorial Murder (gray dot)
  - **Cost Row** (card, bottom):
    - Top: dollar icon + "Project Cost" | "78x ROI" (orange)
    - Bar: $182 (left) | stacked bar | ~$14k (right)

**Data:**
| Field | Type | Example |
|-------|------|---------|
| project.name | string | "Cawnex Platform" |
| project.description | string | "Multi-agent AI..." |
| stats.progress | percentage | 40% |
| stats.tasksDone | number | 12 |
| stats.tasksTotal | number | 30 |
| stats.pendingApprovals | number | 3 |
| stats.roi | number | 78 |
| documents | array | [{type, sectionCount, completion, accentColor}] |
| backlog.activeMilestones | number | 3 |
| backlog.mvisShipped | number | 5 |
| backlog.mvisTotal | number | 18 |
| backlog.pipeline | object | {done, active, refined, draft} |
| murders | array | [{name, type, isActive}] |
| cost.spent | currency | $182 |
| cost.humanEquiv | currency | ~$14k |
| cost.roi | number | 78 |

**Actions:**
| Action | Target |
|--------|--------|
| Tap ← back | S10 Dashboard |
| Tap Vision card | S20 Vision Document |
| Tap Architecture card | S21 Architecture Document |
| Tap Glossary card | S22 Glossary Document |
| Tap Design System card | S23 Design System Document |
| Tap Backlog card | S24 Backlog |
| Tap "Manage" agents | S40 Murders (filtered) |

**Navigation:** S12 → S20, S21, S22, S23, S24, S40

---

## S61 — Credits & Billing

**Purpose:** ROI dashboard, credit balance, usage breakdown, per-project budgets, per-crow costs.

**Layout:**

- StatusBar
- Scroll Content (8px top, 20px sides)
  - **Nav Row:** ← back + "Credits & Billing"
  - **ROI Summary Card** (orange border accent):
    - Header: trending-up icon + "Return on Investment"
    - Main row: ROI multiplier (large, orange) | spent vs saved
    - Details: AI minutes vs human hours, AI cost vs human cost, time saved
  - **Credit Balance Card** (purple border):
    - Header: "Credit Balance" + "Purchase" button
    - Balance row: available credits (large) + total purchased
    - Bar: usage % visualization
    - Meta: estimated days remaining + monthly burn rate
  - **Project Budgets section:**
    - Header: "Project Budgets" + "Set limits" link
    - Per-project cards: name + usage bar + spent/allocated
  - **Cost Breakdown section:**
    - Header: "Cost Breakdown" + period selector
    - Per-project cards: name + breakdown by category (AI tokens, repo ops, workflows)
  - **Crow Costs section:**
    - Card with per-crow rows: name + model + tokens used + cost

**Data:**
| Field | Type | Example |
|-------|------|---------|
| roi.multiplier | number | 78 |
| roi.aiMinutes | number | 45 |
| roi.humanHours | number | 58 |
| roi.aiCost | currency | $182 |
| roi.humanCost | currency | $14,200 |
| credits.available | number | 4,200 |
| credits.total | number | 5,000 |
| credits.daysRemaining | number | 42 |
| credits.monthlyBurn | number | 800 |
| projectBudgets | array | [{name, spent, allocated}] |
| costBreakdown | array | [{project, categories: {ai, repo, workflow}}] |
| crowCosts | array | [{name, model, tokens, cost}] |

**Actions:**
| Action | Target |
|--------|--------|
| Tap ← back | S60 Settings |
| Tap "Purchase" | Purchase flow (S62 — TBD) |
| Tap "Set limits" | Budget config sheet |

**Navigation:** S61 → S60

---

## S20 — Vision Document

**Purpose:** AI-guided conversational document builder for project vision. Purple accent (#7C3AED).

**Layout:**

- StatusBar
- Scroll Content (8px top, 20px sides)
  - **Nav Row:** ← back + "Vision" | status chip (e.g., "3/6 sections")
  - **Doc Preview Banner** (purple border):
    - Top: doc icon + "Vision Document" + section completion
    - Progress row: bar + "3 of 6 sections complete"
  - **Chat Area:**
    - AI message bubble (left-aligned, muted bg):
      - Crow avatar + "Vision AI" label
      - Message text (questions about the project)
    - User message bubble (right-aligned, purple bg):
      - Message text
    - AI message bubble (synthesized response):
      - Structured section content
  - "Preview Document" button (purple outline)
- InputBar: sparkles icon + text field + send button

**Data:**
| Field | Type | Example |
|-------|------|---------|
| document.type | enum | vision |
| document.sections | array | [{title, content, status}] |
| document.sectionsComplete | number | 3 |
| document.sectionsTotal | number | 6 |
| chatMessages | array | [{role, content, timestamp}] |

**Sections (Vision):**

1. Problem Statement
2. Target User
3. Core Value Proposition
4. Key Features
5. Success Metrics
6. Non-Goals

**Actions:**
| Action | Target |
|--------|--------|
| Tap ← back | S12 Project Hub |
| Send message | AI processes and synthesizes |
| Tap "Preview Document" | Full document preview sheet |

**API:** `POST /projects/:id/documents/vision/chat`

**Navigation:** S20 → S12

---

## S21 — Architecture Document

**Purpose:** AI-guided technical architecture document. Blue accent (#3B82F6).

**Layout:** Same as S20 with blue accent color.

**Sections (Architecture):**

1. System Overview
2. Core Services
3. Data Model
4. API Design
5. Infrastructure
6. Security Model
7. Integration Points

**Navigation:** S21 → S12

---

## S22 — Glossary Document

**Purpose:** AI-guided glossary extraction. Green accent (#10B981).

**Layout:** Same chat pattern as S20 with green accent. AI extracts terms from Vision + Architecture docs, user approves/edits each term.

**Navigation:** S22 → S12

---

## S23 — Design System Document

**Purpose:** AI-guided design system definition. Orange accent (#F97316).

**Layout:** Same chat pattern as S20 with orange accent. Visual sections with color swatches, typography preview, spacing tokens.

**Sections (Design System):**

1. Color Palette
2. Typography
3. Spacing & Layout
4. Component Patterns
5. Iconography

**Navigation:** S23 → S12

---

## S24 — Backlog

**Purpose:** Milestone list with expandable goals. The roadmap view.

**Layout:**

- StatusBar
- Scroll Content (8px top, 20px sides)
  - **Nav Row:** ← back + "Backlog" | "+ Milestone" button
  - **Milestone Cards** (repeated):
    - Top row: milestone name + status chip (In Progress/Planned) + chevron
    - Description text
    - **Tasks Section:** progress bar + "X/Y tasks done"
    - **Budget Section:** credits spent + human equiv
    - Expandable: Goal rows within milestone

**Data per Milestone:**
| Field | Type | Example |
|-------|------|---------|
| name | string | "M1: Foundation" |
| status | enum | in_progress, planned, completed |
| description | string | "Platform can accept..." |
| tasksDone | number | 8 |
| tasksTotal | number | 15 |
| creditsSpent | currency | $142 |
| goals | Goal[] | nested |

**Actions:**
| Action | Target |
|--------|--------|
| Tap ← back | S12 Project Hub |
| Tap milestone chevron | Expand goals |
| Tap goal row | S31 Goal Detail (via S30 Milestone) |
| Tap "+ Milestone" | Create milestone sheet |

**Navigation:** S24 → S30, S12

---

## S30 — Milestone Detail

**Purpose:** AI-guided milestone refinement. Shows goals and progress.

**Layout:**

- StatusBar
- Scroll Content (8px top, 20px sides)
  - Nav Row: ← back + milestone name
  - Breadcrumb: "Project › M1: Foundation"
  - Milestone description
  - Stats: status, MVI count, cost
  - Goal list with status
- InputBar (AI chat for milestone refinement)

**Navigation:** S30 → S31, S24

---

## S31 — Goal Detail

**Purpose:** Show MVIs within a goal. ROI per MVI. Approve/Steer/Reject flow.

**Layout:**

- StatusBar
- Scroll Content (8px top, 20px sides)
  - **Nav Row:** ← back + goal name
  - Breadcrumb: "Cawnex › M1: Foundation › API Infrastructure"
  - **Status Row:** status chip + MVI count + cost
  - **Murder Assignment:** Murder card (compact: name + crow count + active indicator)
  - **MVI Cards** (repeated, key screen):
    - **MVI 1 (Completed):**
      - Name + status chip (green "Completed") + chevron → S32
      - Task/time summary: "4/4 tasks · 23 min AI · ~3 days human"
      - Cost comparison: "$18 vs ~$1.2k"
      - Progress bar (full green)
      - ROI Row: trending-up icon + "67x ROI · saved ~$1.2k" (orange)
    - **MVI 2 (In Progress):**
      - Name + status chip (amber "Executing")
      - Task summary + cost comparison
      - Progress bar (partial amber)
      - **Action buttons:** Approve All (green) | Review Tasks (muted)
      - ROI Row: "est. 39x ROI · ~$4.8k human equiv"
    - **MVI 3 (Refining):**
      - Name + status chip (purple "Refining")
      - Spinner + "Dev Murder generating tasks..."
      - Description text

**Data per MVI Card:**
| Field | Type | Example |
|-------|------|---------|
| name | string | "MVI 1.1: REST API Endpoints" |
| status | enum | completed, executing, refining, draft |
| tasksDone | number | 4 |
| tasksTotal | number | 4 |
| aiMinutes | number | 23 |
| humanDays | string | "~3 days" |
| aiCost | currency | $18 |
| humanEquiv | currency | ~$1.2k |
| progress | percentage | 100% |
| roi | number | 67 |
| pendingApprovalCount | number | 0 |

**Actions:**
| Action | Target |
|--------|--------|
| Tap ← back | S30 Milestone Detail |
| Tap completed MVI chevron | S32 MVI Blackboard |
| Tap "Approve All" | Approve all pending tasks |
| Tap "Review Tasks" | S32 MVI Blackboard |

**Navigation:** S31 → S32, S30

---

## S32 — MVI Blackboard

**Purpose:** Live execution monitor. The founder's real-time window into Murder orchestration. Tasks, crows, live feed, merge readiness, ship.

**Layout:**

- StatusBar
- Scroll Content (8px top, 20px sides)
  - **Nav Row:** ← back + MVI name
  - Breadcrumb: "M1 › API Infrastructure › MVI 1.2"
  - **Status Row:** status chip (green "Executing") + task progress + cost
  - **Progress Bar:** green fill proportional to completion
  - **ACTIVE CROWS label:**
    - **Crow Cards** (horizontal, compact):
      - Active dot (green/blue/gray) + crow name + behavior state + model
  - **TASKS label:**
    - **Task List** (card with rows):
      - Completed: green check + task name + "PR #14" link + chevron → S33
      - In Progress: purple spinner + task name + "building" status + chevron → S33
  - **LIVE FEED label + red LIVE badge:**
    - **Feed Card** (dark bg):
      - Timestamped events (JetBrains Mono time + Inter description):
        - "14:32 — Implementer started building Session management"
        - "14:28 — Murder approved PR #15 → merge queue" (green)
        - "14:14 — Reviewer completed review on PR #15"
        - "13:50 — Murder sent PR #14 back → Fixer crow" (amber)
        - "13:32 — Kickoff: spawned 3 crows for MVI 1.2" (muted)
  - **MERGE READINESS label:**
    - **Checklist Card** (green border):
      - ✅ 2/2 PRs reviewed and approved
      - ✅ All CI checks passing
      - ⏳ 1 task still building (purple)
  - **Cost Row:** "Spent $4.20 · Saved ~$1,200" | "286x ROI" (amber)
  - **Ship Button:** git-merge icon + "Ship this MVI" (disabled while tasks building)
  - Hint: "Waiting for all tasks to complete"

**Data:**
| Field | Type | Example |
|-------|------|---------|
| mvi.name | string | "MVI 1.2: Auth & JWT" |
| mvi.status | enum | executing, ready_to_ship, shipped |
| mvi.tasksDone | number | 2 |
| mvi.tasksTotal | number | 3 |
| mvi.creditsSpent | currency | $4.20 |
| mvi.humanEquiv | currency | ~$1,200 |
| mvi.roi | number | 286 |
| activeCrows | array | [{name, behaviorState, model, color}] |
| tasks | array | [{name, status, prNumber, crowName}] |
| liveFeed | array | [{timestamp, message, color}] |
| mergeChecklist | array | [{label, passed: boolean}] |
| canShip | boolean | false (until all checks pass) |

**Actions:**
| Action | Target |
|--------|--------|
| Tap ← back | S31 Goal Detail |
| Tap task row | S33 Task Detail |
| Tap PR link | S34 PR Review |
| Tap "Ship this MVI" | Merge all PRs, close MVI |

**Real-time:** SSE connection for live feed updates and crow state changes.

**Navigation:** S32 → S33, S34, S31

---

## S34 — PR Review

**Purpose:** AI-guided PR review. Not code inspection — question/steering with plan vs execution comparison. No raw diffs on mobile.

**Layout:**

- StatusBar
- NavBarBack (← PR Review)
- Scroll Content (12px top, 20px sides)
  - **PR Header Card:**
    - Title: "Add input validation for user registration endpoint"
    - Branch: `feat/input-validation`
    - Status badge: "Ready" (amber)
    - Breadcrumb: MVI 1.2 › Task: Input Validation
    - **Meta Row:** 12 credits | 8 min | 6 files | +142/-23 lines
  - **AI Verdict Card** (green border):
    - Verdict icon (green shield-check in circle) + "Reviewer Crow: Approved"
    - Confidence: "High confidence · 6 files analyzed"
    - Summary paragraph
    - Separator
    - **Key Findings:**
      - ✅ Zod schemas with proper error messages
      - ✅ Comprehensive test coverage (94%)
      - ⚠️ Email regex doesn't match RFC 5322 (amber)
  - **Plan vs Execution Card:**
    - Header: git-compare-arrows icon + "Plan vs Execution"
    - **Step 1 — Planner** (purple #1 badge):
      - Plan (muted bg): "Create Zod validation schemas for all user input fields"
      - Executed (green tint bg): "Created Zod schemas for registration, login, and profile update"
    - **Step 2 — Implementer** (green #2 badge):
      - Plan: "Add validation middleware to Express routes"
      - Executed: "Added validation + refactored error handler for consistency"
      - **Complexity Hint** (amber border): "Deviated from plan — refactored existing error handler to use new validation patterns. Low risk, improves consistency."
  - **Ask AI Card** (purple border):
    - sparkles icon + "Ask about this PR"
    - Question chips (pill, muted bg):
      - "Why was error handler changed?"
      - "Show me the Zod schemas"
      - "Is this RFC 5322 issue a risk?"
      - "What would break if I merge?"

  _(scrolled variation S34 continues below)_
  - More Plan vs Execution steps (Step 3 — Reviewer)
  - **AI Conversation:**
    - User bubble (purple): "Why was the error handler refactored? That wasn't in the plan."
    - AI bubble (muted bg, crow avatar):
      - Detailed explanation paragraph
      - Risk badge: "Low risk — additive change only" (green)
  - InputBar: sparkles icon + "Ask anything about this PR..." + send button

- **Action Bar:**
  - "Approve & Merge" (green, git-merge icon) — primary
  - "Steer" (amber) — send feedback
  - "Reject" (red) — cancel
  - "GitHub" (muted, external-link icon) — open in browser

**Data:**
| Field | Type | Example |
|-------|------|---------|
| pr.title | string | "Add input validation..." |
| pr.branch | string | "feat/input-validation" |
| pr.status | enum | ready, changes_requested, merged |
| pr.mviRef | string | "MVI 1.2" |
| pr.taskRef | string | "Input Validation" |
| pr.creditsCost | number | 12 |
| pr.aiMinutes | number | 8 |
| pr.filesChanged | number | 6 |
| pr.linesAdded | number | 142 |
| pr.linesRemoved | number | 23 |
| verdict.status | enum | approved, changes_needed, rejected |
| verdict.confidence | enum | high, medium, low |
| verdict.summary | string | ... |
| verdict.findings | array | [{text, type: check|warning}] |
| planVsExecution | array | [{crowName, role, plan, executed, hint?}] |
| askChips | string[] | suggested questions |
| conversation | array | [{role, content, riskBadge?}] |

**Actions:**
| Action | Target |
|--------|--------|
| Tap ← back | S32 MVI Blackboard |
| Tap "Approve & Merge" | Merge PR → back to S32 |
| Tap "Steer" | Opens steer input → sends feedback to Murder |
| Tap "Reject" | Cancel task → back to S32 |
| Tap "GitHub" | Open PR in Safari |
| Tap ask chip | Populates input + sends |
| Send message | AI responds in conversation |

**API:** `POST /prs/:id/review`, `POST /prs/:id/approve`, `POST /prs/:id/steer`, `POST /prs/:id/reject`

**Navigation:** S34 → S32

---

## S33 — Task Detail

**Purpose:** Single task deep-dive. Estimates, implementation plan, acceptance criteria, PR link.

**Layout:**

- StatusBar
- Scroll Content (8px top, 20px sides)
  - **Nav Row:** ← back + task name
  - Breadcrumb: "MVI 1.2 › Auth & JWT › Task 2"
  - **Title Row:** task name (20px bold) + status chip (green "Completed")
  - Description paragraph
  - **Stats Row** (3 equal cards):
    - Estimate: "6h" (human equiv)
    - AI Cost: "$2.40"
    - ROI: "42x"
  - **ASSIGNED CROW label:**
    - Crow Card (compact): active dot + crow name + role + model + behavior state
  - **IMPLEMENTATION label:**
    - Implementation Card (numbered steps):
      1. ✅ Create RolesGuard extending CanActivate
      2. ✅ Implement @Roles() decorator
      3. ✅ Add permission hierarchy map
      4. ✅ Write 403 error response handler
      5. ✅ Add integration tests
  - **ACCEPTANCE CRITERIA label:**
    - Criteria Card (checkmarks):
      - ✅ Guard blocks unauthenticated requests
      - ✅ @Roles decorator works on controller and method level
      - ✅ Hierarchical roles (admin > editor > viewer)
      - ✅ Returns 403 with descriptive error
  - **PULL REQUEST label:**
    - PR Card: git-pull-request icon + PR title + branch + chevron → S34

**Data:**
| Field | Type | Example |
|-------|------|---------|
| task.name | string | "RBAC middleware" |
| task.status | enum | completed, in_progress, pending_approval, queued, failed |
| task.description | string | "Create NestJS guard..." |
| task.humanEstimate | string | "6h" |
| task.aiCost | currency | $2.40 |
| task.roi | number | 42 |
| task.assignedCrow | object | {name, role, model, behaviorState} |
| task.implementationSteps | array | [{text, completed}] |
| task.acceptanceCriteria | array | [{text, passed}] |
| task.pr | object | {title, branch, number, status} |

**Actions:**
| Action | Target |
|--------|--------|
| Tap ← back | S32 MVI Blackboard |
| Tap PR card | S34 PR Review |

**Navigation:** S33 → S34, S32

---

## Scrolled Variations

### S41 scrolled — Create Murder (scrolled)

Shows the bottom sections visible in viewport: Quality Gates, Escalation Rules, Budget Limits. Same data model as S41.

### S51 scrolled — Add Skill (scrolled)

Shows Security & Permissions, Execution, and Test sections visible in viewport. Same data model as S51.

### S34 scrolled — PR Review (scrolled)

Shows the AI conversation thread (user question + crow answer with risk badge), input bar, and action bar. Same data model as S34.

---

## API Summary

| Endpoint                             | Method | Screen  |
| ------------------------------------ | ------ | ------- |
| `/auth/sign-in`                      | POST   | S02     |
| `/projects`                          | GET    | S10     |
| `/projects`                          | POST   | S11     |
| `/projects/:id`                      | GET    | S12     |
| `/projects/:id/documents/:type/chat` | POST   | S20-S23 |
| `/projects/:id/milestones`           | GET    | S24     |
| `/projects/:id/milestones/:id`       | GET    | S30     |
| `/projects/:id/goals/:id`            | GET    | S31     |
| `/projects/:id/mvis/:id`             | GET    | S32     |
| `/projects/:id/mvis/:id/ship`        | POST   | S32     |
| `/projects/:id/tasks/:id`            | GET    | S33     |
| `/prs/:id`                           | GET    | S34     |
| `/prs/:id/approve`                   | POST   | S34     |
| `/prs/:id/steer`                     | POST   | S34     |
| `/prs/:id/reject`                    | POST   | S34     |
| `/murders`                           | GET    | S40     |
| `/murders`                           | POST   | S41     |
| `/murders/:id`                       | PUT    | S41     |
| `/murders/:id/crows`                 | POST   | S42     |
| `/skills`                            | GET    | S50     |
| `/skills`                            | POST   | S51     |
| `/skills/:id`                        | PUT    | S51     |
| `/billing/credits`                   | GET    | S61     |
| `/billing/usage`                     | GET    | S61     |
| `/notifications`                     | GET    | S70     |
| `/notifications/:id/actions/:action` | POST   | S70     |

---

## Real-Time Connections

| Screen             | Protocol   | Purpose                                                   |
| ------------------ | ---------- | --------------------------------------------------------- |
| S32 MVI Blackboard | SSE        | Live feed events, crow state changes, task status updates |
| S34 PR Review      | SSE        | AI conversation streaming                                 |
| S70 Notifications  | Push + SSE | New notification alerts                                   |
| S10 Dashboard      | SSE        | Project status updates (optional)                         |

---

## Pending Screens (Post-MVP)

| ID  | Screen           | Purpose                                          |
| --- | ---------------- | ------------------------------------------------ |
| S03 | Onboarding       | First-run experience (project wizard, LLM setup) |
| S35 | Deployment       | Post-merge Infra Crow deploy flow (inside S32)   |
| S62 | Purchase Credits | Payment flow (Stripe)                            |
