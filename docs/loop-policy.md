# Unproductive-loop detection

Laravel Guild stops a claimed specialist when it repeats the exact same tool
cycle three times. The guard runs before each tool call, so the call that would
complete the third repetition does not execute.

## What counts as a loop

Each call becomes a SHA-256 signature over two values: the tool name and its
canonical JSON input. The detector checks the tail of the current stage history
for exact cycles one to four calls long.

Examples:

- `Read(A), Read(A), Read(A)` is a repeated one-step cycle.
- `Read(A), Bash(test), Read(A), Bash(test), Read(A), Bash(test)` is a
  repeated two-step cycle.
- `Read(A), Read(B), Read(A)` is not a loop because the tail is not three
  identical cycles.
- Repeating a five-step sequence is outside the detector's bounded window and
  is not guessed to be a loop.

Matching is intentionally exact. The kernel does not infer that two different
commands have the same meaning. A changed tool name or input changes the
signature and breaks the pattern.

## What happens when a loop is detected

The pre-tool hook denies the current call, marks the stage `failed`, and marks
the delivery `stopped`. It also clears the active claim timer so the lane cannot
continue consuming its runtime budget.

Inspect the durable event and board:

```sh
python3 scripts/guild-kernel/guild.py loop list \
  --root . --name checkout
python3 scripts/guild-kernel/guild.py board \
  --root . --name checkout
```

`loop list` returns the stage, cycle length, repeat count, tool sequence, short
fingerprint, and detection time. The generated
`docs/delivery/<name>/loops.md` renders the same evidence. The board appends a
reason such as `loop:2-step-cycle-x3` to the failed lane.

Do not retry the same sequence or merely increase its budget. A later attempt
must use an explicitly changed brief or plan that addresses why no progress was
made.

## Privacy and retention

Raw tool input is never persisted in the loop history or event. Kernel state
stores only the SHA-256 signature, tool name, and UTC timestamp. The per-stage
history is capped at 24 calls. A new explicit claim resets the detection window;
durable delivery-level loop events remain available for audit.

The normal trace-redaction policy still applies to other observability output.
The loop guard does not weaken secret, environment-file, production, or
read-only reviewer policies.

## Boundaries

The detector applies to a claimed Guild specialist. Direct single-specialist
work without an active kernel stage is unchanged. The policy detects exact
repetition, not semantic stagnation, and it cannot classify cycles longer than
four calls. Stage budgets remain the broader ceiling for time, tool calls,
turns, tokens, and cost.

## Verification

These repository commands exercise the detector and its guardrail wiring:

```sh
python3 -m unittest tests.kernel.test_loop_policy -v
bash tests/guardrails.test.sh
```

The tests cover one-step and multi-step cycles, changed-call breaks, hook-event
deduplication, the four-step bound, privacy, history retention, claim resets,
legacy state, CLI output, and pre-execution denial.
