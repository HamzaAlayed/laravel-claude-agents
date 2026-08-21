# Design — Guild 2.0 close.md Bash write deny

**Status:** approved 2026-08-21. Follow-up to [close.md shape hook](2026-08-21-guild-v2-close-hook-design.md) after [run 16](../evals/2026-08-21-run-16.md). Not 2.1 Adaptive. Not 2.2 graph.

**Goal:** Stop the coordinator writing `docs/delivery/*/close.md` with Bash, so the existing Write|Edit shape hook can see the payload — without loosening the helper, raising ceilings, or adding a seventh guardrail script.

**Why this is not a new major:** 2.0 already added `close.md`. The Write|Edit hook already bounces journal payloads. Run 16 timed out with a `VERIFIED (` journal written as `cat > docs/delivery/tag/close.md <<'EOF'` (twice). The shape hook was installed and never ran. This slice is the **same script** on the existing Bash PreToolUse matcher.

## Evidence (run 16)

| Contract | On disk / transcript |
| --- | --- |
| Line starts `VERIFIED:` | `VERIFIED (coordinator, independently):` |
| Write\|Edit of close.md | **Zero.** Two Bash `cat > … <<'EOF'` |
| Hook installed | `.claude/settings.json` + `scripts/enforce-close-file.sh` executable |
| `$LOG` VERIFIED / NOT-CHECKED | **PASS** |
| tech-lead.md | `VERIFIED (tech-lead):` — missing `VERIFIED:` |
| Timeout | 1203s, billed usd null, 11.0M tokens (within 14.5M) |

The 2.0 gate remains **close file PASS**, not 12/12. VERSION stays **1.45.0** until that gate passes on a billed `feature` pin. Do not raise `EVAL_TIMEOUT`, `max_usd` ($8.50), or the 14.5M token ceiling.

## Architecture

Same product. Interface block unchanged. Helper stays `^VERIFIED:`. Do not accept `VERIFIED (`. Existing stub files, copy-then-fill, next-Write, `VERIFIED (` ban, and Write|Edit shape check stay.

**Hook.** Reuse `scripts/enforce-close-file.sh` on matcher `Bash` (Claude), `run_shell_command` (Gemini), and Codex `Bash`.

- Extract `tool_input.command` (or treat raw stdin when parsers are missing).
- If the command **writes** `docs/delivery/*/close.md` (`cat >`, `>>`, `<<` heredoc onto that path, `tee`) → **exit 2**: use the Write tool; copy `skills/delivery-templates/close.md`. Do **not** parse the heredoc for labels.
- `cat docs/delivery/tag/close.md` (read) → exit 0.
- `php artisan test`, pint, git → exit 0.
- Write|Edit path: unchanged shape check.
- Fail **closed** if parsers are missing and the payload looks like a close.md write.

Inventory stays **6** production guardrail scripts (`check-hook-sync` still 7 names including the observer).

**Coordinator.** One sentence, count 1: `Bash must not write close.md`. Does not replace the Write|Edit bounce sentence.

## Non-goals

- Do not loosen `check_delivery_close_file` to accept `VERIFIED (`
- Do not uncomment `check_subagent_log`
- Do not raise `EVAL_TIMEOUT` (1200), `feature` `max_usd` ($8.50), or the 14.5M token ceiling
- Do not start 2.1 or 2.2
- Do not bump `VERSION` until the billed close-file helper PASSes
- Do not edit the shared Interface block
- Do not add a seventh guardrail script
- Do not allow Bash if the heredoc happens to be helper shape

## Error handling

| Case | Response |
| --- | --- |
| `cat > docs/delivery/tag/close.md <<'EOF'` | Hook exit 2; model retries with Write |
| Valid four-line Write | Write\|Edit hook exit 0; helper can PASS |
| Timeout / kill | Latest on-disk `close.md` is the scorecard |
| `-fixes` basename | Helper FAIL (already) |

## Testing

**Guardrails (no billed run).** Bash deny/allow fixtures + existing six Write|Edit fixtures. Coordinator needle. Hook-sync still 7 names.

**Eval (`feature`, opt-in billed).** Same command as run 16. Gate: `check_delivery_close_file` PASS. Basename FAIL still blocks. Pin `coordinator_hash`. Receipt `docs/evals/2026-08-21-run-17.md` (or next date).

## Versioning

Still **2.0.0** when the gate passes. Changelog stays `[Unreleased]` until the pin.
