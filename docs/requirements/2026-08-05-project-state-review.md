# Project state review — Laravel Guild pack, 2026-08-05

## Problem

This is a business-analyst review of the current state of the `laravel-claude-agents`
("Laravel Guild") repository — not a Laravel application, but a distributable
Claude Code plugin/pack (17 agents, 13 commands, 8 skills, 5 guardrail hooks,
an eval harness) — to establish what is shipped, what is genuinely in flight,
and where the product's own "done" is ambiguous or under-specified before any
further solution work is scoped.

## Evidence

- `README.md` (root) — product inventory, install paths, design rationale.
- `CHANGELOG.md` — entries through `[1.37.0] - 2026-08-05`.
- `.claude-plugin/plugin.json` — `"version": "1.37.0"`, confirms CHANGELOG head matches shipped manifest.
- `docs/evals/2026-08-04-run-6.md` — eval run 6 findings, "Run-7 checklist" section (lines 299–330).
- `docs/plans/2026-08-04-console-motion-followups.md` — held UI follow-ups from the console motion upgrade.
- `docs/plans/2026-07-29-literature-gap-tranche.md` — three body-level fixes, gate-cleared 2026-07-31.
- `docs/evals/2026-07-31-run-5.md`, `2026-07-28-run-4.md` (referenced, not fully re-read) — prior run history cited by run 6.
- Absence of `docs/team/` in this repo (`Read` on `docs/team/decisions.md` returned "File does not exist").

## Current-state summary

The pack is a mature, versioned product at **v1.37.0** (2026-08-05), consistent
across `CHANGELOG.md` and `.claude-plugin/plugin.json` — no version drift found.
It ships:

- 17 named subagents covering the delivery lifecycle (discovery → architecture →
  build → QA → security → docs → delivery coordination).
- 13 slash commands, each a thin orchestrator delegating to specialists.
- 8 on-demand skills (cookbooks), invoked via the `Skill` tool rather than preloaded.
- 5 guardrail hooks (fail-closed, with a tested jq→python3→bare-string fallback chain).
- Multi-target distribution: Claude Code plugin, Cursor, Gemini CLI extension,
  Codex Core (skills+guardrails only, explicitly scoped down), and a classic `install.sh`.
- An eval harness (`tests/eval/`) run against a fixture app with planted flaws,
  scored by a regex answer key plus an optional advisory rubric judge
  (`EVAL_JUDGE=1`), with cost/token/duration ceilings in `tests/eval/baseline.json`.
- A `docs/team/` **convention** — `conventions.md`, `stack.md`, `decisions.md` —
  but this is scaffolding the pack *installs into consumer projects*, not a
  directory that exists in this repo itself (confirmed absent here). Worth
  noting only because it means this repo cannot dog-food its own team-memory
  feature, which is a legitimate product gap, not a doc gap — see Risks.

The most recent release cycle (2026-08-04 → 2026-08-05, v1.34.0–v1.37.0) closed
a self-contained milestone: cost instrumentation (three ceilings — seconds,
tokens, dollars — after finding tokens alone don't track spend because >99%
of tokens are cache reads), a "literature-gap" tranche of three coordinator
behavior fixes, per-agent `effort`, and eval run 6 (5/5 cases, 19/19 checks,
5/5 judged PASS, $12.50 billed).

## Open work inventory

| Item | Where documented | Clarity rating | Notes |
| --- | --- | --- | --- |
| Eval run 7 | "Run-7 checklist" in `docs/evals/2026-08-04-run-6.md` (bottom) | **Low** | Every item in this checklist is already checked `[x]` and dated 2026-08-05, with fixes already landed in v1.35.0–v1.37.0. There is no unresolved item in this list, and no `docs/evals/2026-08-05-run-7.md` exists. The checklist name implies forward-looking work; its content is a closed retrospective. See Gap 1. |
| Console approval-bar occlusion bug (`LanePanel` covering the Review button) | `docs/plans/2026-08-04-console-motion-followups.md` | **Medium** | Reproduction steps, scope, and three candidate fixes are documented, but the doc explicitly declines to pick one ("every fix is a layout judgment the pack's owner should make"). No owner or deadline assigned. |
| Six "ride-along" minor UI/test items (frame-pop on close, `splitJsonKey` escaped-quote miss, "Decision 1 of N" countdown wording, 3-part a11y findings, two test-coverage gaps, `server.py` BrokenPipeError log) | Same doc, "Ride-along minors" section | **Medium-low** | Each has a one-line description and "triaged CAN RIDE" status, but no tracking issue, owner, or target release is named — they exist only in this narrative doc. |
| `feature` eval case (opt-in, delegation-guarantee case) | `docs/evals/2026-08-04-run-6.md` finding 6 / run-6 changelog v1.34.0 | **Medium** | Explicitly "not yet run billed" — ceilings are estimated from `action`'s shape, not measured. Stated next step: "Run it when coordinator behaviour changes," which is a conditional trigger, not a scheduled task. |
| Console motion-upgrade spec follow-through | `docs/superpowers/specs/2026-08-03-console-motion-usability-design.md` + plan | **Not assessed this pass** | Named but not read in this review; flag for follow-up if console UI work is prioritized. |

## Gaps, ambiguities, and inconsistencies

1. **"Run-7 checklist" is a misleading label — it documents run 6's own closure, not run 7's scope.**
   The memory/briefing framing ("next is the run-7 checklist") reads as forward
   work, but every line item under that heading in `docs/evals/2026-08-04-run-6.md`
   is checked off and dated 2026-08-05 — i.e., it was fully resolved *before* any
   run actually labeled "7" occurred. There is no artifact defining what an actual
   eval run 7 would test that isn't already covered by run 6's closure. This is a
   **naming/scope ambiguity**, not a code defect: is "run 7" (a) simply the next
   scheduled sweep with no new hypothesis, (b) the first billed run of the opt-in
   `feature` case, or (c) something not yet written down? Nothing in the repo
   commits to which.

2. **The `feature` eval case has no committed timeline or trigger.** Its own
   ceilings are marked "not yet run billed," and its scheduling rule is
   "run it when coordinator behaviour changes" — a judgment call with no named
   judge, no review cadence, and no owner. If coordinator behavior *does* change
   silently (e.g., an agent-body edit that reads as a doc tweak but shifts
   delegation), there's no trigger that reliably fires this case.

3. **The console occlusion bug has three candidate fixes and an explicit
   non-decision** ("the pack's owner should make [this call]"). That's a
   legitimate hold, but there is no ticket, no named owner, and no target
   release — so "held" risks becoming "forgotten." Six related minor items sit
   in the same undocumented-ownership state.

4. **`docs/team/` is described in the README as the product's own knowledge-base
   feature, but this repository — which builds and evaluates that feature — does
   not use it on itself.** That's expected (this repo is the pack, not a consumer
   project), but it does mean claims like "the coordinator harvests all three
   [`docs/team/` files] at delivery end" have no example instance to point to for
   verification within this repo. Not a defect, but worth flagging if a
   stakeholder wants to see the feature "in the wild" inside this repo as a demo.

5. **Eval scoring has an acknowledged known-false-negative mode (exact-match
   regex against nondeterministic prose)**, mitigated but not eliminated by the
   advisory rubric judge. v1.37.0 fixed one instance (`check_update_guarded`
   replacing a literal-word grep), but the underlying pattern — a check keyed to
   a specific word/phrase rather than to observable code/behavior — may recur in
   the other four cases' checks. No inventory exists confirming the other checks
   are free of the same fragility.

6. **Time, tokens, and dollars are documented as pointing at "three different
   targets" for cost attribution** (finding 3/4 in run 6), which is a genuinely
   useful finding, but the README and CHANGELOG do not yet state a single
   recommended metric for a maintainer deciding "is this release regressing
   cost." Three ceilings exist; no doc says which one wins when they disagree,
   beyond "check the agent list for delegation before calling it a regression"
   for the two bimodal cases specifically (`policy`, `action`).

## Risks

- **Console UI defect (approval-bar occlusion) is a real, reproduced bug** sitting
  in "held" status with no owner — low severity (has a documented workaround:
  Escape) but user-facing in the `/console` surface. Flag for human triage
  decision: fix now, backlog with an owner, or explicitly accept as known-limitation
  in docs.
- **ASSUMPTION — unconfirmed:** I have not verified whether "run 7" is scheduled,
  in progress, or simply not yet started, because no artifact in the repo commits
  to it. This review treats the run-6 checklist as closed and treats "run 7" as
  an open naming/scope question (Gap 1) rather than assuming any particular answer.
- **ASSUMPTION — unconfirmed:** I did not re-verify the specific pricing/model
  facts in `tests/eval/baseline.json` or the rate table referenced across recent
  CHANGELOG entries — these are described as independently reconciled in-repo,
  but this review took that at face value rather than re-deriving them.

## Highest-value clarifying questions / next requirements-work items

1. **What is eval run 7 actually testing that run 6 didn't close?** If the answer
   is "nothing yet — it's just the next scheduled sweep," say so explicitly in a
   new `docs/evals/` stub or in the CHANGELOG, so the checklist heading stops
   reading as open work. (Blocking, if "run 7" work is meant to start soon —
   otherwise non-blocking.)
2. **Who owns the console approval-bar occlusion bug, and by when should it be
   decided (fix vs. accept-as-known-limitation)?** The three candidate fixes are
   already scoped; this needs a decision-maker and a date, not more analysis.
   (Non-blocking, but aging — flag for product-owner backlog entry with an owner.)
3. **What triggers the first billed run of the opt-in `feature` eval case?**
   "When coordinator behaviour changes" needs an operational definition (e.g.,
   any edit to `agents/delivery-coordinator.md` or the shared `Interface` block
   in commands) or it will silently never run. (Non-blocking; recommend converting
   to a CI-checkable rule.)
4. **Is there a single metric of record for "did this release regress cost"?**
   Three ceilings (seconds/tokens/dollars) each catch different regressions;
   maintainers need one documented tie-breaking rule beyond the two named
   bimodal-case exceptions. (Non-blocking, but affects every future release's
   go/no-go clarity.)
5. **Should the six "ride-along" minor UI/test items get individual tracking
   entries (issues, backlog rows) instead of living only in a narrative plan
   doc?** As written they have no owner, no due date, and will likely be
   rediscovered rather than resolved. (Non-blocking — product-owner backlog
   triage item.)
6. **Are the other four eval cases' checks (`n-plus-one`, `tests`, `hygiene`, plus
   the two `policy`/`action` checks not already fixed) audited for the same
   literal-word-match fragility that `check_update_guarded` just fixed in
   `policy`?** No such audit is referenced. (Non-blocking, but is the kind of
   systemic risk that surfaces one case at a time unless someone looks
   deliberately.)

## Traceability

- Affected artifacts: `docs/evals/2026-08-04-run-6.md`, `docs/plans/2026-08-04-console-motion-followups.md`,
  `docs/plans/2026-07-29-literature-gap-tranche.md`, `tests/eval/baseline.json`,
  `CHANGELOG.md`, `.claude-plugin/plugin.json`.
- No Eloquent models, routes, or jobs apply — this is a plugin/tooling repo, not
  a Laravel application.

---

**Stakeholder sign-off required on this problem statement before solution work begins.**
