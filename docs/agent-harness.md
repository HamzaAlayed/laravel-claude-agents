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
  caller cannot exceed. Every planned stage snapshots its effective values in
  `kernel.json`; later registry changes do not rewrite a running delivery.
- **Scope:** delivery stages require explicit success criteria. Every
  mutation-capable stage also requires at least one project-relative owned
  path; only `deny` profiles may remain pathless. The kernel blocks dependency
  violations, WIP overflow, overlapping claims, and reported outputs outside
  the stage’s ownership. On Claude Code, a pre-tool policy also blocks native
  file writes before claim and outside the running stage’s ownership.
- **Tool gateway:** production mutations, destructive database operations,
  secret writes, irreversible external actions, scope expansion, and changes
  to success criteria require a human decision or are denied by a guardrail.
  A planned stage declares applicable profile categories up front. Pending
  approval pauses dispatch; only a durable user grant permits the claim.
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

For new plans, pass typed `--stage-json` records. Each record must include
`owned_paths`: a nonempty array for `task-owned` and `docs-only` profiles, or
an empty array for a `deny` profile. The v6 kernel rejects the former
comma-delimited `--stage` form because it cannot express a safe ownership
boundary. Each record also carries `approval_categories`. Use an empty array
only when none of the selected agent profile's categories applies.

Each record may also carry a partial `budget` object. Omit it to inherit all
shared defaults, or override only the dimensions that need a narrower
envelope:

```json
{
  "id": "backend",
  "agent": "backend-developer",
  "success_criteria": ["query count is lower and responses are unchanged"],
  "depends_on": [],
  "owned_paths": ["app", "tests"],
  "approval_categories": [],
  "budget": {"max_seconds": 1200, "max_tool_calls": 80, "max_usd": 4.0}
}
```

`ready` returns the complete effective budget. Put that exact envelope in the
specialist brief. Inspect the persisted receipt at any point:

```sh
python3 scripts/guild-kernel/guild.py budget list \
  --root . --name tags
```

On Claude Code, `enforce-kernel-budgets.sh` counts time and tool calls before
each subagent tool boundary. The synchronous Agent completion payload supplies
duration, tool calls, turns, tokens, and model usage; the hook records those
totals and estimates USD using the release-owned conservative pricing table.
The hook rejects missing completion telemetry instead of treating zero as a
measurement. A claimed stage cannot `report` until completion telemetry clears
its claim timer.

Another runtime may record telemetry explicitly only when it exposes all five
dimensions:

```sh
python3 scripts/guild-kernel/guild.py budget record \
  --root . --name tags --stage backend \
  --seconds 84.2 --tool-calls 19 --turns 7 --tokens 182000 --usd 0.73
```

Never guess a missing value. If the runtime cannot supply the receipt, the lane
remains unverified. A breach sets the stage and delivery to
`budget_exceeded`, marks the board `⛔`, stops `ready`/`next`, and rejects a
success report. Usage is cumulative across the one allowed reopen; a retry does
not reset its budget. See [runtime stage budgets](runtime-budgets.md) for the
enforcement and trust boundaries.

The kernel validates every declared category against the profile, marks the
lane `⏸`, excludes it from `ready`, and rejects `claim` until all categories
have a user approval record. Inspect and grant them from the main thread:

```sh
python3 scripts/guild-kernel/guild.py approval list \
  --root . --name tags
python3 scripts/guild-kernel/guild.py approval grant \
  --root . --name tags --stage database \
  --category "destructive migration"
```

The category, `by: user`, and UTC timestamp persist in `kernel.json`. The
approval hook denies subagent grants and direct edits of kernel state. See
[runtime stage approvals](approval-policy.md) for the boundary and examples.

The native-write policy applies when an agent appears in an active kernel
delivery. A queued or finished stage cannot edit; one running stage may edit
only its `owned_paths`; multiple running stages for the same agent fail closed
as ambiguous. Direct point-work keeps the single-specialist fast path when no
active delivery contains that agent. The policy covers `Write`, `Edit`, and
`NotebookEdit`. `docs-only` agents remain limited to the documentation roots
declared in `shared.nativeWritePolicy`, even on the direct fast path. Bash
mutations remain governed by the production, secret, helper-file, Sail, and
read-only-reviewer command guards.

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
