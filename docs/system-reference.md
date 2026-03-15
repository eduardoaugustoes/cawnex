# Murder/Crow System: Quick Reference

## Key Economics

### Cost Structure

```
Wave Budget Ceiling:     $20.00 (safety limit)
Actual Average Cost:     $4.20 (79% under budget)
Token Cost per Crow:     $0.30 (40k tokens avg)
Retry Factor:            1.25x (25% overhead)

Infrastructure Monthly:  $50
  - DynamoDB:           $20
  - Lambda:             $15
  - GitHub API:         $5
  - Monitoring:         $10
```

### Project Scale Economics

```
Project Size    Waves    Cost      Timeline    Traditional    Savings
100k lines      60       $252      3 months    $50k-200k     99.5%+
500k lines      150      $630      6 months    $250k-1M      99.6%+
1M lines        300      $1,260    12 months   $500k-2M      99.7%+
```

## Technical Specifications

### Wave Structure

```
Average Crows per Wave:  10
  - 1 Planner
  - 4 Implementers
  - 4 Reviewers
  - 1 Fixer (25% probability)

MVIs per Wave:           3-5
Lines per Wave:          5-8k deliverable
Execution Time:          ~50 minutes
Parallel Streams:        4 recommended
```

### Token Economics

```
Context Input:           25k tokens ($0.075)
Generated Output:        15k tokens ($0.225)
Cacheable Content:       15k tokens (60% of input)
Fresh Content:           10k tokens (40% of input)

With Strategic Repetition:
  Unique tokens:         15k × $3/1M = $0.045
  Cached repeats:        10k × $0/1M = $0.000
  Output:               15k × $15/1M = $0.225
  Total:                $0.270 (10% savings + quality boost)
```

### Success Rates by Crow Type

```
Crow Type       Success Rate    Max Retries    Retry Factor
Planner         90%            1              1.1x
Implementer     60%            3              1.4x
Reviewer        80%            2              1.2x
Fixer           70%            3              1.3x
```

## Optimization Quick Wins

### 1. Strategic Prompt Repetition

- Repeat critical context 3-4 times per prompt
- Claude auto-caches repeated content = FREE tokens
- Better model adherence to standards

### 2. Memory System Implementation

```
memory/crows/{type}/{id}-summary.md
  - Successful patterns
  - Failed approaches
  - Project-specific learnings
  - Performance metrics
```

### 3. Parallel Execution

- 4 waves in parallel (dependency permitting)
- Implementers + Reviewers parallel within waves
- 31 hours execution time for 500k project

### 4. Quality Gates

- Pre-execution validation
- Post-execution automated checks
- Budget monitoring with 80% warnings
- Automatic retry with enhanced context

## Status Enums & Transitions

### Wave Status Flow

```
PLANNING → PROPOSED → APPROVED → EXECUTING → DELIVERED
              ↓           ↓           ↓
           REVISED    REJECTED    PAUSED
              ↓           ↓           ↓
           PROPOSED   PLANNING   EXECUTING
```

### MVI Status Flow

```
DRAFT → REFINED → QUEUED → EXECUTING → READY_TO_SHIP → SHIPPED
           ↓         ↓         ↓            ↓
       CANCELLED  CANCELLED  FAILED     REJECTED
                                ↓            ↓
                             QUEUED      QUEUED
```

### Crow Status Flow

```
PENDING → RUNNING → COMPLETED
            ↓
         FAILED
```

## Memory Architecture

### Individual Crow Memory

```
## Execution History
- Waves completed: N
- Success rate: X% first attempt
- Average retry count: Y

## Successful Patterns
- What works well
- Specific techniques
- Quality approaches

## Failed Approaches
- What doesn't work
- Recovery strategies
- Lessons learned

## Project-Specific Insights
- Codebase patterns
- Team preferences
- Integration challenges
```

### Cross-Crow Learnings

```
## Handoff Patterns
- Planner → Implementer effective transitions
- Implementer → Reviewer workflows
- Common failure modes

## Collaborative Improvements
- Shared successful strategies
- Cross-type learning transfer
- System optimization insights
```

## Infrastructure Components

### Core Services

```
lambdas/murder/     - Orchestration & decision making
lambdas/worker/     - Execution & GitHub integration

Key Models:
- WaveSnapshot      - Development initiative tracking
- MVISnapshot       - Feature implementation tracking
- CrowSnapshot      - Individual agent execution
- EventRecord       - Audit trail & monitoring
```

### GitHub Integration

```
Functions:
- create_branch()   - Branch management
- create_pr()       - Pull request automation
- fetch_issue()     - Issue tracking integration
- github_api()      - Generic API wrapper
```

### State Management

```
DynamoDB Schema:
PK: tenant#project
SK: S#{wave_id}#m{mvi_id}#{crow_id}

GSI1: Dispatch queue for pending crows
TTL: Automatic cleanup of old events
```

## Monitoring & Alerting

### Key Metrics

```
Wave completion rate:        Target >95%
Budget efficiency:          Target >70% under-budget
First-attempt success:      Target >80%
Average tokens per crow:    Monitor for optimization
Memory application rate:    Track learning effectiveness
```

### Alert Thresholds

```
Budget Warning:    80% of wave budget ($16)
Budget Critical:   95% of wave budget ($19)
Retry Exhausted:   Crow fails after max retries
Quality Gate Fail: Output doesn't meet standards
Memory Stale:      >7 days without updates
```

## Quick Decision Matrix

### When to Use Each Crow Type

```
Planner:      New feature planning, architecture decisions
Implementer:  Code writing, API development, UI components
Reviewer:     Code quality, security, standards compliance
Fixer:        Bug resolution, test failures, integration issues
```

### When to Increase Budget

```
Complex integration:     +50% budget ($30)
New technology:         +100% budget ($40)
Unclear requirements:   +75% budget ($35)
Legacy system:          +50% budget ($30)
```

### When to Use Manual Review

```
Security-critical:      Always human review
Public API:            Always human review
Database schema:       Always human review
Payment processing:    Always human review
New architectural:     Always human review
```

---

_Quick reference for day-to-day system operation and optimization decisions._
