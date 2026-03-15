# 22 Core Problems — Orchestration Engine

> Every architectural decision must trace back to one or more of these problems.
> If a component doesn't solve a listed problem, question whether it's needed.

---

## Founder-Facing

| #   | Problem                                     | Why It Matters                                                                          |
| --- | ------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1   | **Idea to working code without a dev team** | The core value proposition — a founder with a vision but no engineers can ship software |
| 2   | **Human must stay in control**              | Approve, steer, reject at every level. AI advises, never dictates                       |
| 3   | **Real-time visibility into agent work**    | Not a black box — founder sees what crows are doing, live                               |
| 4   | **Quality: reviewed, tested, documented**   | Code must be reviewed, tested, documented — not just generated and dumped               |

## Execution

| #   | Problem                                        | Why It Matters                                                                            |
| --- | ---------------------------------------------- | ----------------------------------------------------------------------------------------- |
| 5   | **Different tasks need different specialists** | Planning, coding, reviewing, documenting need different expertise and models              |
| 6   | **Agent isolation**                            | Each agent works in its own space, can't corrupt another's work (git worktrees)           |
| 7   | **Failure resilience**                         | Retry, fix, escalate — never silently fail. One agent failing shouldn't kill the pipeline |
| 8   | **Scoped context**                             | Each agent gets only what it needs, not the full repo. Reduces cost and confusion         |
| 9   | **Coordination across agents**                 | Multiple agents on the same codebase need to not step on each other                       |
| 10  | **Central decision-maker**                     | Agents don't self-organize. Murder dispatches, judges, and coordinates                    |

## Platform

| #   | Problem                                        | Why It Matters                                                                      |
| --- | ---------------------------------------------- | ----------------------------------------------------------------------------------- |
| 11  | **Multi-tenant isolation**                     | One founder's projects/data/executions must never leak to another                   |
| 12  | **Cost scales with usage, not infrastructure** | Pay-per-execution, not idle servers. Serverless-first                               |
| 13  | **Scales from 10 to 1000+ users**              | Architecture can't have bottlenecks requiring rewrite when load grows               |
| 14  | **Observable**                                 | Structured logs, execution traces, cost per tenant/project/execution — not guessing |

## Project Lifecycle

| #   | Problem                                        | Why It Matters                                                               |
| --- | ---------------------------------------------- | ---------------------------------------------------------------------------- |
| 15  | **New projects: zero to first commit**         | AI needs to understand a vision, plan milestones, scaffold from nothing      |
| 16  | **Existing projects: evolve without breaking** | AI needs to understand existing code, conventions, and make changes that fit |

## Intelligence & Judgment

| #   | Problem                                     | Why It Matters                                                                          |
| --- | ------------------------------------------- | --------------------------------------------------------------------------------------- |
| 17  | **Separate intelligence from judgment**     | Intelligence (how to do) must be separated from judgment (what to do and why)           |
| 18  | **Multiple perspectives catch blind spots** | A single agent deciding priorities misses security risks, tech debt, market timing      |
| 19  | **Advisors evolve with project maturity**   | Security concerns for a new project differ from a 6-month-old project                   |
| 20  | **Decisions must be traceable**             | Who voted what, with what reasoning — not a black box                                   |
| 21  | **Disagreement is a feature**               | Allow debate rounds, dissent, re-evaluation. Suppressing tension leads to bad decisions |
| 22  | **Resource discipline at every layer**      | Budgets, limits, escalation over endless iteration. Long-term thinking over quick fixes |

---

## How Problems Map to Solutions

| Problem   | Solved By                                                |
| --------- | -------------------------------------------------------- |
| 1, 15, 16 | Wave lifecycle + project phases (vision → execution)     |
| 2, 21     | Human approval gates + steer/pause/reject at every level |
| 3         | SSE live feed via DynamoDB Streams                       |
| 4         | Reviewer crow + Documenter crow in every pipeline        |
| 5         | Crow types with specialized prompts and context          |
| 6         | Git worktrees on EFS (POC6 pattern)                      |
| 7         | Guard system + retry engine + escalation to human        |
| 8         | Context assembly — scoped per crow type                  |
| 9         | Murder as central coordinator, one branch per MVI        |
| 10        | Murder Lambda (stream-triggered state machine)           |
| 11        | DynamoDB partition key `T#{tenant_id}` on everything     |
| 12        | Lambda for all compute, DynamoDB on-demand               |
| 13        | DynamoDB + Lambda scale independently                    |
| 14        | Structured JSON logs, cost fields on every snapshot      |
| 17        | Council (judgment) separate from Crows (intelligence)    |
| 18        | 6 advisors with specialized lenses                       |
| 19        | Layered CLAUDE.md memory, pruned to token budget         |
| 20        | Council snapshots with full vote records + dissent       |
| 22        | Token budgets, time limits, max rounds, wave budget caps |
