# Stage timing and live scheduler evaluation

November 25, 2026

## Results

**35 of 36 deliveries verified.** Claude Code reported $0.82277 for the comparison.

Each cell shows median time to verified delivery, median USD per attempt,
and acceptance checks passed across three attempts. The failed run contributes
to the cost and quality totals.

| Workload | One agent | v9.11.2 waves | Rolling dispatch |
| --- | --- | --- | --- |
| Narrow fix | 4.08 s / $0.00466 / 9/9 | 4.44 s / $0.00424 / 9/9 | 4.29 s / $0.00488 / 9/9 |
| Sequential | 14.84 s / $0.02591 / 26/39 | 22.94 s / $0.03343 / 39/39 | 28.21 s / $0.03094 / 39/39 |
| Independent | 10.87 s / $0.01943 / 30/30 | 9.65 s / $0.02527 / 30/30 | 10.41 s / $0.02624 / 30/30 |
| Checkpoint hybrid | 16.20 s / $0.03191 / 39/39 | 16.47 s / $0.03232 / 39/39 | 15.49 s / $0.03174 / 39/39 |

- **Narrow fix.** Each mode made one worker call. The per-trial ranking changed.
  The small median differences provide no evidence of a scheduling effect.
- **Sequential.** One agent finished its two verified trials 9.07–11.98 seconds
  ahead of waves and 9.44–12.41 seconds ahead of rolling. Its other response
  failed JSON parsing, leaving zero gradeable artifacts. Cost per verified
  delivery, including that failed attempt, was $0.04239 for one agent,
  $0.03360 for waves, and $0.03199 for rolling.
- **Independent.** Both parallel modes beat one agent in all three matched
  trials. Waves had the lowest median, 1.22 seconds faster than one agent
  at an extra $0.00584 per attempt. All three tasks were eligible at the
  start, so the two schedulers had the same opportunity to overlap work.
- **Checkpoint hybrid.** Rolling beat waves in two of three matches and had
  the lowest median, 0.97 seconds faster than waves. The Laravel rules
  stage waited a median 2.04 seconds from eligibility to claim with waves
  and 6.33 milliseconds with rolling. Rolling started it before the
  independent QA matrix verified in all three trials. All modes passed
  all 39 checks.

## Method

The [evaluation runner](../../tests/eval/run-stage-timing.py) dispatched live
Claude Code workers using Sonnet 5.5 at low effort. It ran three matched
repetitions per workload and rotated the execution order. The harness ran
one trial at a time. Worker calls within a trial could overlap according to
its scheduling mode.

| Workload | Dependency shape | Checks per trial |
| --- | --- | ---: |
| Narrow fix | Produce the Laravel validation rule from a frozen API contract. | 3 |
| Sequential | Define the contract, derive its validation rule, produce a QA matrix from the rule, then summarize the matrix. | 13 |
| Independent | Produce the contract, validation rules, and QA matrix independently from supplied inputs. | 10 |
| Checkpoint hybrid | QA matrix and review can proceed while the API contract is paused. The Laravel rule depends on the verified contract. The simulated approval arrives after six seconds. | 13 |

One agent produced the deliverables in one Claude Code session. It used one
turn for the first three workload shapes and resumed the same session for a
second turn after the checkpoint in the hybrid. Wave dispatch used the
original v9.11.2 planner and waited for the entire current wave to verify.
Rolling dispatch launched each newly eligible stage when a worker slot
opened. Both scheduler modes used the same instrumented kernel and
specialized worker prompts with the same model and effort settings.

Wall time ran from kernel planning to the final verification. The runner
graded the artifacts deterministically for contract shape and semantics,
Laravel rule structure and PHP PCRE behavior, matrix classification, and
review counts and boundaries. A failed artifact blocked its dependents.
These probes measure synthetic Laravel artifacts and scheduling behavior.
The workers had no tools for making repository changes.

USD values come from Claude Code. In the resumed session, the runner
subtracts the first turn's cumulative usage from the second turn's reported
usage. The comparison uses three trials per cell, so the results describe
these workloads and this client configuration.

## Individual trials

Cells show wall seconds, reported USD, and checks passed. Wall time for
the failed attempt ends when the runner rejects the response.

| Workload | Trial | One agent | v9.11.2 waves | Rolling dispatch |
| --- | ---: | --- | --- | --- |
| Narrow fix | 1 | 5.32 / $0.00518 / 3/3 | 4.44 / $0.00424 / 3/3 | 4.29 / $0.00488 / 3/3 |
| Narrow fix | 2 | 4.04 / $0.00466 / 3/3 | 4.03 / $0.00405 / 3/3 | 5.02 / $0.00494 / 3/3 |
| Narrow fix | 3 | 4.08 / $0.00465 / 3/3 | 7.25 / $0.00496 / 3/3 | 3.68 / $0.00424 / 3/3 |
| Sequential | 1 | 13.87 / $0.02174 / 13/13 | 22.94 / $0.03410 / 13/13 | 23.31 / $0.03451 / 13/13 |
| Sequential | 2 | 19.03 / $0.03714 / 0/13 | 22.82 / $0.03328 / 13/13 | 28.23 / $0.03094 / 13/13 |
| Sequential | 3 | 15.80 / $0.02591 / 13/13 | 27.79 / $0.03343 / 13/13 | 28.21 / $0.03052 / 13/13 |
| Independent | 1 | 12.26 / $0.01963 / 10/10 | 9.61 / $0.02527 / 10/10 | 10.41 / $0.02624 / 10/10 |
| Independent | 2 | 10.87 / $0.01853 / 10/10 | 10.01 / $0.02533 / 10/10 | 10.63 / $0.02702 / 10/10 |
| Independent | 3 | 10.56 / $0.01943 / 10/10 | 9.65 / $0.02488 / 10/10 | 9.70 / $0.02567 / 10/10 |
| Checkpoint hybrid | 1 | 16.20 / $0.03191 / 13/13 | 15.77 / $0.03292 / 13/13 | 15.46 / $0.03288 / 13/13 |
| Checkpoint hybrid | 2 | 17.53 / $0.03215 / 13/13 | 16.95 / $0.03232 / 13/13 | 17.46 / $0.03034 / 13/13 |
| Checkpoint hybrid | 3 | 15.32 / $0.03093 / 13/13 | 16.47 / $0.03227 / 13/13 | 15.49 / $0.03174 / 13/13 |

The [machine-readable trial results](2026-11-25-stage-timing.jsonl) contain
one JSON object per trial. They retain timestamps, checked criteria, reported
usage, and source digests. Provider session IDs are omitted.
