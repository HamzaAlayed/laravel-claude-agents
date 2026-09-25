# Criterion-linked evidence

Laravel Guild does not treat “some check passed” as proof that a stage met all
of its success criteria. Each criterion receives a stable ID at plan time, and
the kernel requires passing evidence for every ID before the stage can finish.

## Plan the evidence contract

Pair `success_criteria` and `criterion_ids` one-to-one. IDs must be unique
lowercase kebab-case names and should describe the observable behavior rather
than the implementation:

```json
{
  "id": "backend",
  "agent": "backend-developer",
  "success_criteria": [
    "the endpoint returns 201 for valid input",
    "an unauthorized caller receives 403"
  ],
  "criterion_ids": ["valid-input-created", "unauthorized-rejected"],
  "depends_on": [],
  "owned_paths": ["app/Http", "tests/Feature"],
  "approval_categories": []
}
```

The CLI derives `criterion-1`, `criterion-2`, and so on when an integration
omits the IDs, but orchestrators should provide meaningful names. The IDs are
persisted in `kernel.json`, so resumes and reports keep the same vocabulary.

## Brief and verify every criterion

`guild ready` returns each lane's `criteria` rows. Include those rows in the
specialist brief. Every `VERIFIED` line must contain exactly `criterion`,
`runner`, and `args`:

```text
VERIFIED: {"criterion":"valid-input-created","runner":"artisan-test","args":["--filter=CreateDonationTest::valid_input"]} → 1 passed
VERIFIED: {"criterion":"unauthorized-rejected","runner":"artisan-test","args":["--filter=CreateDonationTest::unauthorized"]} → 1 passed
```

One criterion may have several evidence records. One passing record does not
cover a different criterion. Before reporting, inspect the matrix:

```sh
python3 scripts/guild-kernel/guild.py criterion list \
  --root . --name donations
```

The board renders the same state compactly:

```text
✔ backend criteria[valid-input-created:✓,unauthorized-rejected:✓]
```

The marks mean:

- `✓` passing registered-runner evidence exists.
- `~` the user explicitly waived the missing evidence.
- `·` evidence is still pending; the stage cannot finish.

Unknown criterion IDs are rejected before any verification runner executes.
`NOT-CHECKED` cannot name an unwaived criterion. A failed runner also cannot
create evidence.

## Human waiver checkpoint

A waiver is an exception for evidence that genuinely cannot be produced, not a
shortcut around a failing check. The coordinator explains the exact criterion,
why evidence is unavailable, and the risk, then offers numbered choices to
verify another way, accept the gap, or stop the lane.

Only after the user chooses to accept the gap may the main thread run:

```sh
python3 scripts/guild-kernel/guild.py criterion waive \
  --root . --name donations --stage backend \
  --criterion unauthorized-rejected \
  --reason "Identity provider sandbox is unavailable; user accepted manual staging verification"
```

The kernel persists the criterion ID, reason, `by: user`, and UTC timestamp.
Subagents are blocked from invoking `criterion waive`, and direct edits to
kernel state are blocked. The board exposes the waiver with `~`, so completion
never makes the exception invisible.

## Compatibility

Completed delivery state written before v8 remains readable and complete.
New reports use the v8 three-field verification schema. An unfinished stage
file from an older release must add a declared `criterion` to every
`VERIFIED` record before `guild report` can accept it.
