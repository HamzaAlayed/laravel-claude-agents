# Design — Guild 2.3.0 resume

**Status:** approved 2026-09-04. Follow-up to [2.2.2 close print](2026-09-02-guild-v2-close-print-design.md) after [v2.2.2](https://github.com/HamzaAlayed/laravel-claude-agents/releases/tag/v2.2.2) and [run 23](../evals/2026-09-02-run-23.md). Minor. Adopter-facing: the same `/make-feature` again must not replay `✔` stages.

**Goal:** When `docs/delivery/<name>/close.md` is `STATUS: running`, a second `/make-feature <Name>` reprints the board from disk, skips skippable stages, and only Agents `▶` and `·`.

**Why a minor:** New user-visible behaviour on every pipeline command. Not a patch on close print. VERSION **2.3.0** only after a billed `feature-resume` pin.

## Evidence (2.2.2)

| Contract | On disk / eval |
| --- | --- |
| Close print + `$LOG` `VERIFIED` / `NOT-CHECKED` | [Run 23](../evals/2026-09-02-run-23.md) 13/13 PASS, 1114s |
| Checkpoint flush to `log.md` | Coordinator already says flush resume state before a human checkpoint |
| Kill / new session | Still replays paid `✔` stages. No Interface sentence reads `close.md` before the first Agent |

Do not raise `EVAL_TIMEOUT`, `max_usd` ($8.50), or the 14.5M token ceiling. Do not uncomment `check_subagent_log`. Do not loosen `check_delivery_close_file`. Default `/make-feature` stays Supervisor.

## Architecture

Prompt-layer stickiness. No new agent, no daemon, no tenth command. `<name>` still comes from the command (`Tag` → `tag`). Before the first Agent:

1. No `close.md` → today’s path (plan, `graph.md`, `close.md`, Agent).
2. `STATUS: done` or `stopped` → print the four close labels from the file, stop.
3. `STATUS: running` → Read `graph.md` and `stages/*.md`. Reprint the board. Skip a **writer** when `stages/<agent>.md` is helper shape with `STATUS: done` **and** at least one path named in `DID:` or `VERIFIED:` exists on disk. Skip a **read-only** type (`tech-lead`, `security-engineer`, `performance-engineer`, `peer-router`) when the stage file is `STATUS: done`. `▶` and missing / `·` still Agent (overwrite the same stage path, no `-fixes`). Then the usual Write-`close.md`-then-print loop.

If `graph.md` already has `NODES:` / `EDGES:` / `PARALLEL:` / `ON-FAIL:`, do not rewrite it. Spawn cap `M` does not reset: remaining = `M` minus distinct `stages/*.md` already present. New Agents, including re-Agent of `▶`, still count.

## Components

- **Interface** (all nine, byte-identical): before the first Agent, if `docs/delivery/<name>/close.md` exists, follow the three-way split. Skip rule in one sentence. Close print unchanged. Graph / Adaptive sentences unchanged.
- **Coordinator Resume:** one paragraph, count **1**. Do not mention `docs/delivery/<name>/close.md` on a new line (Close file already has that path). Do not repeat `copy skills/delivery-templates/close.md`.
- **Eval:** new opt-in `feature-resume`, not in `ALL_CASES`. After `install.sh`, plant a partial `docs/delivery/tag/` plus a Tag model and tags migration in the workdir. Prompt `/make-feature Tag --api`. PASS = close file + `$LOG`/`$FULL_LOG` `VERIFIED`/`NOT-CHECKED` + `cost.json` attributed agents has no `database-developer` + Tag HTTP/tests still land. Harvest miss does not block.
- **Unchanged:** close stub, hook, Bash-must-not-write, harvest, graph stub, Adaptive persist, `check_delivery_close_file` shape.

## Data flow

1. Fresh: unchanged.
2. Resume `running`: Read close → Read stages → skip or Agent → Write close → print four lines → harvest / joins / Adaptive as today.
3. Resume `done` / `stopped`: print four lines, no Agent.
4. `--adaptive` on resume: same skip rule; hops still need a packet and still count against remaining `M`.
5. Direct invoke, no slug: no `close.md`, no resume.

## Error handling

| Case | Behavior |
| --- | --- |
| `STATUS: running`, skippable stage | Reprint `✔`, do not Agent |
| Stage file done, artifact missing | Treat as `·`, Agent |
| Writer stage done, no parseable path in `DID:` / `VERIFIED:` | Do not skip, Agent |
| `▶` when killed | Re-Agent, overwrite same stage file |
| `done` / `stopped` | Print close, stop |
| Remaining cap 0 | Write `STATUS: stopped`, print, stop |
| Planted resume but coordinator still Agents `database-developer` | Eval FAIL — do not drop the `cost.json` assert |
| `graph.md` missing on resume | Byte-copy stub, then continue |

## Testing

**Guardrails.** Interface needle count **9**: `reprint the board from disk`. Coordinator needle count **1**: `before the first Agent, if close.md exists`. Keep close-print needles. `feature-resume` is in `OPT_IN_CASES`, not `ALL_CASES`. `checks_feature_resume` must not uncomment `check_subagent_log`.

**Eval.** Gate is billed `KEEP_TRANSCRIPT=1 KEEP_WORKDIR=1 ./tests/eval/run-evals.sh feature-resume`. Same ceilings as `feature`. Pin `coordinator_hash`. `waivers: []`. Do not grep `stream.jsonl`. Do not run until the user says **run it**. Receipt `docs/evals/2026-09-04-run-24.md` (or next date).

**Ship.** PASS → VERSION **2.3.0**. FAIL → pin hash, stay **2.2.2** / Unreleased.

## Inventory

- Agents still **18**. Commands still **14**. Guardrails still **6**. Default sweep still **5** cases. Opt-in becomes five names (`feature`, `teach`, `teach-delivery`, `feature-adaptive`, `feature-resume`).
- Gemini / Codex rebuild in the same change as the Interface.

## Non-goals

- A `/resume-feature` command
- Re-running per-stage success criteria before skip
- Resuming `done` or `stopped`
- Uncomment `check_subagent_log`
- Raise `$8.50` / 1200s / 14.5M
- Making Adaptive the default `/make-feature`
- Two billed runs (kill then continue)
- Console UI

## Versioning

| Field | 2.3.0 |
| --- | --- |
| Semver | Minor — resume a running delivery on the same command |
| Adopter action | Plugin update; `/make-feature Tag` again continues from `close.md` |
| Do not bump | In the design or plan commit. Bump only after billed `feature-resume` PASS |
