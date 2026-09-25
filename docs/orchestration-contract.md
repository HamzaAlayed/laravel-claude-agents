# Canonical orchestration contract

Last verified 2026-09-25 against pack v9.2.0.

Laravel Guild has one human-readable lifecycle contract for pipeline execution.
Its authoritative source is
[`config/orchestration-contract.md`](../config/orchestration-contract.md).
The source is materialized into the nine pipeline commands and the direct
`delivery-coordinator` surface because those entry points do not load one
another at runtime.

## Ownership boundary

The generated block owns eight shared behaviors: interface, durable checkpoints,
loop detection, retry transitions, feedback routing, interruption recovery,
delivery observability, and outcome benchmarks.
Only the text between the generated markers is synchronized. Command-specific
routing and output instructions, plus coordinator-only board, artifact, and
adaptive-routing rules, remain hand-authored beside it.

Do not edit a generated block in a command or agent. Change the canonical
source, review the shared behavior once, and regenerate every carrier:

```sh
python3 scripts/sync-orchestration-contract.py --write
python3 scripts/sync-orchestration-contract.py --check
python3 -m unittest discover -s tests/orchestration -t tests/orchestration -v
```

Then rebuild the generated distributions:

```sh
python3 scripts/build-gemini-extension.py
python3 scripts/build-codex-extension.py
```

## Carriers

The checked carrier set is intentionally closed:

- `commands/add-policy.md`
- `commands/add-test.md`
- `commands/audit-n-plus-one.md`
- `commands/make-feature.md`
- `commands/optimize-query.md`
- `commands/refactor-to-action.md`
- `commands/review-pr.md`
- `commands/ship-checklist.md`
- `commands/upgrade-laravel.md`
- `agents/delivery-coordinator.md`

Adding or removing a pipeline surface requires an explicit update to `CARRIERS`
in `scripts/sync-orchestration-contract.py`. Discovery fails closed when an
unregistered file contains the contract interface or a registered carrier
loses it.

## Symptoms

- CI reports that a generated orchestration contract is stale.
- The checker reports a missing or unexpected carrier.
- The checker reports duplicate, absent, or reversed generated markers.
- A distribution build changes command or coordinator output unexpectedly.

## Triage

1. Run `python3 scripts/sync-orchestration-contract.py --check` and use the
   reported path as the first inspection target.
2. Confirm the canonical source contains exactly one of each required heading,
   in order, with one final newline.
3. Compare the carrier set with the pipeline entry points the change intends to
   support.
4. Inspect hand-authored text outside the markers separately; the generator
   deliberately does not own it.

## Resolve

1. Make the behavioral change in `config/orchestration-contract.md`, or update
   the explicit carrier registry when the set of runtime entry points changed.
2. Run the write command once, then the check command and unit tests.
3. Rebuild Gemini and Codex distributions and review their diffs.
4. Commit the source, generated carriers, tests, and distribution artifacts in
   the same release.
