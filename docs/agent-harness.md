# Agent harness

Laravel Guild uses one shared runtime harness plus a small policy profile for
each agent. The shared layer owns mechanics that must behave consistently;
profiles describe the authority and escalation boundary for one role. The
machine-readable policy source is
[`config/agent-harness.json`](../config/agent-harness.json). The shared
human-readable pipeline lifecycle is authored separately in
[`config/orchestration-contract.md`](../config/orchestration-contract.md) and
generated into every runtime entry point; see the
[canonical orchestration contract](orchestration-contract.md).

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
- **Verification:** every success criterion has a stable ID, and every unwaived
  ID needs passing evidence before a stage can finish. `VERIFIED` accepts
  registered runner records only and never executes prose as a shell command.
  Only a main-thread user decision can waive a criterion, with a durable reason.
- **Outcome benchmarks:** criteria that claim a query or latency improvement
  declare `benchmark_criteria` and require a passing, source-bound read-only
  receipt. Repeated baseline/candidate runs must preserve behavior and meet the
  selected tail-aware threshold. See the
  [outcome benchmark runbook](outcome-benchmark.md).
- **Laravel capture adapter:** `php artisan guild:benchmark-capture` produces
  comparator-compatible captures from application-owned HTTP, command, job,
  or Livewire scenarios. It blocks non-read-only SQL before execution, rejects
  production, and emits hashes rather than raw payloads below `docs/delivery`.
  See the [capture adapter runbook](benchmark-capture.md).
- **Context packets:** every claimed lane receives one bounded, stage-specific
  brief. Kernel-derived objective, authority, scope, approvals, budget,
  criteria, state, and output contract cannot be trimmed. Selected source
  excerpts are untrusted, hash-bound data; stale state, unsafe paths,
  secret-shaped content, and required context that does not fit fail closed.
  See the [context engineering runbook](context-engineering.md).
- **Adversarial gate:** the versioned attack matrix tests path containment,
  artifact and evidence integrity, authority, measurement, terminal states,
  replay, routing, and concurrency. Every attack asserts its exact safe
  post-state, including no mutation where denial must be side-effect-free. See
  [adversarial engineering-loop testing](adversarial-testing.md).
- **Return contract:** every specialist reports `STATUS`, `DID`, `VERIFIED`,
  `NOT-CHECKED`, `FLAGS`, and `NEXT`.
- **Observability:** every persisted delivery mutation emits a versioned,
  monotonic, hash-chained event carrying delivery/stage correlation, status,
  actor, aggregate usage, and state integrity. `kernel.json` is authoritative;
  `events.jsonl` and `observability.md` are deterministic views. Raw prompts,
  tool inputs, report bodies, and secrets are excluded. Console diagnostics
  remain separately redacted and retention-bounded. See
  [delivery observability](observability.md).
- **Enforcement map:** every strong harness claim names whether it is enforced
  by the kernel, a pre-tool hook, release-required CI, an authoritative human
  decision, or prompt guidance. Each control links to implementation,
  executable evidence, its safe failure mode, and a known limitation. Prompt
  text alone cannot qualify as enforcement. See the generated
  [engineering-loop enforcement map](enforcement-map.md).
- **Loop detection:** claimed specialists stop when an exact one-to-four-step
  tool-call cycle reaches three repetitions. Only SHA-256 input signatures and
  tool names persist; the repeated call is denied before execution.
- **Retries and transitions:** only the main thread may request a retry. The
  first distinct failure requeues the lane for a fresh atomic claim; the second
  fails the stage and stops delivery. Every status change is durably recorded.
- **Recovery:** the kernel exposes active claims before dispatch. A confirmed
  interruption freezes its lane at the last observed activity and stores the
  reason, source, known usage, and unavailable completion metrics. Continuing
  requires a fresh claim; stopping fails the lane. Neither action consumes or
  resets the retry allowance.
- **Feedback routing:** stages declare globally unique CI check names. Failed
  checks route by exact name and review comments route by the longest matching
  owned path. Unmatched events block dispatch until a main-thread assignment;
  open items share one bounded repair attempt and resolve with its report.

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
boundary. Each record also carries a one-to-one `criterion_ids` array,
`benchmark_criteria`, `approval_categories`, and `feedback_checks`. Use an
empty benchmark array when the stage makes no performance outcome claim. Use
an empty approval array only
when none of the selected agent profile's categories applies, and an empty
feedback array only when the stage owns no CI job. Feedback check names must be
globally unique within the delivery. IDs are stable lowercase-kebab names so
reports, boards, and resumes keep referring to the same behavior.

Each record may also carry a partial `budget` object. Omit it to inherit all
shared defaults, or override only the dimensions that need a narrower
envelope:

```json
{
  "id": "backend",
  "agent": "backend-developer",
  "success_criteria": ["query count is lower and responses are unchanged"],
  "criterion_ids": ["queries-lower-with-same-response"],
  "benchmark_criteria": ["queries-lower-with-same-response"],
  "depends_on": [],
  "owned_paths": ["app", "tests"],
  "approval_categories": [],
  "feedback_checks": ["phpunit"],
  "budget": {"max_seconds": 1200, "max_tool_calls": 80, "max_usd": 4.0}
}
```

`ready` returns the criterion rows with their current status. A stage report
binds each verification command to one declared ID:

```text
VERIFIED: {"criterion":"queries-lower-with-same-response","runner":"outcome-benchmark","args":["docs/delivery/tags/benchmarks/receipt.json"]}
```

Inspect the evidence matrix before reporting:

```sh
python3 scripts/guild-kernel/guild.py criterion list \
  --root . --name tags
```

If a criterion truly cannot be verified, the coordinator stops and presents a
numbered decision. After the user chooses to accept that exact gap, only the
main thread records the waiver:

```sh
python3 scripts/guild-kernel/guild.py criterion waive \
  --root . --name tags --stage backend \
  --criterion queries-lower-with-same-response \
  --reason "Staging fixture is unavailable; user accepted manual verification"
```

The criterion, reason, `by: user`, and UTC timestamp survive in `kernel.json`.
Subagents cannot call this command or directly edit kernel state. See
[criterion-linked evidence](criterion-evidence.md) for the full lifecycle.

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

A failed or incomplete attempt is not retried by sending another prompt. After
completion telemetry, the main thread records a typed reason and stable event
ID:

```sh
python3 scripts/guild-kernel/guild.py retry request \
  --root . --name tags --stage backend \
  --source verification --reason "authorization evidence is missing" \
  --event-id verification:backend:1
```

The first request invalidates stale evidence and changes the lane to `queued`.
`ready` returns attempt 2 and the exact retry context; `claim` then rechecks
dependencies, WIP, approvals, and path ownership. Duplicate event IDs are
idempotent. A second distinct request changes the stage to `failed` and the
delivery to `stopped`. Inspect `retry list`, `transition list`, and the generated
`retries.md` and `transitions.md` views. See
[auditable stage retries](retry-policy.md) for the complete lifecycle.

An interrupted process can leave a `running` claim without completion
telemetry. Inspect recovery state before `ready` whenever a delivery starts or
resumes:

```sh
python3 scripts/guild-kernel/guild.py recovery list \
  --root . --name tags
```

An `active_claims` row is not automatically stale. First confirm that the
current runtime no longer owns it. Then only the main thread records the
interruption with a stable source event:

```sh
python3 scripts/guild-kernel/guild.py recovery interrupt \
  --root . --name tags --stage backend \
  --source process-exit --reason "The previous agent process exited." \
  --event-id process:run-01K5M9Y4A7
```

The kernel stops the active timer at `last_activity_at`, keeps cumulative
seconds and tool calls, and explicitly records that turns, tokens, and USD were
not available from the missing completion receipt. It does not charge offline
time or invent zeros. If known activity already reached the time budget, the
normal `budget_exceeded` terminal state wins.

Resolve the durable event before reclaiming the lane:

```sh
python3 scripts/guild-kernel/guild.py recovery resolve \
  --root . --name tags --event-id process:run-01K5M9Y4A7 \
  --action continue --note "Inspect partial files before changing them."
```

`continue` requeues the same lane, leaves retry usage unchanged, and puts the
interruption context in the next `ready` row. A normal `claim` then rechecks
dependencies, WIP, approvals, and owned paths. `stop` changes the stage to
`failed` and the delivery to `stopped`. Duplicate interrupt and resolution
events are idempotent. The generated `recoveries.md` and `transitions.md` views
preserve the audit trail. See
[recover interrupted claims](recovery-policy.md) for the complete procedure.

Pull-request feedback is routed from the same declared ownership. Inspect the
durable ledger before dispatch and after polling:

```sh
python3 scripts/guild-kernel/guild.py feedback list \
  --root . --name tags
```

CI failures match `feedback_checks` exactly. Review comments match the longest
`owned_paths` prefix. An optional `ingest --stage` value asserts the derived
owner but never selects it. If no owner exists, the event remains
`route_required` and blocks dispatch until the main thread verifies and runs
`feedback assign`. A successful repair report resolves every open item for the
stage. See [PR and CI feedback routing](feedback-routing.md) for commands,
statuses, compatibility, and stopping rules.

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

Human decisions that arise after dispatch use a separate durable checkpoint
lifecycle. Inspect it whenever a delivery starts or resumes:

```sh
python3 scripts/guild-kernel/guild.py checkpoint list \
  --root . --name tags
```

Before presenting a question, the main thread stores the exact prompt and its
typed options. Each `--option-json` object has exactly `id`, `label`, and
`action`; `action` is `continue` or `stop`:

```sh
python3 scripts/guild-kernel/guild.py checkpoint open \
  --root . --name tags --stage database --id migration-risk \
  --question "Proceed with the non-reversible backfill?" \
  --risk "A failed deployment can require restoring the snapshot." \
  --option-json '{"id":"proceed","label":"Proceed after snapshot","action":"continue"}' \
  --option-json '{"id":"stop","label":"Stop this delivery","action":"stop"}' \
  --recommended proceed
```

Only the affected stage becomes `paused`; independent stages stay available to
`ready`. After the user answers, only the main thread resolves the record:

```sh
python3 scripts/guild-kernel/guild.py checkpoint resolve \
  --root . --name tags --id migration-risk --option proceed \
  --note "Use the verified snapshot from change CHG-204."
```

The answer includes the option, action, note, `by: user`, and UTC timestamp.
The generated `docs/delivery/<name>/checkpoints.md` view makes that history
readable without allowing direct state edits. See
[durable human checkpoints](checkpoint-policy.md) for resume and failure rules.

The runtime budget hook also detects exact repeated tool-call cycles. Inspect a
stopped delivery with:

```sh
python3 scripts/guild-kernel/guild.py loop list \
  --root . --name tags
python3 scripts/guild-kernel/guild.py board \
  --root . --name tags
```

The detector compares SHA-256 signatures over the tool name and canonical JSON
input. It checks tail cycles one to four calls long and blocks the call that
would complete the third exact repetition. A changed tool or input breaks the
pattern. The affected stage becomes `failed`, the delivery becomes `stopped`,
and `docs/delivery/<name>/loops.md` records the tool sequence and a short
fingerprint. Raw tool input is never written to loop history. Do not retry the
same sequence; start a changed plan or brief. See
[unproductive-loop detection](loop-policy.md) for examples and boundaries.

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
