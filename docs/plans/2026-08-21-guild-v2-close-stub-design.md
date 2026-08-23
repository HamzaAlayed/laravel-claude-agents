# Design — Guild 2.0 close.md stub copy

**Status:** approved 2026-08-21. Follow-up to [close.md procedure](2026-08-20-guild-v2-close-procedure-design.md) after [run 14](../evals/2026-08-21-run-14.md). Not 2.1 Adaptive. Not 2.2 graph.

**Goal:** Make `docs/delivery/<name>/close.md` land with line-start `VERIFIED:` by copying a committed four-line stub, then filling after the colons — without loosening the helper, raising ceilings, or adding a surface.

**Why this is not a new major:** 2.0 already added `close.md`. Stickiness added a four-line skeleton (run 13). Procedure added next-Write + `VERIFIED (` ban + line-anchored helper (run 14). Run 14 finished on time, billed `$6.33`, overwrote through `STATUS: done`, and still wrote `VERIFIED (coordinator's own commands…):` on close.md and on coordinator-persisted `tech-lead.md`. A third prompt pass is the same class of instruction. This slice is a **canonical stub** plus **copy-then-fill**.

## Evidence (run 14)

| Contract | On disk |
| --- | --- |
| Line starts `VERIFIED:` | `VERIFIED (coordinator's own commands, re-run against every specialist claim):` |
| `STATUS: running \| done \| stopped` | `STATUS: done` — would pass vocab |
| Overwrite after every stage | **PASS** — finished close, 4 of cap 6 |
| Re-brief overwrites `<agent>.md` | **PASS** — no `-fixes` |
| Read-only persist six labels | `tech-lead.md` uses `VERIFIED (tech-lead's own read-only commands):` |

The 2.0 gate remains **close file PASS**, not 12/12. VERSION stays **1.45.0** until that gate passes on a billed `feature` pin. Do not bump to 2.0.0 on basename/timeout/$LOG misses alone if close file still FAILs; basename FAIL still blocks the ship.

## Architecture

Same product: `/make-feature` or `/console`, `delivery-coordinator` overwrites `docs/delivery/<name>/close.md`. No new agent, command, daemon, or console scene. Interface block unchanged. Helper stays `^VERIFIED:` / `^NOT-CHECKED:` / `^STATUS:` plus STATUS vocab `running|done|stopped`. Do not accept `VERIFIED (`.

**Stub files** in the pack, under the delivery-templates skill:

- `skills/delivery-templates/close.md` — exactly four lines, starting `VERIFIED:` `NOT-CHECKED:` `STATUS: running` `BOARD:`
- `skills/delivery-templates/stage-return.md` — exactly six lines, starting `STATUS:` `DID:` `VERIFIED:` `NOT-CHECKED:` `FLAGS:` `NEXT:`

**Copy-then-fill.** First Write of close.md is a byte copy of `skills/delivery-templates/close.md`; then Edit only after the colons. When persisting a read-only stage file, copy `skills/delivery-templates/stage-return.md` the same way. Existing next-Write procedure, overwrite sentence, `VERIFIED (` ban, and four-line fence stay.

If the consumer workdir has no plugin `skills/` tree, Skill `delivery-templates` still exposes the stub; the coordinator copies those four (or six) lines, not a paraphrase.

**Static ratchets.** Two new unique coordinator needles, count **1** each:

- `copy skills/delivery-templates/close.md`
- `copy skills/delivery-templates/stage-return.md`

Stub-file expects: `close.md` first four lines start the four labels; `stage-return.md` first six lines start the six labels. Existing overwrite / next-Write / ban / skeleton / helper fixtures stay. Do not grep the word `fixes` in helper source as a pin. Interface block unchanged. `body_budget` may rise for `delivery-templates` SKILL.md if the skill points at the files.

## Non-goals

- Do not loosen `check_delivery_close_file` to accept `VERIFIED (`
- Do not uncomment `check_subagent_log`
- Do not raise `EVAL_TIMEOUT` (1200) or `feature` `max_usd` ($8.50)
- Do not start 2.1 or 2.2
- Do not bump `VERSION` until the billed close-file helper PASSes
- Do not edit the shared Interface block
- Do not add a third prompt-only ban in place of the stub files

## Error handling

| Case | Response |
| --- | --- |
| Timeout / kill | Latest `close.md` is the scorecard. Missing `^VERIFIED:` → FAIL |
| `VERIFIED (` | Helper FAIL (already) |
| Agent returned, close.md not overwritten | Existing next-Write procedure; this slice does not replace it |
| `-fixes` basename | Helper FAIL (already) |
| Stub file missing from pack | Guardrail FAIL |

## Testing

**Guardrails (no billed run).** New expects on the two coordinator needles and the two stub files. Helper fixtures unchanged.

**Eval (`feature`, opt-in billed).** Same command as run 14. Gate: `check_delivery_close_file` PASS. Basename FAIL still blocks the 2.0.0 ship. If `tech-lead.md` is present it must have `^VERIFIED:`. Timeout / `$LOG` greps may still FAIL; that does not move the gate. Pin `coordinator_hash`. Receipt `docs/evals/2026-08-21-run-15.md` (or next date).

## Versioning

Still **2.0.0** when the gate passes. This follow-up does not add a second breaking. Changelog stays `[Unreleased]` until the pin. Adopters re-install once, from 2.0.0.
