# Design — Guild 2.0 close.md shape hook

**Status:** approved 2026-08-21. Follow-up to [close.md stub copy](2026-08-21-guild-v2-close-stub-design.md) after [run 15](../evals/2026-08-21-run-15.md). Not 2.1 Adaptive. Not 2.2 graph.

**Goal:** Bounce `Write`/`Edit` of `docs/delivery/*/close.md` unless the payload is helper shape (`^VERIFIED:` / `^NOT-CHECKED:` / `^STATUS: running|done|stopped` / `^BOARD:`) — without loosening the helper, raising ceilings, or adding a product surface.

**Why this is not a new major:** 2.0 already added `close.md`. Stickiness, procedure, and stub-copy all told the coordinator how to write it. Run 15 timed out with a 122-line journal (`VERIFIED (` , no colon, `STATUS: planning complete…`). Instruction did not stick. This slice is a **sixth production guardrail** in the existing `Write|Edit` PreToolUse matcher — the same class as `protect-env-files.sh`.

## Evidence (run 15)

| Contract | On disk |
| --- | --- |
| Line starts `VERIFIED:` | `VERIFIED (coordinator, at plan time)` — no colon |
| Four-line stub copy | 122-line titled journal; first line `# Close file — Tag (--api)` |
| `STATUS: running \| done \| stopped` | `STATUS: planning complete, stage 1 dispatched` |
| Overwrite after every stage | File grew by section; last write mid re-plan (timeout 1202s) |
| Read-only persist six labels | **PASS** — `tech-lead.md` has `^VERIFIED:` |
| Re-brief overwrites `<agent>.md` | **PASS** — no `-fixes` |

The 2.0 gate remains **close file PASS**, not 12/12. VERSION stays **1.45.0** until that gate passes on a billed `feature` pin. Do not raise `EVAL_TIMEOUT`, `max_usd` ($8.50), or the 14.5M token ceiling (run 15 REGRESSED it).

## Architecture

Same product: `/make-feature` or `/console`, coordinator Writes `docs/delivery/<name>/close.md`. No new agent, command, daemon, or console scene. Interface block unchanged. Helper stays `^VERIFIED:`. Do not accept `VERIFIED (`. Existing stub files, copy-then-fill needles, next-Write procedure, and `VERIFIED (` ban stay.

**Hook.** `scripts/enforce-close-file.sh`, wired on `Write|Edit` next to `protect-env-files.sh`.

- Path matches `docs/delivery/*/close.md` → inspect payload body (`tool_input.contents` on Write, `tool_input.new_string` on Edit).
- Body must have line-start `VERIFIED:` `NOT-CHECKED:` `STATUS: running|done|stopped` `BOARD:`.
- Else **exit 2**: copy `skills/delivery-templates/close.md`; close.md is not `log.md`.
- Other paths: exit 0.
- Fail **closed** if the path matches and the body cannot be parsed (unlike the board observer).
- Parser fallback (no jq/python3): path looks like `close.md` under `docs/delivery` → deny.

**Mirrors.** Gemini `BeforeTool` matcher `write_file|replace`. Codex `Write|Edit` next to the env guard (Codex Core does not run `/make-feature`; this is inventory parity, not the billed gate).

**Coordinator.** One sentence, count 1: the close.md hook bounces a Write that is not helper shape. Does not replace stub copy.

**Static ratchets.** Hook fixtures (deny journal / accept stub / ignore other paths / fail-closed fallback). `check-hook-sync` names the new script. Inventory guardrail count **5 → 6**. Existing close-file helper fixtures stay.

## Non-goals

- Do not loosen `check_delivery_close_file` to accept `VERIFIED (`
- Do not uncomment `check_subagent_log`
- Do not raise `EVAL_TIMEOUT` (1200), `feature` `max_usd` ($8.50), or the 14.5M token ceiling
- Do not start 2.1 or 2.2
- Do not bump `VERSION` until the billed close-file helper PASSes
- Do not edit the shared Interface block
- Do not add a fourth prompt-only ban in place of the hook

## Error handling

| Case | Response |
| --- | --- |
| Journal Write (`VERIFIED (`) | Hook exit 2; model retries with the stub |
| Valid four-line Write | Hook exit 0; helper can PASS |
| Edit whose `new_string` lacks the four labels | Hook exit 2 (forces overwrite-shaped Writes) |
| Timeout / kill | Latest on-disk `close.md` is the scorecard. Missing `^VERIFIED:` → FAIL |
| `-fixes` basename | Helper FAIL (already) |

## Testing

**Guardrails (no billed run).** Hook fixtures + wiring + inventory 6. Helper fixtures unchanged.

**Eval (`feature`, opt-in billed).** Same command as run 15. Gate: `check_delivery_close_file` PASS. Basename FAIL still blocks the 2.0.0 ship. Timeout / `$LOG` greps may still FAIL; that does not move the gate. Pin `coordinator_hash` (coordinator sentence moves the hash). Receipt `docs/evals/2026-08-21-run-16.md` (or next date).

## Versioning

Still **2.0.0** when the gate passes. This follow-up does not add a second breaking. Changelog stays `[Unreleased]` until the pin. Adopters re-install once, from 2.0.0. The new hook is part of that 2.0 Interface-era pack, not a 2.1.
