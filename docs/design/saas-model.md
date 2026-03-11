# 💰 SaaS Business Model

---

## Product Definition

**Cawnex** is an agent orchestration platform that turns GitHub issues into shipped, tested, documented code — using the user's own LLM.

**We sell**: Orchestration (routing, coordination, guards, retry, sync merge)
**User provides**: LLM (API key or subscription), Git repos, Issues

---

## Pricing

### Tiers

| Tier | Price | Target | Includes |
|------|-------|--------|----------|
| **Free** | $0/mo | Indie devs, evaluation | 20 executions/mo, 1 repo, 2 agents (Dev + QA), community support |
| **Pro** | $29/mo | Solo devs, small teams | Unlimited executions, 10 repos, 4 agents, priority queue, email support |
| **Team** | $99/mo | Startups, dev teams | Unlimited repos, 7 agents, multi-repo coordination, sync merge, 5 seats, Slack/Discord notifications |
| **Enterprise** | Custom | Companies | SSO, audit logs, SLA, dedicated support, custom agents, on-prem option |

### Why These Prices
- **$29 Pro**: Lower than Lovable ($50), Cursor ($20 + limits). Competitive entry point.
- **$99 Team**: The multi-repo coordination is the killer feature. No one else offers this.
- **Free tier**: Essential for adoption. 20 executions = enough to get hooked.

### Add-ons (Future)
- Additional seats: $15/seat/mo
- Priority compute: $20/mo (faster execution queue)
- Custom agent templates: $10/agent/mo
- White-label: Enterprise only

---

## Revenue Model

### Unit Economics

| Metric | Value |
|--------|-------|
| LLM cost per execution | $0 (BYOL) |
| Compute cost per execution | ~$0.02-0.05 (sandboxed container) |
| Infrastructure per org | ~$2-5/mo (DB rows, Redis, storage) |
| **Gross margin** | **~95%** |

### Growth Projections (Conservative)

| Month | Free Users | Pro | Team | Enterprise | MRR |
|-------|-----------|-----|------|-----------|-----|
| 3 | 200 | 15 | 3 | 0 | $732 |
| 6 | 1,000 | 60 | 15 | 1 | $3,690 |
| 12 | 5,000 | 200 | 50 | 5 | $12,700 |
| 18 | 15,000 | 500 | 150 | 15 | $30,350 |
| 24 | 30,000 | 1,000 | 400 | 30 | $70,900 |

### Infrastructure Cost at Scale (Month 24)

| Item | Monthly |
|------|---------|
| AWS (ECS/EKS, RDS, ElastiCache) | $8,000 |
| Sandboxed compute (Firecracker/E2B) | $5,000 |
| Monitoring (Datadog/Grafana) | $1,000 |
| DNS/CDN (Cloudflare) | $200 |
| **Total** | **~$14,200** |
| **Revenue** | **$70,900** |
| **Net margin** | **~80%** |

---

## Go-to-Market Strategy

### Phase 1 — Developer Community (Months 1-6)
- Open source the core orchestrator (build trust)
- Free tier drives adoption
- Content marketing: "How we orchestrate 7 AI agents" blog posts
- Show real metrics: cost per PR, success rate, time saved
- Targets: indie hackers, open source maintainers, solopreneurs

### Phase 2 — Startup Teams (Months 6-12)
- Team tier launch with multi-repo coordination
- Linear/Jira integration (teams use these)
- Case studies from Phase 1 power users
- Product Hunt launch
- Dev tool newsletters (TLDR, ByteByteGo, etc.)

### Phase 3 — Enterprise (Months 12-24)
- SOC2 compliance
- SSO (SAML/OIDC)
- On-prem / VPC deployment option
- Custom agents and workflows
- Dedicated sales (inbound from content)

---

## Competitive Positioning

### What We're NOT
- We're NOT a code completion tool (Copilot, Cursor)
- We're NOT a single-agent builder (Lovable, Bolt)
- We're NOT an IDE (Cursor, Windsurf)

### What We ARE
- **The orchestration layer** between your issues and your shipped code
- Multi-agent, multi-repo, synchronized deployment
- BYOL — no token limits, no artificial constraints

### Taglines
- "Your issues. Your AI. Our orchestration."
- "Bring your own brain. We handle the rest."
- "From issue to production. Autonomously."

### vs. Competitors

| Feature | Copilot | Cursor | Lovable | Devin | **Cawnex** |
|---------|---------|--------|---------|-------|-----------|
| Multi-agent | ❌ | ❌ | ❌ | ❌ | ✅ 7 agents |
| Multi-repo | ❌ | ❌ | ❌ | ❌ | ✅ Sync PRs |
| Issue → PR | ❌ | ❌ | ❌ | ✅ | ✅ |
| QA review | ❌ | ❌ | ❌ | ❌ | ✅ Automated |
| Auto docs | ❌ | ❌ | ❌ | ❌ | ✅ |
| BYOL | Partial | ✅ | ❌ | ❌ | ✅ |
| Free tier | ❌ | Limited | Limited | ❌ | ✅ 20 exec |
| Price | $10-19 | $20-40 | $20-50 | $500 | **$0-99** |

---

## Key Metrics to Track

### Product
- Execution success rate (target: >70%)
- Time to PR (target: <10 min for simple issues)
- User retention (D7, D30)
- Free → Pro conversion rate (target: 8-12%)
- Pro → Team upgrade rate (target: 15-20%)

### Business
- MRR / ARR
- CAC (customer acquisition cost)
- LTV (lifetime value)
- Churn rate (target: <5%/month)
- NPS (target: >50)

### Technical
- Execution queue time
- Agent uptime
- API latency (p50, p95, p99)
- Cost per execution (infrastructure only)
