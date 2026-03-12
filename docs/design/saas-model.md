# 💰 SaaS Business Model

---

## Product Definition

**Cawnex** is an agent orchestration platform that turns GitHub issues into shipped, tested, documented code.

**We sell**: Orchestration + execution platform. Users purchase prepaid credits that cover AI, repository, workflow, and infrastructure costs.
**User provides**: Git repos, project vision

---

## Pricing

### Prepaid Credits Model

Cawnex uses a **prepaid credits model** instead of subscription tiers. Users purchase credits and spend them as projects execute.

**What the credit covers (bundled, not itemized to user):**
- AI model usage (tokens, runtime)
- Repository infrastructure (storage, CI/CD)
- Workflow orchestration (Murder coordination, blackboard)
- Compute infrastructure (Lambda, Fargate)

**What the user sees:**
- Credits purchased and remaining balance
- Credits spent per project
- Human equivalent saved (from benchmark database)
- ROI multiplier (spent vs saved)

This model:
- Eliminates tier anxiety ("Am I on the right plan?")
- Aligns cost with actual usage
- Makes ROI immediately visible
- Scales naturally with project complexity

---

## Revenue Model

### Unit Economics

| Metric | Value |
|--------|-------|
| AI cost per task | ~$0.10-2.00 (varies by model and complexity) |
| Infrastructure cost per task | ~$0.02-0.05 |
| Platform price per task | Credit-based (includes margin) |
| Human equivalent per task | ~$175-600 (from benchmark DB at $50/hr mid-level) |
| **Effective ROI for user** | **~50-100x** |

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
- We're NOT a BYOL platform — we handle AI costs internally for a simpler user experience

### What We ARE
- **The orchestration layer** between your issues and your shipped code
- Multi-agent, multi-repo, synchronized deployment
- Credits-based — no token limits, no artificial constraints

### Taglines
- "Your issues. Our platform. Shipped code."
- "From vision to production. Autonomously."
- "From issue to production. Autonomously."

### vs. Competitors

| Feature | Copilot | Cursor | Lovable | Devin | **Cawnex** |
|---------|---------|--------|---------|-------|-----------|
| Multi-agent | ❌ | ❌ | ❌ | ❌ | ✅ 7 agents |
| Multi-repo | ❌ | ❌ | ❌ | ❌ | ✅ Sync PRs |
| Issue → PR | ❌ | ❌ | ❌ | ✅ | ✅ |
| QA review | ❌ | ❌ | ❌ | ❌ | ✅ Automated |
| Auto docs | ❌ | ❌ | ❌ | ❌ | ✅ |
| BYOL | Partial | ✅ | ❌ | ❌ | ❌ (bundled) |
| Free tier | ❌ | Limited | Limited | ❌ | ✅ 20 exec |
| Price | $10-19 | $20-40 | $20-50 | $500 | **Prepaid credits** |

---

## Key Metrics to Track

### Product
- Execution success rate (target: >70%)
- Time to PR (target: <10 min for simple issues)
- User retention (D7, D30)
- Free → Pro conversion rate (target: 8-12%)
- Pro → Team upgrade rate (target: 15-20%)
- Average ROI multiplier per project (target: >50x)
- Human equivalent hours saved per month

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
