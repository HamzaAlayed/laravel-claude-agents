# Design — Guild v2 (Kore orchestration patterns)

**Status:** draft for approval. Source: [Kore.ai — choosing the right orchestration pattern](https://www.kore.ai/blog/choosing-the-right-orchestration-pattern-for-multi-agent-systems) mapped onto pack v1.45.0.

**Goal:** Make the Guild a complete Supervisor, then optionally add Adaptive routing and a declared graph — without leaving Claude Code, without an L4 daemon, and without uncommenting `check_subagent_log`.

**Why a major:** v1.45.0 already *is* Kore’s Supervisor (coordinator decomposes, delegates, Reads stage files, harvests). The billed `feature` run still dies mid-board ([run 11](../evals/2026-08-20-run-11.md): 10/11, `$LOG` is 322 bytes of “Waiting on…”, `NOT-CHECKED` miss). Closing that loop, tightening briefs, and adding join / replan / audit rules **changes the Interface contract**. Adopters re-install. That is 2.0.0, not 1.46.0.

## What v1 already is

| Kore pattern | Guild today |
| --- | --- |
| Supervisor | `delivery-coordinator` + nine pipeline commands. Stage budget, six-field returns on disk, verify-before-advance, harvest. Console is the human view of that hierarchy. |
| Adaptive network | **Not the product.** Specialists do not route to each other. The coordinator owns the board. |
| Custom (SDK graph) | Prompts + guardrails + `coordinator_hash`, not a coded execution graph. |

Kore’s own advice: start with Supervisor or Adaptive; go Custom only when those cannot meet the constraint. The Guild stays Supervisor as the default through v2.

## Roadmap

| Release | Theme | Features (from the Kore list) | Ships when |
| --- | --- | --- | --- |
| **2.0.0** | Supervisor complete | 1 need-to-know briefs · 2 join points · 3 replan on mismatch · 4 stable stage filenames · 5 coordinator close on timeout · 6 audit bundle · 7 spawn cap (cost proxy) | Guardrails green + one billed `feature` pin. `VERSION` **2.0.0**. |
| **2.1.0** | Adaptive opt-in | 8 peer handoff · 9 router agent · 10 no-re-ask packet | Default routing still Supervisor. Opt-in command or flag only. |
| **2.2.0** | Declared graph | 11 dependency graph · 12 typed shared context · 13 named failure paths · 14 parallel-then-sync in the graph | Machine-readable graph the coordinator must follow; eval asserts the file, not nested chat. |

Do not start 2.1 while 2.0’s billed close is still a timeout-shaped FAIL. Do not start 2.2 while 2.0’s Interface is still the 1.45.0 block.

## 2.0 — architecture

Same product shape as v1.45.0: a human starts `/make-feature` or `/console`. No new agent, no daemon, no Kore SDK.

**Timeout close (feature 5) is the reason 2.0 exists.** Claude `-p` is killed at `EVAL_TIMEOUT=1200`. The coordinator cannot speak after death. So close cannot live only in `$LOG`.

**Surface:** `docs/delivery/<name>/close.md`

- Coordinator **overwrites** this file after the plan and after every stage (pass, fail, or checkpoint).
- Shape: `VERIFIED` / `NOT-CHECKED` / `STATUS` (`running` · `done` · `stopped`) / `BOARD` (one-line header). Same six-field discipline as stage files, coordinator-authored.
- Latest write wins. History stays in `log.md`.
- Headless timeout: eval reads this file. `check_log 'NOT-CHECKED'` on `$LOG` stays for runs that actually close; `checks_feature` also accepts `close.md` so a killed run is not scored on mid-board prose.
- Do not raise `EVAL_TIMEOUT` or `max_usd` ($8.50). Do not uncomment `check_subagent_log`.

**Need-to-know briefs (1).** The brief names only: goal, owned paths, success criteria, exact stage path, and named stack facts. No paste of other specialists’ diffs. Coordinator Working interface + `docs/authoring-agents.md`. Guardrail: one Interface sentence, count 9.

**Join points (2).** A stage that depends on others does not `✔` until those stage files exist and verify. `/make-feature` already says b∥c after a; 2.0 makes the join *checkable*: coordinator must Read both files before starting qa / harvest. Guardrail on the Interface sentence.

**Replan on mismatch (3).** `FLAGS` disagree, empty `VERIFIED`, or coordinator re-run fails → re-brief once (overwrite the same stage file). Second failure → `✖`, write `close.md` `STATUS: stopped`, checkpoint. Do not advance.

**Stable filenames (4).** Re-brief overwrites `docs/delivery/<name>/stages/<agent>.md`. No `-fixes` suffix. Run 11’s helper still matches `*/stages/*.md`; 2.0 adds a ratchet that those basenames are registered agent types only (hyphens in `tech-lead` are fine; `-fixes` is not).

**Audit bundle (6).** Before the coordinator’s own final answer — or as the last Write to `close.md` when stopping — these exist when ≥2 specialists have reported:

- `docs/delivery/<name>/log.md` (already)
- `docs/delivery/<name>/stages/*.md` (already)
- `docs/delivery/<name>/close.md` (new)
- `docs/team/stack.md` (already)

That *is* the audit bundle. No second tree. Console stays the human view.

**Spawn cap (7).** Live USD is not visible to the coordinator inside Claude Code. 2.0 does **not** parse `eval-cost.py` at runtime. The board header states a **max specialist spawns** next to the stage budget (`N stages · cap: M spawns · done when:`). Hitting `M` without `done when:` → write `close.md` `STATUS: stopped`, stop. `M` defaults to the stage count + 2 (one re-brief each for two lanes). This is Kore’s “avoid overloading the supervisor,” not a dollar dashboard.

## 2.1 — Adaptive (later)

Opt-in only. A specialist may hand a **context packet** to a named peer when the command or human says so. Packet fields: employee/task ids masked, investigation summary, owned paths, stage path. The coordinator still prints the board (handoff is a stage line, not an invisible hop).

**Not in 2.0.** Peer routing as the default would break the Interface (“you do not build and you do not patch”; coordinator owns `✔`).

## 2.2 — Graph (later)

A small `docs/delivery/<name>/graph.md` (or YAML if a parser already exists in CI) listing: node = agent type, edges = “after”, `parallel:` groups, `on-fail:` stop | re-brief | checkpoint. The coordinator must not spawn off-graph. Failure paths are named, not improvised.

**Not in 2.0.** The nine commands already encode order in prose; a graph without a working close is ceremony.

## Non-goals (whole v2 program)

- No L4 watcher (GitHub / Slack / CI daemon)
- No new default agent (no Welcome/observe-agent on the main path)
- Do not uncomment `check_subagent_log`
- Do not raise `feature` `max_usd` ($8.50) or default `EVAL_TIMEOUT` (1200)
- No Kore / LangGraph / SDK runtime
- Do not merge leftover worktrees (already deleted)
- Console UI is out of 2.0 unless `close.md` must be echoed (it must not — board is enough)

## Constraints (keep from v1.45.0)

- Coordinator Write/Edit only under `docs/**`
- Interface block stays **byte-identical** across the nine pipeline commands
- `checks_*` never grep `stream.jsonl`
- Coordinator never writes a **writer’s** stage file
- Gemini / Codex rebuild in the same release as command/agent edits
- `full_text()` / coordinator close greps stay main-thread files (`$LOG`, `$FULL_LOG`, and now `close.md`) — never a specialist stage file as the answer key for the coordinator’s own `VERIFIED`

## Error handling (2.0)

| Case | Response |
| --- | --- |
| Timeout / process kill | `close.md` from the last completed stage is the scorecard. Missing file → FAIL (coordinator never started the loop). |
| `-fixes` stage filename | Contract break. Re-brief must overwrite `<agent>.md`. Guardrail + eval. |
| Join with a missing peer file | Do not start the dependent stage. Re-brief the missing writer once, or `✖` that lane. |
| Spawn cap hit | `close.md` `STATUS: stopped`, `NOT-CHECKED` names what never ran. Not a silent trim. |
| Direct invoke, no delivery slug | No `close.md`, no stage file. Unchanged. |

## Testing

**Guardrails (no billed run).** New Interface needles count **9**. `close.md` required in coordinator Working interface (count **1** — do not duplicate). Spawn-cap sentence count **1** on coordinator. Stage basename ratchet: no `-fixes` in the writer/coordinator clauses. `check_subagent_log` stays commented.

**Eval (`feature`, opt-in billed).** Keep `check_stage_return_files`. Add: `close.md` exists with `VERIFIED` and `NOT-CHECKED`; stage files’ basenames are registered types; harvest still required. `check_log 'NOT-CHECKED'` on `$LOG` may still miss on timeout — that is expected; the new helper is the close file. Pin `coordinator_hash` from that run. Score may still be FAIL on other checks; the 2.0 gate is **close file PASS**, not 11/11.

**Release.** Bump `VERSION` and the five manifests to **2.0.0** only after that billed pin. Changelog: breaking = re-install; Added = close file, joins, spawn cap, audit bundle as the existing delivery dir.

## Versioning

| Field | 2.0.0 |
| --- | --- |
| Semver | Major — Interface + harvest shape (`close.md`) |
| Adopter action | Re-install / plugin update |
| Do not bump | In the design or plan commit |
