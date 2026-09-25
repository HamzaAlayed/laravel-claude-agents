# How do I prove a performance improvement without changing behavior?

Last verified 2026-09-25 against pack v9.2.0.

Laravel Guild accepts a performance outcome only when repeated baseline and
candidate captures produce a passing, durable receipt. The machine-readable
policy is [`config/benchmark-harness.json`](../config/benchmark-harness.json),
the comparator is
[`scripts/outcome-benchmark.py`](../scripts/outcome-benchmark.py), and the
focused contract tests live in [`tests/benchmark/`](../tests/benchmark/).

The comparator does not execute the application or connect to its database.
The optional [Laravel capture adapter](benchmark-capture.md) runs an
application-owned scenario behind a fail-closed query guard and produces this
exact schema. The comparator then validates and compares the artifacts without
running a migration or database mutation.

## What must a capture contain?

Baseline and candidate files use the same exact scenario object:

```json
{
  "schemaVersion": 1,
  "scenario": {
    "id": "orders-index",
    "version": 1,
    "kind": "http",
    "target": "GET /api/orders",
    "objective": "query-count",
    "datasetHash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "datasetRows": 10000,
    "runtimeHash": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "databaseMode": "read-only",
    "warmupRuns": 2
  },
  "runs": [
    {
      "queryCount": 40,
      "writeQueryCount": 0,
      "latencyMs": 101.4,
      "status": "http:200",
      "responseHash": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
      "databaseHash": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
      "eventsHash": "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
      "jobsHash": "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
    }
  ]
}
```

Repeat the run object at least seven times after at least two unrecorded
warmups. A real capture may contain up to 100 measured runs. The harness
rejects a run with a database write, unstable behavior hashes, extra or missing
fields, non-finite latency, or a mismatched scenario, dataset, or runtime.

Persist hashes and aggregate measurements only. Never put raw SQL, response
bodies, database row values, event payloads, job payloads, or secrets in these
artifacts. Normalize nondeterministic response fields before hashing only when
the scenario contract explicitly defines that normalization.

## Which objective should I choose?

- `query-count` requires both a median reduction of at least one query and 5%,
  with no query-p95 regression. Latency p95 may regress by at most 5%.
- `latency` requires at least a 5% latency-p95 improvement and no query-p95
  increase.
- `query-and-latency` requires both the query and latency thresholds.

Every objective also requires identical status, response, database, event, and
job hashes between baseline and candidate. Latency is reported as nearest-rank
p50, p95, and p99; query count is reported as median and p95. The gate uses the
tail measures named above instead of a single manual timing or an average.

## Create and verify a receipt

Store captures and the receipt below the delivery that owns the work:

```sh
python3 scripts/outcome-benchmark.py compare \
  --root . \
  --baseline docs/delivery/orders/benchmarks/baseline.json \
  --candidate docs/delivery/orders/benchmarks/candidate.json \
  --output docs/delivery/orders/benchmarks/receipt.json

python3 scripts/outcome-benchmark.py verify \
  --root . \
  docs/delivery/orders/benchmarks/receipt.json
```

`compare` writes the receipt even when a valid comparison fails, so the failed
outcome remains inspectable. Its exit codes are `0` for pass, `1` for a valid
comparison that missed its objective, and `2` for malformed or unsafe input.
`verify` recomputes the receipt from the source files and rejects a failed
verdict, changed source hash, altered threshold, or tampered receipt hash.

Declare the performance criterion in the stage's `benchmark_criteria`, then
bind the passing receipt in the stage report:

```text
VERIFIED: {"criterion":"queries-lower","runner":"outcome-benchmark","args":["docs/delivery/orders/benchmarks/receipt.json"]}
```

The kernel runs `verify` again. A benchmark runner on an undeclared criterion,
or a non-benchmark runner on a declared benchmark criterion, is rejected before
the stage can complete.

## Symptoms

- `compare` exits `1` and the receipt has `verdict: fail`.
- `compare` exits `2` because a capture is malformed, mutating, unstable, or
  outside the repository.
- `verify` reports a source hash, receipt hash, or recomputed receipt mismatch.
- The kernel says the criterion requires the `outcome-benchmark` runner.

## Triage

1. Read the receipt's `failures` array and preserve both source captures.
2. Confirm baseline and candidate used the same scenario version, dataset hash,
   dataset row count, runtime hash, warmup count, and read-only target.
3. Confirm every measured run has `writeQueryCount: 0` and stable behavior
   hashes. Treat a behavior mismatch as a correctness failure, not noise.
4. Review median query count, query p95, latency p50/p95/p99, and the selected
   objective's threshold. Do not discard slow runs after seeing the result.
5. If verification changed after comparison, inspect source-control and file
   hashes before rerunning anything.

## Resolve

1. Fix capture instrumentation or the application query shape; do not weaken a
   threshold or normalize away a real behavior difference.
2. Collect a fresh baseline and candidate pair from the same representative
   dataset and runtime, including warmups and all measured runs.
3. Create a new receipt, run `verify`, then let the kernel execute the same
   receipt through the registered runner.
4. To roll back an unpublished optimization, restore the PHP change and its
   matching baseline/candidate/receipt set together. A receipt from a different
   source pair intentionally fails verification.

Escalate when a representative dataset cannot be used safely, capture tooling
cannot guarantee read-only execution, behavior equivalence is disputed, or the
instrumentation may miss database queries. A passing receipt proves the
committed measurements and thresholds; it does not prove that instrumentation
was complete or that the dataset represents production.
