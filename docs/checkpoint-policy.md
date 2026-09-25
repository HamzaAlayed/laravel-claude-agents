# Durable human checkpoints

Human decisions are part of delivery state. Laravel Guild stores a checkpoint
before asking its question, pauses only the affected stage, and records the
user's answer before work resumes. The authoritative record lives in
`docs/delivery/<name>/kernel.json`; the kernel generates
`docs/delivery/<name>/checkpoints.md` for humans to review.

## When to use a checkpoint

Open a checkpoint when work reaches a decision that cannot be inferred safely:
a sensitive change, an accepted verification gap, a material scope choice, or
a specialist's `needs-decision` return. Planned approval categories remain the
earlier pre-dispatch gate; checkpoints cover decisions discovered while the
delivery is running.

Do not use checkpoints for ordinary status updates or choices the existing
brief already answers.

## Open before asking

Only the main-thread orchestrator may open or resolve a checkpoint. Give the
record a stable lowercase-kebab ID, exact question and risk, two to five typed
options, and one recommended option:

```sh
python3 scripts/guild-kernel/guild.py checkpoint open \
  --root . --name checkout --stage backend --id billing-contract \
  --question "May this lane change the billing contract?" \
  --risk "A wrong retry rule can double-charge an invoice." \
  --option-json '{"id":"approve","label":"Approve the guarded design","action":"continue"}' \
  --option-json '{"id":"modify","label":"Continue with my constraint","action":"continue"}' \
  --option-json '{"id":"stop","label":"Stop this delivery lane","action":"stop"}' \
  --recommended approve
```

The command is idempotent only when the full pending record is identical. A
checkpoint ID cannot be reused for different wording, risk, options, or stage.
A claimed stage must first record its completion telemetry; opening a decision
cannot erase an active claim's usage receipt.

After the open succeeds, present the stored question and options exactly. Do
not paraphrase a resumed prompt from memory or a transcript.

## Continue independent work

An open checkpoint changes the affected stage to `paused` and records its
`checkpoint_id`. It does not pause the whole delivery. Continue dispatching any
independent stages returned by `guild ready`; dependent stages remain blocked
by their normal dependency edge.

While the checkpoint is pending, the kernel rejects `claim`, `report`, and
delivery completion for that stage. The board marks it `⏸` and names the
checkpoint ID.

## Resume and answer

At every delivery start or resume, inspect the durable records before asking
or dispatching:

```sh
python3 scripts/guild-kernel/guild.py checkpoint list \
  --root . --name checkout
```

- Present a pending record exactly as stored.
- Never ask a resolved record again.
- Continue independent `ready` lanes while a record is pending.
- Re-brief a continued lane with its stored answer and note.

Record the human's selected option from the main thread:

```sh
python3 scripts/guild-kernel/guild.py checkpoint resolve \
  --root . --name checkout --id billing-contract --option modify \
  --note "Keep the existing idempotency key and response schema."
```

A `continue` option requeues the stage. A `stop` option fails the stage and
stops the delivery. The answer persists the selected option and label, action,
optional note, `by: user`, and UTC timestamp. Repeating the identical resolution
is safe; attempting to rewrite an answer fails.

## Authority and recovery guarantees

Subagents cannot call `checkpoint open` or `checkpoint resolve`, and Bash or
native write tools cannot edit `kernel.json` directly. The coordinator may
narrate the decision in `log.md`, but that log is not authoritative.

Legacy deliveries without checkpoint fields load with empty checkpoint state.
No synthetic decision is created. A delivery interrupted after `open` resumes
with the exact pending prompt; one interrupted after `resolve` resumes from the
recorded answer without charging the human for the same decision twice.

## Verification

The release contract is covered by deterministic kernel and guardrail tests:

```sh
python3 -m unittest discover -s tests/kernel -p 'test_*.py'
bash tests/guardrails.test.sh
```

These commands verify persistence, idempotency, authority, stage-local pause,
resume behavior, independent lane progress, and stop semantics.
