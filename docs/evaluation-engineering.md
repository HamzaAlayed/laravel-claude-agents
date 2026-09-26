# How do we know an agent change got better?

Last verified 2026-09-26 against pack v9.5.0.

Agent output is nondeterministic, so a convincing evaluation needs more than a
successful demo or an LLM saying the answer looks good. Laravel Guild evaluates
representative tasks against declared outcomes, seals the evidence into a
source-bound receipt, and compares the candidate with an accepted baseline.

The live run remains opt-in and billed. Hosted CI validates the evaluator,
fixtures, parsers, safety boundaries, and regression logic without secretly
spending model credits.

## What is the source of truth?

Four files divide responsibility:

| Source | Authority |
| --- | --- |
| [`config/evaluation-cases.json`](../config/evaluation-cases.json) | Case ID, suite, prompt, expected outcomes, forbidden outcomes, minimum deterministic checks, and comparison metrics. |
| [`tests/eval/run-evals.sh`](../tests/eval/run-evals.sh) | Fixture setup and executable answer-key checks. Prompts and descriptions are read from the registry. |
| [`tests/eval/baseline.json`](../tests/eval/baseline.json) | Reviewed per-case ceilings for duration, attributed tokens, and billed USD. |
| [`config/evaluation-harness.json`](../config/evaluation-harness.json) | Receipt schema, authority order, protected metrics, source artifacts, privacy exclusions, and material-regression thresholds. |

Validate their alignment without calling a model:

```sh
python3 scripts/evaluation-harness.py validate --root .
```

Validation fails if the shell suite and registry differ, a case lacks expected
or forbidden outcomes, a checks function or budget is missing, or the
comparison policy stops failing closed.

## Which cases should run?

Run the narrowest representative set affected by the change. The default suite
covers N+1 diagnosis, authorization, action extraction, secure tests, and team
memory hygiene. Opt-in cases cover delegated feature delivery, teaching,
rule replay, adaptive handoffs, and interruption recovery.

```sh
./tests/eval/run-evals.sh --list
./tests/eval/run-evals.sh n-plus-one
./tests/eval/run-evals.sh feature feature-resume
```

Live runs use a disposable fixture worktree. They may write only inside that
throwaway copy. They do not run against the application that contains the
agent pack. A manually dispatched hosted run additionally requires explicit
spend confirmation.

Use sequential runs for comparisons. Parallel runs deliberately ignore the
duration ceiling because shared API and CPU contention makes wall time
incomparable; all other evidence remains authoritative.

## What does one receipt prove?

Each case emits `<case>.receipt.json` next to its derived artifacts. The receipt
contains:

- the exact case-definition, evaluator, registry, and budget hashes;
- deterministic check descriptions and pass/fail totals;
- process exit and timeout status;
- duration, attributed tokens, billed USD, and tool-call count;
- budget limits and any breaches;
- hashes of checks, cost, status, and diff evidence; and
- an optional rubric-judge score marked `advisory-only`.

The receipt intentionally excludes raw transcripts, assistant prose, tool
inputs, diff bodies, and secrets. Those sources can be retained separately for
short-lived diagnosis, but they are never copied into the durable receipt.

Verify both the receipt and its current source files:

```sh
python3 scripts/evaluation-harness.py verify \
  --root . \
  --receipt tests/eval/results/20260926T120000Z/n-plus-one.receipt.json \
  --check-sources
```

A PASS requires all deterministic checks, the declared minimum coverage, a
successful non-timeout execution, complete source evidence, and all applicable
ceilings. The rubric judge can explain a disagreement, but it cannot turn a
FAIL into PASS or a PASS into FAIL.

## How do we detect a regression?

Compare receipts created from the same case definition:

```sh
python3 scripts/evaluation-harness.py compare \
  --root . \
  --baseline /path/to/accepted/n-plus-one.receipt.json \
  --candidate tests/eval/results/20260926T120000Z/n-plus-one.receipt.json
```

Keep the baseline receipt with its complete derived result directory. Comparison
re-verifies both receipts against their source artifacts; a detached JSON file
is not sufficient evidence.

The command exits nonzero when the candidate fails, loses deterministic
quality coverage, lacks a required metric, or materially regresses an enabled
metric beyond both its ratio and minimum-delta threshold. Absolute committed
ceilings still apply independently, so a fast baseline cannot excuse an
over-budget candidate.

One comparison is evidence, not statistical certainty. Agent runs are
stochastic: for an important release, repeat the same sequential case at least
three times with the same model and environment, retain every receipt, and
investigate inconsistent verdicts. Never average away a deterministic failure.
The application-performance claim “fewer queries without behavior change” is a
different layer and still requires the repeated read-only
[outcome benchmark](outcome-benchmark.md).

## How does this gate a release?

The required `evaluation harness` CI job validates the registry and runs the
receipt, tamper, privacy, path, judge-authority, and regression tests. The
existing coordinator hash gate separately refuses changed delegation behavior
unless an operator records a billed feature evaluation or a dated reviewed
waiver in `tests/eval/baseline.json`.

The gate does not pretend that CI executed a live model. When a change affects
agent behavior, the release owner selects the impacted billed cases, reviews
their receipts, and runs `compare`. A regression command exits unsuccessfully;
do not publish until the cause is fixed or the changed expectation and budget
are reviewed as an intentional product change.

## Symptoms

- `validate` says the registry, shell cases, or budget cases differ.
- A run completes but the receipt verdict is `FAIL`.
- `verify --check-sources` reports a stale contract, changed hash, or symlink.
- `compare` reports quality, duration, token, dollar, or tool-call regression.
- The advisory judge disagrees with deterministic checks.

## Triage

1. Preserve the result directory before changing any evidence.
2. Read the receipt's `execution`, `deterministic`, `budget`, and `artifacts`
   sections in that order.
3. Re-run `verify --check-sources`; do not hand-edit a receipt or its hash.
4. For a metric regression, confirm case definition, model, sequential mode,
   environment, and delegation shape match the baseline.
5. For a judge disagreement, inspect the diff and outcome rubric. Treat it as a
   prompt to audit the deterministic answer key, never as authority to override
   it.

## Resolve

1. Fix agent behavior or the evaluator defect and run the same case again.
2. Add a deterministic regression before accepting a newly discovered false
   pass or false failure.
3. Change expected or forbidden outcomes only when product behavior really
   changed; that changes the case hash and intentionally prevents comparison
   with an obsolete definition.
4. Raise a ceiling only from reviewed sequential evidence. Record the basis in
   `tests/eval/baseline.json`; never edit a candidate receipt downward.
5. Roll back an unpublished evaluator change by restoring the manifest,
   registry, shell integration, tests, and documentation together. Old receipts
   remain historical evidence but will correctly verify as stale under a new
   contract.

Escalate to the release owner when the representative case is disputed, live
spend is not authorized, the model or environment cannot be held comparable,
the same deterministic failure repeats, or accepting a regression would change
the promised behavior or budget.
