# Where does each document live?

This page maps the `docs/` corpus so the next review — human or agent — starts warm. The [2026-08-05 project-state review](requirements/2026-08-05-project-state-review.md) had to reverse-engineer this; do not do that again.

Adopting the pack on a Laravel app? [Run your first delivery](onboarding.md). Seeing it work in five minutes? The [README quickstart](../README.md#five-minute-quickstart).

Last verified 2026-08-19 against pack v1.42.0.

## What lives where

| Path | What it is |
| --- | --- |
| [`docs/superpowers/specs/`](superpowers/specs/) | Approved design specs. Intent, scope, non-goals. Written before the plan. |
| [`docs/superpowers/plans/`](superpowers/plans/) | Implementation plans for those specs. File lists, task order, verification. |
| [`docs/plans/`](plans/) | Working plans that are not Superpowers-shaped: follow-ups, held UI work, this Adoption plan. |
| [`docs/evals/`](evals/) | Eval scorecards and audits. One file per billed run or instrument change. |
| [`docs/requirements/`](requirements/) | Discovery / current-state reviews. Input to a spec, not a spec. |
| [`docs/research/`](research/) | Literature and comparative audits. |
| [`docs/design/`](design/) | Visual artifacts (actor study HTML). Not product screenshots. |
| [`docs/examples/`](examples/) | Captured instances from real runs. Dated. Not living docs. |
| [`docs/authoring-agents.md`](authoring-agents.md) | How to write an agent in this pack's voice. |
| [`docs/read-only-by-design.md`](read-only-by-design.md) | How reviewer read-only is enforced, and where it stops. |
| [`docs/onboarding.md`](onboarding.md) | Adopting-team guide: first delivery, `/teach`, reading a scorecard. |
| [`tests/eval/README.md`](../tests/eval/README.md) | How to run the eval harness. Answer key. Not a scorecard. |
| [`CHANGELOG.md`](../CHANGELOG.md) | Shipped user-facing changes. Keep a Changelog. |
| [`CONTRIBUTING.md`](../CONTRIBUTING.md) | How to add an agent or command. |

`docs/team/` is a **consumer** convention the pack writes into *your* Laravel repo (`conventions.md`, `stack.md`, `decisions.md`). It is not a directory in this repository. A captured instance lives in [`docs/examples/team-memory/`](examples/team-memory/).

## Spec vs plan vs eval record

Use the filename and the folder, not the prose tone.

| Kind | Folder | Question it answers | Closed when |
| --- | --- | --- | --- |
| **Requirement** | `docs/requirements/` | What is true right now, and which gaps matter? | A spec cites it. |
| **Spec** | `docs/superpowers/specs/` | What will we build, and what will we refuse? | A plan exists and a release ships the scope. |
| **Plan** | `docs/superpowers/plans/` or `docs/plans/` | Which files, in which order, with which checks? | The listed files exist and verification is green. |
| **Eval record** | `docs/evals/` | What did a billed run (or audit) actually measure? | Always closed — it is a receipt, not a backlog. Open *gaps* named inside a record stay open until a later spec takes them. |
| **Example** | `docs/examples/` | What did a real run produce? | Always closed. The files are a snapshot. |

A spec is not a plan. A plan is not a scorecard. An eval record that names a remaining gap is still a closed record of that run.

## Closed

Shipped or fully resolved. Read these; do not re-open them without a new spec.

| Item | Evidence |
| --- | --- |
| Prove-it **Trust** (v1.39.0) | [prove-it spec](superpowers/specs/2026-08-06-prove-it-milestone-design.md) §1.39; [check audit](evals/2026-08-06-check-audit.md); [trust plan](superpowers/plans/2026-08-06-trust-release-1.39.md) |
| Prove-it **Capability** / run 7 (v1.40.0) | [run 7](evals/2026-08-06-run-7.md); [captured team-memory](examples/team-memory/); [capability plan](superpowers/plans/2026-08-06-capability-release-1.40.md) |
| Harvest on command-driven runs (v1.41.0) | [harvest spec](superpowers/specs/2026-08-07-harvest-interface-fix-design.md); [run 7 second addendum](evals/2026-08-06-run-7.md#second-addendum-the-real-fix-v1410-re-run) |
| Orchestration-contract repair + `/audit-agents` (v1.42.0) | [contract spec](superpowers/specs/2026-08-18-orchestration-contract-fix-design.md); [run 9](evals/2026-08-18-run-9.md) |
| Eval runs 1–6, 8 | [evals/](evals/) dated `2026-07-20` through `2026-08-12` |
| Console v1 + follow-ups | [console spec](superpowers/specs/2026-07-29-guild-web-console-design.md); [follow-ups — closed](plans/2026-07-30-console-followups.md); [smoke](evals/2026-07-30-console-smoke.md) |
| Approval-bar occlusion | Fixed v1.38.1 — note at the top of [motion follow-ups](plans/2026-08-04-console-motion-followups.md) |
| Literature-gap tranche | [plan — gate cleared](plans/2026-07-29-literature-gap-tranche.md); [audit](research/2026-07-29-agent-literature-audit.md) |
| Accuracy / cost instrument | [spec](superpowers/specs/2026-08-04-agent-accuracy-and-cost-design.md); shipped across v1.34–v1.38 |

## Open

Still true as of 2026-08-19. A new review starts here.

| Item | Where | Notes |
| --- | --- | --- |
| **Adoption content** (this slice → v1.43.0) | [this plan](plans/2026-08-19-adoption-1.43.md); prove-it spec §1.41 (renumbered) | Quickstart, this index, onboarding. Version files stay at 1.42.0 until the release tag. |
| **Console screenshots / live GIF** | Same plan, capture recipe | Pending a real mid-run capture. Do not generate images. Does not block the rest of Adoption. |
| **CAN-RIDE console minors** | [motion follow-ups](plans/2026-08-04-console-motion-followups.md) | Seven items in that file (prove-it spec counted six): frame-pop on close, `splitJsonKey` escaped quotes, "Decision 1 of N" wording, three a11y items, two test-coverage gaps, `ago()` future `started_at`, `server.py` BrokenPipeError. Optional rider on 1.43; none blocks. |
| **Actor-sprite hover tooltip** | [spec](superpowers/specs/2026-08-07-actor-sprite-hover-design.md) | Spec exists. No matching CHANGELOG entry; `Actor.tsx` has no tooltip wrapper. Not in Adoption scope. |
| **Per-stage specialist returns unmeasured** | [run 8](evals/2026-08-12-run-8.md) | Harness cannot see subagent `STATUS/DID/…` shape. Filed as a gap, not a coordinator defect. Needs its own plan. |
| **Run 9 cost / `EVAL_TIMEOUT` split** | [run 9 cost](evals/2026-08-19-run-9-cost.md); [next experiment](plans/2026-08-19-run-9-cost-next.md) | $9.00 vs $8.50 is three 419/500 re-briefs under the 1.42 verify-and-don't-patch clause, plus a 1200s kill that cannot observe the 1456s seed. Do not raise `max_usd`. After 1.43.0: one billed `feature` with `EVAL_TIMEOUT=1900`. |

## How a new review should start

1. Read **Open** above. If an item moved, update this page in the same change.
2. Read the latest eval record in `docs/evals/` (sort by date; newest first).
3. Confirm `VERSION` and `.claude-plugin/plugin.json` agree (`scripts/check_inventory_sync.py`).
4. Only then open a spec or a plan.
