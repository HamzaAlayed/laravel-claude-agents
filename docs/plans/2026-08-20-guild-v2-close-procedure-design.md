# Design — Guild 2.0 close.md procedure

**Status:** approved 2026-08-20. Follow-up to [close-file stickiness](2026-08-20-guild-v2-close-stick-design.md) after [run 13](../evals/2026-08-20-run-13.md). Not 2.1 Adaptive. Not 2.2 graph.

**Goal:** Make the coordinator Write `close.md` in helper shape after every Agent return — without loosening the helper, raising ceilings, or adding a surface.

**Why this is not a new major:** 2.0 already added `close.md`. Stickiness already added a four-line skeleton. Run 13 wrote the file and still failed the gate: labels were `VERIFIED (coordinator, own hands):`, and qa/tech-lead stage files landed while `close.md` still said those stages were `▶`. Louder examples are not a new surface. This slice is a **procedure** plus a **ban**.

## Evidence (run 13)

| Contract | On disk |
| --- | --- |
| Line starts `VERIFIED:` | `VERIFIED (coordinator, own hands):` — parenthesis before the colon |
| `STATUS: running \| done \| stopped` | `STATUS: stages a + b done…; stages c + d running` |
| Overwrite after every stage | Last write mid stage 3; `qa-engineer.md` and `tech-lead.md` exist |
| Re-brief overwrites `<agent>.md` | **PASS** — no `-fixes` |

The 2.0 gate remains **close file PASS**, not 12/12. VERSION stays **1.45.0** until that gate passes on a billed `feature` pin.

## Architecture

Same product: `/make-feature` or `/console`, `delivery-coordinator` overwrites `docs/delivery/<name>/close.md`. No new agent, command, stub file, daemon, or console scene. Interface block unchanged.

**Procedure.** After every Agent return — including the coordinator persisting a read-only stage file — the **next Write** is `docs/delivery/<name>/close.md`. Harvest (`stack.md`, `log.md`) and the next Task wait until that Write lands. Existing `overwrite close.md after every stage` stays **count 1**; do not duplicate it.

**Ban.** The four skeleton lines start `VERIFIED:` `NOT-CHECKED:` `STATUS:` `BOARD:` with **nothing between the word and the colon**. `VERIFIED (` is a contract break. Filler only after the colon. `STATUS` value is exactly `running`, `done`, or `stopped` as the first word after the colon.

**Helper (tighten, do not loosen).** Keep STATUS vocab `^STATUS: (running|done|stopped)`. Change the colon checks for `VERIFIED:` and `NOT-CHECKED:` to **line-start** (`^VERIFIED:`, `^NOT-CHECKED:`) so a parenthetical before the colon still fails. Do not accept `VERIFIED (`.

**Static ratchets.** Two new unique coordinator needles, count **1** each:

- `after every Agent return, the next Write is close.md`
- `VERIFIED (` is a contract break

Helper fixture: a `close.md` whose first label is `VERIFIED (coordinator):` must FAIL. The existing `STATUS: running` accept fixture stays. Interface block unchanged. Do not grep the word `fixes` in helper source as a pin.

## Non-goals

- Do not loosen `check_delivery_close_file` to accept `VERIFIED (`
- Do not add a canonical stub file or copy-from-templates Write
- Do not uncomment `check_subagent_log`
- Do not raise `EVAL_TIMEOUT` (1200) or `feature` `max_usd` ($8.50)
- Do not start 2.1 or 2.2
- Do not bump `VERSION` until the billed close-file helper PASSes
- Do not edit the shared Interface block

## Error handling

| Case | Response |
| --- | --- |
| Timeout / kill | Latest `close.md` is the scorecard. Missing `^VERIFIED:` → FAIL |
| `VERIFIED (` | Helper FAIL |
| `STATUS: stages a + b done…` | Helper FAIL (vocab) |
| Agent returned, close.md not overwritten | Timeout run scored from a stale file — the Integrate-step is the prompt fix |
| `-fixes` basename | Helper FAIL (already) |

## Testing

**Guardrails (no billed run).** New expects on the two coordinator needles. Helper fixture rejects `VERIFIED (`. Existing skeleton / STATUS / `-fixes` expects stay.

**Eval (`feature`, opt-in billed).** Same command as run 13. Gate: `check_delivery_close_file` PASS (line-anchored labels + STATUS vocab). Basename FAIL still blocks the 2.0.0 ship. Timeout / `$LOG` greps may still FAIL; that does not move the gate. Pin `coordinator_hash`. Receipt `docs/evals/2026-08-20-run-14.md` (or next date).

## Versioning

Still **2.0.0** when the gate passes. This follow-up does not add a second breaking. Changelog stays `[Unreleased]` until the pin. Adopters re-install once, from 2.0.0.
