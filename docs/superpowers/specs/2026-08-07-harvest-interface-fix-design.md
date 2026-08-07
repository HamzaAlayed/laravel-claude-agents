# Harvest moves to the shared Interface block — design

**Goal:** Make team-memory harvest (`docs/team/stack.md` + `docs/delivery/<name>/log.md`)
actually fire on command-driven deliveries, by moving the requirement from
`agents/delivery-coordinator.md`'s body — a file `/make-feature` and its 8
sibling commands never load — into the shared `Interface` block those 9
commands already carry, matching the exact precedent v1.24.0 (the
`NOT-CHECKED` contract) and v1.36.0 (the stage-budget / `done when:` header)
already set for this same class of bug.

**Why this exists:** [run 7](../../evals/2026-08-06-run-7.md) (v1.40.0) proved
`teach-delivery`'s harvest never fires — the delivery-coordinator agent is
never spawned by `/make-feature`. A coordinator-body edit was shipped and a
$4.49 re-run spent "validating" it before anyone checked that the edited
file was never in context for that case either. This release is the actual
fix: put the requirement where the command's own main thread reads it.

**Versioning:** this release is **1.41.0**. The milestone's originally
planned Adoption release (README quickstart, docs index, onboarding guide)
slides to **1.42.0** — [the milestone spec](2026-08-06-prove-it-milestone-design.md)'s
"v1.39 → v1.41" header needs a one-line note recording the renumber and why,
in the same commit that ships this.

## Scope

- **Harvest artifacts covered: `docs/team/stack.md` and
  `docs/delivery/<name>/log.md` only.** These are the two pieces run 7's
  `teach-delivery` case already answer-key-tests
  (`check_file "docs/team/stack.md"`, `check_file_under "docs/delivery"
  "log.md"`). `docs/team/conventions.md`/`decisions.md` harvesting stays
  coordinator-only — no eval evidence exists yet on whether that needs the
  same fix, and this release shouldn't guess.
- **All 9 pipeline commands carry the new clause, unconditionally** —
  `commands/{add-policy,audit-n-plus-one,add-test,review-pr,refactor-to-action,
  make-feature,optimize-query,upgrade-laravel,ship-checklist}.md`. Matches
  the existing `NOT-CHECKED` and stage-budget clauses: every command carries
  the text regardless of whether a given run ends up delegating, and the
  Interface block stays byte-identical across all 9 (guardrail-enforced
  today; the new clause joins what that guardrail already checks).
- **Harvest fires only once ≥2 specialists have reported** — mirroring the
  coordinator's own existing fast-path exemption ("No board, no delivery
  log — pipeline scaffolding around a single stage is pure latency",
  `agents/delivery-coordinator.md`'s fast-path clause). A single-specialist
  ask has nothing worth harvesting; this release ports that same threshold
  into the shared Interface block for the first time, since the block
  itself has never had a conditional clause before.

## The exact clause

Appended to the existing Interface paragraph, matching its established
terseness and hyphen style (placed after the `NOT-CHECKED` closing-answer
sentence, before the paragraph's final "Stage returns are internal..."
line):

> **Once ≥2 specialists have reported, this delivery harvests too** —
> persist `docs/team/stack.md` (verified project facts + where-things-live,
> `delivery-templates` skill shape) from what they've reported, and
> maintain `docs/delivery/<name>/log.md` (phase by phase, agent by agent,
> artifact by artifact). Both exist before your final answer, not after. A
> single-specialist ask has nothing to harvest — skip both.

This text must land byte-identical in all 9 command files, in the same
position within each file's Interface paragraph.

## Side effect: the coordinator-hash gate

`coordinator_hash()` (`scripts/check_inventory_sync.py`) hashes
`agents/delivery-coordinator.md`'s raw bytes plus every distinct
`> **Interface:**` line across `commands/*.md`. Editing all 9 Interface
blocks changes that hash — `check_inventory_sync.py` will correctly flag
drift the moment the edit lands, exactly as designed. Resolved the normal
way: a billed re-run backs the pin update in the same release, not a
silent hash bump.

## Validation

One re-run of `teach-delivery` (~$4-5, drawn from the milestone's remaining
~$9.69 of its $30 ceiling — this fix is treated as a late addition to the
"Prove it" milestone rather than opening a new budget, per the human's
choice). No new answer-key checks needed: the two harvest checks already
exist from 1.40 and were never satisfied by anything in scope until now.

**Why this re-run should not repeat run 7's timeout:** the coordinator-body
edit that shipped in 1.40 (parallel lanes must be awaited, not backgrounded)
added synchronous waiting behavior to `agents/delivery-coordinator.md` — a
file this case still doesn't load, so that edit remains irrelevant to
`teach-delivery` either way. This release's actual change (two file writes
before the final answer) adds no new waiting and should not change the
run's duration materially from the original, un-mis-fixed baseline (962s).

## Testing

- **New guardrail ratchet**: the harvest clause's text is present and
  byte-identical across all 9 command files — same pattern as the existing
  stage-budget/`done when:` ratchet added in v1.36.0.
- **Existing guardrail** (Interface block byte-identical across all 9)
  continues to cover the paragraph as a whole; no changes needed there
  beyond it now covering one more sentence.
- **Existing answer-key checks** (`checks_teach_delivery`'s two harvest
  checks, `tests/eval/run-evals.sh`) are the acceptance test — no new checks
  to write.
- **Dry validation before billing**: read the edited command files back
  and confirm the clause parses as a clear, mechanically followable
  instruction (would a competent reader actually know what file to write
  and when) — the same "read it before trusting it" habit this milestone
  has used throughout, since a real re-run costs money and a synthetic
  transcript can't substitute for a live agent's follow-through.

## What this release does not do

- No change to `agents/delivery-coordinator.md` beyond what 1.40 already
  shipped (kept as-is, still correctly documented as separate,
  interactive-session-only guidance).
- No new commands, agents, or skills.
- No attempt at `conventions.md`/`decisions.md` harvesting — out of scope,
  noted above.
- No re-run of `feature` — its answer key doesn't test harvest, so it adds
  cost without adding evidence.
