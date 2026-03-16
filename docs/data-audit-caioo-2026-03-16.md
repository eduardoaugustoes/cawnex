# Data Audit — Caioo Project (cawnex-dev)

**Date:** 2026-03-16
**Table:** cawnex-dev
**Tenant:** t_0_71899937
**Project:** caioo-653d43

## DynamoDB Records

| SK | Entity Type | Description |
|----|-------------|-------------|
| `S#` | Snapshot | Project root — name, status, murders, AI cost tracking |
| `DOC#vision` | Document | 6 sections, complete |
| `DOC#architecture` | Document | 7 sections, complete |
| `DOC#glossary` | Document | 5 sections, complete |
| `DOC#design` | Document | 6 sections, complete |
| `BACKLOG#milestones` | Backlog | 1 milestone, 5 goals |

## Project Root (`S#`)

| Field | Value |
|-------|-------|
| Name | Caioo |
| One-liner | The AI Revolution in the Accounting Industry |
| Status | draft |
| Murders | [dev] |
| AI Cost | $0.071 |
| AI Calls | 42 |

## Documents

All 4 documents completed via AI-guided chat (POST /ai/chat proxy).

| Document | Sections | Status |
|----------|----------|--------|
| **Vision** | Problem Statement, Target User, Core Value Proposition, Key Differentiators, Success Metrics, Non-Goals | complete |
| **Architecture** | System Overview, High-Level Components, Data Flow, Data Model, Security Model, Infrastructure & Deployment, Technology Decisions | complete |
| **Glossary** | Domain Terms, User-Facing Terms, Technical Terms, Business Terms, Abbreviations | complete |
| **Design** | Visual Identity, Typography, Spacing & Layout, Component Patterns, Iconography, Motion & Interaction | complete |

## Milestones

### M1: WhatsApp Channel Foundation

> Establish a live, bidirectional WhatsApp communication channel. Operators send pre-approved outbound template messages to target phone numbers, receive inbound replies via webhook, view conversations in real time on the dashboard, and send free-form follow-ups within the 24-hour customer service window.

**5 Goals:**

| ID | Goal | Description |
|----|------|-------------|
| g1 | WhatsApp Business Account & Template Integration | Register and configure WhatsApp Business Account on Meta's platform. Submit and obtain approval for message templates. |
| g2 | Outbound Template Message API | Build Lambda endpoint that accepts operator requests (target phone, template name, parameters) and calls WhatsApp API. |
| g3 | Inbound Webhook Receiver & Message Ingestion | Expose webhook endpoint (API Gateway + Lambda) to receive WhatsApp inbound message events and status updates. |
| g4 | Dashboard Conversation Display & Live Updates | Build dashboard page showing list of active conversations: sender phone, last message preview, timestamp, status. |
| g5 | Operator Reply & 24-Hour Session Window Management | Enable operators to compose and send free-form replies to inbound messages within the 24-hour customer service window. |

## MVIs

**None yet.** No `BACKLOG#goal#{id}#mvis` records exist.

This is the next step — the user taps a goal, the AI proposes MVIs (≤8h each), and they get persisted as `BACKLOG#goal#g1#mvis`, etc.

## Cost Summary

- Total AI cost for project setup: **$0.071**
- Total Claude calls: **42**
- All via claude-haiku-4-5 (cheapest model)
- Covers: 4 complete documents + 1 milestone with 5 goals
- Human equivalent of this work: ~8-12 hours of product/strategy consulting (~$800-1200)
- **ROI: ~11,000x to 17,000x**

## Data Model Pattern

```
PK: T#{tenant_id}                    SK: PROFILE                    — tenant profile
PK: T#{tenant_id}                    SK: P#{project_id}             — project list entry
PK: T#{tenant_id}#P#{project_id}     SK: S#                         — project root snapshot
PK: T#{tenant_id}#P#{project_id}     SK: DOC#{type}                 — completed document
PK: T#{tenant_id}#P#{project_id}     SK: BACKLOG#milestones         — all milestones + goals
PK: T#{tenant_id}#P#{project_id}     SK: BACKLOG#goal#{goalId}#mvis — MVIs for a goal (planned)
```
