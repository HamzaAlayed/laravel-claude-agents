# Recover interrupted claims

Laravel Guild treats a missing process as an interruption, not a failed stage
and not a successful return. Recovery preserves what the kernel observed,
requires an explicit decision, and starts continued work through the normal
claim path.

## Inspect before changing state

Every delivery start or resume begins with:

```sh
python3 scripts/guild-kernel/guild.py recovery list \
  --root . --name checkout
```

The result separates `active_claims` from durable recovery `events`. An active
claim can still belong to a live runtime. Confirm the user interrupt, process
exit, runtime error, or host restart before recording it as interrupted. The
kernel does not use an age threshold because elapsed time cannot prove that a
process is dead.

## Freeze a confirmed interruption

Only the main thread may freeze a claim:

```sh
python3 scripts/guild-kernel/guild.py recovery interrupt \
  --root . --name checkout --stage backend \
  --source process-exit \
  --reason "The previous agent process exited before returning." \
  --event-id process:run-01K5M9Y4A7
```

Valid sources are `user`, `process-exit`, `runtime-error`, and `host-restart`.
The event ID identifies the observed interruption. Repeating identical data is
safe; reusing the ID with different data fails.

The stage changes from `running` to `interrupted`. Its active claim timer is
cleared, native writes remain blocked, and `report` is rejected. The generated
`docs/delivery/<name>/recoveries.md` and `transitions.md` files show the event
and status change.

## Preserve only observed usage

Claim and pre-tool boundaries update `last_activity_at`. Recovery accounts for
known elapsed time only through that timestamp and preserves already-metered
tool calls. Time while the runtime was offline is not charged.

The missing completion receipt means turns, tokens, and USD are unavailable.
The event records those dimensions as unavailable; the kernel never substitutes
zero or a guess. A continued attempt later records its own complete receipt,
while all known usage remains cumulative. If known activity already reached
`max_seconds`, the stage and delivery become `budget_exceeded` instead of
recoverable.

## Continue or stop

Continue when the partial workspace is safe to inspect:

```sh
python3 scripts/guild-kernel/guild.py recovery resolve \
  --root . --name checkout \
  --event-id process:run-01K5M9Y4A7 \
  --action continue \
  --note "Inspect partial backend files before editing."
```

`continue` changes the stage to `queued`. It does not consume the one retry,
erase known usage, or pretend that the interrupted attempt completed. The next
`ready` row includes the event ID, source, and reason. A fresh `claim` rechecks
dependencies, approvals, WIP, and path ownership before the specialist can
write or report.

Stop when the partial state cannot be trusted:

```sh
python3 scripts/guild-kernel/guild.py recovery resolve \
  --root . --name checkout \
  --event-id process:run-01K5M9Y4A7 \
  --action stop \
  --note "The external operation cannot be proven idempotent."
```

`stop` changes the stage to `failed` and the delivery to `stopped`. The main
thread must then present the board and recovery record to the human. An
identical resolution is idempotent; a conflicting second resolution fails.

## Compatibility

Existing `kernel.json` files load with an empty recovery ledger. A legacy
claimed stage derives `last_activity_at` from `claimed_at`, so recovery can
freeze it without inventing later activity. No historical interruption event
is synthesized.

Direct single-specialist work outside a planned delivery is unchanged.
Interrupted planned deliveries remain subject to native-write and Bash policy;
they cannot fall through to the direct-work fast path.

## Verification

Run the focused state-machine suite and guardrail harness:

```sh
python3 -m unittest tests.kernel.test_recovery_policy -v
bash tests/guardrails.test.sh
```

The focused suite covers discovery, last-activity accounting, unavailable
metrics, authority, idempotency, continue and stop actions, retry preservation,
budget precedence, legacy state, generated views, and the CLI lifecycle.
