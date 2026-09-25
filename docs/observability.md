# How do I verify a delivery trace?

Last verified 2026-09-25 against pack v8.9.0.

Laravel Guild records one typed observability event for every persisted delivery
mutation. The machine-readable contract is
[`config/observability-harness.json`](../config/observability-harness.json). The
runtime implementation is in
[`scripts/guild-kernel/kernel.py`](../scripts/guild-kernel/kernel.py), and its
independent conformance suite is
[`tests/observability/test_delivery_observability.py`](../tests/observability/test_delivery_observability.py).

## Which artifact is authoritative?

`docs/delivery/<name>/kernel.json` remains the authority source. Its
`observability_events` array is a monotonic, hash-chained ledger. The kernel
atomically derives two human- and tool-facing artifacts from that state:

- `events.jsonl` contains one compact schema-versioned JSON object per event.
- `observability.md` summarizes the trace, status, usage, event counts, and
  current stage statuses.

Both files are views. Do not hand-edit them or use them to override
`kernel.json`.

## What does each event prove?

Every event carries a schema version, sequence, event ID, timestamp, trace and
span correlation, delivery and stage identity, actor, status snapshot,
aggregate usage, authoritative state hash, previous event hash, and its own
event hash. Event types cover plans, claims, approvals, waivers, checkpoints,
tool and completion telemetry, budget and loop stops, retries, recovery,
feedback, pull requests, pairing, and reports.

The ledger deliberately excludes raw prompts, raw tool inputs, report bodies,
and secret values. It records bounded state and correlation evidence, not
conversation history.

The hash chain detects missing, reordered, or modified records and drift
between the current state and derived files. It is not a digital signature and
does not defend against arbitrary code running as the same operating-system
account and deliberately rewriting every hash.

## Verify a delivery

From the repository root, run:

```sh
python3 scripts/guild-kernel/guild.py observe verify \
  --root . --name <delivery>
```

A current delivery returns exit code `0` and output shaped like:

```json
{"status":"healthy","events":5,"latestStateHash":"<sha256>","errors":[]}
```

`unavailable` is expected only for a delivery created before v8.9.0 and not yet
mutated by the upgraded kernel. Its next persisted mutation starts the ledger
without inventing earlier events. `unhealthy` returns exit code `1` and blocks
dispatch or closure.

Inspect the typed trail without reading raw conversations:

```sh
python3 scripts/guild-kernel/guild.py observe list \
  --root . --name <delivery>
```

## Symptoms

- `observe verify` returns exit code `1` with `status: unhealthy`.
- The output reports an invalid sequence, previous hash, event hash, or state
  hash.
- The output says `events.jsonl` or `observability.md` is missing, unreadable,
  symlinked, or different from kernel state.
- A later kernel mutation refuses to save because the authoritative event
  ledger is invalid.

## Triage

1. Run `observe verify` and preserve its complete JSON result.
2. Run `observe list` only when the authoritative ledger can still be parsed.
   Confirm the last valid `seq`, `eventId`, and `eventHash`.
3. Inspect `git status --short` and the delivery directory. Determine whether
   only a derived file changed or whether `kernel.json` also changed.
4. If only `events.jsonl` or `observability.md` drifted, compare it with the
   authoritative `observability_events` array. Do not copy the derived data
   back into `kernel.json`.
5. If the latest event state hash differs from `kernel.json`, stop the delivery.
   A derived-view repair cannot safely determine which authoritative mutation
   was intended.

## Resolve

1. When only a derived file is missing or stale, regenerate both views:

   ```sh
   python3 scripts/guild-kernel/guild.py observe repair \
     --root . --name <delivery>
   ```

   The command first verifies the authoritative chain and state hash. It emits
   no new lifecycle event because it does not mutate authoritative state.

2. Run `observe verify` again. Continue only when it returns `healthy` with an
   empty `errors` array.
3. When `kernel.json` or its embedded chain is invalid, do not use `repair` and
   do not recalculate hashes manually. Restore the whole delivery directory
   from a known-good checkpoint or source-control revision, then verify it
   before resuming.
4. Roll back an unpublished v8.9 kernel change by restoring the previous pack
   version and the matching known-good delivery directory together. Mixing a
   newer `kernel.json` with older derived files intentionally reports drift.

Escalate to the release owner when authoritative state is invalid, the last
known-good checkpoint is unclear, a trace contains a forbidden raw payload, or
repair would require inventing a missing lifecycle event.
