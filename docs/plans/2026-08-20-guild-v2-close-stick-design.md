# Design — Guild 2.0 close-file stickiness

**Status:** approved 2026-08-20. Follow-up to [Guild v2 design](2026-08-20-guild-v2-design.md) after [run 12](../evals/2026-08-20-run-12.md). Not 2.1 Adaptive. Not 2.2 graph.

**Goal:** Make the coordinator Write `close.md` in the shape the eval already scores, and re-brief onto the registered stage path — without loosening helpers, raising ceilings, or adding a surface.

**Why this is not a new major:** 2.0 already added `close.md`, joins, need-to-know briefs, spawn cap, and the basename ratchet. Run 12 showed the coordinator *did* write `close.md` and *did* print `cap: M spawns`, then paraphrased labels (`VERIFIED (`) and invented `backend-developer-fixes.md`. The templates already contained colons. This slice is stickiness.

## Evidence (run 12)

| Contract | On disk |
| --- | --- |
| `VERIFIED:` / `NOT-CHECKED:` | `VERIFIED (` and `NOT-CHECKED` — no colons |
| `STATUS: running \| done \| stopped` | `STATUS: in-progress` (board language leaked) |
| Overwrite after every stage | Last write mid stage 3; replan / spawn 6 did not overwrite |
| Re-brief overwrites `<agent>.md` | `stages/backend-developer-fixes.md` |

`check_delivery_close_file` FAILed on `VERIFIED:`. `check_stage_return_files` FAILed on the unregistered basename. Both helpers did their job. Do not change them to match this run.

The 2.0 gate remains **close file PASS**, not 12/12. VERSION stays **1.45.0** until that gate passes on a billed `feature` pin.

## Architecture

Same product: `/make-feature` or `/console`, `delivery-coordinator` overwrites `docs/delivery/<name>/close.md`. No new agent, command, daemon, or console scene.

**Close skeleton (copy-paste).** The fenced example is four literal lines the coordinator must Write as the start of `close.md`. Labels first. No parentheticals on the label. Filler only after the colon.

```
VERIFIED: <commands you ran → counts>
NOT-CHECKED: <what nobody verified, or none>
STATUS: running
BOARD: <progress board as last printed>
```

`STATUS` on disk is exactly one of `running`, `done`, `stopped`. `running` is the in-flight default in the skeleton; replace with `done` or `stopped` when the run ends. Never `in-progress`. Stage-return files keep `done | blocked | needs-decision` — two files, two lists.

Overwrite after the plan, after every stage, and again after a re-brief returns — last Write to `close.md` before the next Task. Existing sentence `overwrite close.md after every stage` stays **count 1**. Do not duplicate it.

**Re-brief path.** The Task prompt includes one path line:

`Stage file (overwrite, no other name): docs/delivery/<name>/stages/<agent>.md`

Coordinator still never writes a writer’s stage file. No sibling (`backend-developer-fixes.md`). Existing `never spawn a `-fixes` suffix` stays count 1.

**Helper (tighten, do not loosen).** Keep colon-strict `VERIFIED:` / `NOT-CHECKED:` / `STATUS:`. Add: the STATUS line matches `^STATUS: (running|done|stopped)` so `in-progress` fails even when the colon is present. Basename ratchet unchanged.

**Static ratchets.** Guardrails extract the Close file section (not the whole agent body) and assert the four line prefixes. Delivery-templates close example uses the same four first tokens. A fixture `close.md` with `STATUS: in-progress` must FAIL the helper (same style as the existing `-fixes` fixture). Do not grep the word `fixes` in helper source as a pin. Interface block unchanged (nine commands, already byte-identical).

## Non-goals

- Do not loosen `check_delivery_close_file` to accept `VERIFIED (`
- Do not allow `-fixes` basenames
- Do not uncomment `check_subagent_log`
- Do not raise `EVAL_TIMEOUT` (1200) or `feature` `max_usd` ($8.50)
- Do not start 2.1 or 2.2
- Do not bump `VERSION` until the billed close-file helper PASSes
- Do not unify stage-return STATUS with close STATUS

## Error handling

| Case | Response |
| --- | --- |
| Timeout / kill | Latest `close.md` is the scorecard. Missing file or missing `VERIFIED:` → FAIL |
| `STATUS: in-progress` | Helper FAIL |
| `-fixes` stage filename | Helper FAIL (already) |
| Re-brief without overwriting close.md | Timeout run scored from a stale mid-board close — still a product miss; the skeleton + “last Write before next Task” is the prompt fix |

## Testing

**Guardrails (no billed run).** New expects on the extracted close skeleton (four prefixes, both coordinator and delivery-templates). Helper fixture rejects `in-progress`. Re-brief path needle count 1. Existing close/spawn/fixes expects stay.

**Eval (`feature`, opt-in billed).** Same command as run 12. Gate: `check_delivery_close_file` PASS. Basename FAIL still blocks the 2.0.0 ship. Timeout / `$LOG` greps may still FAIL; that does not move the gate. Pin `coordinator_hash` from that run. Receipt `docs/evals/2026-08-20-run-13.md` (or next date).

## Versioning

Still **2.0.0** when the gate passes — Interface already changed in the parent design. This follow-up does not add a second breaking. Changelog stays `[Unreleased]` until the pin. Adopters re-install once, from 2.0.0.
