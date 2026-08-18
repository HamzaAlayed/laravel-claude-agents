# Close the orchestration-audit contract — design

**Date:** 2026-08-18
**Status:** Approved for planning
**Release:** 1.42.0

**Goal:** Make the three Blocking rules the 2026-08-12 orchestration audit
found — write-scope, never-patch, verify-before-advancing — actually bind
command-driven runs, by moving them from `agents/delivery-coordinator.md`'s
body into the shared Interface block the 9 pipeline commands already carry.
Apply the five Should-fix routing/note items in the same release. Ship
`/audit-agents` (already on main) as the repeatable check that this class of
drift stays closed.

**Why this exists:** [the 2026-08-12 audit](../../evals/2026-08-12-orchestration-audit.md)
returned DRIFT-FOUND: 3 Blocking, 5 Should-fix, 8 Nit. The audit was
report-only by design. Those three Blocking rules still live only in the
coordinator body — a file `/make-feature` and its 8 siblings never load.
Same bug shape as v1.24.0 (`NOT-CHECKED`), v1.36.0 (stage-budget), and
v1.41.0 (harvest).

**Versioning:** this release is **1.42.0**. The milestone's originally
planned Adoption release (README quickstart, docs index, onboarding guide)
slides from 1.42.0 to **1.43.0** — the second slide; 1.41.0 already took
the first. Record that in
[the milestone spec](2026-08-06-prove-it-milestone-design.md)'s header in
the same commit that ships the version bump.

## Scope

**In:**

- The three Blocking Interface-placement findings, as one compact clause
  appended to the shared Interface paragraph, byte-identical across all 9
  pipeline commands.
- The five Should-fix items: a documented-exception note under the
  coordinator's Working interface, plus four routing-table path additions
  (`docs/tech-debt.md`, `docs/db/<migration>.md`, `docs/design/system.md`,
  `docs/backlog/backlog.md`).
- Changelog, VERSION + five manifests → 1.42.0, Gemini (and Codex)
  rebuild, billed `feature` re-pin of `coordinator_hash`, README
  negative-control wording for the `feature` case, `/audit-agents`
  verification (empty-diff + full scan).

**Out:**

- The eight Nits (do not dump them into the Interface paragraph).
- Sprite-hover, agent-cost instrument, `/ship-checklist` wiring, Adoption.
- Any change to agent capabilities or tool grants.

## The exact Interface clause

Appended to the existing Interface paragraph, matching its established
terseness and hyphen style — after the harvest sentence, before the
paragraph's final "Stage returns are internal..." line:

> **You do not build and you do not patch** — Write/Edit only under
> `docs/**`; never edit a specialist's files to "just fix it" (re-brief or
> escalate). **Verify before advancing** — re-run that brief's success
> criteria yourself; a specialist's `STATUS: done` is a claim, not a `✔`.

Write-scope and never-patch are one refusal (the main thread does not
touch app code). Verify-before-advancing is its own sentence. Coordinator
body keeps the long form; this clause is the command-driven binding.

This text must land byte-identical in all 9 command files, in the same
position within each file's Interface paragraph:

`commands/{add-policy,audit-n-plus-one,add-test,review-pr,refactor-to-action,make-feature,optimize-query,upgrade-laravel,ship-checklist}.md`

Then `python3 scripts/build-gemini-extension.py` (and the Codex builder)
so the mirrors do not drift.

## Should-fix edits

In `agents/delivery-coordinator.md`:

1. Directly under `## Working interface`, one note that this section is
   the coordinator's own superset of the shared Interface contract the 9
   pipeline commands carry, and that omitting that blockquote here is
   deliberate. The note must **not** contain the exact substring
   `> **Interface:**` — Dimension 3 of `/audit-agents` identifies Interface
   blocks by that marker, and a mention would look like a drifted block.
2. Routing table:
   - Prioritization artifact column also lists `docs/backlog/backlog.md`.
   - Design artifact column also lists `docs/design/system.md`.
   - Database impl artifact column also lists `docs/db/<migration>.md`.
   - New row: Tech debt / `tech-lead` / `docs/tech-debt.md`, immediately
     after the existing Code review row.

## Side effect: the coordinator-hash gate

`coordinator_hash()` hashes `agents/delivery-coordinator.md`'s raw bytes
plus every distinct `> **Interface:**` line across `commands/*.md`. Both
the Interface clause and the coordinator Should-fix edits change that
hash. Resolved the normal way: a billed re-run of
`./tests/eval/run-evals.sh feature` backs the pin update in the same
release, not a silent hash bump or a waiver. Approved 2026-08-18.

## Validation

- **New guardrail ratchets** (TDD): the two Interface phrases present in
  all 9 command files; the Working-interface note present once; the four
  routing paths present in the coordinator file. Same pattern as the
  harvest ratchet added in v1.41.0.
- **Existing guardrail** (Interface block byte-identical across all 9)
  continues to cover the paragraph as a whole.
- **`/audit-agents HEAD`** → `CLEAN — no agent-facing files changed vs HEAD`,
  no reviewers spawned.
- **`/audit-agents` full scan** → CLEAN. Remaining findings are Nits;
  Nits do not fail the verdict. A Should-fix or Blocking after this
  release's edits means the fix missed.
- **Billed `feature` run** (~$5–7, last comparable run 8 was $3.44 / 726s).
  Re-pin `coordinator_hash` from that run. Write
  `docs/evals/2026-08-18-run-9.md`. Harvest + closing `VERIFIED` /
  `NOT-CHECKED` already asserted by the answer key; the new Interface
  rules are observed qualitatively in the transcript (the harness cannot
  currently see per-stage specialist returns — [run 8](../../evals/2026-08-12-run-8.md)).

## README negative-control

`tests/eval/README.md` currently claims an inline Tag stub "passes nine of
ten checks and fails exactly that one." Harvest checks on `feature` are
unconditional, and harvest is gated on ≥2 specialists, so a non-delegating
stub also misses `docs/team/stack.md` and the delivery log. Correct to:
fails `check_delegated` and the two harvest checks; the other seven pass.

## What this release does not do

- Does not fold the eight Nits into the Interface paragraph. The block is
  already one dense paragraph; adding them recreates unreadability, which
  is how rules get stranded in the coordinator body.
- Does not wire `/audit-agents` into CI or `/ship-checklist`.
- Does not add a subagent-inclusive eval log (run-8 gap; own plan).
- Does not ship sprite-hover, cost-instrument, or Adoption.
