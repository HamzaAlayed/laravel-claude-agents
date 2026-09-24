# Agent harness

Laravel Guild uses one shared runtime harness plus a small policy profile for
each agent. The shared layer owns mechanics that must behave consistently;
profiles describe the authority and escalation boundary for one role. The
machine-readable source is [`config/agent-harness.json`](../config/agent-harness.json).

## Shared harness

Every agent run inherits these controls:

- **Lifecycle:** queued, running, paused, done, failed, stopped,
  budget-exceeded, or interrupted. Run metadata and traces survive process
  interruption so work can resume without repeating completed steps.
- **Budgets:** 30 minutes, 200 tool calls, 120 assistant turns, 5 million
  tokens, and $10 by default. The registry also defines hard ceilings that a
  caller cannot exceed.
- **Scope:** delivery stages require explicit success criteria and owned paths.
  The kernel blocks dependency violations, WIP overflow, and overlapping path
  claims.
- **Tool gateway:** production mutations, destructive database operations,
  secret writes, irreversible external actions, scope expansion, and changes
  to success criteria require a human decision or are denied by a guardrail.
- **Verification:** `VERIFIED` accepts registered runner records only. It never
  executes prose as a shell command.
- **Return contract:** every specialist reports `STATUS`, `DID`, `VERIFIED`,
  `NOT-CHECKED`, `FLAGS`, and `NEXT`.
- **Observability:** events carry run, trace, span, lane, tool, approval, usage,
  and budget evidence; persisted values are redacted and retention-bounded.
- **Recovery:** interrupted runs reload their original request and current
  workspace state. They are told to inspect persisted kernel state before
  continuing.

The harness enforces what can be decided mechanically. Agent prompts still
provide domain judgment, such as when a proposed authentication change is
material enough to escalate.

## Agent-specific profiles

`task-owned` means the agent may change only paths assigned to its stage.
`docs-only` narrows mutation to delivery or design documentation. `deny` is a
read-only role; frontmatter removes Edit and Write, and the Bash guard closes
common command-line write vectors.

| Agent | Class | Mutation | Approval boundary | Primary handoffs |
| --- | --- | --- | --- | --- |
| backend-developer | Builder | task-owned | Auth, billing, PII, tenancy, mass communication | Database, frontend, mobile, QA, security, performance, DevOps, tech lead |
| business-analyst | Planner | docs-only | Stakeholder sign-off, sensitive requirements, scope | Product owner, architect, UI/UX |
| database-developer | Builder | task-owned | Destructive or irreversible schema/data work | Backend, DevOps, security, architect |
| delivery-coordinator | Orchestrator | docs-only | Sensitive, unverifiable, or scope-changing stages | Any registered specialist |
| devops-engineer | Builder | task-owned | Production infrastructure, apply, DNS/TLS, keys, residency, DR | Backend, database, QA, security, writer |
| frontend-developer | Builder | task-owned | Payment, PII, auth, unsafe HTML, major migrations | Backend, performance, QA, security, UI/UX |
| mobile-developer | Builder | task-owned | Store, push, auth, purchase, PII, device permissions | Backend, QA, security, UI/UX |
| package-developer | Builder | task-owned | Major release, license, ownership, maintainer access | QA, security, tech lead, writer |
| peer-router | Router | deny | Invalid adaptive packet | None; it validates only |
| performance-engineer | Reviewer | deny | Behavior-for-speed, spend, sensitive caches, shared load tests | Backend, database, DevOps, frontend |
| product-owner | Planner | docs-only | Roadmap, pivot, security commitments, external communication | Analyst, coordinator, architect |
| qa-engineer | Builder | task-owned | Release decision, test removal, weaker gates, known defects | Backend, frontend, mobile, tech lead |
| scrum-master | Planner | docs-only | Human conflict, individual performance, morale | Coordinator, product owner |
| security-engineer | Reviewer | deny | Incident, residual risk, auth, crypto, audit, PII, payment, identity | Backend, database, DevOps, tech lead |
| solution-architect | Planner | docs-only | Long-term cost, lock-in, regulation, tenancy, auth model | Backend, database, DevOps, security, tech lead |
| tech-lead | Reviewer | deny | Sensitive merge, major refactor, framework migration, people management | Backend, frontend, QA, security |
| technical-writer | Builder | docs-only | Brand, legal, or compliance language | DevOps, product owner, QA |
| ui-ux-designer | Planner | docs-only | Brand, PII, auth, consent, checkout, final design | Analyst, frontend, product owner, QA |

## Changing the harness

Update the registry and the affected agent definition together, then run:

```sh
python3 scripts/check-agent-harness.py
python3 -m unittest discover -s tests/console -t tests/console -v
python3 -m unittest discover -s tests/kernel -t tests/kernel -v
./tests/guardrails.test.sh
```

CI also validates the registry as JSON and rejects missing agents, dangling
handoffs, unsafe read-only drift, unsupported budget keys, or a second agent
receiving the orchestration tool.
