# Design — Guild 2.2.2 close print

**Status:** approved 2026-09-02. Follow-up to [2.2.1 hop persist](2026-08-31-guild-v2-adaptive-persist-design.md) after [v2.2.1](https://github.com/HamzaAlayed/laravel-claude-agents/releases/tag/v2.2.1) and [run 22](../evals/2026-09-01-run-22.md). Patch only. Adopter-facing: the close scorecard in the transcript, not only on disk.

**Goal:** After every `close.md` Write, print `VERIFIED:` / `NOT-CHECKED:` / `STATUS:` / `BOARD:` in the same turn so an interrupt or 1200s kill still leaves those labels in the last visible message.

**Why a patch:** 2.0 already shipped `close.md`. Run 22’s file helper PASSed; `$LOG` missed `VERIFIED` / `NOT-CHECKED` because the last turn was “waiting…”. Same artifact; visibility stickiness.

## Evidence (2.2.1)

| Contract | On disk / eval |
| --- | --- |
| Adaptive packet / `peer-router.md` / `handoff:` / close file | [Run 22](../evals/2026-09-01-run-22.md) PASS |
| `$LOG` `VERIFIED` / `NOT-CHECKED` | Run 22 FAIL — timeout; final text “Both parallel stages are running…” |
| Close file | PASS — helper shape; `STATUS: running`; qa-engineer still `▶` |
| VERSION | **2.2.1** tagged on `08fca37` |

Do not raise `EVAL_TIMEOUT`, `max_usd` ($8.50), or the 14.5M token ceiling. Do not uncomment `check_subagent_log`. Do not loosen `check_delivery_close_file`. Print is not a substitute for the file.

## Architecture

Prompt-layer stickiness. Same `close.md` helper. After every overwrite of `docs/delivery/<name>/close.md` (plan, every stage, re-brief), that turn also **prints** the four lines just written: `VERIFIED:` / `NOT-CHECKED:` / `STATUS:` / `BOARD:`. Not only the final answer.

Write the file first (byte copy of `skills/delivery-templates/close.md`, fill after the colons). Then print. Bash still must not write `close.md`. The hook still bounces a non-helper Write.

Interface stays byte-identical across the nine commands. Default `/make-feature` stays Supervisor. VERSION **2.2.2** only after a billed `feature` pin where `$LOG` or `$FULL_LOG` carries `VERIFIED` and `NOT-CHECKED` even if the run times out.

## Components

- **Interface** (all nine, byte-identical): after overwriting `close.md`, print those four labels in the same turn. The existing “final answer closes the same way” sentence stays. Graph / Adaptive sentences unchanged.
- **Coordinator Close file:** same Write order as today. New: after that Write, print the four lines. Existing close needles stay count **1**. Add one needle for print-after-write (count **1** — do not mention the path twice).
- **Unchanged:** close stub, close.md hook, Bash-must-not-write, harvest, graph, Adaptive persist, spawn cap.
- **Eval:** no new case. Gate is billed `feature`. `check_delivery_close_file` still the file. `$LOG` greps may use `$FULL_LOG` the same way handoff does (`check_log_anywhere`) so a killed run’s earlier printed close still scores. Harvest miss does not block.

## Data flow

1. After the plan: Write `graph.md` (as 2.2), Write `close.md`, **print** the four close lines + board.
2. After every Agent return: persist read-only stage file if needed → Write `close.md` → **print** the four lines + board → then harvest / next Task / Adaptive hop as today.
3. Re-brief return: same Write-then-print.
4. Spawn cap hit: Write `close.md` `STATUS: stopped` → print → stop.
5. `done when:` met: Write `close.md` `STATUS: done` → print those lines as the closing answer.
6. Kill / timeout: last printed block is what `$LOG` / `$FULL_LOG` can still grep. Latest `close.md` on disk remains the file helper.

`--adaptive` hops sit inside step 2. They do not skip the close print.

## Error handling

| Case | Behavior |
| --- | --- |
| Kill / timeout after a printed close | `$LOG` / `$FULL_LOG` can grep `VERIFIED` / `NOT-CHECKED` from that turn. File helper still scores `close.md` |
| Last turn is “waiting…” with no print | Contract miss — eval `$LOG` / `$FULL_LOG` FAIL. Do not drop those greps. Do not raise 1200s |
| Print without Write | File helper still requires `close.md`. Print is not a substitute |
| `VERIFIED (` / Bash `close.md` | Still bounce |
| Spawn cap `M` | Write `STATUS: stopped` → print → stop |
| `done when:` unmet, still running | `STATUS: running` on both file and print |
| `--adaptive` hop | Close print still happens after `peer-router` persist and after the hop Agent returns |
| Direct invoke, no delivery slug | No `close.md`, no print. Unchanged |

## Testing

**Guardrails.** Do not uncomment `check_subagent_log`. Do not drop `VERIFIED` / `NOT-CHECKED` output checks. Do not loosen `check_delivery_close_file`. Keep existing close needles at count **1**. Add Interface needle count **9**: print the four close labels after the Write. Coordinator needle count **1**: after that Write, print `VERIFIED:` / `NOT-CHECKED:` / `STATUS:` / `BOARD:`.

**Eval.** No new case. Gate is billed `KEEP_TRANSCRIPT=1 KEEP_WORKDIR=1 ./tests/eval/run-evals.sh feature`. PASS = close file + `$LOG` or `$FULL_LOG` carries `VERIFIED` and `NOT-CHECKED`. Harvest miss does not block. Pin `coordinator_hash`. `waivers: []`. Same ceilings. Do not grep `stream.jsonl`. Do not run until the user says **run it**. Receipt `docs/evals/2026-09-02-run-23.md` (or next date).

**Ship.** Those PASS → VERSION **2.2.2**. FAIL → pin hash, stay **2.2.1** / Unreleased. Adaptive is not the gate.

## Inventory

- Agents still **18**. Commands still **14**. Guardrails still **6**.
- No new stub. Gemini / Codex rebuild in the same change as the Interface.

## Non-goals

- Uncomment `check_subagent_log`
- Raise `$8.50` / 1200s / 14.5M
- Loosen `check_delivery_close_file`
- Print as a substitute for `close.md`
- Making Adaptive the default `/make-feature`
- A new eval case
- Console UI changes

## Versioning

| Field | 2.2.2 |
| --- | --- |
| Semver | Patch — print existing close labels in the transcript |
| Adopter action | Plugin update; every board turn shows `VERIFIED:` / `NOT-CHECKED:` / `STATUS:` / `BOARD:` |
| Do not bump | In the design or plan commit. Bump only after billed `feature` PASS |
