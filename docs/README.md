# Where does each document live?

This page maps the `docs/` corpus so the next review — human or agent — starts warm. The [2026-08-05 project-state review](requirements/2026-08-05-project-state-review.md) had to reverse-engineer this; do not do that again.

Adopting the pack on a Laravel app? [Run your first delivery](onboarding.md). Seeing it work in five minutes? The [README quickstart](../README.md#five-minute-quickstart).

Last verified 2026-08-24 against pack v2.1.0.

## What lives where

| Path | What it is |
| --- | --- |
| [`docs/superpowers/specs/`](superpowers/specs/) | Approved design specs. Intent, scope, non-goals. Written before the plan. |
| [`docs/superpowers/plans/`](superpowers/plans/) | Implementation plans for those specs. File lists, task order, verification. |
| [`docs/plans/`](plans/) | Working plans that are not Superpowers-shaped: follow-ups, held UI work, Adoption, the console company-theater redesign, Guild v2. |
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
| Prove-it **Adoption** (v1.43.0) | [adoption plan](plans/2026-08-19-adoption-1.43.md); README quickstart; [onboarding](onboarding.md); [this index](README.md) |
| Console company-theater redesign (v1.44.0) | [design](plans/2026-08-19-console-company-theater-design.md); [plan](plans/2026-08-19-console-company-theater.md); fixture still at [console-board-mid-run.png](images/console-board-mid-run.png) |
| Console board screenshot | [docs/images/console-board-mid-run.png](images/console-board-mid-run.png) — fixture-driven, not a billed live `/console` run. Optional GIF not taken. |
| CAN-RIDE console minors + actor-sprite hover (v1.43.0) | [motion follow-ups](plans/2026-08-04-console-motion-followups.md); [hover spec](superpowers/specs/2026-08-07-actor-sprite-hover-design.md) |
| Eval `$SUBAGENT_LOG` extractor | [subagent-log write-up](evals/2026-08-19-subagent-log.md). [Run 10](evals/2026-08-19-run-10.md) inspected a billed transcript: 125 nested turns, all `tool_use` only, log empty. Feature greps stay commented. |
| Run 9 cost / `EVAL_TIMEOUT` split | [run 9 cost](evals/2026-08-19-run-9-cost.md); [run 10](evals/2026-08-19-run-10.md) ticks row 1 — $6.70, 1387s, no `SendMessage` loop, orchestrator close. `max_usd` stays $8.50. |
| Eval runs 1–6, 8 | [evals/](evals/) dated `2026-07-20` through `2026-08-12` |
| Console v1 + follow-ups | [console spec](superpowers/specs/2026-07-29-guild-web-console-design.md); [follow-ups — closed](plans/2026-07-30-console-followups.md); [smoke](evals/2026-07-30-console-smoke.md) |
| Approval-bar occlusion | Fixed v1.38.1 — note at the top of [motion follow-ups](plans/2026-08-04-console-motion-followups.md) |
| Literature-gap tranche | [plan — gate cleared](plans/2026-07-29-literature-gap-tranche.md); [audit](research/2026-07-29-agent-literature-audit.md) |
| Accuracy / cost instrument | [spec](superpowers/specs/2026-08-04-agent-accuracy-and-cost-design.md); shipped across v1.34–v1.38 |
| Per-stage specialist returns on disk (v1.45.0) | [design](plans/2026-08-19-l3-stage-returns-design.md); [plan](plans/2026-08-19-l3-stage-returns.md); [run 11](evals/2026-08-20-run-11.md) — `check_stage_return_files` PASS. Do not uncomment `check_subagent_log`. |
| Guild v2 — Supervisor complete (2.0.0) | [design / roadmap](plans/2026-08-20-guild-v2-design.md); [run 17](evals/2026-08-21-run-17.md) — `check_delivery_close_file` PASS (timeout 1203s, harvest still FAIL). Close file, joins, spawn cap, need-to-know briefs. |
| Guild v2 — 2.1 Adaptive (2.1.0) | [design](plans/2026-08-23-guild-v2-adaptive-design.md); [plan](plans/2026-08-23-guild-v2-adaptive.md); [run 18](evals/2026-08-23-run-18.md) — billed Adaptive packet, peer-router.md, and handoff FAIL; close file PASS. Opt-in `--adaptive` ships. |

## Open

| Item | Evidence |
| --- | --- |
| Guild v2 — 2.1.1 required hop | [design](plans/2026-08-24-guild-v2-adaptive-graph-design.md). In progress. `--adaptive` must hop once (coordinator fallback). VERSION stays 2.1.0 until billed PASS. |
| Guild v2 — 2.2.0 graph | [design](plans/2026-08-24-guild-v2-adaptive-graph-design.md); [roadmap](plans/2026-08-20-guild-v2-design.md). Waits until 2.1.1 is tagged. |

## How a new review should start

1. Read **Open** above. If an item moved, update this page in the same change.
2. Read the latest eval record in `docs/evals/` (sort by date; newest first).
3. Confirm `VERSION` and `.claude-plugin/plugin.json` agree (`scripts/check_inventory_sync.py`).
4. Only then open a spec or a plan.
