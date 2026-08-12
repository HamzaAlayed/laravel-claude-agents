# Agent orchestration audit — design

**Date:** 2026-08-12
**Status:** Approved for planning

## Purpose

The Guild's orchestration logic — `delivery-coordinator.md`, the 13 multi-stage
commands, and the Interface/contract sections of all 17 agents — has accumulated
several fixes for the same class of bug over time: a rule written into an agent's
body instead of the shared Interface block, silently failing to govern work the
main thread does inline (hit and fixed four times, most recently the harvest fix
in v1.41.0); and a tool-grant gap where `allowed-tools` doesn't actually cover an
action an Interface obligation requires, which a `--dangerously-skip-permissions`
test run can mask rather than reveal.

Both bugs were found one at a time, after the fact, by dedicated fix passes.
This project does two things:

1. Runs a full-system, one-time audit across every agent-facing file, checking
   specifically for these known failure patterns (plus three adjacent ones), and
   produces a findings report.
2. Builds a repeatable way to catch the same class of drift going forward, split
   across what can be checked for free (static) and what can only be observed by
   actually running the coordinator (behavioral).

## Scope

**In scope:** `agents/*.md` (17 files), `commands/*.md` (13 files),
`hooks/hooks.json` + the guard scripts it wires up, and
`docs/read-only-by-design.md` as the existing spec those guards must satisfy.

**Out of scope:** the console UI, the evals cost-tracking scripts, and any
change to agent *capabilities* (this is a review of the coordination contract,
not a feature audit).

## 1. One-time audit

**Method:** fan out 5 dimension-focused reviewer agents in parallel via the
`Agent` tool, each given the full file set in scope and one dimension to check.
Each reviewer reads real files (not summaries) and returns concrete
`file:line` findings only — no proposed fixes at this stage. This mirrors
`/review-pr`'s own fan-out/aggregate shape, applied to prompts instead of a
diff.

**Dimensions:**

1. **Interface placement** — any rule intended to govern main-thread/inline
   command behavior that lives in an agent-only body section instead of the
   shared Interface block.
2. **Tool-grant correctness** — every Interface obligation that requires a
   write/edit/run action, cross-checked against that agent's/command's
   `tools:` / `allowed-tools:` frontmatter.
3. **Stage-return & progress-board contract compliance** — do all multi-stage
   commands and the coordinator use the same `STATUS/DID/VERIFIED/
   NOT-CHECKED/FLAGS/NEXT` shape and board format, or has one drifted from the
   others?
4. **Artifact routing accuracy** — does delivery-coordinator's routing table
   match where each command/agent actually persists output? Any path named in
   the table that nothing writes to, or vice versa?
5. **Read-only enforcement** — re-verify `tech-lead`, `security-engineer`,
   `performance-engineer` still carry `disallowedTools: Edit, Write` and no
   Bash write-vector gap, against `docs/read-only-by-design.md`'s own
   checklist.

**Aggregation:** I read all 5 reviewers' returns, de-dupe overlaps, and bucket
each finding as **Blocking** (contract violation that will cause a real
failure in a live run — e.g. a tool-grant gap), **Should-fix** (drift that
degrades quality without breaking a run), or **Nit**. Fixes are proposed in
the report but **not applied during the audit** — same convention that keeps
`tech-lead`/`security-engineer` trustworthy as reviewers. A human decides
which fixes to apply, as a separate step, the way the `c41b9f9` /
`4749e2a` fix-wave commits already did for the harvest bug.

**Output:** `docs/evals/2026-08-12-orchestration-audit.md`, in
`check-audit.md`'s format — intro stating trigger and scope, one table per
dimension (`File | Line | Finding | Severity | Proposed fix`).

## 2. Repeatable layer A — `/audit-agents` command

New `commands/audit-agents.md`, modeled on `review-pr.md`:

- `argument-hint: [base-branch]`. Given a base (or one inferable from the
  branch), scope to `git diff` on `agents/**`, `commands/**`, `hooks/**`. No
  base and no diff → full scan, the same file set the one-time audit covers.
- **Empty-diff short-circuit:** if the scoped diff touches no agent-facing
  file, skip the fan-out entirely and report CLEAN immediately — this command
  is meant to run often, and most invocations will have nothing to check.
- Fans out the same 5 dimension-reviewers from section 1, scoped to the
  changed (or full) file set.
- **Aggregation** produces a verdict: **CLEAN** or **DRIFT-FOUND**, with the
  same Blocking/Should-fix/Nit buckets as the one-time audit.
- **Report-only** — never edits files, same convention as every other
  reviewer in this pack.
- Persists a dated doc to `docs/evals/` only when DRIFT-FOUND (avoids
  bloating the directory with empty CLEAN runs); a CLEAN result is just
  printed.
- **Error handling:** a reviewer agent that fails or times out is reported as
  its own Nit-severity finding ("dimension N could not be checked") rather
  than silently dropped — an audit command that swallows its own failures is
  worse than no audit.
- Cost: a normal command invocation, no billed fixture-app run — pure static
  analysis over files already in the working tree, meant to be run often
  (after editing any agent/command file, and as a step worth adding to
  `/ship-checklist` later, though that wiring is a follow-up, not part of
  this project).
- **Interface block:** unlike the other 9 fan-out commands, `audit-agents.md`
  deliberately omits the shared `> **Interface:**` progress-board/harvest
  block — it has no target-project stack facts or delivery artifact to
  harvest, since it reviews the pack's own prompt files rather than
  application code. It carries one short note stating this explicitly, so a
  later audit run's dimension-3 check treats the documented note as
  satisfying the consistency check rather than flagging the omission as
  drift.

## 3. Repeatable layer B — eval-harness extension

Dimensions 1, 2, and 5 are static/declared properties fully covered by layer
A. The eval harness (`tests/eval/run-evals.sh`) only earns its keep on what
layer A structurally cannot see: whether the contract is actually **followed
at runtime**, not just declared correctly on paper.

Rather than adding a new fixture case (the README already flags `action`'s
$5.16/run-6 cost as the reason `feature` — the only case that reliably forces
delegation via `check_delegated` — stays opt-in), this extends the existing
opt-in `feature` case with two new assertions:

- the full `STATUS/DID/VERIFIED/NOT-CHECKED/FLAGS/NEXT` shape appears for
  every delegated stage in the run log, not just the `NOT-CHECKED`/
  `done when:` strings already checked (dimension 3, observed).
- the artifact the coordinator's closing report claims to have routed (per
  its routing table) actually exists at the declared path on disk (dimension
  4, observed — layer A can only check the table is internally consistent, not
  that a real run honors it).

These are added as `check_*` calls in `case_rubric`/the case's check list for
`feature` in `tests/eval/run-evals.sh`, following the existing `check_log` /
`check_file` idiom in that file. No new fixture, no new billed case — the
assertions ride along on a run that already happens.

## Testing

- **One-time audit:** before trusting the 5 reviewer prompts, sanity-check
  each dimension's phrasing against a known historical bug it should have
  caught — dimension 1 against the pre-v1.41.0 harvest placement bug, and
  dimension 2 against the `allowed-tools` gap from the same fix wave (both in
  `CHANGELOG.md`). A dimension that wouldn't have caught the bug it's named
  for gets rewritten before the audit runs for real.
- **`/audit-agents`:** after implementation, run it once against the
  post-audit-fixes repo state and confirm it reports CLEAN. No fixture harness
  needed — this command only needs to prove it can find and report drift, and
  the one-time audit's findings (before they're fixed) are a ready-made
  DRIFT-FOUND fixture: run the new command against that pre-fix commit and
  confirm it surfaces the same findings the manual audit did.
- **Layer B assertions:** verified by running
  `./tests/eval/run-evals.sh feature` (billed run, pre-release cadence per the
  harness's own README) and confirming the two new checks pass on a
  known-good coordinator run.

## Non-goals

- No change to any agent's actual capabilities or tool grants as part of this
  project — findings are reported; applying fixes is separate follow-up work,
  reviewed on its own.
- No new eval fixture app or fixture case.
- No automatic wiring of `/audit-agents` into CI or `/ship-checklist` — worth
  considering later, out of scope here.
