# Auditable stage retries

Laravel Guild treats a retry as a state transition, not another prompt sent to
the same specialist. The first distinct failure requeues the stage for a fresh
atomic claim. A second distinct failure marks the stage `failed` and stops the
delivery.

## Request the retry after telemetry

Only the main-thread orchestrator may request a retry. Wait until the completed
specialist attempt has recorded all five budget dimensions, then provide a
stable event ID, typed source, and exact reason:

```sh
python3 scripts/guild-kernel/guild.py retry request \
  --root . --name checkout --stage backend \
  --source stage-return \
  --reason "The return omitted NOT-CHECKED." \
  --event-id agent-turn:01K5M9Y4A7
```

Valid sources are `stage-return`, `verification`, `ci`, and `review`. The event
ID must identify the originating event rather than the retry invocation. Using
the same event ID with identical data returns the stored result without
consuming another retry. Reusing it with different data fails.

The kernel rejects a request while the stage still has an active claim timer.
This prevents a retry from cancelling live work or erasing its usage receipt.
Subagents cannot request their own retry.

## Requeue, then claim normally

The first request changes the stage from `running` or `done` to `queued`. It
clears the previous attempt's `DID`, verification, flags, pairing state, and
short loop window because those records cannot prove the next attempt. Budget
usage remains cumulative.

Inspect the next wave:

```sh
python3 scripts/guild-kernel/guild.py ready \
  --root . --name checkout
```

The ready row carries the next attempt number and the stored retry source and
reason. Put that exact context in the revised brief. Start the retry through
the normal atomic claim path:

```sh
python3 scripts/guild-kernel/guild.py claim \
  --root . --name checkout --stage backend
```

This claim re-runs dependency, approval, WIP, and owned-path checks. A queued
stage cannot report. Only a claimed `running` stage whose completion telemetry
has cleared its claim timer may submit a success report.

## Stop after the second distinct failure

One retry is allowed. When a later, distinct failure requests another retry,
the kernel records the event, changes the stage to `failed`, changes the
delivery to `stopped`, and returns no ready work. The board therefore cannot
show a successful stage beside a stopped retry outcome.

Print the board and ask the human whether to change the plan or stop. Do not
increase the retry count, fabricate another event ID, or mutate kernel state.

## Inspect the audit trail

Two views answer different questions:

```sh
python3 scripts/guild-kernel/guild.py retry list \
  --root . --name checkout
python3 scripts/guild-kernel/guild.py transition list \
  --root . --name checkout
```

`retry list` shows each failure event, attempt, source, reason, authority,
timestamp, and whether it requeued or stopped the lane. `transition list`
shows every kernel-owned stage status change. The generated
`docs/delivery/<name>/retries.md` and `transitions.md` files render the same
records for review.

Confirmed CI checks and review comments enter the same retry lifecycle through
`guild ingest` or the watch loop. Their external identity becomes the stable
event ID, so duplicate delivery is safe while a different run or comment can
produce the one permitted retry or terminal second failure.

## Compatibility

Existing delivery state loads with empty retry and transition ledgers. The
kernel derives a conservative attempt count from the legacy stage status and
reopen counter; it does not invent historical events. Direct single-specialist
work outside a planned delivery remains unchanged.

## Verification

Run the focused policy suite and the complete guardrail harness:

```sh
python3 -m unittest tests.kernel.test_retry_policy -v
bash tests/guardrails.test.sh
```

The policy suite covers legal transitions, unclaimed report denial, fresh
claims, telemetry preservation, authority, idempotency, retry exhaustion,
legacy state, generated views, and CLI inspection.
