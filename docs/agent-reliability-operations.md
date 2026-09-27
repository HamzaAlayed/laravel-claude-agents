# How do we keep an agent dependable after release?

Last verified 2026-09-27 against pack v9.7.0.

Laravel Guild turns recorded agent operations into one source-bound health
receipt with a `promote`, `hold`, or `rollback` decision. The harness evaluates
success, latency, cost, human intervention, recovery, safety, duplicate side
effects, circuit state, and material change from an accepted baseline.

It does not deploy agents or route traffic. The operator or hosting platform
controls canary allocation, process termination, rollback, and circuit reset.

## What is the reliability contract?

Three sources divide responsibility:

| Source | Authority |
| --- | --- |
| [`config/reliability-harness.json`](../config/reliability-harness.json) | SLOs, retry classes, circuit-breaker rules, canary thresholds, rollback unit, receipt privacy, and known limitations. |
| [`config/reliability-scenarios.json`](../config/reliability-scenarios.json) | Deterministic degraded-condition and interruption sequences with expected decisions, circuit state, and applied-side-effect count. |
| [`scripts/reliability-harness.py`](../scripts/reliability-harness.py) | Validation, fault replay, cohort aggregation, canary comparison, receipt issuance, and source verification. |

Validate the contract without network access, model calls, application writes,
or database access:

```sh
python3 scripts/reliability-harness.py validate --root .
python3 scripts/reliability-harness.py exercise --root .
```

The first command rejects malformed policy, incomplete SLOs, unsafe automatic
database rollback, missing sources, unknown outcomes, and incomplete fault
coverage. The second replays nine scenarios: unavailable tools, timeouts, rate
limits, partial outages, corrupt state, retry exhaustion, interruption after a
committed side effect, duplicate effects, and safety violations.

## What evidence do we record?

Store baseline and canary evidence inside the repository delivery folder. Each
file contains schema version `1`, its `baseline` or `canary` cohort, a stable
release version, and contiguous attempts grouped by operation.

```json
{
  "schemaVersion": 1,
  "cohort": "canary",
  "release": "9.7.0",
  "attempts": [
    {
      "id": "delivery-42-a1",
      "operationId": "delivery-42",
      "attempt": 1,
      "outcome": "timeout",
      "durationSeconds": 20,
      "costUsd": 0.08,
      "humanIntervention": false,
      "safetyViolations": 0,
      "idempotencyKey": "delivery-42",
      "sideEffect": "applied"
    },
    {
      "id": "delivery-42-a2",
      "operationId": "delivery-42",
      "attempt": 2,
      "outcome": "success",
      "durationSeconds": 12,
      "costUsd": 0.05,
      "humanIntervention": false,
      "safetyViolations": 0,
      "idempotencyKey": "delivery-42",
      "sideEffect": "deduplicated"
    }
  ]
}
```

Allowed retryable outcomes are `tool-unavailable`, `timeout`, `rate-limited`,
and `partial-outage`. `corrupt-state`, `application-failure`, and
`safety-violation` stop immediately. The maximum is three attempts. Once a
side effect may have committed, every later attempt uses the same idempotency
key and reports `deduplicated` rather than applying it again.

Do not put prompts, assistant prose, tool input or output, commands, responses,
or secrets in this evidence. The attempt schema records aggregate operational
facts only.

## When may a canary be promoted?

Create and immediately verify the receipt:

```sh
python3 scripts/reliability-harness.py assess \
  --root . \
  --baseline docs/delivery/example/reliability/baseline.json \
  --canary docs/delivery/example/reliability/canary.json \
  --output docs/delivery/example/reliability/operational-health-receipt.json

python3 scripts/reliability-harness.py verify \
  --root . \
  --receipt docs/delivery/example/reliability/operational-health-receipt.json
```

A `promote` decision requires at least ten operations in both cohorts, a healthy
baseline, a healthy canary, a closed circuit, and no material regression. The
declared SLOs require at least 95% completion, p95 duration no greater than
1,200 seconds, p95 cost no greater than $10, no more than 10% human
intervention, at least 90% recovery, and zero safety violations or duplicate
side effects.

A candidate also rolls back when it materially loses completion or recovery,
raises human intervention, or increases p95 duration or cost beyond both the
ratio and absolute-change threshold. This prevents a broad absolute ceiling
from hiding a real regression against a much healthier baseline.

`hold` means evidence is insufficient or the baseline is already unhealthy.
It does not authorize wider traffic. `rollback` means the canary failed an SLO,
materially regressed, or opened its circuit. It does not execute the rollback.

## What does the circuit breaker protect?

The recorded circuit opens after three consecutive retryable failures, any
safety violation, or a duplicate applied side effect. Later observed attempts
are counted as attempts after open and the receipt remains `rollback`.

The operational response is to stop new traffic at the platform boundary,
preserve aggregate evidence, and restore the last accepted exact release unit:
agent instructions, model selection, tool grants, policy manifests, and harness
version. Do not mix an old prompt with a new policy or model and call that a
rollback.

Database migration, rollback, deletion, or repair is never automatic. If an
agent release coincides with a database change, follow the application-specific
deployment runbook and require explicit operator approval.

## What does the receipt prove?

The receipt stores only cohort summaries, decisions, evidence paths and hashes,
scenario count, release identities, and hashes of the policy, scenario
registry, shared harness, canonical instructions, and reliability engine. Any
receipt edit or sealed-source change fails verification.

It proves what the recorded checkout and aggregate evidence imply. It does not
prove that telemetry was complete, traffic was representative, an external
platform obeyed the decision, or untested dependencies are healthy. Source
hashes are integrity checks, not signatures against a same-account attacker.

## Symptoms

- `validate` reports a missing source, incomplete outcome class, or unsafe
  rollback contract.
- `exercise` reports a mismatch between a fault sequence and its expected safe
  decision.
- `assess` prints `hold` or `rollback` instead of `promote`.
- `verify` reports tampering, source drift, an invalid schema, or inconsistent
  decision evidence.
- The canary platform reports new attempts after the receipt circuit opened.

## Triage

1. Stop widening canary traffic. Preserve baseline, canary, and receipt files.
2. Run `verify` before changing evidence. A source-drift result means the
   receipt no longer describes the current checkout.
3. Read `decision.reasons`, then `baselineBreaches`, `canaryBreaches`, and
   `regressions` in that order.
4. Inspect `canary.circuit`. `openedAtAttempt` identifies the aggregate attempt
   that crossed the boundary; `attemptsAfterOpen` reveals host enforcement
   gaps.
5. Confirm both cohorts used comparable routing, workloads, telemetry, and
   release identity. Do not improve a metric by omitting slow or failed work.
6. For a duplicate effect, verify the application-side idempotency mechanism
   before any retry. Do not edit the attempt from `applied` to `deduplicated`.

## Resolve

1. For `insufficient-evidence`, gather representative operations without
   widening beyond the approved canary allocation, then issue a new receipt.
2. For `baseline-unhealthy`, repair or replace the baseline before judging the
   candidate. Do not promote merely because both cohorts are equally unhealthy.
3. For a dependency failure, correct the dependency or retry policy, then
   replay the exact degraded-condition test and collect a fresh canary cohort.
4. For an SLO breach or material regression, repair the release or restore the
   last accepted exact release unit at the hosting platform.
5. For a safety violation or duplicate side effect, keep the circuit open,
   investigate the boundary, add a deterministic regression, and require an
   explicit operator decision before reset.
6. Verify the new receipt, confirm `promote`, and only then let the external
   platform widen traffic.

Rollback the agent release as one artifact. Leave backward-compatible database
migrations in place unless the application-specific runbook proves a reviewed
`down()` is non-destructive and the operator separately approves it. Restart
long-running workers when the host platform requires it, then repeat health and
authenticated smoke checks before traffic returns.

Escalate to the release owner when telemetry completeness is disputed, the
baseline is not comparable, the circuit opened, any safety or duplicate-effect
signal appears, attempts continued after open, a database action is proposed,
or the hosting platform cannot restore the exact accepted release.
